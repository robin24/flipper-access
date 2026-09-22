# Flipper Zero accessibility investigation

Date: 2026-09-14. Scope: can a Flipper Zero running Momentum firmware be modified so that a fully blind user can operate it, primarily through speech output? Everything below marked "verified" was checked directly in the Momentum firmware source (branch dev, cloned 2026-09-14), the source of the relevant community apps, the STM32WB55 alternate-function table, or official Flipper documentation. Things I could not verify are listed in section 9.

## 1. Short answer

Yes. It is feasible, nobody has done it yet, and the building blocks already exist:

- The built-in speaker can play sampled audio, not just beeps. Several community apps already do this, including a text-to-speech app (Text to SAM) that ships with Momentum.
- Every piece of text the firmware draws passes through three functions in one file. A screen reader can capture all displayed text and detect the highlighted menu item there, without touching individual apps.
- Momentum is built from source with a command-line tool, and the device also has a full text command-line interface over USB serial that you can drive from a computer with your own screen reader.

The two real uncertainties are sound quality and loudness of the internal piezo speaker for speech, and how much per-app polishing is needed after the generic screen reader works. Both have workable answers (an external amplifier module on the GPIO header, and module-level hooks), described below.

## 2. Hardware facts (verified)

Processor and memory:

- STM32WB55RG: Cortex-M4 at 64 MHz for the firmware, plus a Cortex-M0+ radio core.
- 1 MB flash. 256 KB SRAM in total, of which the linker script gives the firmware about 192 KB (RAM1) plus two 10 KB regions. Momentum builds with size optimization (COMPACT=1), so flash is not generous.
- No digital-to-analog converter on this chip. All audio output is pulse-width modulation (PWM) or digital.

Speaker:

- A piezo buzzer on pin PB8, driven by timer TIM16 channel 1. Official specification: 100 to 2500 Hz, 87 dB.
- The official speaker driver (furi_hal_speaker) only produces square-wave tones at a given frequency and volume. Access is guarded by a mutex; the notification service grabs it for at most 30 ms per beep and gives it back, so a speech service can share it politely.
- Community apps reprogram TIM16 as an 8- to 10-bit PWM carrier (62.5 kHz to 250 kHz) and change the duty cycle at the audio sample rate. The bundled WAV Player does this with DMA paced by TIM2, so playback runs in the background. The Video Player and MP3 Player do the same. Text to SAM does it by busy-waiting with microsecond delays, which blocks the thread that is speaking.
- Honest quality expectation, quoting the MP3 Player author: "The Flipper's internal sounder is a piezo buzzer, not a music speaker. Expect buzzy, low-fidelity sound." and "It is very quiet, even at 100% volume. This is a hardware limitation of driving a piezo element from a GPIO PWM carrier." Speech synthesis can compensate somewhat (SAM already applies a tanh loudness curve), but plan for "understandable in a quiet room", not "loud on the street".

External audio through the GPIO header (18-pin header on top):

- Pin 3 (PA6) can carry the same TIM16 signal as the internal speaker. The WAV Player and Video Player already route audio there. With a two-stage RC low-pass filter it feeds an analog amplifier board such as a PAM8403 (about 2 to 5 euros).
- I2S digital audio to a MAX98357A amplifier module (about 5 euros, drives a small speaker directly): the MP3 Player bit-bangs I2S using pins 5 (PB3, bit clock), 2 (PA7, data) and 4 (PA4, word clock), powered from pin 1 (5 V). The author reports this is "dramatically louder than the internal sounder". The chip's SAI peripheral (sub-block B) is also mapped to header pins PB3, PA4 and PA13, so a proper hardware I2S implementation is possible later.
- UART on pins 13 and 14 (PB6, PB7) can talk to an external microcontroller. The bt_audio project uses this to make an ESP32 stream audio to Bluetooth headphones over A2DP, because the Flipper itself only has Bluetooth Low Energy and cannot do Bluetooth audio.
- No headphone jack. No USB audio.

Controls and feedback:

- Five-way directional pad (up, down, left, right, OK) plus a separate Back button. All tactile.
- Vibration motor, usable for haptic cues (start and end of list, errors) through the existing notification service.
- USB-C with a serial command-line interface (CLI), see section 5.

## 3. Speech synthesis on the device (verified)

- Text to SAM is included in every Momentum release (applications/external/text2sam). SAM is the 1982 "Software Automatic Mouth" synthesizer: English only, distinctly robotic, but intelligible and tiny. The Flipper port needs only a 4 KB stack and a few hundred bytes of tables. A demo video exists: https://www.youtube.com/watch?v=JG2Fqn8tKP8 (I could not listen to it).
- Its playback loop blocks while speaking (furi_delay_us busy-wait). For a screen reader it would run in its own worker thread, ideally converted to DMA playback borrowed from the WAV Player so it stops burning CPU.
- Bigger engines (eSpeak NG, Flite) need megabytes of data and far more RAM than the 192 KB available. They are realistic only on an external coprocessor (section 6, option C) or on a computer.

## 4. Where a screen reader hooks into the firmware (verified)

How a frame is drawn:

- The GUI service composes every frame in one function, gui_redraw, on its own thread, then commits the frame buffer. Applications never draw directly; they draw into a Canvas inside a draw callback.
- All text drawing ends in three functions in applications/services/gui/canvas.c: canvas_draw_str, canvas_draw_str_aligned and canvas_draw_glyph. Menus, dialogs, the on-screen keyboard, status text in apps, everything. Momentum already patches this file (its dark mode inverts colours in canvas_set_color), so modifying it is normal practice in this firmware.
- After each commit the GUI calls registered frame-buffer callbacks. The phone app's screen streaming uses this. It is the natural "frame finished, now speak the changes" point.

How selection is shown, which a screen reader can detect:

- Submenus, settings lists (variable item list) and the on-screen keyboard all draw a filled black box and then draw the selected label in white. Reading the current draw colour at text-draw time identifies the highlighted item.
- The main menu in Momentum has nine visual styles. In the "List" style the selected entry is the middle row and is drawn in the primary font; the other styles show the selected item's name as text as well. Setting the style to List makes announcements simplest.

Design of a first version (my recommendation, not yet built):

1. Add a small recorder to canvas.c: while a frame is being drawn, append each drawn string with its position, colour, and font to a buffer.
2. Add a new firmware service, in the spirit of the notification service, that receives the buffer after each frame, diffs it against the previous frame, and queues what to say: the highlighted item first, then new text.
3. Subscribe that service to the input service's event stream (record "input_events"), which every key press passes through. This gives hotkeys such as "hold Back then press Up" to re-read the whole screen, without changing any app.
4. A speech worker thread owns the speaker only while speaking, so notification beeps and other apps keep working.
5. A toggle and a rate or verbosity setting in Momentum Settings, Interface section, stored in the existing momentum_settings structure.

Caveats to plan for:

- Long labels are truncated with an ellipsis or scrolled as a marquee at draw time, so the capture sees partial text for long names. The fix is a second, more precise hook inside the list modules (submenu, variable item list, main menu, keyboard), which also gives "item 3 of 12" style position information.
- Icons, the status bar, and the home-screen animations carry no text. A few app screens are icon-only; those need individual attention later.
- This cannot be a normal installable app (FAP). Apps run one at a time in the foreground and cannot intercept the GUI service. It has to be a firmware modification, which means building Momentum from source. Momentum's stated policy is to include "all third-party features and apps as long as they fulfill a useful purpose and they work correctly", so a clean implementation could plausibly be contributed upstream.
- The firmware has a plugin loader that loads code from the SD card. If flash space in the firmware image turns out to be tight, the SAM engine can live on the SD card as a plugin while only the small hook stays in flash.
- Momentum's JavaScript API includes GUI modules but cannot run in the background or hook the GUI, so it is not a route for this.

## 5. A second path: operating the Flipper from a computer (verified)

The device exposes a text CLI over USB serial (230400 baud). On macOS: `screen /dev/tty.usbmodemflip_XXXX 230400`, or `python3 scripts/serial_cli.py` from the firmware repository. Relevant commands in Momentum:

- `loader list` and `loader open <name>`: list and start applications.
- `input keyboard`: drive the d-pad and buttons from the computer keyboard (arrows, Enter, Backspace).
- `input send <key> <type>`: send single button events.
- `storage` commands and the `scripts/storage.py` helper: list, read, send, receive files on the SD card.
- `log`: stream the firmware log to the terminal.
- Plus command sets for Sub-GHz, NFC, RFID, infrared, iButton, GPIO, Bluetooth, power, LED and vibration.

With the screen-text recorder from section 4 printing to the log or to a new CLI command, the current screen becomes readable in your terminal with your normal screen reader. This is also the fastest way to test the capture logic before any speech works. The limitation is obvious: it needs a computer, so it is a development and desk tool, not a way to use the device in the field.

## 6. Options compared

Option A: SAM voice through the internal piezo. Fully standalone, no extra hardware, no cost. Robotic voice, quiet, English only. Best first milestone.

Option B: Option A plus an external amplifier module on the GPIO header. Either a MAX98357A I2S amplifier with a small speaker, or a PAM8403 board with the RC filter, following the MP3 Player wiring. Much louder and clearer, still SAM's voice. Adds a small board on top of the device; needs basic wiring or a ready-made breakout. The Flipper's 5 V rail can power it.

Option C: An external speech coprocessor. An ESP32 board on the UART pins receives text from the Flipper and speaks it with a better engine (eSpeak NG or Flite ports exist for ESP32 class chips) through its own DAC, or streams to Bluetooth earbuds over A2DP as the bt_audio project does. Best voice and private listening, but more bulk, more battery drain, and two firmwares to maintain. The Flipper-side work is the same capture service as in the other options; only the output changes.

Option D: Computer-tethered CLI mirror. Smallest change, immediately usable with your existing screen reader, but not standalone.

Recommendation: build the capture and announcement service first, because every option needs it, and verify it through the CLI (D). Add the SAM worker (A). Decide between B and C after you have heard SAM on the real device, since that is a judgement only you can make.

Rough effort, assuming the device is available: capture service with CLI mirror, one to two days; SAM worker with announcements, hotkeys and settings toggle, three to five days; module-level hooks and per-app polish, ongoing.

## 7. Practical matters for a blind owner

- Installing Momentum: the recommended route is a web updater in Chrome (WebSerial) or the qFlipper desktop app. I could not assess how well either works with a screen reader. A fully terminal-based route exists: download the release package (for example flipper-z-f7-update-mntm-012.tgz from the mntm-012 release of 31 December 2025), unpack it, and install with `python3 scripts/selfupdate.py` from the firmware repository, or build from source and run `./fbt flash_usb`. The build tool (fbt) downloads its own ARM toolchain and works from the command line on macOS.
- File transfers: `scripts/storage.py` over USB, the CLI storage commands, or the microSD card in a computer.
- There is no emulator. Development and testing need the physical device.
- Momentum's "lock on boot" and PIN lock features should stay off until the lock screen is announced.
- Hardware note: header pins PB8 and PB9 are marked dangerous in the firmware; the audio options above only use the normal user pins.

## 8. Prior art search

- Flipper forum searches for "blind", "screen reader", "text to speech", "SAM speech": nothing about accessibility (the "blind" hits are all about window blinds).
- GitHub issue and repository searches for accessibility terms: nothing.
- Reddit could not be searched from this environment.
- Related but not accessibility-focused: Text to SAM (Round-Pi, fixes by Willy-JL, lineage via the ctoth/SAM cleanup), WAV Player (DrZlo13, LTVA1), Video Player (LTVA1), MP3 Player (coolshrimp), bt_audio (FatherDivine).

## 9. Not verified

- How intelligible and how loud SAM actually is from the piezo; no device here.
- Screen-reader accessibility of qFlipper, the Momentum web updater, and the Flipper mobile apps.
- Remaining flash headroom in the Momentum image (needs a build; the SD-card plugin route avoids the question).
- Whether the SAI peripheral can be used with the existing pin usage of Momentum; the MP3 Player deliberately bit-bangs I2S instead.

## 10. Sources

- Momentum firmware: https://github.com/Next-Flip/Momentum-Firmware and https://momentum-fw.dev
- Flipper tech specs: https://docs.flipper.net/zero/development/hardware/tech-specs
- Flipper GPIO documentation: https://docs.flipper.net/gpio-and-modules
- Text to SAM: https://lab.flipper.net/apps/text2sam and https://github.com/Round-Pi/flipperzero-text2sam
- SAM cleanup the port derives from: https://github.com/ctoth/SAM
- WAV Player: https://github.com/LTVA1/wav_player
- Video Player: https://github.com/LTVA1/flipper-zero-video-player
- MP3 Player with external amplifier wiring: https://github.com/coolshrimp/flipperzero-mp3-player
- Bluetooth audio via ESP32: https://github.com/FatherDivine/bt_audio
- STM32WB55 alternate-function table (MicroPython): https://github.com/micropython/micropython/blob/master/ports/stm32/boards/stm32wb55_af.csv
- Momentum releases: https://github.com/Next-Flip/Momentum-Firmware/releases
