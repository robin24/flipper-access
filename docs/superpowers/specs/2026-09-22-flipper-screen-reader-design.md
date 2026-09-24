# Flipper Zero screen reader for Momentum firmware: design

Date: 2026-09-22. Status: approved by Robin on 2026-09-22; phase 1 implemented and reviewed on 2026-09-22 (see section 16 for the deviations made during implementation). Author: Claude, for Robin.

## 1. Goal and scope

Make a Flipper Zero running Momentum firmware operable without sight. The firmware gains a
screen reader service that captures every string drawn on the display, decides what changed and
what has focus, and announces it through two outputs: speech from the built in piezo speaker
using the SAM synthesizer, and a text stream on the USB serial console for use with a computer
screen reader.

In scope for the first four phases: capture of all drawn text, focus and screen change
detection, announcements, a serial console command that mirrors the screen and drives the
buttons, on device speech, settings, hotkeys, and synthesized announcements for screens that
draw no text (home screen, lock menu). Out of scope: external audio hardware, Bluetooth audio,
other synthesizers, and app specific rewrites beyond small hints.

## 2. Facts the design rests on

Verified in the Momentum source clone (branch dev, commit d3f89dfe2, API 87.1) and on the device:

- All text drawing ends in three functions in applications/services/gui/canvas.c:
  canvas_draw_str, canvas_draw_str_aligned and canvas_draw_glyph. Nothing else in the tree calls
  the u8g2 text functions. Icons with baked in lettering are the only text a hook cannot see.
- The drawing colour lives inside the u8g2 struct and canvas_set_color inverts it when
  Momentum's dark mode is on, so the hook must record the logical colour, not the raw one.
- Frames are composed by gui_redraw on the GUI service thread while the GUI mutex is held:
  canvas_reset, then the topmost enabled view port of the Fullscreen layer, or else the Window
  layer, or else the Desktop layer, then the status bar, then canvas_commit. The canvas is
  shared and carries no layer identity, so gui.c must tag the layer.
- Most list modules highlight the selected item by drawing a black box and then the label in
  white. The main menu in List style marks the selected item only by using the primary font and
  a frame. The lock menu and PIN screen draw no text for their items. Dialog buttons in the
  bottom row are also drawn inverted, so inversion alone does not mean focus.
- Long labels are shortened before drawing. elements_string_fit_width chops a string in place
  and appends an ellipsis; elements_scrollable_text_line_centered draws a scrolling window of the
  full string and forces a redraw every 333 ms while such a list is on screen. Both receive the
  full string.
- Input events are broadcast synchronously to subscribers; a subscriber cannot suppress an
  event. Long and Repeat events come from the timer task, Press, Release and Short from the
  input thread. Momentum's ascii events let the console type into on screen keyboards.
- The console is pipe based. Commands are registered with cli_registry_add_command; a command
  marked parallel safe can run while an app is open; printf inside a command goes to the pipe;
  a streaming command polls for Ctrl-C. Only one command runs per shell at a time.
- Services are declared in an application.fam with apptype SERVICE and started in order of
  their order field; a new service must be listed in the basic_services metapackage.
- Momentum settings are a flat struct in lib/momentum/settings.h saved to
  /int/.momentum_settings.txt. Adding a setting is one field, one default, one table row.
  Missing keys keep their defaults, so a partial file written from the console is valid.
- The speaker HAL owns TIM16 behind a mutex. Acquiring it enables the timer clock, configures
  PB8, and blocks deep sleep. Notification beeps acquire with a 30 ms timeout and silently skip
  if the speaker is busy. TIM16 can pace DMA itself: dtmf_dolphin drives DMA1 channel 1 from the
  TIM16 update event at the carrier rate. DMA1 channels 1 to 3 are unused by the core firmware.
  TIM2 and TIM1 are used by Sub-GHz, infrared, RFID and NFC and must not be borrowed.
- SAM in the bundled Text to SAM app is a single C++ class with no templates, exceptions or
  heap use, about 7.5 KB of constant tables and 3.9 KB of static working memory, one float call
  (tanhf) in its output stage, and a busy wait output loop. Its sample timing is expressed in
  units of one fiftieth of a 22050 Hz sample.
- Full firmware build leaves 205 KB of flash unused; that region also hosts the internal
  storage file system, which needs a few tens of KB. Idle free heap is 116 to 142 KB depending
  on which home screen animation is loaded. A full build takes under three minutes on the Mac.
- Robin judged SAM's default voice intelligible on the piezo. Slower speed sounded stretched,
  higher pitch was worse. Defaults stay pitch 64, speed 72, mouth 128, throat 128.

## 3. Architecture

Five parts, each with one job:

1. Text tap in the GUI service: records every drawn string with position, font, layer, logical
   colour, and optional hints, into a fixed buffer during a frame. Runs on the GUI thread.
2. Screen model: pure C, no firmware dependencies. Turns a frame's records into a screen
   description, compares it with the previous one, and emits announcements. Unit tested on the
   Mac.
3. Screen reader service: a firmware service with its own thread. Receives frames from the tap,
   runs the screen model after a short settle delay, correlates with button presses, and routes
   announcements to the console stream and the speech engine. Owns the settings and hotkeys.
4. Speech engine: SAM as plain C rendering into a ring buffer that DMA feeds to the speaker
   timer. Runs on its own thread, holds the speaker only while speaking, supports interruption.
5. Console command sr: prints the current screen, streams announcements, forwards arrow keys to
   the device, and exposes on, off, say, rate and volume.

Data flows one way: draw calls, tap records, frame, screen model, announcements, outputs. The
GUI thread never waits on the service; the service never calls back into the GUI.

## 4. Text tap

Placement follows Momentum's existing style: inline additions at the existing call sites in
canvas.c and gui.c, declared in the internal headers canvas_i.h and gui_i.h so the public SDK
API and its version stay unchanged.

Record produced for each drawn string:

- x and y: absolute framebuffer coordinates after the frame offset, in the canvas orientation.
- layer: the GuiLayer being drawn (Desktop, Window, StatusBarLeft, StatusBarRight, Fullscreen),
  set by gui.c before each view port draw and before the status bar.
- font: the Font enum value, or a marker for a custom u8g2 font.
- inverted: true when the logical colour was White at draw time. In dark mode the raw u8g2
  colour is inverted back before recording.
- role: Normal or Focus. Focus comes from a hint (below).
- index and count: one based position hint, zero when unknown.
- text: up to 63 characters, NUL terminated.

Frame lifecycle: gui_redraw calls frame_begin after canvas_reset and frame_end after
canvas_commit. Both happen on the GUI thread with the GUI mutex held, so frame_end only copies
the record buffer under the service's own mutex and sets a thread flag. Frames drawn through
gui_direct_draw bypass gui_redraw and are not captured; that is accepted.

Glyph runs: canvas_draw_glyph draws one character at a time (text boxes, keyboards). The tap
keeps one pending run and appends a glyph to it when the font, colour, layer and baseline
match and x advances; any other draw or frame_end flushes the run as one record. This keeps a
text box page as a handful of records instead of hundreds.

Hints, all internal functions that apply to the next text draw only:

- canvas_hint_focus(canvas, index, count): the next drawn string is the focused item. Added as
  one line in submenu, variable item list (label and value), main menu (all styles), file
  browser, button menu, text input, byte input and number input (the selected key).
- canvas_hint_full_text(canvas, text, verify): the next drawn string is a fragment of the given
  full text. elements_scrollable_text_line_centered sets it right before its own draw with
  verify off. elements_string_fit_width copies the original into the hint buffer before
  truncating, with verify on; the tap then accepts the hint only if the drawn string minus a
  trailing ellipsis is a prefix of it. The hint text is copied into a 64 byte buffer inside the
  canvas, so no allocation happens during drawing.

Cost: one branch per draw call when the reader is off; when on, a bounded strncpy per draw.
Buffer: 40 records of 76 bytes, about 3 KB, held in the GUI canvas.

## 5. Screen model

Pure C in applications/services/screen_reader/screen_model.c with a header that depends only on
stdint, stdbool and string.h. Compiles on the host for tests.

Inputs: a frame (records as above), the current time in milliseconds, and whether a button was
pressed within the last 500 ms. Output: zero or more announcements, each with text, a kind
(focus, screen, change, typed, status) and an interrupt flag.

Normalisation of each record: trim spaces, drop a lone text cursor bar inserted by text input,
collapse runs of spaces, drop empty strings. Records in the status bar layers are kept aside
for on demand reading. Records in the bottom button row (y above 52 in the Window or Fullscreen
layer, inverted, secondary font) are classified as buttons. Rows are formed from records with
the same baseline within 2 pixels, ordered by x; a row's text is its records joined with a
space, except that a lone less than or greater than sign is dropped, so a settings row reads
as label followed by value.

Focus: the rows containing a Focus role record, else the rows containing inverted records that
are not buttons, joined in reading order. Position text comes from the hint when present.

Title: the topmost row in the primary font that is not the focus and not a button, if it sits in
the upper third of the frame; else none.

Screen signature: the ordered list of normalised rows excluding focus rows and the status bar.
A screen change is declared when the title changed, or when fewer than half of the previous
signature rows appear in the new one, or when the layer with content changed.

Decision rules, in order:

1. Identical frame: nothing.
2. Screen change: announce the title if any, then the focus if any, else all rows top to bottom
   up to a length limit, then the buttons as "buttons: left Cancel, right OK" using their row
   order. Kind screen, interrupt on.
3. Focus changed on the same screen: announce the focus text, plus position when verbosity is
   high or when requested. Kind focus, interrupt on.
4. Other rows changed: announce only the changed rows. If a button was pressed within 500 ms
   the announcement is immediate; otherwise it is rate limited to one per 1500 ms and the text
   is limited to 80 characters. Kind change, interrupt off.
5. A frame with no rows in the Window and Fullscreen layers after a screen with rows: announce a
   synthesized name when one is known (home screen when the Desktop layer is active), else
   nothing. The loading screen, which draws no text, therefore stays silent.

Typing: when the frame contains a text input header and the text row changed by exactly one
appended character, announce that character (kind typed, interrupt on) instead of the row.

Pronunciation: a small replacement table applied to announcement text before speech only:
NFC, RFID, GPIO, USB, BLE, IR, U2F, PIN, LED, kHz, MHz, GHz, Sub-GHz, iButton, dBm, percent
sign, slash, and a rule that splits digit groups from letters. The console stream receives the
untouched text.

## 6. Screen reader service

Directory applications/services/screen_reader with application.fam (SERVICE, entry point
screen_reader_srv, requires gui, input, notification, cli, stack 2048, order 110) and the appid
added to the basic_services metapackage. The service publishes a record so the settings app and
the console command can reach it.

Thread loop: wait on thread flags with a timeout. Flags: frame ready, input event, control
message. A frame starts a 50 ms settle timer; if another frame arrives the timer restarts; when
it expires the latest frame is processed. Input events arrive through a small queue filled by
the pubsub callback, which only enqueues. The service keeps the timestamp of the last Press and
uses it for the key correlation rule and, in phase 3, for chords.

Enable state: the tap is installed at start and consults momentum_settings.screen_reader on
every frame, so toggling from the console or the settings app takes effect immediately without
a reboot. When off, the tap records nothing and the service idles.

Outputs: every announcement goes to a ring of the last 8 announcements for the console watch
command, and, when speech is enabled and built, to the speech queue with its interrupt flag.

## 7. Console command sr

Registered by the service as a built in parallel safe command. Subcommands:

- sr screen: prints the last captured frame, one line per record: layer, x, y, font, inverted
  flag, role, position, text. Used for debugging hints and the model.
- sr watch: streams announcements as "kind: text" lines until Ctrl-C. While streaming, arrow
  keys, Enter and Backspace are forwarded as button presses exactly like Momentum's input
  keyboard command, and printable characters are sent as ascii events. This is the tethered
  screen reader and the integration test harness.
- sr on, sr off: set and save the setting.
- sr status: prints enabled state, rate, volume, verbosity, and memory use of the service.
- sr say text: speaks text (phase 2). sr rate n, sr volume n, sr verbosity n: set and save.

## 8. Speech engine

Source: the SAM code from applications/external/text2sam converted to plain C under lib/sam,
with the class removed, globals gathered in one struct, overloads and default arguments dropped,
and the output stage replaced by a callback that receives up to five sample values and the
timing delta in fiftieths of a 22050 Hz sample. The reciter and renderer are unchanged.

Output path in applications/services/screen_reader/speech.c:

- Timer: TIM16 as a 50 kHz PWM carrier (prescaler 4, autoreload 255), the same as the demo
  Robin heard. The TIM16 update event triggers DMA1 channel 1, circular, memory to the CCR1
  register, byte samples, half and complete interrupts. No second timer is needed, so Sub-GHz,
  infrared, RFID and NFC timers are untouched.
- Ring buffer: 4096 bytes, about 82 ms of audio. The SAM callback converts its 22050 Hz
  positions to 50 kHz slots by holding each value across the slots it covers, applies the
  loudness curve through a 256 entry lookup table that also folds in the volume setting, and
  writes. When the buffer is within one half of the read position the callback blocks on a
  semaphore that the DMA interrupts release. The interrupt handler only signals.
- Utterance end: fill the rest of the buffer with the mid rail value, wait for the read pointer
  to pass, stop DMA and the timer output.
- Speaker sharing: acquire with a 100 ms timeout when the queue becomes non empty, retrying a
  few times; release after the queue has been empty for 200 ms so that notification beeps and
  other apps can use the speaker between announcements. If the speaker cannot be acquired the
  utterance is dropped and counted in sr status.
- Interruption: the queue holds up to 4 utterances of 160 characters. An announcement with the
  interrupt flag clears the queue and sets an abort flag; the SAM callback returns immediately
  while the flag is set, so synthesis finishes without blocking, and the buffer is silenced.
- Thread: 2 KB stack, normal priority. SAM's static working memory is 3.9 KB and lives in the
  firmware image's data segment.

Known conflict inherited from the speaker HAL: the ISO15693 listener in NFC also claims TIM16,
so the reader must not speak while that listener runs. The service checks whether the speaker
mutex is available and skips speech rather than crashing; this mirrors what notification beeps
already do.

## 9. Hotkeys

A filter hook is added to the input service: input_set_filter(callback, context). The dispatch
loop and the timer callback call it before publishing any event and drop the event when the
callback returns true. Only the screen reader installs it, and only while enabled.

Chords use Back as the modifier. While Back is held, a Press of another key is swallowed and
executed as a command; Back's own Short event is then swallowed on release. Commands: Back plus
Up reads the whole screen from the top; Back plus OK repeats the focus with its position; Back
plus Down reads the status bar (time, battery, connection); Back plus Left and Right lower and
raise the speech rate and speak the new value. Any other key press stops current speech.

Side effect, accepted by Robin: with the reader on, a Long press of Back alone is delivered
when the button is released rather than after 300 ms, so that a slow chord is not misread as
a long press. Repeat events for Back are dropped while the reader is on.

## 10. Settings

New fields in MomentumSettings with defaults: screen_reader false, sr_rate 72 (SAM speed 40 to
120), sr_volume 100 (0 to 100), sr_verbosity 1 (0 terse, 1 normal, 2 verbose). Registered in
the settings table so the console can set them before any spoken settings screen exists. In
phase 3 an Accessibility scene in the Momentum settings app exposes them as a variable item
list; changes apply live, no reboot.

## 11. Memory and flash budget

Estimated heap: service thread 2 KB, speech thread 2 KB, three frame buffers 9 KB, DMA ring
4 KB, speech queue 1 KB, console ring 1 KB, total about 19 KB, plus 3.9 KB of static SAM
memory in the image. Estimated flash: about 40 KB of the 205 KB unused. The measured headroom
of core apps is recorded here once the RAM probe (tools/ram_probe.py) has completed:

Measured on 2026-09-22 with tools/ram_probe.py on Momentum mntm-012, total heap 189648 bytes,
raw log in docs/measurements/2026-09-22-ram-probe-mntm-012.txt. Free heap at the lowest point
while each app was in its busy state:

- Home screen idle: 142 KB on this boot; 116 KB on another boot with a larger animation.
- NFC read: 51 KB. The heaviest core app by far.
- Infrared universal remote (first category loaded): 61 KB.
- Infrared learn: 71 KB.
- Sub-GHz frequency analyzer: 81 KB. Sub-GHz read: 84 KB.
- TOTP: 97 KB. RFID read: 107 KB. Momentum settings: 109 KB. Bad KB file browser: 111 KB.
  iButton read: 114 KB. Text to SAM: 116 KB. GPIO manual control: 125 KB.
- uPython: 10 KB. It sizes its interpreter heap to whatever is free, so it will simply get
  less with the reader present; it is not a core feature.

Conclusion: with the reader's estimated 19 KB of heap plus 4 KB of static memory, NFC read mode
still keeps about 27 KB free, and every other core app keeps 37 KB or more. The home screen
animation variance of about 26 KB is the largest single uncertainty, so the reader must stay
within its budget and must not allocate on the fly while an app runs. All of the reader's
buffers are allocated once at service start.

Two firmware behaviours discovered during the probe, both avoided by the design: sending the
loader's exit signal to the NFC app in read mode crashes and reboots the device, and uPython
cannot be closed from the console at all, only by a reboot. The reader never sends exit signals.

## 12. Failure handling

- Tap buffer full: further records in that frame are dropped and the frame is flagged, so the
  model can say "and more".
- Frame arrives while the service is still processing: the newest frame wins; intermediate
  frames are never queued.
- Speaker busy: utterance dropped, counted.
- SAM given text longer than 255 characters: truncated at a word boundary.
- Settings file missing: defaults, reader off.
- Console watch and an app both running: allowed, the command is parallel safe.

## 13. Testing

- Host unit tests for the screen model: a test file with a tiny assert macro compiled with
  clang on the Mac by tools/run_host_tests.sh. Cases cover normalisation, row joining, focus
  by hint and by inversion, buttons, title detection, screen change versus focus change,
  rate limiting, typing echo, the marquee stability guarantee, and the empty frame rules.
- Device integration: tools/sr_drive.py opens the console, runs sr watch, sends key sequences,
  and asserts the announcement lines for scripted paths through Settings, Sub-GHz, NFC, the
  file browser and the on screen keyboard.
- Manual: Robin listens; Robin navigates with the device alone.
- Regression: the RAM probe is rerun with the reader enabled and its numbers compared with the
  baseline in section 11.

## 14. Phases

1. Tap, service, screen model with host tests, sr screen and sr watch, the enable setting.
   Done when Robin can drive the device from one terminal window and hear, through the Mac's
   screen reader, every menu, dialog and keyboard.
2. Speech: SAM port, DMA playback, queue and interruption, sr say, rate and volume. Done when
   the phase 1 announcements are spoken by the device.
3. Control: input filter and chords, position and verbosity, the Accessibility settings scene,
   synthesized announcements for the home screen, lock screen and lock menu, typing echo.
4. Polish: app by app fixes as gaps appear, then cleanup for upstream contribution.

## 15. Open items

- The second probe run left the console unresponsive at some point after the NFC crash; the
  third run completed without it, so the cause was not identified. If it recurs, the emergency
  reboot is Left and Back held for five seconds.
- Whether Text to SAM stays as a separate app once lib/sam exists (likely yes, it can link the
  library).

## 16. Phase 1 as built: deliberate deviations from the sections above

Recorded after the final review so that later phases build on what exists rather than on the
original text.

- Capture buffer: 32 records of 48 characters per frame (section 4 said 40). Rows are limited to
  16 per screen with 64 characters each. Overflow is flagged and read as "and more".
- Rows join by baseline only when the records agree on being focused or not, so a selected key
  on the on screen keyboard is its own row. Buttons never join other records.
- Screen change rule: fewer than half of the previous rows, ignoring roles and the status bar,
  remain; plus layer, content and title changes. A list scrolling by one row is not a screen
  change. Frames on the home screen never count as a screen change against a previous home
  screen frame: bubble text arrives as a rate limited, non interrupting change (which phase 2
  does not speak without a recent key press, see "Phase 2 as built"), and "Home screen" is
  announced only when arriving from another layer.
- Buttons carry a side hint set by the three dialog button helpers; the x position rule remains
  only as a fallback for third party drawing. The bottom row threshold for that fallback is
  y 61.
- The file browser's parent entry ". ." reads as "Parent folder"; rows made only of dashes are
  loading placeholders and are dropped.
- Focus hints exist in the submenu, settings list, file browser, Archive browser, button menu,
  text input keyboard and the List style of the main menu. Other main menu styles are read by
  inversion where possible and get hints in a later phase.
- Latency: frames settle for 50 ms, with a 300 ms cap when frames keep coming.
- Console: `sr watch` replaces the announcement ring of section 6 with a queue attached by the
  watching command; Tab prints the whole screen description; a bare Escape is ignored and
  unknown control sequences are consumed.
- The full text hint set by the ellipsis helper is accepted only when the drawn string ends
  with an ellipsis.
- Test tooling lives in the project repository: tests/host and tools/run_host_tests.sh for the
  model, tools/sr_drive.py for scripted and interactive device driving.
- Known residuals, carried to phase 3: a home screen transition inside 1.5 s of a spontaneous
  change without a key press can be dropped; desktop layer popups whose only new text is a
  button label are silent; moving between keyboard rows is announced with kind "screen"
  instead of "focus" with identical text.

### Phase 2 as built

Recorded after the Task 6 device checks. Where this list disagrees with sections 5, 8, 11, 12
and 14, this list is what the code does.

- Synthesizer: the SAM port is applications/services/screen_reader/sam/sam.c with sam.h, not
  lib/sam; sources under the service directory are compiled into the firmware automatically.
  The port matches the original C++ synthesizer value for value on the host test cases and
  carries guards, marked "port guard", only where the original hangs or reads past its tables
  (forced breath breaks, phoneme list positions at 255, the T/D rule at the end of unpunctuated
  text, a phoneme string that wrapped its buffer, and the four byte values the reciter mistakes
  for its end marker). sam_speak takes at most 250 characters and reports through `consumed` how
  much text it rendered: the reciter stops at a word boundary once its phoneme string reaches
  120 characters, and the worker calls again with the rest, so no words are lost.
- Text: speech_text_expand rewrites an announcement into at most 800 characters (SPEECH_TEXT_MAX;
  a screen of two digit hex pairs expands 4.7 times) and speech_text_next_chunk cuts that into
  chunks of at most 80 characters (SPEECH_CHUNK_MAX) at a sentence, a comma or a word boundary.
  The worker upper cases each chunk and appends a period when it ends without punctuation. The
  rules, numbered as in speech_text.c: (1) a one character announcement is named, a letter by
  its name with A as "ay", a digit by its word, punctuation by its name; (2) the text is scanned
  as tokens of letters and digits with inner apostrophes, periods and hyphens; (3) whole tokens
  in the term table take its pronunciation: Sub-GHz and SubGHz "sub gigahertz", kHz, MHz, GHz
  and Hz as words, dBm "dee bee em", dB "dee bee", iButton "eye button", OK "okay", PIN "pin",
  Wi-Fi "why fye", mAh "milliamp hours", MNTM "momentum"; (4) periods inside a token that is not
  a decimal read "dot", an unmatched token with hyphens is split at them; (5) a number followed
  by letters, such as 433.92MHz or 3V3, is the number and its unit, the letters through the term
  table or spelled; (6) numbers up to four digits without a leading zero are words, longer ones
  digit by digit, a decimal part is "point" and digits; (7) upper case letter and digit mixes
  outside the stop list are spelled by runs: one to five letters character by character (so
  NFC, RFID, GPIO, USB, BLE, IR, U2F, LED and hex bytes are spelled), six or more as a word, one
  to three digits as a number, longer digit runs digit by digit; (8) other tokens are copied in
  pieces of at most 20 characters, because the synthesizer never returns on words of about 30
  letters; (9) between tokens, sentence punctuation stays with its word, a colon becomes a comma
  (a space between digits), symbols become words, everything else a single space; (10) chunks
  end at a sentence, a comma or a word boundary; (11) a hyphen before a digit outside a token is
  "minus"; (12) a hyphen next to a digit is "to" between two digit runs of equal length, a space
  before a word of two or more letters, "dash" otherwise; (13) a lone upper case A is "ay". A
  stop list of about a hundred common upper case words (ON, OFF, SAVE, READ, MENU and so on)
  keeps them as words. The console stream still receives the untouched text.
- Output path: TIM16 is the 50 kHz PWM carrier (prescaler 4, autoreload 255) on the speaker pin
  as in section 8, but the samples move by DMA2 channel 4 with the TIM16 update event as its
  DMAMUX request, not DMA1 channel 1, which every bundled audio app uses; there is no second
  timer. The firmware's own drivers do not use DMA2 channel 4, but the external CC1101 radio
  driver in the apps submodule uses it for its asynchronous transmit, so speech during a Sub-GHz
  transmit with an external radio garbles both; it cannot hang or crash.
- Ring buffer 4096 bytes, about 82 ms, in two halves. The DMA's half and complete interrupts set
  thread flags on the worker, which waits for the flag of the half it is about to fill (no
  semaphore); an underrun is counted when the DMA has already moved into the half being filled.
  Each SAM value is held for delta / 8 microseconds, the Text to SAM demo's hold, plus a
  calibrated overhead of 7400 ns per value (SPEECH_OVERHEAD_NS; measured 7362 and 7422 ns on the
  two calibration sentences with tools/sam_calibrate.py, mean 7392; the played time then matches
  the demo within 0.2 percent once the 40 ms of pre fill and flush padding is taken off). The
  loudness curve is a lookup table that folds in the volume setting.
- Speaker sharing: the worker takes the speaker with a 500 ms timeout (SPEECH_ACQUIRE_TIMEOUT_MS;
  section 8 said 100 ms with retries) when it dequeues an item, refuses it without waiting when
  the TIM16 bus is already enabled by someone else, and hands it back after 200 ms of silence.
  An utterance that cannot get the speaker is dropped and counted (sr status "dropped"). The
  NFC-V listener (ISO15693 emulation) needs TIM16 and now takes the speaker mutex for each wait
  for a reader command instead of enabling the bus directly, which was a furi_check crash
  whenever speech held the speaker at that moment: it waits for a running utterance to end, and
  while it holds the speaker every announcement is dropped and counted, so NFC-V emulation is
  silent, including its own "Emulating" screen when speech was idle at the open (when speech was
  running, the screen is announced and the listener starts after it). The listener reads the
  timer's control register only after the acquire, when the bus enable has just released the
  peripheral reset, so it never copies a register that speech owns; and since the acquire puts
  the speaker pin on the timer's alternate function, the listener parks the pin as analog with
  a pull down right after it, for the whole emulation, so it does not float on the timer (the
  release re-initialises the pin).
- Queue and interruption: 4 items of 160 characters (SR_ANN_TEXT_MAX) and a generation counter.
  Screen, focus, typed and home announcements interrupt: the utterance in progress is aborted at
  its next sample and the queue is cleared. Change announcements do not interrupt and are
  replaceable: a change still waiting is overwritten by the next change instead of queuing
  behind it. Any key press stops speech and clears the queue (the service's input subscription
  sets the worker's stop flag on every press, before the app has seen the key; section 14 had
  this in phase 3); the announcement the press causes follows after the settle time. Measured:
  a sentence was cut 30 ms after an OK press, and a Back press on the NFC-V emulation screen
  cut the announcement within 10 ms with the app gone 0.6 s later. `sr say` interrupts as well
  and cuts its text at 159 characters, saying so.
- Home screen: the desktop keeps redrawing its dolphin speech bubbles, which the model reports
  as change announcements on the same screen. The service speaks a change on the desktop only
  when a key was pressed in the last 2 s (SR_DESKTOP_KEY_MS in screen_reader.c); otherwise it
  drops the utterance and counts it as "suppressed" on the frames line of sr status, while the
  announcements counter counts only what was handed to speech. The console mirror (sr watch)
  still receives every announcement, and "Home screen" on arrival is a different kind and is
  spoken.
- Worker thread: 3 KB stack (at most 812 bytes used), high priority (section 8 said 2 KB,
  normal). SAM's working memory is 3.9 KB of static RAM in the image. Flash: about 23 KB for
  the port, the engine, the text and PCM stages and the console commands.
- Console: sr say, sr stop, sr rate 40..120 (bigger is slower, saved), sr volume 0..100 (saved);
  sr status shows the speech counters (utterances, aborted, dropped, underruns, queue dropped),
  the last utterance's played and nominal time with its value count, and the worker's stack
  watermark.
- Memory, measured on 2026-09-23 with tools/ram_probe.py, raw log in
  docs/measurements/2026-09-23-ram-probe-speech-on.txt: total heap 185,720 bytes (3.9 KB less
  than phase 1, SAM's static tables), 115.8 KB free on the home screen. The phase 2 code takes
  9.7 KB of heap at service start (the 4 KB ring, the 800 byte text buffer, the queue, the PCM
  tables and the worker's 3 KB stack with its records), inside the 13 KB budget, and nothing
  per utterance.
  Lowest free heap while each core app was busy: NFC read 23.8 KB (51 KB before the reader,
  37.5 KB with the phase 1 reader), infrared universal remotes 35.3 KB, infrared learn 44.4 KB,
  TOTP 65.3 KB, RFID read 80.5 KB, Doom 80.7 KB, Momentum settings 81.8 KB, Bad KB browser
  84.0 KB, iButton read 87.3 KB, Text to SAM 88.5 KB, GPIO 98.3 KB; uPython no longer loads
  ("Not enough memory" at preload, as with the phase 1 reader). Sub-GHz is the exception: in
  this firmware base it is a MENUEXTERNAL app loaded from the card into RAM (mntm-012 built it
  into flash and shipped no subghz.fap; the phase 1 reader-on probe could not open it because
  the card still held the mntm-012 resources), about 55 KB of code and data, so its read mode
  leaves 2.0 KB free and the frequency analyzer runs out of memory, which is a furi_check that
  reboots the device. Sub-GHz is therefore not usable while the reader is enabled, until
  phase 3 addresses memory. Building it into the firmware again was tried in the final fix
  round (manifest apptype APP with the fap's file set listed explicitly, 42 KB of flash) and
  reverted: the updater validates every page of the image against the start of the BLE stack
  (SFSA 0xD7 for ble_light 1.20.0, so the firmware may use 880,640 bytes) and refused the
  910,360 byte image before writing, while fbt's .free_flash line, measured against the
  nominal 1024 KB linker region, had shown 175 KB free. The true headroom of this branch is
  11,972 bytes (firmware.bin 868,668 bytes after the round; mntm-012 was 876,900 with 3.7 KB
  spare), so phase 3 cannot add 60 KB of code to the firmware on this base;
  tools/flash_headroom.sh prints the spare bytes and is run before every flash. The other main
  apps (NFC, RFID, infrared, iButton, GPIO, Bad USB, U2F, Momentum settings) load as external
  faps as well; NFC read leaves about 24 KB.

## 17. Phase 3 as designed on 2026-09-24: on-device control

Agreed with Robin on 2026-09-24 (build authorised without further approval). It replaces the chord table of section 9 and the settings paragraph of section 10 where they differ, and adds the icon-only screens.

Input filter. `input_set_filter(InputFilterCallback callback, void* context)` in the input service, called before every publish (the four sites in input.c and the console's `input send` path), on the publishing thread (the input service thread for Press, Release and Short; the timer service thread for Long and Repeat), under the pubsub mutex. The callback fills `InputFilterResult { bool drop; bool emit_long; }`: drop suppresses the event, emit_long publishes an extra Long event for the same key right after the original. Only the screen reader installs it, while enabled. The callback must not block: it feeds a pure state machine (`sr_chords`, host tested) and posts commands to the reader thread.

Chords, Back held as the modifier. Back Press and Release pass through; Back Repeat is dropped; Back's Long from the timer is dropped and delivered on release when Back was held at least 300 ms and no chord was used; Back Short is dropped when a chord was used. While Back is down, the first Press of another key starts a chord: every event of that key is dropped until its Release. Commands, executed on the reader thread: Back plus Up reads the whole screen (`sr_screen_describe`); Back plus Down reads the status rows (time, battery, connections); Back plus OK Short repeats the focus with its position, Back plus OK Long spells it letter by letter with the recorded letters; Back plus Left and Right lower and raise the volume by ten (0 to 100, saved) and speak the new value. The rate is not on a chord: with the recorded voice it only affects SAM. Any other Press stops speech, as today. Console: `sr chord up|down|ok|okhold|left|right` runs a command without keys.

Spelling. `speech_say_spelled(text)` queues an item whose words are spelled with the letter and digit clips, 60 ms between letters and 150 ms between words.

Settings. An "Accessibility" scene in the Momentum settings app (a variable item list under the app's root list, after Misc): Screen reader OFF/ON, Voice SAM/Recorded, Rate 40 to 120 in steps of 4, Volume 0 to 100 in steps of 10, Verbosity Terse/Normal/Verbose. Values apply live because the reader reads `momentum_settings` itself: `screen_reader` and `sr_verbosity` per frame as today, `sr_rate`, `sr_volume` and `sr_voice` pushed to the speech engine before every announcement; the app saves when it exits, as its other scenes do.

Icon-only screens get spoken hints through a new tap call, `canvas_tap_hint_note(canvas, text, focus)`: a synthetic text record on the current layer that the model treats as a row (a focus row when focus is true), so no module needs real text on screen. Internal users: the desktop's lock menu (the selected tile's name, "Brightness N", "Volume N"), the PIN entry ("N digits entered", never the digits), the lock screen ("Locked, press Back three times to unlock" or "Locked with PIN, press Up to enter it"), and the unlock ("Unlocked") through the desktop status pubsub. External users: `button_panel_item_set_name(panel, index, name)` stores a name for a button, the module hints the selected button's name; the infrared app names its universal remote buttons ("Power", "Mute", "Volume up", "Volume down", "Channel up", "Channel down", and the AC, audio, projector, fan, LED, monitor, Blu-ray and digital sign sets). `canvas_tap_hint_note` and `button_panel_item_set_name` are exported for external apps: API version 87.1 becomes 87.2 (additions only; existing apps keep loading), and the infrared and Momentum settings apps are rebuilt and copied to the card.

NFC-V. The ISO15693 listener's signal reader waits 400 ms before its first speaker acquire after allocation, so the reader's "Emulating" announcement takes the speaker first and finishes; later acquires do not wait. During the emulation announcements are still dropped (section 16).

Deviations from section 9: no rate chord (volume instead); OK Long spells; Long on release stays as designed. Out of scope: hotkeys for apps other than through their own text and hints, a repeat-last-announcement history beyond the current focus, and voice feedback for the lock menu sliders beyond their value.
