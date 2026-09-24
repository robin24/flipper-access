# Task 2 report (saved by the controller from the implementer's reply; the harness refused the file write)

Status: DONE_WITH_CONCERNS.

## Commits
- Firmware 6187eeb42 "screen reader: Back chords read, repeat, spell, status and volume; live settings" (screen_reader.c/.h, screen_reader_cli.c, speech.h/.c, speech_queue.h/.c, screen_model.h/.c), base 1f91f640f.
- Project 1f92cb0 "host tests: spelled items, status and focus helpers" (test_speech_queue.c, test_screen_model.c), base 35dbf72.

## Host runner (final, exit 0)
104 checks (model), port 0 failures, 11 SAM cases, speech text 1006, speech queue 125, PCM 700, voice 4433, chords 73, all 0 failures. Test-first evidence: the model test failed to compile without the helpers, then failed "14:05 100" vs "14:05, 100" until status records stopped joining rows; the queue test failed to compile without push_spelled; a deliberate stale-spell-flag mutant failed 2 checks.
New tests: status bar rows (clock primary y 8, battery font y 9 → "14:05, 100"); focus with position ("Apps, 3 of 11", "Read" without position, empty without focus); spelled queue items (new generation, spell true, file false, replaceable false; later pushes leave spell false; a replaceable text after a spelled item is appended, not merged).
Extra host check (not committed): spelled chunk builder outputs "AY p p s, 3, o f, 1 1" for "Apps, 3 of 11"; "S u b, G H z" for "Sub-GHz"; a 46 character run splits after 31 characters over two chunks.

## Build, lint, headroom, stack
./fbt exit 0 (only the two known manifest warnings, API 87.1 up to date); ./fbt lint exit 0 after one clang-format fix; firmware.bin 874,048 bytes, 6,592 spare (+1,808 over Task 1: sr_chords now linked). -fstack-usage: input_publish_event 32, sr_input_filter 40, sr_chords_feed 20, screen_reader_run_command 8, screen_reader_srv 64, speech_worker 104, speech_sam_chunk 56 bytes.

## Flash
Idle check: no application, announcements 195 flat over 90 s. ./fbt flash_usb_full (rebuilt all external apps including cli_input.fal; package f7-update-mntm-screen-reader-6187eeb4; port back after 382 s). First commands: sr screen showed the post-update splash (0 records), info device 6187eeb4 dirty (submodule), API 87.1, no crash popup; Back dismissed the splash.

## Device verification (counters identify the spoken text: "Home screen" 15,972 subsamples 2 clips; "one hundred" 14,716; "No focus" 16,399; "Volume one hundred" 26,563 3 clips; "Volume ninety" 20,146; "Apps, 1 of 11" 30,272 4 clips; spelled "Apps" 24,961 4 letter clips)
1. sr chord from the home screen: up → "Home screen" (desktop draws no text); down → "one hundred"; ok → "No focus"; okhold → "No focus" spoken, not spelled; right twice → "Volume one hundred"; left → "Volume ninety" and the status line shows volume 90; right → 100. Each command one utterance, announcements unchanged. In the main menu: ok → "Apps, 1 of 11"; okhold → spelled a p p s (4 clips, 1,666 ms); with sr voice off SAM spelled "AY P P S." (no clips); voice back on.
2. Real chords through input send (which now passes the filter): back press, up press, up release, back release → "Home screen" spoken, nothing opened; back press, ok press, ok short, ok release, back release → "No focus", nothing opened (Back's Press passes through by design and the dolphin drew a bubble that the command interrupted: aborted 1); back press, ok press, ok long, ok release, back release → "No focus". Stronger: back press, up short, back release → the lock menu did NOT open (battery still drawn), "Home screen" spoken. In the main menu: Back + OK short → "Apps, 1 of 11" (same 30,272 subsamples), menu stays; Back + OK long → spelled "Apps" (24,961), menu stays.
3. Back alone: ok short opened the menu; back short returned home (2 announcements). back press, wait 0.5 s, back release → nothing (no press timer on console keys, as predicted). input send back long → "Turn Off Device?" dialog opened and was announced (5,117 ms, buttons Battery, Power Off); back short left it.
4. Chord inside an app: "loader open Settings" fails (Settings is not an app); in the Momentum settings app (loader open Momentum): Back + Up read the whole screen (9.6 s, 18 clips, the hex commit spelled), the app stayed open on the same screen; back short left it, "Home screen" announced.
5. Reader off: sr off; back press, up short, back release → the lock menu opened (Up went through: 0 records, status bar hidden); sr on; back short closed it. With the reader on the same keys were swallowed (step 2).
Final state: home screen, no application, rate 72 volume 100, speech idle, underruns 0, dropped 0, voice on, fallback 0, missing 0.

## Stack on the device
top 0: TimersSrv 1020 stack, 796 min free; InputSrv 1020, 580 min free; SpeechWorker 3068, 2180; ScreenReaderSrv 3068, 2068. Caveat: no physical key was pressed after the flash; console keys run the filter on the CLI thread (3,380 free), so InputSrv and TimersSrv do not include the filter yet (estimate +70 bytes plus furi_thread_flags_set). Re-read top 0 after physical keys.

## Deviations and why
1. The filter is installed once at start and checks momentum_settings.screen_reader itself, letting everything through while the reader is off (the brief installed it in set_enabled: Task 3's external settings app writes the setting directly and cannot call screen_reader_set_enabled, so chords would stay swallowing after an off, or stay dead after an on). NEEDS THE CONTROLLER'S RULING.
2. Status records never join a row (clock y 8 and battery y 9 were one row "14:05 100").
3. Spelling with no focus says "No focus" normally instead of spelling it.
4. Back + Up on a text-free home screen says "Home screen" (the model's wording) instead of "Nothing on screen".
5. Spelled items take the text as written, not the expanded text (expansion would spell number words); letters and digits kept, other characters separate words, runs over 31 characters split.
6. Each spelled letter counts as a clip; nothing added to fallback or missing.
7. Voice-off spelling: "AY" for A and a comma between words, built in the chunk buffer 80 characters at a time.
8. Settings pushed to the engine before commands as well as before announcements.
9. Helpers speech_sam_chunk and sr_append_focus_position added to avoid repetition.
10. sr chord prints the command it ran (two help lines).
11. Verification adjustments: Momentum settings app instead of "Settings"; input send back long for the Long check; splash dismissed.

## Concerns
1. Deviation 1 ruling.
2. Input and timer thread stacks not yet measured with the filter on physical keys.
3. Back + Down reads the battery as a bare "one hundred"; status bar icons have no text.
4. Returning to the home screen from the power-off dialog, lock menu or splash is not announced (desktop to desktop is the same screen in the model; predates this task); the icon-only lock menu itself reads as "Home screen" (Task 4).
5. Back's Press passes through, so a dolphin bubble may be drawn and then interrupted by the command.
6. sr watch keys bypass the filter (single keys, harmless).

## Fix round 1 (saved by the controller from the implementer's reply)
Commits: firmware b6a683b7e "screen reader: long descriptions in parts, atomic command, fresh screen for commands"; project 20e52fc "host tests: spelled copy" (also the parts checks). Runner green: text 1022, queue 156, model 104, PCM 700, voice 4433, chords 73, SAM 11 cases. ./fbt clean, lint 0, firmware.bin 874,448 bytes, 6,192 spare.
1. Long descriptions: commands build into a 640 byte buffer (SR_DESCRIBE_TEXT_MAX) and say it with speech_say_parts → speech_queue_push_parts (pure, tested): parts of at most 159 characters cut after the last ". " or ", ", else the last space, else hard; the first interrupts, the rest follow, none replaceable, at most 4 parts (more counted in queue dropped); all pushed under one lock with one wake. The command reads the model's screen in place (no 1.3 KB copy). sr screen and sr watch print the full description.
2. Atomic command: __atomic_store_n on post, __atomic_exchange_n(SrChordNone) on read; latest wins, none twice.
3. Fresh screen: a pending frame is processed before the command; the reader thread drops a command if the reader was turned off meanwhile; sr chord prints "screen reader is off" when off.
4. Nothing to spell: the worker makes the spelled copy first; if empty, the text is expanded and said normally (all spelled items).
5. One static speech_push helper used by say, say_parts, say_spelled and play.
6. speech_text_spell_copy in speech_text.c with 16 checks (Apps, 3 of 11 → "Apps 3 of 11"; Sub-GHz → "Sub GHz"; a 46 run split after 31; symbols only and empty → ""; separators, non ASCII, small buffer, null); a static assert ties 31 to the clip player's word size; four mutants caught.
Stack after Robin's real key presses (top 0 at 15:05): TimersSrv 1020 stack 740 min free (was 796), InputSrv 580 (unchanged), SpeechWorker 2180, ScreenReaderSrv 2052; heap free 102,320 with the popup dialog open earlier, minimum 67,872.
Flash: idle confirmed (no app, announcements 65 and utterances 101 flat); flash_usb 15:05:47 to 15:06:22, port back after 30 s; sr screen plain home screen; info device b6a683b7.
Survey: the Apps browser reads "Bluetooth. Games. GPIO. iButton. Parent folder, 1 of 13" (55 characters). `loader open Sub-GHz` crashed the device out of memory (popup "Flipper crashed and was rebooted, out of memory", uptime 13 s afterwards) — the documented Sub-GHz limit; remaining checks pending the resume.
Deviations: splitting lives in the speech queue behind speech_say_parts; the command reads the screen in place; the console shows the full description; the nothing-to-spell decision is in the worker.

## Fix round 1, completion (saved by the controller)
Recovery: the popup dismissed at 15:10:34 was a SECOND crash ("furi_check failed", reboot at 15:09:51, while the Task 3 agent had the Momentum app open; the Task 2 agent sent nothing between 15:07:38 and 15:10:34); cause unknown.
Longest screens ("reads as" lengths): About 87 and its pages 106, 119, 106, 117, 31, 43; Storage 78, About Internal Storage 104, About SD Card 101; Power 58, Battery Info 30; System 77; LCD and Notifications 83; Desktop 80; Clock 49; Input 45; Passport 37; Bluetooth 40; Expansion 25. None over 160: the parts split is proven by the host tests only.
(a) Back + Up with real keys on About page 3 (119 characters): one part, clips +40, fallback +1 exactly as the host prediction; 21,004 ms played; the app stayed on the page.
(b) sr off; sr chord up → "screen reader is off"; utterances unchanged; sr on.
(c) Back + OK long on the keyboard's "_" key (Text to SAM): "underscore" spoken normally (one clip, 11,183 subsamples, same as the focus announcement); nothing typed; Back left the app.
(d) Back + Down on the home screen: "one hundred" (2 clips) plus the dolphin bubble drawn after Back's Press and announced once (5 clips); nothing aborted.
Final state 15:21:15: home screen, no app, rate 72 volume 70, speech idle, utterances 68, aborted 6, dropped 0, underruns 0; heap free 108,184, minimum 73,304; TimersSrv 796 free, InputSrv 620, ScreenReaderSrv 2,028.
