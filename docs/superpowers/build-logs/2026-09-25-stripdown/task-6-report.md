# Task 6 report: clean release build, full flash, device pass, measurements

Status: DONE_WITH_CONCERNS. Every step of the brief is done. The concerns are about what the figures mean, not about failures. Nothing crashed, and no reboot happened that I did not ask for.

Commits, project repo, main, not pushed:
- f1903a5 "ram_probe: no Doom row, the games are gone" (tools/ram_probe.py only)
- 63de944 "Stripdown measurements: flash, static RAM, idle heap, RAM probe and device pass; tools/map_size.py" (tools/map_size.py and docs/measurements/2026-09-25-stripdown.txt)

No firmware commit: the firmware stays at cc7212c6c, and `git status` there shows only the untouched ` m applications/external`. The repo-root voice/ directory is untouched.

## What I did, step by step

### Step 1: the probe without the game
- Deleted the line `    ("Doom (game)", "/ext/apps/Games/doom.fap", [], 4),` from tools/ram_probe.py.
- The diff is that one line. The syntax check passed.
- Committed with `git add tools/ram_probe.py` and `git commit -m "ram_probe: no Doom row, the games are gone" -- tools/ram_probe.py`, as f1903a5.

### Step 2: clean build and manifest check (firmware repo)
- `rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps && ./fbt`: exit 0, 04:37:23 to 04:37:41.
  - The firmware objects were current from Task 5, so fbt only rebuilt the version stamp and relinked the image.
  - I logged the output to a file and then ran the brief's grep over it. That keeps the same output lines and also gives the exit code.
  - The filtered output: the two known manifest warnings (cli_bridge "Invalid appid '.cli_gui'", mtp "Invalid appid '.f0_mtp'"), "Excluded 45 external apps by configuration: 4inrow, … zombiez" and "API version 87.2 is up to date". No error line.
- `./fbt resources`: exit 0 at 04:39:24.
  - It printed the same two manifest warnings.
  - It printed 20 compiler warnings, all in the external apps' own sources: the asn1 code of seader, picopass and passy, flipboard, airmouse and mitsubishi_ac_remote. None is in a file of this round.
- The brief's manifest check, `grep -c -E 'apps/Games/|apps/Scripts/|js_app|cli_js|test_js|apps/Sub-GHz/subghz.fap' build/f7-firmware-C/resources/Manifest`: **0**.
- I added a check the brief does not ask for:
  - Directory entries without the trailing slash (`D:apps/Games`, `D:apps/Scripts`) and `apps_data/js_app`: 0.
  - The Manifest lists 11 top-level app folders and 20 files under apps/Sub-GHz.
  - .extapps holds no js_ file, no cli_js, no test_js and no subghz.fap.
- `tools/flash_headroom.sh`: **firmware.bin 862588 bytes, limit 880640, spare 18052 bytes**. The md5 of firmware.bin is a71e546a69dc990e4995858cd0893102.

### Step 3: flash
- Idle check, as in Task 4 Step 9, at 04:41:05 and 04:41:36:
  - "No application is running" both times.
  - Announcements 13 both times, utterances 18 both times, speech idle.
  - The device ran 4bda0a4a.
- `./fbt flash_usb_full`: 04:41:52 to 04:44:17, exit 0. The package was f7-update-mntm-screen-reader-cc7212c6.
  - Its last three lines: the upload progress line, ending "<100%, chunk 15 of 15 @ 117.84 kb/s"; "[INFO] Closing current app, if any"; `Touch("build/usbinstall.flag")`.
- After the flash build, firmware.bin and firmware.elf.map had the same md5 as after Step 2, and the manifest check again gave 0.
- **The port was gone at 04:44:15 and back at 04:50:24, 369 s (6 min 9 s).** I polled for it with a watcher script.
- `sr screen` 10 s after the port came back gave "records: 0, content layer: desktop". That is the post-update splash.
- `input send back short` closed it. `sr screen` then showed one record, the battery "100".
- `info device`: firmware.commit.hash cc7212c6, dirty true (the submodule), branch screen-reader, build date 25-09-2026, API 87.2.

### Step 4: the device pass
I sent every command through tools/flipper_cli.py's own open_cli and run functions, using a small scratch driver that adds waits and time stamps. The three unlock Backs were sent with the brief's exact command.

The verbatim command-and-reply log of every step is in the measurements file, under "Device pass". Here are the key replies.

1. Animations off, the first boot after the flash, 30 s after the port came back:
   - `sr status`: enabled yes; volume 80, verbosity 1, change delay 3000 ms; frames 3; announcements 1; speech idle; utterances 1, last 15,972 subsamples ("Home screen").
   - `sr voice status`: voice on, vocabulary yes, clips 2, fallback 0, missing 0, muted 0.
   - `free`: **Free heap size 116672**, Total 189560, Minimum 114096, Maximum heap block 116672.
   - `uptime`: 0h0m32s.
2. Home screen:
   - `sr chord up` replied "back + up: read the screen". Utterances went from 1 to 2, the last one 15,972 subsamples ("Home screen").
   - `input send ok short` opened the main menu. `sr screen` reads as "Settings. Sub-GHz. Apps, 1 of 11". The announcement was one clip, 521 ms, 7,837 subsamples, the same figures as in Task 4.
   - `input send back short`: announcements went from 2 to 3, the last utterance 15,972 ("Home screen"). One record, the battery. No application.
3. Lock:
   - `input send up short` opened the lock menu. `sr screen` showed FOCUS NOTE "Lock", which was said (435 ms).
   - `input send ok short` on the Lock tile did **not** lock. It opened the lock popup: "PIN Code Lock. PIN Lock + OFF. Keypad Lock, 1 of 3", with the focus on Keypad Lock.
   - After reading it, a second `input send ok short` on Keypad Lock locked (`desktop_lock(desktop, false)`, no PIN). The PIN items were never touched.
   - `sr status`: announcements 6, suppressed 1. The last utterance was 4,132 ms and 65,151 subsamples, 8 clips.
   - `sr screen`: "Locked, press Back 3 times quickly to unlock. 25-09-2026. 04:50".
   - `.venv/bin/python tools/flipper_cli.py --quiet "input send back short" "input send back short" "input send back short"`: no output, exit 0.
   - `sr status`: announcements 6 to 9, utterances 7 to 10, aborted 0 to 1, clips 18 to 22, the last 15,972 ("Home screen"). This is phase 3's pattern: the hint cut short, then "Unlocked", then "Home screen".
   - `sr screen`: the home screen, the battery only. No application.
4. The Animations row:
   - `loader open Momentum`: "MNTM-DEV CC7212C6. Protocols. Misc. Interface, 1 of 4".
   - OK: "Mainmenu. Lockscreen. Statusbar. Graphics, 1 of 6".
   - OK on Graphics: "Asset Pack Default. Anim Speed 100%. Cycle Anims Meta.txt. **Animations OFF, 1 of 5**".
   - `input send right short`: "**Animations ON, 1 of 5**", said in 1,334 ms.
   - Back gave Interface. Back gave the start list. Back, then `sr screen` 0.3 s later: "**Rebooting.... Applying changes...**".
   - The port was gone at 04:53:08 and back at 04:53:10.
   - `sr screen` after that boot: the battery only.
   - At 30 s, `free`: **116736**, minimum 114592, largest block 116736, uptime 0h0m32s.
   - `sr status`: announcements 1, suppressed 0 (no bubble drawn). The frame counter was 27 at 10 s and 62 at 30 s.
   - Two extra read-only samples at 3 min 37 s and 3 min 57 s: frames 433 to 473 (2.0 a second), free 116,872 and 116,768.
   - OFF again, the same path. The row read "Animations ON, 1 of 5". Right does nothing on the last value (the list does not wrap), so I used `input send left short`: "**Animations OFF, 1 of 5**".
   - Back three times, the same "Rebooting..." popup. The port was gone at 04:57:55 and back at 04:57:57.
   - `sr screen`: the battery only.
   - At 30 s, `free`: **116752**, minimum 114608, largest block 116752, uptime 0h0m32s.
   - The frame counter stayed at 2 at 10 s, 30 s and 50 s.
5. `.venv/bin/python tools/ram_probe.py`: 04:59:06 to 05:01:20, exit 0. The summary is under "Probe summary" below.
   - `loader info` afterwards: "No application is running". uPython had failed to preload, so no `power reboot` was needed.
   - `sr status`: announcements 54, utterances 54, aborted 31, dropped 0, underruns 0.
6. The card:
   - `storage list /ext/apps`: Bluetooth, GPIO, Infrared, Media, NFC, RFID, Sub-GHz, Tools, USB, assets, iButton. That is **11 folders**, with no Games and no Scripts.
   - `storage list /ext/apps/Sub-GHz`: 20 faps, no subghz.fap.
7. A long screen:
   - `loader open Momentum`.
   - `sr chord up`: one utterance of 9,780 ms, 154,866 subsamples, 19 clips. It cut the app's own opening announcement, so aborted went from 31 to 32. The screen text is 54 characters. The reader cuts text into parts of up to 159 characters (speech.h), so it was one part.
   - `input send back short`: the app left without a reboot. "Home screen" was said, announcements 55 to 56. No application.
8. Final:
   - `sr status`: enabled yes; volume 80; speech idle; utterances 57, aborted 32, dropped 0, underruns 0.
   - `sr voice status`: voice on, clips 190, fallback 0, missing 0, muted 0.
   - `free`: 116472, minimum 23160, largest block 57880.
   - `uptime`: 0h3m32s. `loader info`: no application. `sr screen`: the home screen.
   - `storage read /int/.momentum_settings.txt`, filtered: desktop_anims false, screen_reader true, sr_volume 80, sr_verbosity 1, sr_change_ms 3000.
   - A last check before this report gave the same state, with frames still at 345.

### Step 5: the map script and the measurements file
- I created tools/map_size.py and made it executable. Its content is byte-identical to the brief's code block (I checked with diff).
- `python3 tools/map_size.py Momentum-Firmware/build/f7-firmware-C/firmware.elf.map lib` printed:
  - `TOTAL flash 866398 static ram 5897`
  - the screen reader's line: `19798       8  applications/services/screen_reader`
  - the Sub-GHz app's line: `43142      25  applications/main/subghz`
- docs/measurements/2026-09-25-stripdown.txt is plain text in the brief's sections: Flash, Static RAM, Idle heap, RAM probe (the full output), and Device pass.
  - The device pass gives each step's summary followed by its verbatim replies.
  - `info device` is cut to its firmware lines, because the full reply carries the hardware UID and radio details. The file says so.

## Flash figures (in the file, each with its commit)
- Round start, 22ae265ef: 877,036 bytes, 3,604 spare.
- Task 2, 8fe7f533d: 835,748 bytes, 44,892 spare.
- Task 3, 59140fcd2: 877,776 bytes, 2,864 spare.
- Task 4, 4bda0a4ae: 862,432 bytes, 18,208 spare.
- Task 5, cc7212c6c: 862,588 bytes, 18,052 spare. 582cad9f3 before the latch: 862,612 bytes.
- **Final, cc7212c6c: 862,588 bytes, 18,052 spare.**
- Net: 14,448 bytes less than at the start of the round.

## Static RAM
- 5,897 bytes (941 data, 4,956 bss by input section), against 9,580 at 22ae265ef. That is 3,683 less; SAM's share was 3,704.
- The output sections with alignment fill are 988 + 5,020 = 6,008 bytes, the figure fbt's "Firmware size" prints.
- The screen reader: 19,798 flash (35,073 at 22ae265ef, so 15,275 less) and 8 static RAM.
- The script's flash total, 866,398, is **not** the image size.
  - The map lists the mergeable .rodata strings at their size before the linker merges duplicates: 191,331 counted, 186,280 linked.
  - It also leaves out alignment fill. The file explains this.

## Idle heap, 30 s after boot (uptime 32 s each time)
- Animations off (the first boot, no key in the settings file): 116,672.
- Animations on: 116,736.
- Animations off again: 116,752.
- The total heap was 189,560 each time.

## Probe summary
- No row reports a reboot.
- Sub-GHz Read: free before 116,840, lowest sampled **53,064**, low-water mark 52,992.
- Sub-GHz Frequency Analyzer: lowest sampled **51,136**, low-water mark 50,616.
- On 2026-09-23 Read went down to 2,080 and the analyzer crashed.
- NFC Read is the lowest row, at 23,232 (low-water mark 23,160).
- The other rows: RFID 79,256; Infrared Learn 42,280; Universal Remotes 31,152; iButton 86,464; GPIO 97,144; Bad KB 83,800; Momentum settings 79,624; Text to SAM 88,248; TOTP 63,984.
- uPython: "Preload failed … Not enough memory", as expected.
- Global low-water mark: 23,160.

## Files changed
- /Users/robin/Downloads/flipper-access/tools/ram_probe.py (one line deleted)
- /Users/robin/Downloads/flipper-access/tools/map_size.py (new)
- /Users/robin/Downloads/flipper-access/docs/measurements/2026-09-25-stripdown.txt (new)
- This report.

Scratch files are in the session scratchpad: the driver dev.py, the watcher waitport.py, the build and flash logs, the transcript, and the generator for the measurements file.

## Self-review
- Every figure has its commit or its condition:
  - Each flash figure has its commit.
  - The static RAM figure names the map and its md5.
  - Each heap reading is 30 s after the port came back, with the device's uptime.
  - The probe line has its times and exit code.
- The device pass has all eight steps, in the brief's order, with their replies. The flash and its idle check come first.
- The file reads linearly: one fact per line, the section names as plain lines, and no tables.
- Commits were made only with explicit paths. Nothing was pushed, and nothing was committed in the firmware repo or in applications/external.
- The device is left on the home screen with no app, reader on, voice on, speech idle and animations off. The settings file says false, and the running boot has no redraws.
- Checked against the source rather than assumed:
  - The lock popup (desktop_view_lock_menu.c): the first OK opens it; Keypad Lock locks without a PIN; PIN Code Lock with no PIN set would open PIN setup.
  - The settings list does not wrap values.
  - Parts are up to 159 characters.
  - The settings are loaded from the card before the desktop starts at boot, so the latch reads the saved value.
  - `loader open` records no dolphin deed; only the Apps browser does (loader_applications.c line 136).

## Concerns
1. **The idle heap with animations on did not measure an animation's cost.**
   - On: 116,736. Off: 116,672 and 116,752. They differ by under 100 bytes.
   - With animations on, the desktop redrew exactly 2 times a second, with no text and no bubble. The free heap equalled the largest block, so no animation frames were loaded from the card: the animation was one compiled into flash.
   - That fits the "new mail" animation (6 frames at 2 a second, no bubbles), which the manager shows while a dolphin level up is pending. L1_AnimationError, the only other flash animation allowed at idle, runs at 1 frame a second.
   - This is an inference; the console cannot show a pending level up. If one was pending, it matches Task 5's deferred minor: the first boot raised no deed or card event, so the guard had nothing to grant on.
   - So the spec's "animations off add 10 to 26 KB at idle" is not measured by this pass, and Task 7 should not quote it as measured. The measured difference is the redrawing: 2 frames a second with animations on, none with them off.
   - A real figure needs a boot on which a card animation plays. That could be after the level up is granted (with animations off, any deed does it, for example starting an app from the Apps browser), or through a key on the new mail animation with animations on. Neither is in this brief, so I did not do it.
2. **The brief's lock step is slightly off for this firmware.** OK on the Lock tile opens a three-item popup, and a second OK on "Keypad Lock" locks. I read the popup with `sr screen` first and never touched the PIN items.
3. **The brief expects "twelve folders" under /ext/apps. There are 11.** The build's Manifest lists the same 11, and Task 4's listing had 11, so it looks like a miscount in the brief. There is no Games and no Scripts folder.
4. **The heap is fragmented after the probe.** At the end, free is 116,472 but the largest block is 57,880. That is normal after running apps, and a reboot restores it. No reboot was asked for, so I left the device as it is. The controller may want to reboot it with `power reboot` before restarting the log capture.
5. Minor notes:
   - `uptime` is a console plugin loaded from the card. I ran it only after each `free`, so it cannot have affected a reading.
   - The resources build's 20 compiler warnings are the external apps' own.
   - NFC Read shows no gain against 2026-09-23 (23,232 now, 23,800 then). That probe predates the recorded voice, so only the Sub-GHz rows compare cleanly.

## Fix report 1 (task review, fix round 1 of 5)

Commit: c92e607 "Stripdown measurements: the long-screen ruling, the animations-on qualifier, section markers". It changes only docs/measurements/2026-09-25-stripdown.txt (18 insertions, 13 deletions). Not pushed. There was no device work and no firmware build.

I made the edits in the scratch generator for the file and then regenerated it. `git diff` against 63de944 shows that only the lines below changed; every verbatim console block is byte-identical.

### Changes, by the reviewer's line numbers (the committed 63de944)
- **Section headings, lines 8, 24, 34, 47 and 76:** now "Section: Flash", "Section: Static RAM", "Section: Idle heap", "Section: RAM probe" and "Section: Device pass", in the same order.
  - Each is exactly one hit in the file, and "Section:" occurs only on these five lines.
  - Step 5 still says "the RAM probe section above", deliberately without "Section:", so the hits stay unique.
- **Line 37:** the animations-on figure now ends "(the built-in new-mail animation was showing, not a card animation; see below)".
- **Line 40:** "for the whole boot" is replaced. With animations off again, the counter was 2 at each of the three samples, 10 s, 30 s and 50 s after the port came back.
- **Line 41:** the evidence now given is that the "on" reading, 116,736, lies between the two "off" readings, 116,672 and 116,752, where a card animation would hold 10 to 26 KB. The claim that free equals the largest block is gone.
- **Line 42:** "the only flash animation allowed at idle" is now "the only other animation in the firmware that can show at idle with a healthy battery and a card in".
- **Line 43:** the inference is replaced by the controller's ruling, marked "Ruling:":
  - a level up is pending on the owner's dolphin;
  - the built-in "new mail" animation showed while animations were on;
  - with animations off, Task 5 grants a pending level up only at the next dolphin deed or card event, not at boot;
  - the grant at boot when animations are off joins the round's final fix wave.
  - It ends "This ruling is the controller's, from the Task 6 review."
- **After line 43, a new line marked "Note, not part of the ruling":**
  - The probe's Frequency Analyzer row records a dolphin deed (subghz_scene_start.c line 104).
  - Every deed publishes the dolphin update (dolphin.c line 245), which makes the manager look at the dolphin's state. With animations off, that grants a pending level up.
  - So the level up was most likely granted during the probe, at about 04:59. The device was not checked for it.
  - See concern 1 below.
- **Line 229:** the unlock text no longer rests on phase 3. It is three lines now:
  - the device unlocked, the home screen shows, no application runs;
  - the counts from the sr status before the Backs to the one after: 3 announcements (6 to 9), 3 utterances (7 to 10), 1 aborted (0 to 1), 4 clips (18 to 22), the last utterance 15,972 subsamples, "Home screen";
  - "Unlocked" is inferred from these counts, since the console does not log the words: of the three announcements, the last is "Home screen" and one was cut by a Back, which leaves one for the unlock.
- **Line 300:** "nothing was said" is corrected. Announcements 1 and utterances 1 were the boot's "Home screen" (15,972 subsamples), with suppressed 0; no bubble was drawn, and nothing else was said or held back.
- **Lines 701 to 704 (step 7):** the summary is unchanged and keeps the 54-character reading.
  - After the recorded reply, before "8. Final", a new line: "Ruling: the check is void on this device. No screen of this firmware exceeds one 159-character part; phase 3 measured the longest, the About pages, at 119 characters. The parts path (speech_say_parts and speech_queue_push_parts) was not touched this round, and its host tests pass. The chunking that left with SAM was the synthesizer's own input splitting, not the queue's parts. This ruling is the controller's, from the Task 6 review. The 54-character reading above stays as the evidence."
- **Line 788:** the command line now carries a time stamp: "[about 05:02:40] == storage read /int/.momentum_settings.txt (sent with tools/flipper_cli.py directly, within 2 s after the command above, so its exact second was not logged; only the animation and reader keys kept)".
  - "about" is deliberate. That command ran outside the time-stamping driver, right after the driver's last command at 05:02:39, so the exact second was never recorded.
  - Re-running it would have been device work, which this round excludes.
- **Line 300, a consistency fix from the re-read:** "Two more samples near 3 min 40 s: 433 to 473 frames in 20 s" is now "Two more samples, at uptime 3 min 37 s and 3 min 57 s: frames 433 and 473". It now quotes the same uptimes as the Idle heap section.

### The ruling's facts, checked read-only before recording
- `git diff --stat 22ae265ef cc7212c6c -- speech_queue.c speech_queue.h` is empty, and speech.c's diff over the round has no say_parts, push_parts or SpeechPushParts line.
- 4bda0a4ae removed `SPEECH_CHUNK_MAX 80` and `speech_text_next_chunk` from speech_text.h: SAM's input chunks.
- tools/run_host_tests.sh, re-run: exit 0. Speech queue 156 checks, 0 failures; its test file calls push_parts 7 times.
  - It writes only to the temp directory, and the tree stayed clean.
- Phase 3's longest screen, 119 characters (About page 3), is in docs/measurements/2026-09-24-phase-3.txt.

### Consistency re-read
- I read the whole file once.
- A script took every comma-grouped figure from the summary lines and checked it against the verbatim parts (transcript and probe output).
  - The device figures all match.
  - Each figure not in the verbatim parts is accounted for: the flash figures of earlier tasks and my headroom run; the spec's 22ae265ef figures; the 2026-09-23 probe figures; the map script and section sizes; Task 4's two heap figures; and computed differences (14,448, 15,275, 3,683, 41,288, 42,028, 15,344), each re-computed.
  - "14,664" is the milliseconds of a log time stamp, not a figure.

### Concerns after the fix
1. **The ruling says the level up "is pending", but the probe most likely granted it at about 04:59.** The Frequency Analyzer row records a deed, and with animations off Task 5 grants a pending level up at the next deed.
   - This matters for the final fix wave: if it tests the grant at boot on the device, there may no longer be a pending level up to test with.
   - Checking needs the device (for example the Passport screen), which this round excludes. The file states it as a note beside the ruling.
2. Line 788's time stamp is "about 05:02:40" for the reason above; nothing more exact exists.
