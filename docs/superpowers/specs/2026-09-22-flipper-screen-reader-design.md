# Flipper Zero screen reader for Momentum firmware: design

Date: 2026-09-22. Status: approved by Robin on 2026-09-22, memory measurements in section 11. Author: Claude, for Robin.

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
