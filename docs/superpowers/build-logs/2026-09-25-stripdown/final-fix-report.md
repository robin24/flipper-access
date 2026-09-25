# Final fix wave report

Status: DONE_WITH_CONCERNS (small ones, listed at the end). Firmware commit 08e80106f, project commit fd6acff. Both committed with the brief's subjects and explicit paths; nothing pushed; applications/external untouched and not committed; voice/ and patches/text2sam-cli-mode.patch untouched.

## Firmware fixes (commit 08e80106f)

1. applications/services/desktop/animations/animation_manager.c. In animation_manager_alloc, the block `if(animation_manager->anims_enabled) { if(!animation_manager_check_blocking(...)) animation_manager_start_new_idle(...); }` got `else { animation_manager_grant_pending_levelup(); }`. The helper's comment now says the level is granted "at boot (from alloc) and at every later check, whenever the manager is asked to look at the dolphin's state". The helper is defined at line 158, above animation_manager_check_blocking_process and above alloc (line 320), so no forward declaration was needed.
   - Checked in the built ELF: alloc's off branch is `cbz` to `bl animation_manager_grant_pending_levelup`; check_blocking_process tail-calls the same helper.
   - Safe at boot: dolphin_stats is a send-and-wait on the dolphin's queue, which upstream's alloc already does through animation_manager_check_blocking; dolphin_upgrade_level only queues an event (dolphin_event_send_async), and the level event publishes nothing, so no callback loop. The dolphin state is on /int and loaded in dolphin_srv before its event loop runs.
2. applications/services/screen_reader/speech.h, SpeechVoiceStats.enabled: the comment is now "recorded clips are used when the vocabulary is present; false means muted (sr voice off)", continued on a second line aligned the way the aborted field's comment in the same file is, to stay within 99 columns. clang-format 18.1.8 (the toolchain's) dry run: clean.
3. fbt_options.py, the comment above EXCLUDE_EXT_APPS gains: "An app that a metapackage still names (for example in applications/system/application.fam) keeps deploying its resources to the card even when excluded here, so such an app must leave the metapackage too, as js_app did."

## Build, lint, headroom

- ./fbt before the commit: exit 0, 06:21:36 to 06:21:55 (incremental: animation_manager.c plus screen_reader.c, screen_reader_cli.c and speech.c, which include speech.h; image relinked). Output: the two known manifest warnings (cli_bridge "Invalid appid '.cli_gui'", mtp "Invalid appid '.f0_mtp'"); "Excluded 45 external apps by configuration: ..." with the same 45 names as the measurements file (compared byte for byte); "API version 87.2 is up to date". No error line.
- ./fbt lint: exit 0.
- tools/flash_headroom.sh: "firmware.bin 862612 bytes, limit 880640, spare 18028 bytes". The same after the flash build, which restamped the image with 08e80106 (md5 325957f1c6a849729a7de747c94646a5).
- The 24 bytes above 862,588: at cc7212c6c the compiler inlined the helper into its only caller, check_blocking_process. With a second caller it is its own function (48 bytes), check_blocking_process shrinks from 116 to 88 bytes and alloc grows from 192 to 196. Verified by compiling the cc7212c6c and the new animation_manager.c alone with the build's exact flags from compile_commands.json: 2,519 and 2,543 bytes of code, exactly 24 more; no helper symbol in the old object.
- Static RAM from tools/map_size.py over the new map: TOTAL flash 866430 static ram 5897, so static RAM is unchanged; the screen reader (19,798 flash, 8 RAM) and Sub-GHz (43,142, 25) lines are unchanged.

## Flash

- Idle check at 06:23:01 (loader info, sr status): No application is running; speech idle; announcements 56, utterances 57 (as Task 6 left it); free heap 116,488.
- `rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps && ./fbt flash_usb_full`: 06:23:59 to 06:27:41, exit 0, package f7-update-mntm-screen-reader-08e80106. Last lines: progress "<100%, chunk 15 of 15 @ 124.19 kb/s", "Closing current app, if any", Touch("build/usbinstall.flag"). Same filter result as the ./fbt run; 20 compiler warnings, all under applications/external (the same count as Task 6).
- Resource manifest after the flash build: the section 8 grep is 0, and 0 without the slashes; 11 app folders; 20 files under apps/Sub-GHz; .extapps holds no js_*, cli_js, test_js or subghz.fap.
- Port gone 06:27:39, back 06:33:43: 364 s, 6 min 4 s. A background watcher logged the transitions and waited 10 s more.

## Device replies after the flash

- sr screen at 06:34:00: "records: 0, content layer: desktop" (the post-update splash); loader info: No application is running. input send back short; sr screen: 1 record, the battery "100", on the desktop.
- info device, firmware lines: firmware.commit.hash 08e80106; firmware.commit.dirty true (the untouched submodule); firmware.branch.name screen-reader; firmware.version mntm-dev; firmware.build.date 25-09-2026; firmware.api.major 87; firmware.api.minor 2.
- sr status: enabled: yes / volume: 80, verbosity: 1, change delay: 3000 ms / frames: 3, dropped: 0, announcements: 1, suppressed: 0 / speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0 / last utterance: 1089 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2516 / voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0, muted 0, open max 26 ms, last 26 ms / free heap: 116552.
- sr voice status: voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0, muted 0, open max 26 ms, last 26 ms.
- free: Free heap size 116560; Total heap size 189560; Minimum heap size 114024; Maximum heap block 115888; Pool free 876; Maximum pool block 672. Uptime 0h0m29s. The probe's fragmentation (largest block 57,880) is gone.
- Left on the home screen, no application, reader on, voice on, speech idle; frames 3 at 29 s, so no animation. Not touched again; the log capture was not started.

## Project fixes (commit fd6acff)

4. tests/host/test_speech_pcm.c: the last check of test_volume is now `CHECK(pcm.lut[v[0]] > full[v[0]]);`. Mutation check: against a speech_pcm_reset that also restores full volume, the old check passed (597 checks, 0 failures) and the new one fails (597 checks, 1 failure).
5. tests/fbt/test_exclusions.py: the synthetic manager gains `app("test_js", FlipperAppType.PLUGIN, requires=["cli", "js_app"])`. Nothing excluded: test_js in the set. js_app and cli_js by id plus Games: ["nfc_plugin", "nfc_tool", "subghz", "test_js"]. Category only: test_js in the set. The unknown-id case now uses the fork's real configuration, exclude_apps ["js_app", "cli_js", "test_js", "nope"]: the set stays ["nfc_plugin", "nfc_tool", "subghz"] and the count rises from "Excluded 4" to "Excluded 5". The docstring and the case comments say why (the second case is no longer called the fork's configuration, since the fork names test_js). `python3 tests/fbt/test_exclusions.py`: "fbt exclusions: 0 failures", exit 0.
6. tests/fbt/test_subghz_sources.py, new: walks applications/main/subghz for .c files and collects the quoted .c paths in its application.fam; prints the names of any unquoted or missing file, then "subghz sources: N on disk, M quoted, K unquoted, J missing", and exits 1 when K or J is not 0. Only path-like quoted strings count, because the manifest's own comment quotes the glob "*.c" (a first version counted it and reported 51 quoted, 1 missing). subghz_fap.c counts as quoted through Momentum's commented-out subghz_fap App block, which is how the final review's 50 arises. Today: "subghz sources: 50 on disk, 50 quoted, 0 unquoted, 0 missing". Failure paths checked on a scratch copy of the tree (a new scene added, views/transmitter.c removed): both named, exit 1. tools/run_host_tests.sh runs it last, in the exclusion block's shape (its own output file subghz_sources.txt, `echo "$(tail -n 1 ...)"`); its header comment names the new check.
7. README.md: Device state names 08e80106f, 862,612 bytes, 18,028 spare. The Back chords bullet: "With animations on (they are off by default), the dolphin on the home screen may answer it with a speech bubble...". The flash-limit paragraph leads with "after the firmware stripdown and its final fixes, at 08e80106f on 2026-09-25: 862,612 bytes, 18,028 spare", then the old history. Useful commands: "With animations on, the dolphin's speech bubbles on the home screen are not spoken unless...", and the paragraph was rewrapped under 100 columns. Recorded voice: "With the voice off, the vocabulary figure keeps its last value: the card is looked at again only when something is spoken with the voice on" (checked in speech.c: speech_speak_item tests voice_enabled before speech_voice_ready, so the card is not looked at while muted). Beyond the list, for consistency: the Plan's "Flash 862,612 bytes, 18,028 spare" line, and the tools list, which said the runner finishes with test_exclusions.py, now names both Python checks and describes test_subghz_sources.py.
8. docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md, section 18:
   - Build options: plumbed through site_scons/commandline.scons, scripts/fbt_tools/fbt_apps.py and scripts/fbt/appmanifest.py; firmware.scons was not touched, since the values reach the firmware environment through the base environment's variables. Checked: git diff 22ae265ef..HEAD shows no firmware.scons change, and firmware.scons builds its environment with ENV.Clone. The sentence "now runs as the last step of tools/run_host_tests.sh" became "now runs in", because the new check is the last step now.
   - Sub-GHz paragraph: one sentence on test_subghz_sources.py (not in the brief; the runner sentence needed it).
   - Animations: the guards test anims_enabled, which alloc latches from momentum_settings.desktop_anims; alloc has no early return, skips its loading block and grants a pending level up in the else branch; the five other entry points named with what each does; "A pending level up is granted at boot and at every later check, which the manager runs after every dolphin deed and every card event". The forward reference is gone. The latch-deviation paragraph stays as it was, and a new paragraph after it, "A second deviation from the stripdown spec, made by the round's final fixes", gives section 7's reason against a boot-time grant and why it is safe: upstream's alloc already calls dolphin_stats at that point through animation_manager_check_blocking, on the desktop's thread.
   - The final-image sentence: the final fixes at 08e80106f add 24 bytes; the final image, 862,612 bytes, 18,028 spare. The Task 6 figures paragraph keeps its figures, and its round total now reads "to that image: 14,448 bytes less...; to the final image, after the round's final fixes: 14,424 less".
9. docs/roadmap.md: the Release mechanics bullet's "known limits (NFC-V silence)" became a short list: NFC-V emulation silences the reader; the sync guard reads the voice flag once per item, so an utterance already playing when sr voice off arrives keeps opening clips and writes the missing list at its end while the generator has already started the transfer; sr play still plays a file with the voice off, by design. Beyond the brief: memory plan step 4's "Final image" line re-stamped to 08e80106f, 862,612 bytes, 18,028 spare.
10. docs/measurements/2026-09-25-stripdown.txt:
   - Flash: "Final build, cc7212c6c, the image that ships" became "Final build of Task 6, cc7212c6c, the image of the device pass below". A new line after it: "Final fix wave, 08e80106f, the image that ships: 862,612 bytes, 18,028 spare", with the 24 bytes explained and the md5. The round total: 14,424 less to the image that ships (14,448 to cc7212c6c). "The final build:" became "Task 6's final build:". Three lines on the wave's builds, filter output and manifest check.
   - Static RAM: one line for the new map (TOTAL flash 866430 static ram 5897, unchanged).
   - Header lines 3 and 4 name the fix wave's commit and its second flash.
   - Device pass: the sentence on the engine checks at 4bda0a4ae with the pointer to docs/superpowers/build-logs/2026-09-25-stripdown/task-4-report.md, the engine unchanged since (checked: since 4bda0a4ae only speech.h's comment and the settings' desktop_anims changed). A last step, "9. The final fix wave's flash, 08e80106f", with the idle check, the flash timing, the splash and the verbatim time-stamped replies (info device reduced to the firmware lines, as in step 3).
   - Every figure written is from this wave or already in the file; 14,424 is 877,036 minus 862,612.

## Test runs

- tools/run_host_tests.sh, final tree, exit 0: model 174 checks 0 failures; speech text 959/0; speech queue 156/0; speech PCM 597/0; speech voice 4433/0; chords 73/0; throttle 119/0; "fbt exclusions: 0 failures"; "subghz sources: 50 on disk, 50 quoted, 0 unquoted, 0 missing".
- python3 tests/fbt/test_exclusions.py: 0 failures, exit 0. python3 tests/fbt/test_subghz_sources.py: exit 0.

## Commits

- Firmware, screen-reader: 08e80106f "Final fixes: a pending level up granted at boot with animations off; the enabled field's comment; the resources rule beside EXCLUDE_EXT_APPS" (3 files).
- Project, main: fd6acff "Final fixes: tests pinned, Sub-GHz source coverage check, README and spec corrections, the shipped image re-stamped" (8 files, one new).
- Both messages end with the session's Co-Authored-By trailer after the brief's subject.

## Concerns

1. The image is 24 bytes above 862,588, not "a few": the helper is no longer inlined (measured, above). 18,028 spare.
2. The boot-time grant was not seen on the device: Task 6 found the pending level up most likely granted during the RAM probe, so none was pending at this boot. The path is verified in the disassembly only.
3. Beyond the brief's lists, for consistency with the new check and the re-stamp: the README tools list and Plan line, section 18's runner sentence, the new Sub-GHz sentence and the round total, the roadmap's final-image line, and the measurements header, Static RAM line and build lines. All are listed above.
4. The measurements file points to docs/superpowers/build-logs/2026-09-25-stripdown/task-4-report.md, which does not exist until the controller files that directory.
