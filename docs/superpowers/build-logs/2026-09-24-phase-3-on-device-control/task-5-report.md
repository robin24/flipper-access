# Task 5 report: documents and a chord session for sr_drive

Status: DONE_WITH_CONCERNS (small ones, listed at the end). Nothing pushed; no firmware file changed.

## Commit

Project main, base 3794700:
- 5230ae5 "docs: phase 3 as built; sr_drive chord session" (with a body and the Co-Authored-By line). Files: README.md, docs/roadmap.md, docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md, docs/measurements/2026-09-24-phase-3.txt (new), tools/sr_drive.py, tools/voice_words.txt. Added and committed with explicit paths.
- Firmware repo untouched: still 6c7469a79, only the pre-existing modified submodule applications/external.
- The repo-root voice/ folder was only added to by voice_build (28 clips), never moved or deleted.

## Device work

Log capture stopped at 17:03:29 (pid 88568), restarted at 17:08:52; stopped again at 17:14:06 for the README path check and restarted at 17:15:37 (pid 89649, running now).
info device: commit 6c7469a7, branch screen-reader, API 87.2, system.stealth 1.
Idle check 17:03:44 to 17:04:15: "No application is running", announcements flat at 35, speech idle. A second idle check before the path check: announcements flat at 66.

### Vocabulary run

`.venv/bin/python tools/voice_build.py --extract --pull-missing --sync`, 18.93 s wall clock:

    extract: 6248 distinct strings from the firmware sources, 71 bubble texts
    extract: 2893 words; longest: animationmanager animationstorage ...
    extract: 10 with an apostrophe: can't doesn't don't flipper's i'll i'm isn't it's who's you're
    voice: silenced for the transfer
    skipped 6 words that cannot be clips
    pulled 16 missing words from the device
    voice: restored
    2915 words, 27 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
    made 27 clips, 0 failed, 13 s; vocabulary 2926 words in .../voice
    voice: silenced for the transfer
    sync: 27 sent, 2899 skipped, 0 missing, 0 failed, 4 s
    voice: restored

The 27: accessibility android backward chord chords chromeos de demos digit dry dvorak es fi fox fr gnome ios muted nown okhold qflipper runs spell spelled terse unk verbose. "entered" already had a clip. "digits" got none: the PIN note is `"%u digit%s entered"`, and the extractor strips printf fields, so it only ever sees "digit". I added "digits" to tools/voice_words.txt (the base list of words the firmware builds at run time) and ran the same command again, 3.13 s: pulled 0, "2902 words, 1 to make", made 1, "sync: 1 sent, 2926 skipped, 0 missing, 0 failed". Vocabulary 2,927 words.

On the card (storage stat), each equal to the local clip: digit 6,949 bytes in 16/, digits 8,723 in 3f/, dry 7,722 in 1e/, backward 9,170 in 04/, muted 7,065 in 10/, entered 7,577 in 14/.
`sr voice status`: voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 107, fallback 1, missing 1, open max 32 ms, last 24 ms.
Spoken check, `sr say Volume muted. 2 digits entered. 1 digit. Dry. Fast backward.`: clips 107 to 117 (+10, every word from a clip), fallback and missing unchanged, 6,433 ms played, underruns 0.

### Chord session

The session (tools/sr_drive.py, `chords()`): `sr on`, require the home screen, then for each of Back + Up, Back + Down, Back + OK short, Back + OK long, on the home screen and in the main menu: wait for speech idle, read `sr status` and `sr screen`, send the plan's input send sequence, wait until the utterance counter rose and speech is idle with nothing queued (5 s to start, 60 s to finish), and compare the screen: content layer, focus records, and away from the desktop the "reads as" line (on the desktop the bubbles come and go, so only layer and focus count there; the lock menu would show a focus). Back to the home screen at the end, checked.

`.venv/bin/python tools/sr_drive.py --chords`, 17:05:59, 25.7 s:

         home  desktop, no focus
    ok   home  back + up       utterances +2, aborted +0, dropped +0, announcements +1; last 2570 ms played, 39989 subsamples
    ok   home  back + down     utterances +2, aborted +0, dropped +0, announcements +1; last 1097 ms played, 15972 subsamples
    ok   home  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 1107 ms played, 16399 subsamples
    ok   home  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1107 ms played, 16399 subsamples
         menu  fullscreen, FOCUS 1/11 "Apps", reads as: Settings. Sub-GHz. Apps, 1 of 11
    ok   menu  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 4386 ms played, 68392 subsamples
    ok   menu  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 1525 ms played, 22825 subsamples
    ok   menu  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 2005 ms played, 30272 subsamples
    ok   menu  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1674 ms played, 24961 subsamples
    ok   end   home screen expected, got: desktop, no focus
    0 failures

The two "+1 announcements" lines on the home screen are a dolphin bubble after the chord's Back press (the last utterance there is the bubble, or the "Home screen" when it vanished). The main menu is fullscreen with no status bar records (checked with sr screen), so Back + Down there said "No status bar".

All three sessions, `.venv/bin/python tools/sr_drive.py`, 17:07:41, 58.7 s: sessions one and two all 17 steps ok, then

    ok   home  back + up       utterances +1, ... last 1107 ms played, 15972 subsamples      ("Home screen")
    ok   home  back + down     utterances +1, ... last 2169 ms played, 32784 subsamples      ("battery one hundred percent")
    ok   home  back + ok       utterances +1, ... last 1108 ms played, 16399 subsamples      ("No focus")
    ok   home  back + ok long  utterances +2, announcements +1; last 67546 subsamples       ("No focus", then a bubble)
    ok   menu  back + up       68392 / back + down 22825 / back + ok 30272 / back + ok long 24961
    ok   end   home screen expected, got: desktop, no focus
    0 failures

(verbatim in docs/measurements/2026-09-24-phase-3.txt). Every chord's own utterance matches the subsample values the earlier tasks recorded.

I checked first that session one is safe to run now: the main menu is allocated on every open with the selection on Apps, so its "open the selected app" step opens the Apps browser, not Sub-GHz.

README path check (so the instructions are verified, not inferred): OK on the home screen "Apps, 1 of 11"; Up "Settings, 11 of 11"; Up "Momentum, 10 of 11"; OK "MNTM-DEV 6C7469A7. Protocols. Misc. Interface, 1 of 4"; Up "Accessibility, 4 of 4"; OK "Voice Recorded. Rate 72. Volume 70. Screen Reader ON, 1 of 5"; three Backs home. Nothing changed.

Final state: home screen, no application, reader on, voice on, speech idle, rate 72, volume 70, underruns 0, dropped 0, heap 110,280; log capture running.

Host runner (TMPDIR in the scratchpad), exit 0: model 159, port 0 failures, SAM 11 cases, text 1022, queue 156, PCM 700, voice 4433, chords 73.

## What each document says now

- README.md: a new section "Using it on the device" after Device state, in prose and lists, no tables: Back chords (each chord, then Back alone, Long on release, Back's press reaching the app, reader off, which keys bypass), `sr chord` in a code block; the Accessibility settings (the verified path, the five rows, save on exit, how to undo an accidental OFF); the home screen and the lock menu (grid layout, keys, names, stealth); locking and unlocking (the sentences, the 2 s quiet window, three quick Backs under 0.6 s, the PIN entry, untested); universal remotes (names, the quarter-turn key orientation, the TV layout); NFC-V; known limits. Also updated: the device runs screen-reader 6c7469a79 API 87.2; Sub-GHz waits for the memory plan (opening it crashed on 2026-09-24); API 87.2 in Folder contents; sr_drive's three sessions and `--chords`; flash numbers after phase 3; `sr chord` in the console paragraph; Plan item 7 done, item 8 the memory plan.
- Spec: the top status line names phases 2 and 3; section 14 marks phase 3 done; section 17 opens with a status paragraph (6c7469a79, API 87.2, 875,928 bytes, 4,712 spare) and the five corrections (the filter lock, Long before the Release, installed once and gated on the setting, notes first and counted as content, the lock announced from the desktop status pubsub) plus "the rate stays in settings"; a "Phase 3 as built" list at the end of section 17 in the style of the phase 1 and 2 lists (filter details, chords, commands, texts, parts, spelling, volume, the scene, notes, desktop, lock, infrared, NFC-V, API, vocabulary, budget and stacks, tests, known limits including the unexplained 15:09:51 reboot).
- docs/roadmap.md: a status line (the voice and phase 3 done; next the memory plan from step 2), where phase 3 left memory (875,928 bytes, 4,712 spare, about 110 KB idle heap, Sub-GHz out of memory), and the phase 3 feature line marked done with a summary and pointers.
- docs/measurements/2026-09-24-phase-3.txt: plain lines; the subsample key for spoken texts, flash per task, the Task 2, Task 2 fix, Task 3, Task 4 and Task 4 fix device outputs from the reports, then Task 5: the idle check, both vocabulary runs, the card sizes, the spoken check, both chord session outputs verbatim, the path check and the final state.
- tools/sr_drive.py: the third scripted session "chords", run by default after the two watch sessions, or alone with `--chords`.
- tools/voice_words.txt: "digits".

## Concerns

1. tools/voice_words.txt is outside the brief's file list. Without it "digits" has no clip until the device logs it as missing on a first PIN entry. One line, flagged here; revert if unwanted.
2. The device is in stealth mode (info device system.stealth 1): the lock menu's Volume tile reads "Volume muted". Possibly left on by Task 4's stealth check, possibly Robin's choice; I did not change it. The reader speaks regardless (it never reads the stealth flag).
3. The chord check "the utterance counter rose" can also be met by a dolphin bubble on the home screen, because the chord's Back press makes bubbles speakable. The session prints the announcements delta and the subsamples, so such a case is visible (twice in the first run). I rejected a stricter "utterances rose more than announcements": a bubble handed to speech and then cleared by the chord's interrupt before it starts would fail it falsely.
4. The session uses the plan's OK sequences: `ok press`, `ok short`, `ok release` sends two OK Presses and two Releases, which a real device never does. The stray Release passes the filter and the GUI discards it. Task 2's cleaner "back press, up short, back release" is not repeated here.
5. The volume chords are not in the session (they change a saved setting); Task 2 checked them.
6. The README's "first key press on the home screen after a long idle may open the lock menu" is written as given; no report explains the mechanism, and I did not reproduce it.
7. Not device-verified, so the README says only what the code does: what a lock menu tile says after OK switches it, and the PIN entry (as in Task 4).
8. The spec keeps the design paragraphs of section 17 as they were and corrects them in the status paragraph and the as-built list, as the brief asked, rather than editing the design text itself.

Report path: /Users/robin/Downloads/flipper-access/.superpowers/sdd/2026-09-24-phase-3-on-device-control/task-5-report.md
