# Flipper Zero screen reader for Momentum firmware: design

Date: 2026-09-22. Status: approved by Robin on 2026-09-22; phase 1 implemented and reviewed on 2026-09-22 (see section 16 for the deviations made during implementation); phase 2 built on 2026-09-23 ("Phase 2 as built" in section 16) and phase 3 on 2026-09-24 (section 17). Author: Claude, for Robin.

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
4. Other rows changed: the model reports every changed row (kind change, interrupt off); it no
   longer rate limits them itself. The service says it at once within 500 ms of a key press,
   otherwise at most once per change delay (sr_change_ms, 500 to 10000 ms, default 3000) with
   the latest text, cut at 80 characters without a recent key.
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
it expires the latest frame is processed. The wait also ends when a held change is due; while a
frame is settling, the held change waits for it rather than firing mid-settle. A key press drops
a held change before the frame it causes is modelled. Input events arrive through a small queue
filled by the pubsub callback, which only enqueues. The service keeps the timestamp of the last
Press and uses it for the key correlation rule and, in phase 3, for chords.

Enable state: the tap is installed at start and consults momentum_settings.screen_reader on
every frame, so toggling from the console or the settings app takes effect immediately without
a reboot. When off, the tap records nothing and the service idles.

Outputs: the console mirror (the ring of the last 8 announcements for sr watch) receives an
announcement when it is said, or when it is suppressed on arrival by the quiet rules; a change
replaced by a newer one while held, or dropped by the quiet rules once it comes due, never
reaches it. A said announcement also goes to the speech queue, when speech is enabled and built,
with its interrupt flag.

## 7. Console command sr

Registered by the service as a built in parallel safe command. Subcommands:

- sr screen: prints the last captured frame, one line per record: layer, x, y, font, inverted
  flag, role, position, text. Used for debugging hints and the model.
- sr watch: streams announcements as "kind: text" lines until Ctrl-C. While streaming, arrow
  keys, Enter and Backspace are forwarded as button presses exactly like Momentum's input
  keyboard command, and printable characters are sent as ascii events. This is the tethered
  screen reader and the integration test harness.
- sr on, sr off: set and save the setting.
- sr status: prints enabled state, rate, volume, verbosity, change delay, and memory use of the
  service.
- sr say text: speaks text (phase 2). sr rate n, sr volume n, sr verbosity n: set and save.
  sr delay ms (500 to 10000): set and save.

## 8. Speech engine

SAM left the firmware on 2026-09-25 (docs/superpowers/specs/2026-09-25-firmware-stripdown-design.md,
section 6). The engine below is described as built in phase 2; section 18 says what remains.

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
120), sr_volume 100 (0 to 100), sr_verbosity 1 (0 terse, 1 normal, 2 verbose), sr_change_ms 3000
(500 to 10000). Registered in the settings table so the console can set them before any spoken
settings screen exists. In phase 3 an Accessibility scene in the Momentum settings app exposes
them as a variable item list; changes apply live, no reboot. Rate is shown only when the voice
is SAM; Change delay is a row of seven values: 0.5, 1, 1.5, 2, 3, 5 and 10 s.

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
   synthesized announcements for the home screen, lock screen and lock menu, typing echo. Done on
   2026-09-24: see section 17.
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

Status: built, and verified on the device on 2026-09-24. Firmware branch screen-reader at
6c7469a79, API 87.2, firmware.bin 875,928 bytes with 4,712 spare; after the final review fixes at
af4ee0952, 876,056 bytes with 4,584 spare. The paragraphs below are the design as agreed.
"Phase 3 as built", at the end of this section, lists where the code differs; where the two
disagree, that list is what the code does. The design text is wrong in five places:

- The filter runs under the input service's own filter lock, a mutex held around each filter
  call and around input_set_filter, not under the pubsub mutex, which is private to
  furi_pubsub_publish.
- An emitted Back Long is published just before the Back Release that carries it, not right
  after the original event: the GUI drops a Long that arrives after its key's Release.
- The filter is installed once, when the reader starts, and checks the screen_reader setting
  itself, letting every event through while the reader is off. It is not installed and removed
  with the setting, because the settings app writes the setting without calling the reader.
- Notes are read first, before the drawn text, and count as screen content: a screen that shows
  only notes is not "Home screen".
- The lock is announced by the reader from the desktop status pubsub, not by the lock screen's
  note, which stays for Back plus Up.

The rate stays in the settings, on the Accessibility screen and in `sr rate`; no chord changes it.

Input filter. `input_set_filter(InputFilterCallback callback, void* context)` in the input service, called before every publish (the four sites in input.c and the console's `input send` path), on the publishing thread (the input service thread for Press, Release and Short; the timer service thread for Long and Repeat), under the pubsub mutex. The callback fills `InputFilterResult { bool drop; bool emit_long; }`: drop suppresses the event, emit_long publishes an extra Long event for the same key right after the original. Only the screen reader installs it, while enabled. The callback must not block: it feeds a pure state machine (`sr_chords`, host tested) and posts commands to the reader thread.

Chords, Back held as the modifier. Back Press and Release pass through; Back Repeat is dropped; Back's Long from the timer is dropped and delivered on release when Back was held at least 300 ms and no chord was used; Back Short is dropped when a chord was used. While Back is down, the first Press of another key starts a chord: every event of that key is dropped until its Release. Commands, executed on the reader thread: Back plus Up reads the whole screen (`sr_screen_describe`); Back plus Down reads the status rows (time, battery, connections); Back plus OK Short repeats the focus with its position, Back plus OK Long spells it letter by letter with the recorded letters; Back plus Left and Right lower and raise the volume by ten (0 to 100, saved) and speak the new value. The rate is not on a chord: with the recorded voice it only affects SAM. Any other Press stops speech, as today. Console: `sr chord up|down|ok|okhold|left|right` runs a command without keys.

Spelling. `speech_say_spelled(text)` queues an item whose words are spelled with the letter and digit clips, 60 ms between letters and 150 ms between words.

Settings. An "Accessibility" scene in the Momentum settings app (a variable item list under the app's root list, after Misc): Screen reader OFF/ON, Voice SAM/Recorded, Rate 40 to 120 in steps of 4 (shown only when Voice is SAM), Volume 0 to 100 in steps of 10, Verbosity Terse/Normal/Verbose, Change delay 0.5 to 10 s in a table of seven values (default 3 s). Values apply live because the reader reads `momentum_settings` itself: `screen_reader`, `sr_verbosity` and `sr_change_ms` per frame as today, `sr_rate`, `sr_volume` and `sr_voice` pushed to the speech engine before every announcement; the app saves when it exits, as its other scenes do.

Icon-only screens get spoken hints through a new tap call, `canvas_tap_hint_note(canvas, text, focus)`: a synthetic text record on the current layer that the model treats as a row (a focus row when focus is true), so no module needs real text on screen. Internal users: the desktop's lock menu (the selected tile's name, "Brightness N", "Volume N"), the PIN entry ("N digits entered", never the digits), the lock screen ("Locked, press Back three times to unlock" or "Locked with PIN, press Up to enter it"), and the unlock ("Unlocked") through the desktop status pubsub. External users: `button_panel_item_set_name(panel, index, name)` stores a name for a button, the module hints the selected button's name; the infrared app names its universal remote buttons ("Power", "Mute", "Volume up", "Volume down", "Channel up", "Channel down", and the AC, audio, projector, fan, LED, monitor, Blu-ray and digital sign sets). `canvas_tap_hint_note` and `button_panel_item_set_name` are exported for external apps: API version 87.1 becomes 87.2 (additions only; existing apps keep loading), and the infrared and Momentum settings apps are rebuilt and copied to the card.

NFC-V. The ISO15693 listener's signal reader waits 400 ms before its first speaker acquire after allocation, so the reader's "Emulating" announcement takes the speaker first and finishes; later acquires do not wait. During the emulation announcements are still dropped (section 16).

Deviations from section 9: no rate chord (volume instead); OK Long spells; Long on release stays as designed. Out of scope: hotkeys for apps other than through their own text and hints, a repeat-last-announcement history beyond the current focus, and voice feedback for the lock menu sliders beyond their value.

### Phase 3 as built

Recorded after the Task 5 device runs on 2026-09-24. Where this list disagrees with sections 9
and 10 or with the design above, this list is what the code does. The device outputs are in
docs/measurements/2026-09-24-phase-3.txt.

- Input filter: input_publish_event(pubsub, event) is the one publish path, used by the four
  sites in input.c and by the console's fake_input. The console command is the cli_input plugin
  on the card, so input_publish_event is exported ("+" in the API table); input_set_filter stays
  internal ("-"), a single slot for the reader. The filter lock is allocated before the input
  record is created, and input_set_filter opens that record first, so the filter can be
  installed at any point of the reader's start. Once input_set_filter returns, the old filter is
  not running and will not run again. The lock is released before publishing, so it never nests
  with the pubsub mutex. The callers are the input service thread (Press, Release, Short), the
  timer service thread (Long, Repeat) and console threads, which can preempt one another; the
  filter must not block, call input_set_filter or publish. Stack cost: input_publish_event 32
  bytes, sr_input_filter 40, sr_chords_feed 20.
- The emitted Long is published before the event when that event is a Release, after it
  otherwise, and alone when the event is dropped too. It is a copy of the event, so it keeps the
  press's sequence number, and it does not pass the filter. Section 9's side effect stands: with
  the reader on, a Long of Back alone arrives when Back is released.
- The filter reads momentum_settings.screen_reader on every event; while it is off, every event
  passes and the chord state is reset. Publishers that bypass the filter: remote control
  (rpc_gui.c) and the keys of `sr watch` (sr_cli_press). Console keys (`input send`) pass it but
  have no press timer: a press followed by a release never makes a Long, and `input send back
  long` sends Press, Long, Release.
- sr_chords keeps no time of its own (now_ms is reserved; the input service's 300 ms threshold
  decides the Long). OK decides on its Short (repeat) or its Long (spell); a Short after a Long
  is ignored. 73 host checks, including Back held past 300 ms before the chord key.
- Commands reach the reader thread through one atomic slot: the latest wins and none runs
  twice. A frame still settling is modelled first, so a command reads the screen as it is, and
  reads the model's screen in place, without a 1.3 KB copy. A command is dropped when the reader
  was turned off in between; `sr chord` answers "screen reader is off" then. Every command
  interrupts. The rate, volume and voice are pushed to the engine before every command, as
  before every announcement.
- Texts: Back plus Up on a screen without text says "Home screen" on the desktop (the model's
  word for it) and "Nothing on screen" elsewhere. Back plus Down: status records never join a
  row; the battery's digits read as "battery N percent", after the clock when the clock is
  shown; "No status bar" when there is none. Back plus OK with no focus says "No focus"; so does
  Back plus OK Long, spoken, not spelled, and a focus without letters or digits is said
  normally.
- Long texts: commands build their text in a 640 byte buffer (SR_DESCRIBE_TEXT_MAX) and say it
  in parts of at most 159 characters, cut after the last ". " or ", ", else the last space,
  else hard; at most four parts (more count as queue dropped), the first interrupting, the rest
  following. sr status counts each part as an utterance. No screen found on the device reads
  longer than 160 characters (the longest, About page 3, has 119), so the split is proven by the
  host tests only.
- Spelling spells the text as written, not the expanded text, which would spell number words:
  letters and digits are kept, other characters separate words, and runs over 31 characters are
  split. Each spelled letter counts as a clip; nothing is logged as missing. With the voice off,
  SAM spells, with A as "AY".
- The volume chord steps by 10 within 0 to 100 and saves at once. The chord and the
  Accessibility scene write the same setting.
- Accessibility scene: momentum_app_scene_accessibility.c, the fourth item of the app's root
  list, after Misc. When the saved rate or volume is off the scene's grid (set from the
  console), the row shows the nearest step (volume 75 shows 80); the first Left or Right moves
  from that step. The app saves on exit. Turning the reader back on, in the scene or with sr on,
  reads the screen again: the frame tap sees the setting go from off to on, and the model forgets
  its previous screen, so the screen shown is announced as a new one even when it is the one the
  reader last saw (on the Screen Reader row, "Screen Reader ON"). Rate is shown only when Voice
  is SAM: five rows with the recorded voice, six with SAM. Change delay is a seven-value table
  (0.5, 1, 1.5, 2, 3, 5, 10 s; default 3 s) rather than a step grid; an off-table saved value
  snaps to its nearest entry, the same as Rate and Volume snap to their nearest step.
- Notes: canvas_tap_hint_note records text with the note flag at position 0, 0 in the secondary
  font. In the model a note is a row, a focus row when focus is set, never the title and never
  joined with drawn text. Notes are read before the drawn text (the lock screen's date sits
  above the top edge while its cover slides down). A screen with only notes has content, so it
  is not "Home screen". sr screen marks notes NOTE.
- Desktop: "Home screen" is also said when a desktop screen closes without leaving the desktop,
  such as the lock menu or the power-off dialog, once the desktop's text is gone. That one does
  not interrupt and follows the bubble rule: it is spoken only within 2 s of a key press. The
  lock menu names the selected tile, a switch with "on" or "off", a slider with its level
  ("Brightness 100", "Volume 95"), and in stealth mode the Volume slider with its level and
  "muted" ("Volume 95, muted"). The lock popup's choices are a focus with a position ("Keypad
  Lock, 1 of 3"). The PIN entry's note says "1 digit entered" or "N digits entered" and is read
  before "Enter PIN:"; the PIN entry was not exercised on the device.
- Lock: the reader subscribes to the desktop status pubsub once the desktop record exists
  (retried on every frame, because the desktop creates the record at the end of its setup) and
  announces the lock itself, as a new announcement kind ("lock:" in sr watch), interrupting and
  never suppressed, so an auto-lock is heard without a key press: "Locked, press Back three times
  quickly to unlock" (quickly: the lock screen counts afresh after 600 ms without a key), or
  "Locked with PIN, press Up to enter it" when the RTC lock flag of a PIN lock is set. For 2 s
  after it, or until a key press, the desktop says nothing more: not the lock screen arriving,
  not the bubbles behind its cover, not a late frame of the lock menu. "Unlocked" is said on
  every locked=false message, which only desktop_unlock publishes, without interrupting, so the
  "Home screen" that follows is queued behind it. The lock screen keeps its own note for Back
  plus Up, with the 3 as a digit ("Locked, press Back 3 times quickly to unlock", spoken as
  "three") because a note keeps 47 characters; while its hint shows after a key press, a second
  note names the key, "Press Back three times quickly to unlock" or "Press Up to enter the PIN",
  also when the visual prompt is turned off.
- Infrared: button_panel_item_set_name gives each ButtonItem a name, and the panel hints the
  selected item's name as a focus note after its icons, so the panel's label stays the title.
  The universal remotes name all 56 buttons of their 9 scenes, beyond the design's table: Stop,
  Exit, Fast backward, Fast forward, Power on, Power off, and the LED colours as written. The
  panels are vertical, so with the device held normally Right and Left move down and up a column
  and Up and Down move between the columns.
- NFC-V: as designed. On the device the "Emulating" screen played in full, 11,076 ms, before the
  listener took the speaker, and an utterance during the emulation was dropped.
- API 87.2 exports canvas_tap_hint_note and button_panel_item_set_name. The firmware was flashed
  with flash_usb_full, so every app on the card was rebuilt for it.
- Vocabulary: the hint words were added by the routine voice_build run (27 clips, among them
  digit, dry, backward and muted). The PIN note's "digits" is built by printf, which the
  extraction cannot see, so tools/voice_words.txt lists it. The final review fixes added one
  clip, "quickly", also listed there.
- Budget: firmware.bin 875,928 bytes at 6c7469a79, 4,712 spare; phase 3 took 3,880 bytes (8,592
  spare at d5b77c219). The final review fixes took 128 more: 876,056 bytes at af4ee0952, 4,584
  spare. The polish round (change throttle, Rate shown only for SAM, Change delay) took 980
  more: 877,036 bytes at 859c87c98, 3,604 spare. Idle heap about 110 KB free, as before. Lowest
  free stack seen: InputSrv 580 of 1,020 bytes, TimersSrv 740 of 1,020, DesktopSrv 1,084 of
  2,044, GuiSrv 1,108 of 2,044, ScreenReaderSrv 2,028 of 3,068, SpeechWorker 2,180 of 3,068.
- Tests: host checks for chords 73, the model 159, speech text 1,022, the queue 156, PCM 700 and
  the voice 4,433, plus the 11 SAM cases. On the device, tools/sr_drive.py's third session sends
  the four chords that change no setting (Back plus Up, Down, OK and OK Long) with `input send`,
  on the home screen and in the main menu, and checks that each one speaks and leaves the screen
  as it was: 0 failures. Robin judged the spelling and volume chords by ear: great.
- Known limits: Sub-GHz runs out of memory with the reader on (opening it restarted the device);
  the memory plan comes next. Dolphin bubbles behind the lock screen can be read around a lock.
  The splash screen after an update is dismissed silently. After a PIN unlock "Unlocked" and
  "Home screen" can swap. Twice the scripted driver's first synthetic OK on the home screen after
  a long idle opened the lock menu; not reproduced since, not explained (Up is the default
  keybind that opens the lock menu). Remote control and `sr watch` keys bypass the chords. One
  unexplained "furi_check failed" reboot happened during phase 3 (15:09:51, the project's third);
  tools/flipper_log.py now keeps the log, so the next one names its thread.

### Polish round as built (2026-09-24)

Three items: a change delay so same-screen changes such as a progress bar are throttled instead
of read on every frame, Rate shown only when Voice is SAM, and `tools/voice_build.py` extracting
vocabulary from the apps already on the card instead of from firmware source alone. Deviations
from the design sections above: the model's own rate limiter (section 5 rule 4, a flat 1500 ms)
was removed rather than kept alongside a service-side one; the throttle lives in the service
(`sr_throttle.c`, host tested), so the model itself just reports every changed row. Change delay
is a seven-value table (0.5, 1, 1.5, 2, 3, 5, 10 s), not a uniform step range like Rate and
Volume. The card-apps extraction reads the strings already built into the `.fap` files on the
SD card, so a clip is produced even when its source text lives in an app outside this
repository.

## 18. Stripdown as built (2026-09-25)

Recorded after the firmware stripdown round
(docs/superpowers/specs/2026-09-25-firmware-stripdown-design.md) and the Task 6 device pass.
Where this section disagrees with a section above, this section is what the code does; the
sections above stay as history.

Build options: two new options in `fbt_options.py`, tracked, next to `SKIP_EXTERNAL` and
`EXTRA_EXT_APPS`: `EXCLUDE_EXT_APPS = ["js_app", "cli_js", "test_js"]` and
`EXCLUDE_EXT_CATEGORIES = ["Games"]`, plumbed through `site_scons/commandline.scons`,
`scripts/fbt_tools/fbt_apps.py` and `scripts/fbt/appmanifest.py`; `firmware.scons` was not
touched, since the values reach the firmware environment through the base environment's
variables. An excluded app's plugins leave with it, and the build prints "Excluded 45 external
apps by configuration". Two deviations from the stripdown spec: `test_js`, the JavaScript
engine's own unit-test plugin, had to be named in `EXCLUDE_EXT_APPS` too, because the plugin
grouping keeps a plugin when any of its parents is still built, and `test_js`'s other parent is
the unit-test runner, which stays; `js_app` also had to be dropped from the `system_apps`
metapackage in `applications/system/application.fam`, because that metapackage is what deployed
the example scripts to the card. A plain Python test over synthetic manifests,
`tests/fbt/test_exclusions.py`, now runs in `tools/run_host_tests.sh`.

JavaScript engine out: `lib/SConscript` drops `mjs`; `targets/f7/api_symbols.csv` drops its 82
functions and 8 headers. The API version stays 87.2 (the build prints "API version 87.2 is up to
date"): nothing shipped imports the removed symbols, and a major bump would only make the app
catalog stop offering builds for this firmware, protecting nobody. The loader's and the file
browser's `.js` handling stay in place as inert code. Saving: 41,288 bytes of flash (877,036 to
835,748).

Sub-GHz built in: `applications/main/subghz/application.fam` becomes the version of commit
1c113c28a, `apptype APP` with an explicit source list; no `subghz.fap` is produced any more.
Cost: 42,028 bytes of flash (835,748 to 877,776). Since the round's final fixes,
`tests/fbt/test_subghz_sources.py`, the last step of `tools/run_host_tests.sh`, fails when a `.c`
file under `applications/main/subghz` is not named in that manifest or a named one is missing,
so a Momentum rebase that adds a scene cannot leave it out of the build unnoticed.

SAM out of the speech engine: the engine now plays clips and spelled letters only. With the voice
off (`sr voice off`) or without `/ext/sr/voice` on the card, a text item completes at once,
without opening a file, playing anything, or writing the missing list; `sr voice status` counts
these under a new "muted" figure. `sr voice on|off` is runtime only: on after a reboot, never
saved. A letter whose own clip is missing is now skipped and logged like a missing word, rather
than spoken by SAM. `speech_set_volume` replaces `speech_set_voice`; `SpeechVoiceStats.muted` is
new. `sr_rate` and `sr_voice` are removed from `MomentumSettings` and from the settings table; an
old settings file that still carries those keys loads fine, and the keys are dropped at the next
save. `sr rate`, the Rate row and the Voice row are gone; the Accessibility screen now has four
rows: Screen Reader, Volume, Verbosity, Change delay. The chunking that existed for SAM's
250-byte input is gone (`speech_text_next_chunk`); an item's text, up to 800 characters, is
walked in one pass. The SAM host test, its reference build, and `tools/sam_calibrate.py` are
gone. Two comments crediting Momentum's Text to SAM demo app, for the loudness curve and the
50 kHz carrier, stay: they name where those numbers came from. Saving: 15,344 bytes of flash
(877,776 to 862,432) and 3,683 bytes of static RAM (9,580 to 5,897).

Animations off by default: a new setting, `desktop_anims` (file key `desktop_anims`, default
false). The Momentum settings app shows it as the row "Animations", first under Momentum,
Interface, Graphics, OFF then ON; changing it sets the app's reboot flag, so leaving the app
shows "Rebooting..." and the device reboots. The guards in `animation_manager.c` test the field
`anims_enabled`, which `animation_manager_alloc` latches from `momentum_settings.desktop_anims`
(the first deviation below). `animation_manager_alloc` has no early return: with animations off
it skips its loading block, the first blocking check and the first idle animation, and in the
`else` branch grants a pending level up. The five other entry points return early:
`animation_manager_check_blocking_process`, which first grants a pending level up;
`animation_manager_new_idle_process`, `animation_manager_unload_and_stall_animation` and
`animation_manager_load_and_continue_animation`, which just return; and
`animation_manager_interact_process`, which returns false. A pending level up is granted at boot
and at every later check, which the manager runs after every dolphin deed and every card event
(the second deviation below).

Deviation from the stripdown spec: the animation manager latches the `desktop_anims` setting once,
at allocation, into a field of its own, and every guard tests that field rather than the live
setting. The spec had the guards read the live setting; that could let a settings change reach
the manager, between the row changing and the reboot happening, while the manager sits in a state
`animation_manager_load_and_continue_animation` does not handle, which crashes. Latching the
setting at allocation closes that window.

A second deviation from the stripdown spec, made by the round's final fixes: its section 7 had a
pending level up granted only at the manager's next check, after a dolphin deed or a card event,
and not at boot, because nothing should run against the dolphin while the desktop is still being
set up. The grant at boot is safe all the same: upstream's `animation_manager_alloc` already
calls `dolphin_stats` at that point, through `animation_manager_check_blocking`, on the desktop's
thread. The grant adds that one call and, when a level is pending, `dolphin_upgrade_level`, which
only queues an event for the dolphin's own thread.

Flash for the animations step: 156 bytes (862,432 to 862,588). The round's final fixes, at
08e80106f, add 24 bytes. The final image, 08e80106f: 862,612 bytes, 18,028 spare below the BLE
stack.

The card, after the first full flash: the updater removed the games, the Scripts folder, the
JavaScript runner and its modules, and the old `subghz.fap`, by itself, because none of them are
in the new resource manifest any more. The Apps browser now lists eleven folders: Bluetooth,
GPIO, Infrared, Media, NFC, RFID, Sub-GHz, Tools, USB, assets, iButton.

Figures from the Task 6 device pass (docs/measurements/2026-09-25-stripdown.txt). Flash after
each step, against the BLE stack's 880,640-byte limit: round start 877,036 bytes (3,604 spare);
the JavaScript engine out, 835,748 bytes (44,892 spare, 41,288 less); Sub-GHz built in, 877,776
bytes (2,864 spare, 42,028 more); SAM out, 862,432 bytes (18,208 spare, 15,344 less); the
animations setting, 862,588 bytes (18,052 spare, 156 more). The round in total, to that image:
14,448 bytes less than at its start; to the final image, after the round's final fixes: 14,424
less. Idle heap, 30 seconds after boot: with animations off, 116,672 bytes free on
the first boot and 116,752 on a second; with animations on, 116,736 -- but that reading caught the
firmware's own built-in "new mail" animation, not a card animation (a dolphin level-up was
pending), so it does not measure what a card animation costs. The stripdown spec's estimate of 10
to 26 KB of idle heap for a card animation therefore still comes from the 2026-09-22 probe, not
from this round. On the RAM probe, with the reader on throughout: Sub-GHz Read keeps 53,064 bytes
free at its lowest, and the Frequency Analyzer 51,136, where on 2026-09-23, with Sub-GHz still a
fap on the card, Read went down to 2,080 bytes and the Frequency Analyzer crashed the device out
of memory. NFC Read is now the heaviest core app, at 23,232 bytes free.

The dolphin in words (2026-09-25). With the animations off, the dolphin's state reaches a blind
user only in words, so three small changes followed the round. The pronunciation layer has a rule
14: a slash between two digits is "of", so the Passport's "18/100" is "eighteen of one hundred";
any other slash stays "slash". The dolphin service now publishes `DolphinPubsubEventUpdate` after a
level up as it does after a deed (two lines in `dolphin.c`; the event enum is unchanged). The
reader sets up the dolphin the way it subscribes to the desktop: at its start, after its own record
and console so that a wait for the dolphin cannot delay them, and on every frame until the
dolphin's record exists; then it opens the record, subscribes (the handle is kept), and reads the
starting level into `last_level`. In a special boot (an update) the dolphin never starts; the check
stays cheap and the reader keeps reading the update's screens. The callback only sets
`SR_FLAG_DOLPHIN`, because `dolphin_stats` waits on the dolphin's own event loop, the thread that
runs the callback. On the flag the service thread reads the stats. A higher level is held for two
seconds (`SR_LEVEL_HOLD_MS`), and while it is held every interrupting announcement (in
`sr_announce`: a new screen, a focus, the home screen, a lock, a typed character) holds it two
seconds more from then,
at most five seconds after the level rose (`SR_LEVEL_HOLD_MAX_MS`); a second rise meanwhile only
updates the level to be said, and the loop's wait includes the due time as it does a held change's.
Then, once no frame is settling, it is said as "Level up, level N" without interrupting, so it
follows the screens a deed brings: a Save's "Saved!" popup, which closes by itself after 1.5 s (the
longest of the core apps' popups), and the screen after it. One second, the first value, was too
short: on R0skie a proxy of the Save flow (OK on Frequency Analyzer, Back 1.2 s later) queued the
level up before the Back, which silenced it. It has a kind of its own, `SrAnnLevel` ("level" in `sr
watch`), goes through `sr_say_event` (formerly `sr_say_lock`), is never kept quiet, and keeps a
held change: only a lock or an unlock drops one. With the reader off when it comes due it is
dropped, the level kept. A level raised by hand in Momentum, Misc, Dolphin publishes nothing and is
said as a level up at the next deed; a level lowered by hand is only noted. After a card mount the
reader notes the level afresh, silently: when the card was not ready as the dolphin started, the
dolphin loads its state on the mount and publishes nothing. The reader subscribes to the storage
pubsub (the handle is kept) and its callback sets `SR_FLAG_STORAGE` on a mount only; it hears of
the mount before the dolphin, since pubsub calls the newest subscriber first, so it pauses 50 ms
(`SR_MOUNT_SETTLE_MS`) before asking, and the dolphin's reload goes first in its queue. Back and
Down appends the level and the mood to the status bar: "battery 87 percent, level 3, mood happy",
or the dolphin part alone where there is no status bar; "No status bar" is left only for a special
boot, where there is no dolphin. The mood is happy for a butthurt of at most 4, okay at most 9,
angry above: the Passport's thresholds (`applications/settings/dolphin_passport/passport.c`),
repeated on purpose since the Passport is an app of its own. `sr_status_text` in the model is
unchanged. Flash: 672 bytes (862,612 to 863,284, 17,356 spare); static RAM unchanged at 5,897
bytes. On R0skie: Back and Down on the home screen said "battery one hundred percent, level two,
mood happy", 8 clips; the Passport's "7/100" was read as "seven of one hundred" from clips; with
c502de5a, after a deed in the Frequency Analyzer with the points one short of level 3, "Level up,
level 3" came 1,998 ms after the analyzer's screen announcement and played in full behind it when
the analyzer was left open, and with Back pressed 1.2 s after OK it came 1,996 ms after the menu's
screen announcement and played in full.

The crash address (2026-09-25). The device rebooted now and then with the generic "furi_check
failed" popup, and the crash handler prints its registers only to the debug UART, which the USB
console never sees. Now `__furi_crash_implementation` (`furi/core/check.c`), in its release branch,
right after `furi_hal_rtc_set_fault_data`, also keeps two values in RTC backup registers added
after `FuriHalRtcRegisterPinValue`, before `FuriHalRtcRegisterMAX`: `FuriHalRtcRegisterFaultLr`
(index 8), the lr it stored on entry (`__furi_check_registers[12]`, the return address into the
function whose check failed), and `FuriHalRtcRegisterFaultBuild` (index 9), the first eight hex
digits of the build's git hash as a number, parsed from `version_get_githash(version_get())` by a
small loop that allocates and locks nothing and reads the hash only when its pointer lies in flash,
since the crash may come from overwritten RAM; 0 when unknown. The build is kept because nothing on
the update path resets the backup registers: after a flash the address of the older build stays,
and decoding it with the new elf would name a wrong function without any sign of error. No existing
index moved (as compiled: Header 0 to PinValue 7, FaultLr 8, FaultBuild 9, MAX 10). The RTC's
header register holds only a magic and a version, no count or checksum; every reset of the
registers, such as a factory reset, clears both with the rest. The API stays 87.2, since enum
values change no symbol. The desktop's crash popup (`desktop_scene_fault.c`) builds its text in a
static buffer of 64 characters, because the popup keeps the pointer; the buffer costs 64 bytes of
.bss (static RAM 5,897 to 5,961 by `tools/map_size.py`). The text is the message, then a line "at
0803ABCD", eight upper case hex digits without "0x". The message is read with a precision, 51
characters with the address line and 63 without, so the address always fits and a stale message
pointer is read no further than the buffer; with no address kept the popup shows the message alone.
Leaving the popup clears the fault message as before but not the address. `sr status` prints, after
its "enabled" line, "last crash: at 2001384F in build 9028a849", "in build unknown" for an address
stored by an earlier build that kept none (a2dfdd28 kept the address alone), or "last crash: none"
for 0.

Decoding: an address in flash (08...) minus 2, given to `arm-none-eabi-addr2line -f -i -C -a` with
the `firmware.elf` of the build `sr status` names (built in a git worktree if the build directory
has moved on), gives the function and the line of a check; `-i` adds the functions inlined there,
which it does at 171 of the 1,848 calls. Minus 2 because the address itself is the instruction
after the call: in the build before this change, of 1,848 calls to the crash routine, the address
itself named the call's own line at only 55 and another function at 154; the address minus 2 named
a check's line at every one of a sample of twelve. That line is the failed check's own only when
the check has a call of its own: GCC merges identical crash-call sequences within a function, and a
rough count of the branches into each call found about 700 of the 1,848 entered from more than one
source line (in `ble_svc_serial_notify_buffer_is_empty` four checks share one call, and addr2line
names the last). So the function named, or the one it is inlined into, is the one that failed, and
the line is one of its checks. An address starting with 20 (2000 to 2003) is in RAM, inside an app
loaded from the card, which the firmware's elf cannot name. For any message other than "furi_check
failed" or "Check serial logs", the address is in the routine that reported the crash, such as a
fault handler.

The Passport's points line is now labelled, "XP 7/100", and rule 3's table has XP as "experience",
so it reads "experience seven of one hundred"; the label fits, since the longest line, "XP
9999/9999", is 59 pixels wide in the 5x7 font and ends at x 117. Flash: 360 bytes in all (863,284
to 863,644, 16,996 spare; a2dfdd28, before the build register, was 863,468). On R0skie with
a2dfdd28: the Passport read "XP 7/100"; "experience" was not yet in the vocabulary, so the first
time it was spelled from letter clips and logged as missing, and after
`tools/voice_build.py --extract --card-apps --pull-missing --sync` the line played 15 clips, R0skie
the only word spelled; `sr say "Dolphin XP"` played two clips. The crash test's Check item
(`furi_check(false)` in an app from the card) rebooted the device, and the popup read "Flipper
crashed", "and was rebooted", "furi_check failed", "at 200137DF", spoken as "at two zero zero one
three seven D F" from 17 clips in all; `sr status` said "last crash: at 200137DF" before and after
Back closed the popup. With 9028a849 flashed, `sr status` said "last crash: at 200137DF in build
unknown"; a second trial gave "at 2001384F" in the popup and "last crash: at 2001384F in build
9028a849" in `sr status`, before and after Back. The call sits at offset 0x20 of the app's code, so
the app had been loaded at 0x200137BC and then at 0x2001382C.

The reader toggle and the positioned note (2026-09-25). Back held with Down held long now turns the
reader off, or on again, also while it is off. The chord machine (`sr_chords.c`) splits Down as it
splits OK: Down pressed while Back is held becomes the chord key and is swallowed until its
release; its Short is `SrChordStatus` and its Long `SrChordToggleReader`, once, with no Status
after it (`key_long_seen`, formerly `ok_long_seen`, serves both keys). `sr_chords_feed` takes
`reader_on`, which the input filter passes from the setting at every event, instead of resetting
the machine while the reader is off. With the reader off the toggle is the only chord: only Down
starts one, held back from its Press, and it becomes a chord at its Long, which then drops Back's
own Short and cancels a held-back Long, as any chord does with the reader on; a short Down with
Back held is lost, since its Press cannot be given back; Up, OK, Left and Right while Back is held
pass untouched. Back itself is handled alike in both modes: its Short at once, its Long held back
to the release. The brief had Back's own Long pass as an ordinary key while the reader is off, but
at Back's Long the machine cannot tell yet whether Down will follow, and a Long passed at 300 ms
would open the power-off dialog on the home screen before the usual slow chord, with Back held
first; so the chord drops what it drops with the reader on, and a long Back alone still reaches the
app, on its release. The chord key stays swallowed across a change of mode, so the reader turning
on or off in the middle of the chord drops the rest of it all the same. One timing differs by mode:
with Back let go before Down's Long, Back's Short passes while the reader is off, since no chord
has run yet, and the toggle still comes at Down's Long; with the reader on the chord began at
Down's Press, and the Short is dropped. The reader runs the toggle on its service thread whether it
is on or off, and on every screen, the lock screen and the PIN entry included, where Back with Down
means nothing else: after a reboot into a PIN lock with the reader off it is how speech comes back.
(The first build ignored the toggle while the desktop was locked; the review found that this gate
could not hold while the reader had been off since boot, and it was dropped.) For that boot the
service loop now tries to subscribe to the desktop and the dolphin at every wake-up, and while
either record is missing it wakes every 250 ms (`SR_SUBSCRIBE_POLL_MS`), whatever the setting: only
frames drove the retry before, and none come while the reader is off, yet the lock announcements
and the status chord's level must work as soon as the chord turns the reader on. In a special boot
(an update), where neither service starts, the loop keeps waking so. Off: as
`screen_reader_set_enabled(sr, false)` does it (the setting saved, speech stopped), then "Screen
reader off" through `speech_say`, interrupting, which the engine plays with the reader off, as it
plays `sr say`. On: the setting saved; a frame asked for with `gui_update` and awaited as the loop
lets a screen settle (50 ms after the last frame, about 350 ms at most: 300 ms, then one last 50 ms
wait); that frame, which the tap marks as a new screen, modelled without its announcements, so it
is the screen announced and its next frame brings no news; then one `speech_say_parts` utterance,
"Screen reader on. " and the text Back and Up reads for the screen (`sr_read_all_text`, now shared
with the ReadAll command, "Home screen" on the bare desktop), the confirmation first and the screen
right after it; "Screen reader on" alone when no frame came in time. One deliberate difference from
the brief, which wanted "Screen reader on" alone when the screen's description is empty: the text
is Back and Up's, fallbacks included, so a screen with no text of its own other than the home
screen gives "Screen reader on. Nothing on screen", and only a missing frame leaves the
confirmation alone. A screen longer than the speech queue's four parts loses its tail, as it does
with Back and Up. The frame handover, `sr_model_ready`, is shared with `sr_process`. A held change
is dropped on either toggle. `sr chord downhold` runs it, also with the reader off, when the other
chord keys still answer "screen reader is off". The Accessibility row and `sr on|off` read and
write the same setting.

The positioned note: `canvas_tap_hint_note_at(canvas, x, y, text)` records a note as
`canvas_tap_hint_note` does (not drawn, the secondary font, never a focus; one that joins a row
begun by title-font text at the top of the screen is read inside that title) but at
x and y plus the canvas offset, where `canvas_draw_str` would record the text. The model reads a
note at x 0, y 0 as before, first and a row of its own, and a placed note in reading order among
the drawn text, by baseline and x, joined to the row on its baseline as drawn text is. The model
joins by row kind and a 2-pixel baseline tolerance, with no gap rule, so the note needs no width:
its x only orders it within the row. A row that a note begins is never the title. The Passport
records "to level N" at x 59 plus the points' width in the battery font plus 2, y 42: the next
level; the last one, 30, while OK shows the points in total (a refinement of the brief, whose next
level would misstate the total); none at "Max Level!". API 87.3: one new entry in
`targets/f7/api_symbols.csv` and the version bumped by hand; the build prints "API version 87.3 is
up to date"; apps built for 87.2 keep loading, and only the Passport was rebuilt (`./fbt
fap_passport`) and copied to `/ext/apps/assets/passport.fap`.

Flash: 752 bytes (863,644 to 864,396, 16,244 spare; 864,420 before the review fixes); static RAM
unchanged at 5,961 bytes. Host tests: the chords 208 checks (73 before), the model 195 (174
before). On Delphi with f9f1e168: the chord on the home screen said "Screen reader off" (3 clips,
1,512 ms) and the settings file then read `screen_reader: false`; the chord again said "Screen
reader on. Home screen" as one utterance (5 clips, 2,820 ms, nothing aborted), the frame counter
one up and the announcement counter unchanged, and nothing more in the next 4 seconds; `sr chord
downhold` twice turned it off (3 clips) and on (5 clips); Back with a short Down still read
"battery one hundred percent, level two, mood happy" (8 clips). With the reader off, Back and Up
opened the lock menu, and the toggle made there said "Screen reader on. Lock" (4 clips), the screen
as it was then, not the one from before the reader went off. With 4a442043, after the review fixes,
on the lock screen of a keypad lock: the chord said "Screen reader off" in full (1,505 ms; the lock
hint that the chord's Back press brings up had begun to be read and was cut), and the chord again
said, as one utterance of 35 clips (19,290 ms, nothing aborted, no announcement), "Screen reader
on. Locked, press Back three times quickly to unlock. Press Back three times quickly to unlock.
Press three x. to unlock!", the date and the time: the lock screen with the hint the chord's own
Back press had brought up; three quick Backs then unlocked, with "Unlocked" and "Home screen".
After `sr off` and a reboot, with the reader off since boot and no frame captured, the chord said
"Screen reader on. Home screen", and a status chord straight after it, with no frame in between,
"battery one hundred percent, level two, mood happy". The Passport read "Delphi. Mood, Happy.
Level, two. experience seven of one hundred to level three", 13 clips, no fallback, the note
recorded at x 100, y 42; with OK, "XP 107/9999 to level 30", the note at x 115. `tools/sr_drive.py
--chords`, whose Down step now sends Down's Short, passed all eight chords on the home screen and
in the main menu.
