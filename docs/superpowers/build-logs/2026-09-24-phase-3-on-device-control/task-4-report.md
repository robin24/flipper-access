# Task 4 report (saved by the controller from the implementer's reply)

Status: DONE_WITH_CONCERNS.

## Commits
Firmware (base 0bb191c32): 61836bdb7 "gui: tap notes for icon-only screens; button panel names; desktop lock hints; infrared remote names; API 87.2" (24 files incl. api_symbols.csv); 6c8da316b "screen reader: notes are read first" (found on the device). Project (base 88c5ea6): c833c19 "host tests: note rows" (test_screen_model.c, runner: the model test now under sanitizers); 3794700 "host tests: notes read first".

## Host runner
Model 159 checks (was 104), 0 failures; all other suites unchanged. Seven mutants caught (notes joining rows, note as title, desktop Home screen interrupting, no Home screen when the desktop text goes, battery digits apart, status rows counted as text, notes not first).

## Build, lint, headroom, API
./fbt "API version 87.2 is up to date"; lint exit 0 after one clang-format fix; firmware.bin 875,648 bytes, 4,992 spare (task cost 1,200). API table: Version 87.2; added button_panel_item_set_name(ButtonPanel*, uint32_t, const char*) and canvas_tap_hint_note(Canvas*, const char*, _Bool). infrared imports button_panel_item_set_name; desktop_settings imports canvas_tap_hint_note (it compiles the PIN entry view).

## Flashes
1. flash_usb_full 15:56:50 to 16:00:26 (package 61836bdb), port back by 16:07:12, splash then home, info device api.minor 2. 2. flash_usb 16:14:05 to 16:14:40 for the reading-order fix (6c8da316), plain home screen.

## Device verification
1. Infrared, Universal Remotes, TVs: after the tv.ir load (about 10 s) sr screen shows `FOCUS NOTE "Power"` and the title "TVs", "reads as: TVs. Power" (announcements 4 to 5). Moves (the panel is vertical, keys rotated): right → "Channel up"; down at the edge → nothing; left → "Power"; up → "Mute"; right → "Volume up"; each announced exactly once, sr screen shows the matching FOCUS NOTE. Three Backs home ("TVs, 1 of 10", "Universal Remotes, 1 of 5", home). A vanishing bubble counted as suppressed, no announcement.
2. Lock menu: no keybind file on /int, defaults apply (Up opens the Lock Menu). Up → `FOCUS NOTE "Lock"` (435 ms); right → "Momentum"; right → "Brightness 100"; right → "Volume 95"; right → "Settings"; up → "Left handed off"; right → "Dark mode on"; right → "Bluetooth on" (reading only). Back → "Home screen" (15,972 subsamples, same as the boot Home screen): the return from the lock menu is now spoken.
3. Lock and unlock: Up, OK on Lock → popup focus "Keypad Lock, 1 of 3" (PIN Code Lock, PIN Lock + OFF); OK → locked: `NOTE "Locked, press Back three times to unlock"`, big "16:09", "24-09-2026"; three Backs: announcements 27 to 31, aborted +1 ("Press 3x to unlock!" cut by the next Back), a 688 ms one-clip utterance = "Unlocked". sr watch on the final image: focus: Lock; focus: Keypad Lock; change: Locked, press Back three times to unlock. 24-09-2026. 16:14; change: (a bubble under the cover); change: 16:15 (suppressed); change: Press 3x. to unlock!; lock: Unlocked; home: Home screen.
4. NFC-V: sr say of a long sentence then loader open NFC /ext/nfc/sr_nfcv_test.nfc: the sentence was cut (aborted +1), "Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?" played in full (11,076 ms, utterances +1, dropped +0), then the listener took the speaker; sr say during the emulation dropped 1; Back left. 10 underruns in the first second (the NFC app loading from the card while clips read).
5. PIN: not exercised (code read and the host note-row test only).
Extra: power-off dialog then Back → "Home screen" (15,972); sr chord down → "battery one hundred percent" (4 clips, 32,784 subsamples). Stacks min free: DesktopSrv 1,084 of 2,044, GuiSrv 1,108 of 2,044, ScreenReaderSrv 2,120, SpeechWorker 2,468, InputSrv 588, TimersSrv 796; heap free 108,216, minimum 18,088 during the NFC emulation.

## Final state
Home screen, no application, reader on, voice on, speech idle, rate 72 volume 70; the log capture restarted at 16:19:21 (pid 86054).

## Deviations
1. Notes count as screen content (a note-only screen is not "Home screen"); never the title, never joined. 2. Notes are read first (the lock screen's date sat above the top edge mid-animation). 3. The desktop "Home screen" does not interrupt and follows the bubble rule (silent without a key press in 2 s; at most once). 4. "Unlocked" on every locked=false message, new announcement kind "lock:". 5. Lock menu: switches say on/off, the lock popup gets a focus hint, stealth not spoken, slider text formatted in the draw callback. 6. "1 digit entered" singular. 7. The lock screen note is not drawn while the cover opens after an unlock. 8. Infrared names beyond the table: STOP "Stop", EXIT "Exit", Fast_ba/Fast_fo "Fast backward/forward", Power_on/off, colours as they are; 56 names over 9 scenes; Blu-ray keeps CRLF. 9. Model test under sanitizers; sr screen marks NOTE. 10. Vertical TV panel: Right reached "Channel up", Up "Mute".

## Concerns
1. Four hint words not in the vocabulary yet: digit, digits, dry, backward (spelled until the routine voice_build run). 2. Auto-lock is silent (the lock note arrives without a key press and the bubble rule suppresses it); the first key press then gives "Press 3x. to unlock!" ("Press. to unlock!" for a PIN lock, the arrow is an icon). 3. Dolphin bubbles keep being drawn under the opaque lock screen and are spoken within 2 s of locking; one line joined the date row. 4. The post-update splash is dismissed silently. 5. "Unlocked" and "Home screen" could swap order if the unlock takes longer than the settle. 6. The PIN entry reads its note first ("0 digits entered. Enter PIN:"). 7. 10 underruns while the NFC app loaded.

## Fix round 1 (saved by the controller from the implementer's reply)
Commit: firmware 6c7469a79 "screen reader: locks are announced; the lock screen hint names its key; muted volume tile" (6 files). Runner green (model 159); ./fbt 87.2 up to date; lint 0; firmware.bin 875,928 bytes, 4,712 spare.
1. Lock announcement from the desktop status message: "Locked, press Back three times to unlock" or "Locked with PIN, press Up to enter it" (the RTC lock flag desktop.c sets before publishing); interrupting, never suppressed, "lock:" in sr watch; the lock screen's note stays for Back + Up. 2. While the hint shows, a note names the key: "Press Back three times to unlock" / "Press Up to enter the PIN". 3. Stealth: "Volume muted". 4. canvas.h comment made exact.
Addition found on the device: a lock-menu frame processed after the lock announcement cut it off ("focus: Lock", aborted +1); now for 2 s after a lock announcement, or until a key press, the desktop says nothing more (also silences the lock screen's arrival repeating the sentence and the bubble behind the cover).
Device (6c7469a7): lock from the lock menu → "lock: Locked, press Back three times to unlock" in full (3,639 ms, aborted 0; the lock screen change and the bubble suppressed); one Back after 5 s idle → "change: Press Back three times to unlock. Press 3x. to unlock!"; three quick Backs (the hint takes 6 s and the lock screen resets its count after 600 ms) → "lock: Unlocked", "home: Home screen". Auto-lock: Desktop settings Auto Lock Time set to 10 s (Auto Lock Pin off, no PIN), no key pressed → the lock announced in full at 16:50:14–18; unlocked, delay restored to OFF, no further lock. Stealth: lock menu Volume tile reads "Volume muted". Stacks min free: DesktopSrv 1,084, GuiSrv 1,252, ScreenReaderSrv 2,052, SpeechWorker 2,468, InputSrv 596, TimersSrv 796.
Final: home screen, no app, reader on, voice on, speech idle, rate 72 volume 70, Auto Lock OFF, log capture restarted 16:52:24 (pid 88568).
Deviation: the hint note is spoken even when the visual lock-screen prompt setting is off. Concerns: "muted" not in the vocabulary yet; the PIN variants checked by code reading only.
