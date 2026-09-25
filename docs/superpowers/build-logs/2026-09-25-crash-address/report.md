# Report: the crash's return address in the popup; "XP" spoken as experience (2026-09-25)

Status: DONE_WITH_CONCERNS. Firmware commit a2dfdd286 (branch screen-reader), flashed, the device reports a2dfdd28. Project commit 51a9c18 (branch main). Nothing pushed. The submodule applications/external was not touched or committed.

## What changed, per file

Firmware (commit a2dfdd286):

- furi/core/check.c: in the release branch of `__furi_crash_implementation`, right after `furi_hal_rtc_set_fault_data(ptr);`, the line `furi_hal_rtc_set_register(FuriHalRtcRegisterFaultLr, __furi_check_registers[12]);` with a comment: the lr stored on entry (`GET_MESSAGE_AND_STORE_REGISTERS`, `str lr, [r12, #48]`, index 12) is the return address into the function whose check failed; the popup and `sr status` show it; addr2line on that build's firmware.elf, given the address minus 2, names the line (see concern 1); a RAM address is inside an app from the card; the backup register write is the same call furi_hal_rtc_set_fault_data makes, safe with interrupts disabled.
- targets/f7/furi_hal/furi_hal_rtc.h: `FuriHalRtcRegisterFaultLr, /**< Return address of the last failed check, 0 when none */` right before `FuriHalRtcRegisterMAX` (after PinValue; the blank line before MAX kept).
- applications/services/desktop/scenes/desktop_scene_fault.c: `static char desktop_fault_text[64]`; the popup text is the message, then "\nat %08lX" of the register. The message is printed with a precision of 51 characters (64 minus the 12-character address line minus the terminator) so the address line can never be cut; the longest crash message in flash is 45 characters, so nothing is cut today. With the register at 0 the popup shows the message alone (the same rule as the console's "none"; the brief did not say what to show then). On exit the scene clears the fault data as before and leaves the address register, with a comment saying so.
- applications/services/screen_reader/screen_reader_cli.c: `#include <furi_hal_rtc.h>`; after the "enabled" line, `last crash: at %08lX` or `last crash: none` for 0.
- applications/settings/dolphin_passport/passport.c: `xp_str` 16 characters; `"XP %lu/%lu"`; "Max Level!" unchanged.
- applications/services/screen_reader/speech_text.c: `{"XP", "experience"},` after `{"MNTM", "momentum"},` in the rule 3 table.

Project (commit 51a9c18):

- tests/host/test_speech_text.c: in test_rule3_terms, a comment and `expect("XP 7/100", "experience seven of one hundred");` and `expect("Dolphin XP", "Dolphin experience");`.
- README.md: in "Using it on the device", after the Passport sentence: the points line is labelled XP, said "experience", "experience seven of one hundred" with 7 of 100 points. In "Useful commands", a closing paragraph starting "When the device crashes": the popup's "at" line, how the reader speaks the address (character by character, except that one to three digits after a letter are a number unless they start with 0), `sr status`'s "last crash", Back keeps it, decoding a flash address from the project folder with `Momentum-Firmware/toolchain/current/bin/arm-none-eabi-addr2line -e Momentum-Firmware/build/f7-firmware-C/firmware.elf -f -C -a 0x0803ABCB` for "at 0803ABCD" (the address minus 2; `toolchain/current` is a real symlink to `toolchain/arm64-darwin`), that the line can be another check of the same function (concern 2), the elf of the commit named on `info device`'s `firmware.commit.hash` line, a worktree rebuild, a 2000 address being inside a card app that the firmware's elf cannot name, and fault messages such as HardFault pointing into the handler. I ran the README's command exactly as written from the project folder on a real address of this build (0x08001AC9): exit 0, it printed ble_svc_serial_notify_buffer_is_empty and serial_service.c:210.
- docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md: section 18 ends with "The crash address (2026-09-25)": the register and its index, the RTC header, the API, the popup buffer and line, the console line, the decoding with the minus 2 and the shared-call caveat with the counts, the XP label and rule 3 entry with the width figures, the flash figure, and the R0skie results. The phase 2 rule list above was left as history, as the section's preface says.

## RTC init and register layout

`furi_hal_rtc_init_early` reads register 0 as a header of a 16-bit magic (0x10F1) and an 8-bit version (0); a mismatch calls `furi_hal_rtc_reset_registers`, which writes 0 to all RTC_BKP_NUMBER (20) registers and then the header. There is no count or checksum of the registers, so nothing had to be kept consistent. The enum values as compiled, read from the new elf's DWARF: Header 0, System 1, Version 2, LfsFingerprint 3, FaultData 4, PinFails 5, UpdateFolderFSIndex 6, PinValue 7, FaultLr 8, MAX 9. Every existing index is unchanged; nothing in the firmware uses FuriHalRtcRegisterMAX.

## Tests

Baseline before any edit: speech text 964 checks, 0 failures (all suites green).

RED (the two checks added, no table entry), `tools/run_host_tests.sh` exit status 1:

    174 checks, 0 failures
    FAIL expand("XP 7/100")
      got  "X P seven of one hundred"
      want "experience seven of one hundred"
    FAIL expand("Dolphin XP")
      got  "Dolphin X P"
      want "Dolphin experience"
    966 checks, 2 failures
    speech text checks failed

GREEN (the table entry added), exit status 0, and the same again at the end before the project commit:

    174 checks, 0 failures
    speech text: 966 checks, 0 failures
    speech queue: 156 checks, 0 failures
    speech PCM: 597 checks, 0 failures
    speech voice: 4433 checks, 0 failures
    chords: 73 checks, 0 failures
    throttle: 119 checks, 0 failures
    fbt exclusions: 0 failures
    subghz sources: 50 on disk, 50 quoted, 0 unquoted, 0 missing

## Build, lint, headroom, API

- `./fbt` 15:54:14 to 15:54:53 (incremental), exit status 0. The only warnings are the two known manifest ones (cli_bridge: "Invalid appid '.cli_gui'", mtp: "Invalid appid '.f0_mtp'"); "Excluded 45 external apps by configuration: 4inrow, ..., zombiez"; no compiler warnings; check.c, furi_hal_rtc.c, desktop_scene_fault.c, screen_reader_cli.c and speech_text.c were compiled. Firmware size: .text 675724, .rodata 186416, .data 988, .bss 5084, .free_flash 185108.
- The API check's exact line: `API version 87.2 is up to date` (the same line in the fap builds and in the flash build).
- `./fbt lint` exit status 0.
- `tools/flash_headroom.sh`: `firmware.bin 863468 bytes, limit 880640, spare 17172 bytes`, 184 bytes above 863,284. The image `./fbt flash_usb` rebuilt after the commit has the same size (re-run: the same line).
- Passport width, measured with the firmware's own u8g2 code (`u8g2_GetStrWidth`, the function canvas_string_width calls) and the points line's real font, u8g2_font_5x7_tr (FontBatteryPercent, not the secondary font): "XP 7/100" 39 px, "XP 9999/9999" 59 px (x 59 to 117; Momentum's last level threshold is 9999, so this is the longest possible line), "Max Level!" 48 px, the brief's "XP 62500/62500" 69 px (x 59 to 127, the last column). The label always fits; no condition was needed.
- Disassembly of the new handler: the prologue is still `push {r7, lr}; sub sp, #32; cpsid i; ...; str.w lr, [ip, #48]`, so lr is stored before anything changes it; after `bl furi_hal_rtc_set_fault_data` come `ldr r1, [r6, #48]; movs r0, #8; bl furi_hal_rtc_set_register`, r6 being the pointer to `__furi_check_registers` that the "lr :" print also uses.

## Faps, flash, copies

- `./fbt fap_passport` exit 0: passport.fap 4,156 bytes, md5 4a252cd9e1aeeef0c823390ce20c9bd4 (contains "XP %lu/%lu"). `./fbt fap_crash_test` exit 0: crash_test.fap 3,144 bytes, md5 b108984e590b8d3287c8d20fa40eb0ed.
- The firmware was committed (a2dfdd286) before the flash.
- Capture stopped at 15:57:10: `pkill -f flipper_log.py` exit 0; `pgrep -f flipper_log.py` exit 1 (none). The device crashed within seconds (see "The crash I did not trigger"); I closed its popup with `input send back short` at 15:58:10 so the old fault message would not carry into the new image. Before the flash: `firmware.commit.hash : c502de5a`, `firmware.commit.dirty : true`, no application running.
- `./fbt flash_usb` 15:58:21 to 15:58:59, exit status 0: package `f7-update-mntm-screen-reader-a2dfdd28` (firmware.dfu md5 7872b6cae08987c4e7fb6ec7d250a835), "Using flip_R0skie on /dev/cu.usbmodemflip_R0skie1", firmware.dfu 106 chunks, update.fuf, updater.bin 15 chunks sent, "Closing current app, if any". Port gone 15:59:09, back 15:59:27; after 10 s, `sr screen` at 15:59:44: records 1, content layer desktop, only the battery "100": no popup, no post-update screen.
- Copies with `.venv/bin/python Momentum-Firmware/scripts/storage.py -p /dev/cu.usbmodemflip_R0skie1`: `send .../passport.fap /ext/apps/assets/passport.fap` exit 0 (16:00:13); `mkdir /ext/apps/Debug` exit 0; `send .../crash_test.fap /ext/apps/Debug/crash_test.fap` exit 0 (16:00:15). `storage md5` on the device: 4a252cd9e1aeeef0c823390ce20c9bd4 and b108984e590b8d3287c8d20fa40eb0ed, matching; `storage list /ext/apps` then showed Debug among the folders.

## Device checks (all with `.venv/bin/python tools/flipper_cli.py`)

Check 1, 15:59:52.
- `info device`: hardware.name R0skie; `firmware.commit.hash : a2dfdd28`; `firmware.commit.dirty : true`; firmware.branch.name screen-reader; firmware.version mntm-dev; firmware.build.date 25-09-2026; firmware.api.major 87, minor 2.
- `sr status`: "enabled: yes", "last crash: none", "volume: 80, verbosity: 1, change delay: 3000 ms", "frames: 2, dropped: 0, announcements: 1, suppressed: 0", "speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0", "last utterance: 1090 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2516", "voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0, muted 0, open max 27 ms, last 27 ms", "free heap: 116544".
- `uptime`: 0h0m27s. `loader info`: No application is running.

Check 2, the Passport.
- 16:00:27 baseline `sr status`: announcements 1, utterances 1, clips 2, fallback 0, missing 0.
- 16:00:33 `input send right short`, then `sr screen`: records 4, content layer fullscreen; "R0skie" (x 59, y 10, secondary), "Mood: Happy" (y 22), "Level: 2" (y 34), "XP 7/100" (x 59, y 42, battery font); "reads as: R0skie. Mood: Happy. Level: 2. XP 7/100". `loader info`: Application "Passport" is running.
- Idle at 16:00:46, `sr status`: announcements 2, utterances 2, aborted 0; "last utterance: 11693 ms played, 184999 subsamples, 11562 ms nominal"; "clips 26, fallback 2, missing 2", open max 46 ms; free heap 113256. So "experience" was not a clip: it was spelled, and missing rose by 2. `storage read /ext/sr/missing.txt`: "Size: 32", r0skie, r0skie, r0skie, experience.
- 16:01:07 `input send back short`: home screen, no application.
- The brief's remedy, 16:01:16 to 16:01:23, `.venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync`, exit status 0: 6251 distinct strings, 71 bubble texts, 10519 words; card apps 161 faps, 161 matched, 7633 words added; "skipped 3 words that cannot be clips", "pulled 1 missing words from the device"; "10524 words, 4 to make"; "made 4 clips, 0 failed" (experience, plus crashtest, shouldve and wstringop from the crash test app then on the card); "sync: 4 sent, 10779 skipped, 0 missing, 0 failed"; the voice was silenced and restored around each transfer.
- Check again: `sr voice status` before: clips 28, fallback 2, missing 2 (the Back's "Home screen" added 2). 16:01:38 `input send right short`; `sr screen` the same four records, "XP 7/100". Idle at 16:01:49: announcements 4, utterances 4, aborted 0; "last utterance: 8171 ms played, 129615 subsamples, 8100 ms nominal"; "clips 43, fallback 3, missing 2": clips +15, fallback +1, missing +0. The words of "R0skie. Mood, Happy. Level, two. experience seven of one hundred": R0skie spelled as six letter clips (the one fallback) plus nine word clips, experience among them, is exactly 15.
- 16:02:01 `input send back short`: home screen, no application; clips 45, fallback 3, missing 2.
- 16:02:05 `sr say Dolphin XP`: "queued 10 characters; sr status shows the timing when it is done"; idle at 16:02:07: utterances 6, "last utterance: 1503 ms played, 23338 subsamples, 1458 ms nominal", clips 47 (+2), fallback 3 (+0), missing 2 (+0): two clips.

Check 3, the crash trial.
- 16:02:17 `loader open /ext/apps/Debug/crash_test.fap`; `sr screen`: records 4, fullscreen: `inverted FOCUS 1/8 "Check"` (x 6, y 12), "Check with message" (y 28), "Assert" (y 44), "Assert with message" (y 60); "reads as: Check with message. Assert. Assert with message. Check, 1 of 8". `loader info`: Application "Crash Test" is running.
- 16:02:26 `input send ok short` on Check: the console tool ended with "serial.serialutil.SerialException: read failed: [Errno 6] Device not configured"; port gone 16:02:27, back 16:02:29.
- 16:02:44, after 10 s, `sr screen`, the popup's exact records:

      records: 5, content layer: desktop
      desktop      x= 27 y= 26 primary    "Flipper crashed"
      desktop      x= 19 y= 37 primary    " and was rebooted"
      desktop      x= 30 y= 48 secondary  "furi_check failed"
      desktop      x= 37 y= 59 secondary  "at 200137DF"
      status-right x=103 y=  9 battery    inverted "100"
      reads as: Flipper crashed. and was rebooted. furi_check failed. at 200137DF

- `sr status` at once: "enabled: yes", "last crash: at 200137DF" (the same digits), announcements 1, utterances 1, aborted 0, "last utterance: 8782 ms played, 140238 subsamples, 8764 ms nominal", "clips 17, fallback 0, missing 0", free heap 116608; `uptime` 0h0m17s. The pronunciation layer on the host gives "Flipper crashed. and was rebooted. furi check failed. at two zero zero one three seven D F": nine words and eight characters, 17 clips, matching.
- 16:02:56 `input send back short`: home screen (records 1, battery only); `sr status`: "last crash: at 200137DF" still; announcements 2, utterances 2, last utterance 1097 ms ("Home screen"), clips 19; no application.
- The address checks out: in crash_test_d.elf the menu callback's single crash call is `blx r3` at .text offset 0x20, so the return address is offset 0x23 and the app's code was loaded at 0x200137DF - 0x23 = 0x200137BC, 4-byte aligned as the section requires. (The compiler merged all eight menu cases into that one call.)
- 16:05:32 `storage remove /ext/apps/Debug/crash_test.fap` (no output), `storage remove /ext/apps/Debug` (no output), `storage list /ext/apps`: Bluetooth, GPIO, Infrared, Media, NFC, RFID, Sub-GHz, Tools, USB, assets, iButton. No Debug folder.

Check 4, final, 16:05:46.
- `sr status`: "enabled: yes", "last crash: at 200137DF", "volume: 80, verbosity: 1, change delay: 3000 ms", "frames: 3, dropped: 0, announcements: 2, suppressed: 0", "speech: idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0", "last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2516", "voice: on, ..., clips 19, fallback 0, missing 0, muted 0, open max 27 ms, last 27 ms", "free heap: 116584".
- `loader info`: No application is running. `sr screen`: records 1, content layer desktop, battery "100" only (the home screen). `uptime`: 0h3m20s. `/ext/sr/missing.txt` does not exist.
- The capture was restarted from the project root with the brief's nohup command at 16:05:58 (PID 78905): "log debug", "Current log level: debug". At 16:09:28 it was still logging, uptime tick 421,460 ms (the boot after the deliberate crash). The device is left on the home screen, reader on, voice on, speech idle.

## The crash I did not trigger

At 15:57:10 I stopped the capture (`pkill -f flipper_log.py`; its signal handler sends Ctrl-C to end the console's `log` command, then closes the port; the log ends "== log stopped 15:57:10"). The port was gone at once, back by 15:57:21, and `uptime` read 0h0m17s at 15:57:31, so the device rebooted at about 15:57:14, about four seconds after the stop. It ran c502de5a (up about 64 minutes, the log's last line 15:57:00, nothing unusual). `sr screen` at 15:57:31: "Flipper crashed", " and was rebooted", "furi_check failed" ("reads as: Flipper crashed. and was rebooted. furi_check failed"), no address since that image did not keep one. Closed with Back at 15:58:10. Of the earlier stops in today's log, the one at 13:45:28 was not followed by a crash (the uptime ran on); the others were followed by flashes and say nothing. One data point, but it suggests ending `log` with Ctrl-C and closing the port may trigger a failed check; with a2dfdd28 flashed, the next one will name its address.

## Commits

- Firmware a2dfdd286 "The crash address kept across the reboot and shown in the crash popup; the Passport's points labelled XP, said as experience": furi/core/check.c, targets/f7/furi_hal/furi_hal_rtc.h, applications/services/desktop/scenes/desktop_scene_fault.c, applications/services/screen_reader/screen_reader_cli.c, applications/settings/dolphin_passport/passport.c, applications/services/screen_reader/speech_text.c (explicit git add, then git commit -- the same paths; 6 files, 48 insertions, 4 deletions).
- Project 51a9c18 "The crash address and the XP label: the rule 3 test, README and spec": tests/host/test_speech_text.c, README.md, the design spec (the same way; I amended my own unpushed commit once, from 7e509ce, to add the line "Firmware: Momentum-Firmware a2dfdd286." as the earlier project commits have). Not pushed.

## Self-review

- The diff: read in full (`git show a2dfdd286`, `git diff` before the project commit); it does what the brief says, plus the message precision and the address-less case in the popup.
- The popup buffer outlives the popup: `desktop_fault_text` is a file-scope static, so it lives as long as the firmware runs; it is written only in on_enter; on exit `popup_reset` drops the popup's pointer to it before anything else can use the shared popup.
- The RTC enum keeps every existing index: see "RTC init and register layout" (DWARF values 0 to 7 unchanged).
- Nothing else prints or clears the new register: only check.c writes it; only the fault scene and `sr status` read it (grep of the whole tree outside build/). The fault scene clears only the fault data. The register is cleared only with all the others by `furi_hal_rtc_reset_registers`: at boot when the RTC header is invalid (backup domain lost), the storage settings' factory reset and wipe device, the console's `storage factory_reset`, the RPC reset, recovery mode, and ten failed PINs with Momentum's bad-PIN format option. No app in applications/external touches backup registers; `furi_hal_rtc_get_register`, `set_register` and `reset_registers` are public in the API, so a third-party fap could.
- Only release builds keep the address: with DEBUG=1 or a debugger attached the handler halts and never writes it (as for the fault message).
- Popup layout: the two text lines sit at y 48 and 59 of the 64-pixel screen, below the header.
- A pre-existing edge, unchanged: a fault message pointer left by an older image across an update points into the new image. With an address kept the popup now reads at most 51 characters of it; without one (a crash on an image older than this change) the `%s` copy reads to the first zero byte, as the old code's drawing did.

## Concerns

1. The brief's decoding example used the address as shown. The stored value is the return address with the Thumb bit set, the instruction after the call; since the call never returns, that is often a later line or another function. On the build before this change, of 1,848 calls to the crash routine the raw address named the call's own line at only 55 and another function at 154; the address minus 2 named the check's line at all twelve sampled. The README, the spec and the check.c comment say to subtract 2.
2. Even with the minus 2, the line is exact only when the failed check has its own crash call. The compiler shares one call among checks of a function: a rough count of branches into each call found about 700 of the 1,848 entered from more than one source line (for example ble_svc_serial_notify_buffer_is_empty: four checks, lines 196, 197, 199 and 210, share one call, and addr2line names 210). So a crash names its function (or the function it is inlined into) for certain, and the line is one of that function's checks. The README and the spec say so; the check.c comment, committed and flashed before I found this, does not, and a comment-only follow-up could add it. Making every check's call distinct (for example a line number in the flag word) would stop the merging but costs flash; not done, a decision for Robin.
3. The crash above, about four seconds after the capture was stopped, on c502de5a.
4. "experience" was not in the vocabulary, although the brief expected it; the brief's generator command added it. The same run also made three clips from the crash test app (crashtest, shouldve, wstringop); they stay in voice/ and on the card after the app was removed. Harmless, a few kilobytes.
5. `sr status` and the next crash popup: the device now holds "last crash: at 200137DF" from the deliberate test, by design, until the next crash. Robin should know that this address is the test's.
6. `info device` says dirty: true on every build here, because the applications/external submodule has local changes; the build date is then the build day. The image embeds no absolute paths (strings of firmware.bin: none with /Users/) and the date has a fixed length, so a rebuild of the same commit elsewhere should lay out the code identically, as the README says; I did not prove it by rebuilding in a worktree.
7. The README's "Device state" still names 08e80106f and its size; the device now runs a2dfdd28 (it already ran c502de5a before this task). Not in the brief, so not changed.
8. For a fault such as HardFault, BusFault or MemManage the address points into the fault handler in furi_hal_interrupt.c, not to the faulting code; the message names the fault. Documented in the README and the spec.

# Fix round 1 (2026-09-25)

Status: DONE_WITH_CONCERNS. Firmware commit 9028a8499 (check.c, the RTC header, desktop_scene_fault.c, screen_reader_cli.c), committed before the flash; the device reports 9028a849. Project commit f0a7b7a (tests, README, spec). Nothing pushed; applications/external untouched.

## What changed, per item and file

1. The RAM prefix. check.c's comment, the README's caveats paragraph and the spec's decoding paragraph now say "an address starting with 20 (2000 to 2003)". A grep of the three files finds no other "2000" wording.
2. The build beside the address.
   - targets/f7/furi_hal/furi_hal_rtc.h: `FuriHalRtcRegisterFaultBuild` right after FaultLr, before MAX. Its doc comment ("First eight hex digits of the git hash of the build that stored FaultLr, 0 when unknown") sits on the line before, because the trailing form went past 99 columns.
   - furi/core/check.c: `#include <toolbox/version.h>`; a static `__furi_crash_build_id()` parses the first eight characters of `version_get_githash(version_get())` with a loop (0-9, a-f, A-F), returning 0 at the first other character, which also covers a hash shorter than eight. It stores the result with `furi_hal_rtc_set_register(FuriHalRtcRegisterFaultBuild, ...)` right after the lr store. I added one thing to the ruling: the hash is used only when its pointer lies in flash (`FLASH_BASE` to `FLASH_BASE + FLASH_SIZE - 8`), otherwise 0. The string is a literal in flash, but the pointer to it sits in Momentum's `version` struct, which is writable RAM (it also holds the custom name). A crash from overwritten RAM could otherwise send the handler after a wild pointer and fault inside it. The handler already checks the message pointer the same way.
   - screen_reader_cli.c: "last crash: none" when the address is 0; "last crash: at %08lX in build %08lx" when the build register is set; "last crash: at %08lX in build unknown" otherwise. The popup is unchanged.
   - README and spec: decode with the elf of the build `sr status` names, and build that commit in a git worktree if the build directory has moved on.
3. check.c comment: GCC merges identical crash-call sequences within a function, so the line can be another check of the same function; the function is certain, and addr2line -i adds the functions inlined there. It also mentions the build and the new `sr status` form.
4. README, how the address is spoken: "four digits at the start followed by a letter are said as a number too ("2001ABCD" is "two thousand one ay B C D")"; `sr status` shows the address exactly. Checked on the host with the real speech_text.c: "at 2001ABCD" is "at two thousand one ay B C D", "at 2000ABCD" is "at two thousand ay B C D", "at 20012ABC" is "at two zero zero one two ay B C".
5. README command: `-f -i -C -a`. On the flashed build, 0x08001AC9 gives ble_svc_serial_notify_buffer_is_empty, serial_service.c:210, exit 0. `-i` prints an inlining chain for 171 of the 1,848 crash calls.
6. README: the HardFault and BusFault sentence is replaced by "For any message other than "furi_check failed" or "Check serial logs", the address is in the routine that reported the crash."
7. README: the crash section is now three paragraphs: what is heard; how to decode, with the command; and the caveats.
8. desktop_scene_fault.c: the no-address branch uses `"%.*s"` with `(int)(sizeof(desktop_fault_text) - 1)`, 63, with a comment that a message kept across an update can be stale.
9. tests/host/test_speech_text.c: after the XP entries, a comment and `expect("xp", "xp")` and `expect("XPS", "X P S")`. On the host "xp" gives "xp" and "XPS" gives "X P S" (rule 7 spells it). Both passed on their first run, so there was no RED.
10. Spec: the popup buffer costs 64 bytes of .bss. `nm -S` shows `desktop_fault_text` with size 0x40, and `tools/map_size.py` gives static RAM 5,961 against 5,897 at c502de5a, exactly 64 more (the desktop line is 245).
11. README: the Device state bullet and the flash-limit list name 9028a8499 (863,644 bytes, 16,996 spare), keep 08e80106f as the last full flash, and add c502de5ab (863,284, 17,356) to the list. Both passages were rewrapped, with code spans kept whole.

The spec's closing part of section 18 is now three paragraphs: the mechanism (both registers and why the build is kept, the compiled indexes, the RTC header, the API, the popup buffer and its RAM, the bounded message, the console line); the decoding (minus 2, -i, the shared-call counts, the RAM range, other messages); and the XP label with the flash figure and the R0skie results of both rounds.

## Tests, build, lint, headroom

- `tools/run_host_tests.sh` exit status 0: 174 checks, 0 failures; speech text 968 checks, 0 failures; speech queue 156; speech PCM 597; speech voice 4433; chords 73; throttle 119, all 0 failures; fbt exclusions 0 failures; subghz sources 50 on disk, 50 quoted, 0 unquoted, 0 missing. The same again before the project commit.
- `./fbt` 16:33:07 to 16:33:48, exit status 0: `API version 87.2 is up to date`; only the two known manifest warnings (cli_bridge, mtp); "Excluded 45 external apps by configuration"; no compiler warnings; check.c, furi_hal_rtc.c, desktop_scene_fault.c and screen_reader_cli.c compiled. Sizes: .text 675848, .rodata 186472, .data 988, .bss 5084, .free_flash 184932.
- `./fbt lint` exit status 0.
- `tools/flash_headroom.sh`: `firmware.bin 863644 bytes, limit 880640, spare 16996 bytes` (176 more than a2dfdd28's 863,468; 360 more than c502de5a's 863,284).
- The enum as compiled, from DWARF: Header 0, System 1, Version 2, LfsFingerprint 3, FaultData 4, PinFails 5, UpdateFolderFSIndex 6, PinValue 7, FaultLr 8, FaultBuild 9, MAX 10.
- The handler, disassembled: the prologue is unchanged (`push {r7, lr}` ... `str.w lr, [ip, #48]`); after `furi_hal_rtc_set_fault_data` come `ldr r1, [r6, #48]; movs r0, #8; bl furi_hal_rtc_set_register`, then `bl version_get; bl version_get_githash`, the flash-range compare, the parse loop, and `movs r0, #9; bl furi_hal_rtc_set_register`. On the early-out paths the 0 comes from r5, which holds the debugger flag (DHCSR bit 0) and is 0 on this release path.
- `./fbt fap_crash_test` exit 0, "API version 87.2 is up to date". The object was recompiled (the RTC header changed), but the fap came out identical: 3,144 bytes, md5 b108984e590b8d3287c8d20fa40eb0ed.
- Before rebuilding I kept the flashed a2dfdd28 build's elf and bin in the scratchpad (elf md5 4fb13fc79a8a9d6fdeb743a5b37cc5b6), in case stopping the capture crashed the device again and its address needed that build to decode. It did not crash.

## Flash and device replies (tools/flipper_cli.py through the project venv)

- The capture log shows that someone else stopped and restarted the capture at 16:15:41 and 16:15:57 while I was idle; the device did not reboot then (its uptime runs on from 16:02).
- 16:35:33: capture stopped with `pkill -f flipper_log.py` (exit 0); `pgrep -f flipper_log.py` exit 1. The port stayed present for the 20 s I watched. At 16:36:03: `uptime` 0h33m37s, so no crash this time; `sr screen` records 1, desktop, battery "100" only; `sr status` "enabled: yes", "last crash: at 200137DF" (a2dfdd28's format), speech idle, utterances 2, clips 19, free heap 116448; `loader info` No application is running; `info device` firmware.commit.hash a2dfdd28, dirty true, API 87.2.
- `./fbt flash_usb` 16:36:14 to 16:36:52, exit status 0: package `f7-update-mntm-screen-reader-9028a849`, "Using flip_R0skie on /dev/cu.usbmodemflip_R0skie1", firmware.dfu, update.fuf and updater.bin sent, "Closing current app, if any". The only warnings were the two manifest ones, once per build environment. Port gone 16:36:52, back 16:37:20.
- 16:37:38, after 10 s: `sr screen` records 1, content layer desktop, battery "100" only: no popup. `sr status`: "enabled: yes", "last crash: at 200137DF in build unknown", "volume: 80, verbosity: 1, change delay: 3000 ms", "frames: 2, dropped: 0, announcements: 1, suppressed: 0", "speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0", "last utterance: 1090 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2516", "voice: on, ..., clips 2, fallback 0, missing 0, muted 0", "free heap: 116632". `uptime` 0h0m20s. `loader info` No application is running. `info device`: `firmware.commit.hash : 9028a849`, dirty true, branch screen-reader, build date 25-09-2026, API 87.2.
- 16:37:46: `storage.py mkdir /ext/apps/Debug` exit 0; `storage.py send .../crash_test.fap /ext/apps/Debug/crash_test.fap` exit 0; `storage md5` on the device b108984e590b8d3287c8d20fa40eb0ed.
- 16:37:54: `loader open /ext/apps/Debug/crash_test.fap`; `sr screen` records 4, fullscreen, `inverted FOCUS 1/8 "Check"`, "Check with message", "Assert", "Assert with message"; "reads as: Check with message. Assert. Assert with message. Check, 1 of 8"; `loader info` Application "Crash Test" is running.
- 16:38:03: `input send ok short`; the tool ended with "serial.serialutil.SerialException: read failed: [Errno 6] Device not configured"; port gone 16:38:04, back 16:38:06.
- 16:38:20, after 10 s, `sr screen`:

      records: 5, content layer: desktop
      desktop      x= 27 y= 26 primary    "Flipper crashed"
      desktop      x= 19 y= 37 primary    " and was rebooted"
      desktop      x= 30 y= 48 secondary  "furi_check failed"
      desktop      x= 37 y= 59 secondary  "at 2001384F"
      status-right x=103 y=  9 battery    inverted "100"
      reads as: Flipper crashed. and was rebooted. furi_check failed. at 2001384F

  `sr status`: "enabled: yes", "last crash: at 2001384F in build 9028a849", frames 2, announcements 1, utterances 1, aborted 0, "last utterance: 8782 ms played, 139530 subsamples, 8720 ms nominal", "clips 17, fallback 0, missing 0, muted 0", free heap 116576. `uptime` 0h0m17s. On the host the popup reads "... furi check failed. at two zero zero one three eight four F": 9 words and 8 characters, 17 clips, matching. The app's code was loaded at 0x2001384F - 0x23 = 0x2001382C, 4-byte aligned.
- 16:38:31: `input send back short`; `sr screen` desktop, battery only; `sr status` "last crash: at 2001384F in build 9028a849", announcements 2, utterances 2, last utterance 1097 ms ("Home screen"), clips 19; `loader info` none.
- 16:38:40: `storage remove /ext/apps/Debug/crash_test.fap` and `storage remove /ext/apps/Debug` (no output); `storage list /ext/apps`: Bluetooth, GPIO, Infrared, Media, NFC, RFID, Sub-GHz, Tools, USB, assets, iButton. No Debug folder.
- 16:38:46, final: `sr status` "enabled: yes", "last crash: at 2001384F in build 9028a849", "volume: 80, verbosity: 1, change delay: 3000 ms", "frames: 3, dropped: 0, announcements: 2, suppressed: 0", "speech: idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0", "voice: on, ..., clips 19, fallback 0, missing 0, muted 0", "free heap: 116576"; `loader info` No application is running; `sr screen` home screen (battery only); `uptime` 0h0m42s. So: home screen, reader on, voice on, speech idle.
- 16:38:53: capture restarted with the brief's nohup command (PID 82220). It logs "log debug", "Current log level: debug", and at 16:42:05 uptime tick 241,468 ms.

## Self-review

- The diff (`git show 9028a8499`): four files, as ruled; the popup is unchanged apart from the bounded no-address branch.
- Only check.c writes FaultBuild and only `sr status` reads it; as with FaultLr, it is cleared only by the whole-register resets.
- The build id on the device, 9028a849, matches `info device`, which proves the parse and the flash check on a real build.
- A build older than 9028a849 left "in build unknown", as ruled; a2dfdd28 never wrote index 9, and nothing else did.
- With a2dfdd28 and before it, MAX was 9 and 8; nothing uses MAX, and nothing iterates the enum.

## Concerns

1. The flash check on the hash pointer goes beyond the ruling, for the reason above; without it the handler would read through a RAM pointer while it handles a crash that may come from memory corruption. If the controller prefers the literal ruling, it is a three-line removal.
2. The crash after the 15:57:10 capture stop did not repeat: not at someone else's stop at 16:15:41, and not at mine at 16:35:33. It stays one unexplained data point.
3. The device holds "last crash: at 2001384F in build 9028a849" from the deliberate test until the next real crash.
4. The earlier concerns about shared crash calls and the minus 2 stand as documented; the build register does not change them.
