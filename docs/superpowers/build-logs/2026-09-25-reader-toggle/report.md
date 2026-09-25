# Report: Back and Down held toggles the reader; the Passport says "to level 3" (2026-09-25)

Status: DONE_WITH_CONCERNS. Both changes are built, committed, flashed and checked on Delphi. Every
check in the brief passed. The concerns are two places where I departed from the brief's wording
(the first needs Robin's yes or no), and some small follow-ups. They are listed first.

## Commits

- Firmware, branch screen-reader: f9f1e168f "Back and Down held long toggles the reader, also while
  it is off; positioned tap notes; the Passport says "to level N"; API 87.3". 11 files. Parent
  4585cdb98.
- Project, branch main: 1a42046 "The reader toggle and the Passport's next level: tests, README,
  spec, chord driver". 5 files. Parent 2fe9ca1.
- Nothing pushed. applications/external was not touched and not committed (it still shows as
  modified, as before).

## Decisions and deviations, read these first

1. Back's own Long while the reader is off. The brief asks for two things here. First: "every other
   key passes exactly as an ordinary key, including Back's own short and long". Second: when the
   toggle fires with the reader off, "the drops are the same as in the on mode for that chord".
   With the usual timing, where Back is held past 300 ms before Down comes, these cannot both
   hold. Back's Long arrives before the machine can know whether Down will follow. If it passed at
   once, the home screen would open the power-off dialog before the chord, and the reader would
   then come on reading that dialog. So I kept Back exactly as it is with the reader on, in both
   modes. Its Short passes at once. Its Long is held back and delivered on the release, unless a
   chord ran. Back's Repeats are dropped, as with the reader on. A long Back alone still reaches the
   app, on its release. This is the README's own rule: "a slow chord is never mistaken for a long
   press". It is what the tests pin (test_off_back_alone) and what the README and spec now say. If
   Robin wants Back's Long passed at once while the reader is off, the change is one condition in
   sr_chords.c, plus its test and the documents. The cost would be the power-off dialog on a slow
   chord from the home screen.
2. The Passport's total view. OK in the Passport switches the points line to the total, "XP
   107/9999", counted toward the last level. The brief's note, the current level plus one, would
   say "to level 3" there, which is wrong. The note therefore names the last level, 30, while the
   total is shown. In the default view it is exactly the brief's note ("to level 3"). "Max Level!"
   has no note. This was checked on the device.
3. Files outside the brief's lists, both committed:
   - applications/services/gui/canvas_i.h: one comment. The record's note flag said "at x 0, y 0",
     which is no longer always true.
   - tools/sr_drive.py: its status chord sent Down's Press and Release without a Short. Down now
     names its chord on its Short, as OK does, so without this change the driver's check would
     fail. It now sends "down short", as its OK entries do. The driver then passed all eight chords
     on the device.
4. README, Device state section: I also corrected the device name (Delphi since 2026-09-25, R0skie
   before) and the serial port (/dev/cu.usbmodemflip_Delphi1). Historical mentions of R0skie were
   left as they are, for example "checked on R0skie".
5. Order on the device: I first ran check 7 before copying the Passport fap. I had missed the copy
   step, so the old Passport answered, without the note. I then copied the fap and redid check 7.
   Both runs are recorded below.
6. Extra device checks beyond the brief:
   - the toggle made inside the lock menu, which proves check 6 opened it;
   - the toggle ignored on a keypad-locked lock screen, and working again after the unlock;
   - the Passport's total view;
   - tools/sr_drive.py --chords.

## What changed, per file

Firmware (f9f1e168f):

- sr_chords.h and sr_chords.c:
  - Down is split as OK is. Down pressed while Back is held becomes the chord key: its Press is
    dropped and it is swallowed until its release.
  - Down's Short gives SrChordStatus. Down's Long gives the new SrChordToggleReader, once, with no
    Status after it. The flag ok_long_seen became key_long_seen and serves both keys; one chord
    key at a time needs only one flag.
  - sr_chords_feed takes a new bool reader_on. With the reader off, only Down starts a chord. It is
    held back from its Press and becomes a chord at its Long. From then on Back's own Short is
    dropped and a held-back Long is cancelled, as with any chord while the reader is on. A short
    Down with Back held names no command and is lost: its Press was dropped and cannot be given
    back. Up, OK, Left and Right while Back is held pass untouched. Back is handled alike in both
    modes (see decision 1). A chord key stays swallowed across a change of mode.
  - The contract comments in the header describe all of this.
- screen_reader.c:
  - The input filter now feeds every event to the machine, with the setting as it is now. Before,
    it reset the machine while the reader was off.
  - A new field, desktop_locked, set from the desktop's status pubsub callback. It is kept with the
    reader off too. When the reader subscribes, it is seeded from desktop_api_is_locked, the RTC PIN
    flag, because only a PIN lock at boot can come before the subscription.
  - The service loop runs SrChordToggleReader whether the reader is on or off. The other commands
    still need the reader on. The toggle (sr_toggle) does nothing while desktop_locked is set, and
    it drops a held change either way.
  - Toggle off: screen_reader_set_enabled(sr, false), then the volume, then speech_say("Screen
    reader off", interrupting).
  - Toggle on: the setting set to true and saved. Then sr_model_screen_quietly:
    - it clears the frame flag, calls gui_update, and waits for a frame and for more frames within
      50 ms, at most 300 ms in all, as the loop lets a screen settle;
    - it models the last frame under the mutex without saying its announcements (the tap's
      turned_on logic makes that frame a new screen);
    - it returns false if no frame came.
    Then one speech_say_parts: "Screen reader on. " followed by sr_read_all_text for model.prev.
    That is the ReadAll text, which is now shared with the ReadAll command, including its "Home
    screen" and "Nothing on screen" fallbacks. If no frame came, it says "Screen reader on" alone.
- screen_reader_cli.c:
  - "downhold" is in the chord table after "okhold" ("turn the reader off or on"), and in the usage
    and error text.
  - sr chord downhold works while the reader is off. The other keys still answer "screen reader is
    off".
- screen_model.c and screen_model.h:
  - A plain note is a note at x 0, y 0. It is still read first, as a row of its own, and never
    joins another row.
  - A note with any other position sorts among the drawn text by baseline and x, and joins the row
    on its baseline as drawn text does.
  - A row that a note begins keeps row.note set, so it is never the title.
  - Width handling: the model joins records by row kind and a 2-pixel baseline tolerance, with no
    gap rule. So the note needs no width; its x only orders it within the row. Nothing was added
    for width.
  - Comments updated.
- canvas.h and canvas.c:
  - New function canvas_tap_hint_note_at(Canvas*, uint8_t x, uint8_t y, const char* text). It
    makes the same record as a plain note: not drawn, note true, the secondary font, focus false.
    The position is x and y plus the canvas offset, as canvas_draw_str would record them.
  - A shared static helper builds both kinds of note record.
  - The documentation of canvas_tap_hint_note points to the new function.
- canvas_i.h: the comment on the note flag.
- targets/f7/api_symbols.csv:
  - One new entry after canvas_tap_hint_note: Function,+,canvas_tap_hint_note_at,void,"Canvas*,
    uint8_t, uint8_t, const char*"
  - Version,+,87.3,, instead of 87.2.
- passport.c: after the points line is drawn, and while the battery font is still set, and only
  below the maximum level, it calls canvas_tap_hint_note_at(canvas, (uint8_t)(59 +
  canvas_string_width(canvas, xp_str) + 2), 42, note). The note is "to level %u": the current level
  plus one, or DOLPHIN_LEVEL_COUNT + 1 while the total is shown (decision 2). A 16-byte local
  buffer and snprintf. Nothing drawn changes.

Project (1a42046):

- tests/host/test_sr_chords.c:
  - The helpers feed() (reader on) and feed_off() (reader off) replace the old helper.
  - Two existing tests changed where Down used to give Status at its Press. It now gives it at its
    Short.
  - Twelve new tests: Down short gives Status; the brief's toggle sequence; the usual timing with
    Back's Long first; Long then Short; Down outliving Back; Down long without Back, in both modes;
    off mode with Back plus Up, OK and Right; off mode with Back alone; the off-mode toggle; the
    off-mode short Down; a mode change mid-chord in both directions; the console's sequence.
- tests/host/test_screen_model.c: the helper add_note_at, a Passport frame, and
  test_positioned_note:
  - "XP 7/100" plus the note at (100, 42) reads as one row, whatever the order the records came in;
  - the whole Passport describes as "Delphi. Mood: Happy. Level: 2. XP 7/100 to level 3";
  - a plain note is still read first;
  - a positioned note is never the title, even in the primary font at y 12, and drawn text joining
    a row the note begins does not make that row the title.
- README.md:
  - Device state: name, port, commit, API 87.3, figures, the rebuilt Passport.
  - Back chords: Back and a short press of Down; the new chord line, as the brief gives it; the
    off-mode rule; locked; Back's Long rule also while the reader is off; the downhold key.
  - Accessibility settings: the chord as the way back.
  - The Passport paragraph: "to level 3", the total view, Max Level.
  - The API 87.3 line, the flash history line, and the sr chord list in Useful commands.
- docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md: at the end of section 18,
  "The reader toggle and the positioned note (2026-09-25)", as three paragraphs:
  - the toggle, including the off-mode rule, why Back is handled as with the reader on, and the
    announcement order;
  - the positioned note and API 87.3;
  - the figures and the device results.
- tools/sr_drive.py: the status chord sends "down short" (decision 3).

## Tests: RED, then GREEN

RED, model, against the unchanged screen_model.c. It failed for the expected reason: the note was
sorted first, as a row of its own.

    FAIL tests/host/test_screen_model.c:762: s.row_count == 1
    FAIL tests/host/test_screen_model.c:763: got "to level 3" expected "XP 7/100 to level 3"
    FAIL tests/host/test_screen_model.c:771: s.row_count == 1
    FAIL tests/host/test_screen_model.c:772: got "to level 3" expected "XP 7/100 to level 3"
    FAIL tests/host/test_screen_model.c:777: s.row_count == 4
    FAIL tests/host/test_screen_model.c:780: got "to level 3. Delphi. Mood: Happy. Level: 2. XP 7/100" expected "Delphi. Mood: Happy. Level: 2. XP 7/100 to level 3"
    FAIL tests/host/test_screen_model.c:788: s.row_count == 2
    FAIL tests/host/test_screen_model.c:790: got "to level 3" expected "XP 7/100 to level 3"
    FAIL tests/host/test_screen_model.c:804: s.row_count == 1
    FAIL tests/host/test_screen_model.c:805: got "Wi-Fi" expected "Wi-Fi Settings"
    FAIL tests/host/test_screen_model.c:806: s.title_row == -1
    190 checks, 11 failures

RED, chords: first a compile error, because the API did not exist yet ("too many arguments to
function call, expected 6, have 7" and "use of undeclared identifier 'SrChordToggleReader'"). I then
added only the API surface: the reader_on parameter, ignored, and the enum value. The run then
failed on behaviour: 200 checks, 46 failures. Every failure is one of three kinds:
- Down's Press still gave Status. Lines 71, 153, 163, 175, 187, 199, 212, 287, 294, 306, 314, 326,
  334 and 354.
- No toggle on Down's Long, and no Status on Down's Short. Lines 72, 154, 164, 176, 189, 200, 215,
  288, 295, 327, 336 and 356.
- The off mode behaved as the on mode: Up, OK and Right while Back is held were dropped as chords,
  Back's Short was dropped after them, and Back's Long was not emitted. Lines 246 to 258, 273 to 279,
  309 and 317.
The full list is in the session's scratchpad (red_chords.txt). All failures had these reasons.

GREEN, tools/run_host_tests.sh, exit 0. The same result again before the project commit:

    190 checks, 0 failures
    speech text: 968 checks, 0 failures
    speech queue: 156 checks, 0 failures
    speech PCM: 597 checks, 0 failures
    speech voice: 4433 checks, 0 failures
    chords: 200 checks, 0 failures
    throttle: 119 checks, 0 failures
    fbt exclusions: 0 failures
    subghz sources: 50 on disk, 50 quoted, 0 unquoted, 0 missing

The baseline before any change was 174 model checks and 73 chord checks, all passing.

The pronunciation layer, run on the host with tests/host/speech_expand.c, which is unchanged,
predicted the device's words:
- "Delphi. Mood: Happy. Level: 2. XP 7/100 to level 3" becomes "Delphi. Mood, Happy. Level, two.
  experience seven of one hundred to level three".
- "XP 107/9999 to level 30" becomes "experience one hundred seven of nine thousand nine hundred
  ninety nine to level thirty".

## Build, lint, API, headroom

- ./fbt: exit 0. It printed "API version 87.3 is up to date", the two known manifest warnings
  (cli_bridge, mtp) and "Excluded 45 external apps by configuration". There were no compiler
  warnings.
- ./fbt lint: exit 0. Before building I ran the toolchain's clang-format on the changed files. It
  rewrapped three of my own lines in screen_reader.c and canvas.c and nothing else.
- tools/flash_headroom.sh: "firmware.bin 864420 bytes, limit 880640, spare 16220 bytes". That is
  776 bytes more than 863,644. The image that ./fbt flash_usb rebuilt with the committed hash has
  the same size and contains f9f1e168.
- Static RAM, from tools/map_size.py: 5,961 bytes, unchanged.
- ./fbt fap_passport: exit 0, "API version 87.3 is up to date", passport.fap 4,364 bytes.

## Flash and the fap copy

- pkill -f flipper_log.py, then pgrep -f flipper_log.py: nothing left, exit 1. The log's last line:
  "== log stopped 18:10:10".
- Baseline before the flash:
  - info device: hardware.name Delphi, firmware.commit.hash 9028a849, firmware.api.minor 2.
  - sr status: enabled yes; utterances 36, clips 87, fallback 3, missing 1.
  - loader info: No application is running.
- ./fbt flash_usb: exit 0. It rebuilt the version file ("API version 87.3 is up to date") and sent
  dist/f7-C/f7-update-mntm-screen-reader-f9f1e168 (firmware.dfu, update.fuf, updater.bin) to
  /ext/update. Its script printed "Closing current app, if any". No app was running, and I sent no
  loader close myself.
- The port dropped and was back after 16 seconds, then stayed present for 25 seconds. The first
  console look (below) showed the home screen. The boot had announced "Home screen": 1
  announcement, 2 clips. There was no post-update screen, so I did not send Back.
- Fap copy, from the project root:

      .venv/bin/python Momentum-Firmware/scripts/storage.py -p /dev/cu.usbmodemflip_Delphi1 send Momentum-Firmware/build/f7-firmware-C/.extapps/passport.fap /ext/apps/assets/passport.fap

  Reply: Sending "Momentum-Firmware/build/f7-firmware-C/.extapps/passport.fap" to
  "/ext/apps/assets/passport.fap", "<100%, chunk 1 of 1 @ 71.85 kb/s", exit 0. Before it,
  "storage stat /ext/apps/assets/passport.fap" said "File, size: 4156b". After it, "File, size:
  4364b". "storage md5" said fc7cc5e7fb7be3e0743bc7f33a96be87, the same as the local file's md5.

## Device checks, with commands and replies

All commands went through tools/flipper_cli.py's functions, in one port session per step, with a
small driver of mine (scratchpad dev.py). The driver's "idle" step polls sr status until speech is
idle with nothing queued. Its "mark" and "said" steps also wait until the utterance counter has
passed the mark. Replies are quoted as printed. For info device and storage read, only the relevant
lines are quoted; the settings file has about 60 keys. Clip counts are sr status's "voice: ...
clips N". The earlier "last crash: at 2001384F in build 9028a849" is Robin's crash test from before
this work and stayed unchanged. No new crash occurred.

Check 1, 18:13:06 to 18:13:21:
- sr screen: records 1, content layer desktop, status-right x=103 y=9 battery inverted "100", reads
  as (nothing).
- info device: firmware.commit.hash f9f1e168; firmware.commit.dirty true (the submodule);
  firmware.branch.name screen-reader; firmware.api.major 87; firmware.api.minor 3.
- loader info: No application is running.
- sr status: enabled: yes; volume 80, verbosity 1, change delay 3000 ms; frames 2, dropped 0,
  announcements 1, suppressed 0; speech idle, queued 0, utterances 1, aborted 0, dropped 0,
  underruns 0; voice on, vocabulary yes, clips 2, fallback 0, missing 0, muted 0; free heap 116616.
- storage read /int/.momentum_settings.txt: screen_reader: true.

Check 2, 18:13:31. The toggle chord on the home screen, reader on:
- Commands: input send back press, input send down press, input send down long, input send down
  release, input send back release.
- sr status 1.6 s later: enabled: no; frames 2, announcements 1; utterances 2, aborted 0; last
  utterance 1512 ms played; clips 5, fallback 0. So there was one utterance of 3 words, "Screen
  reader off", played in full.
- storage read: screen_reader: false.
- sr screen: desktop, battery "100".
- loader info: No application is running.

Check 3, 18:13:42. The same chord with the reader off:
- sr status 2.9 s later: enabled: yes; frames 3, announcements 1; utterances 3, aborted 0; last
  utterance 2820 ms played (2713 ms nominal); clips 10, fallback 0. So there was one utterance of 5
  words, "Screen reader on. Home screen", in that order and in full.
- The frame counter rose by one, which is the frame modelled quietly. The announcement counter did
  not rise. 4 seconds later sr status was unchanged (utterances 3, announcements 1, frames 3), so
  the screen was not read a second time.
- storage read: screen_reader: true.
- sr screen: desktop, battery "100".

Check 4, 18:13:59. The status chord (back press, down press, down short, down release, back
release):
- sr status 4.2 s later: utterances 4, aborted 0; last utterance 4135 ms played; clips 18. That is 8
  words: "battery one hundred percent, level two, mood happy".
- sr screen: still the desktop.

Check 5, sr chord downhold twice. The first attempt, at 18:14:12, was spoiled by my driver:
- Its idle poll read sr status before "Screen reader off" had started (enabled: no, utterances 4,
  clips 18; storage read: screen_reader: false).
- The second downhold, 1 second later, cut that utterance off: enabled: yes; utterances 6, aborted
  1; clips 24; storage read: screen_reader: true.
- This is why "aborted 1" appears from here on.

The clean run, 18:14:47:
- The first sr chord downhold replied "back + downhold: turn the reader off or on". Then: enabled:
  no; utterances 6 to 7; last 1503 ms played; clips 24 to 27 (3 words); storage read:
  screen_reader: false.
- The second replied the same. Then: enabled: yes; frames 5, announcements 1; utterances 7 to 8;
  last 2819 ms played; clips 27 to 32 (5 words); storage read: screen_reader: true.

Check 6, 18:15:07, in the brief's order:
- The toggle chord turned the reader off: enabled: no; utterances 9; last 1512 ms; clips 35.
- input send back press, input send up short, input send back release. 1.5 s later sr status still
  said utterances 9, clips 35: nothing was said, the reader was off.
- input send back short.
- The toggle chord: enabled: yes; frames 6, announcements 1; utterances 10; last 2815 ms played;
  clips 40, that is "Screen reader on. Home screen".
- sr screen: desktop. 3 s later, unchanged.

Check 6, supplementary, 18:15:28. This proves the lock menu opened:
- sr chord downhold: enabled: no; utterances 11; clips 43. The tool captured no reply line that
  time; the effect is as before.
- input send back press, input send up short, input send back release. 1.5 s later, the toggle
  chord.
- sr status: enabled: yes; frames 7, announcements 1; utterances 12; last 2164 ms played; clips 43
  to 47. That is 4 words: "Screen reader on. Lock".
- sr screen: records 1, content layer desktop, desktop x=0 y=0 secondary FOCUS NOTE "Lock", reads
  as "Lock". So the toggle read the screen as it was then, not the home screen from before the
  reader went off.
- input send back short: announcements 2, utterances 13, clips 49 ("Home screen"). sr screen:
  desktop.

Check 7, first run, 18:15:50, with the old fap still on the card (decision 5):
- input send right short: utterances 14; last 6115 ms; clips 49 to 59 (10 words).
- sr screen: 4 records. x=59 y=10 secondary "Delphi"; x=59 y=22 "Mood: Happy"; x=59 y=34 "Level:
  2"; x=59 y=42 battery "XP 7/100". Reads as "Delphi. Mood: Happy. Level: 2. XP 7/100".
- loader info: Application "Passport" is running.
- input send back short: utterances 15, clips 61. loader info: No application is running.
- Then the fap copy above.

Check 7, 18:16:50, with the new fap:
- input send right short. sr status 7.7 s later: enabled yes; frames 11, announcements 5;
  utterances 15 to 16; aborted 1 (unchanged); last utterance 7426 ms played; clips 61 to 74, that
  is 13 words; fallback 0 (unchanged).
- sr screen: records 5, content layer fullscreen:
  - x=59 y=10 secondary "Delphi"
  - x=59 y=22 secondary "Mood: Happy"
  - x=59 y=34 secondary "Level: 2"
  - x=59 y=42 battery "XP 7/100"
  - x=100 y=42 secondary NOTE "to level 3"
  Reads as "Delphi. Mood: Happy. Level: 2. XP 7/100 to level 3". Spoken: "Delphi. Mood, Happy.
  Level, two. experience seven of one hundred to level three". The 13 clips match these words.
  Delphi has a clip; no fallback.
- loader info: Application "Passport" is running.

Check 7, extra, the total view, 18:17:08:
- input send ok short: announcements 6, utterances 17, last 7264 ms, clips 74 to 88 (14 words).
  sr screen: x=59 y=42 battery "XP 107/9999", x=115 y=42 secondary NOTE "to level 30". Reads as
  "... XP 107/9999 to level 30".
- input send ok short again: clips 88 to 96 (8 words). sr screen: "XP 7/100", NOTE "to level 3" at
  x=100.
- input send back short: announcements 8, utterances 19, clips 98 ("Home screen"). loader info: No
  application is running.

Check 8, 18:17:32:
- input send ok short: utterances 20, clips 99. sr screen: fullscreen, x=22 y=36 primary FOCUS 1/11
  "Apps", reads as "Settings. Sub-GHz. Apps, 1 of 11".
- sr chord okhold replied "back + okhold: spell the focus". Then utterances 21, last 1672 ms
  played, clips 99 to 103: A, P, P, S.
- input send back short: announcements 10, utterances 22, clips 105 ("Home screen"). sr screen:
  desktop. loader info: No application is running.

Extra, tools/sr_drive.py --chords, 18:18, exit 0:

    home  desktop, no focus
    ok   home  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 1107 ms played, 15972 subsamples
    ok   home  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 4135 ms played, 65194 subsamples
    ok   home  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 1108 ms played, 16399 subsamples
    ok   home  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1108 ms played, 16399 subsamples
         menu  fullscreen, FOCUS 1/11 "Apps", reads as: Settings. Sub-GHz. Apps, 1 of 11
    ok   menu  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 4386 ms played, 68392 subsamples
    ok   menu  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 1919 ms played, 30010 subsamples
    ok   menu  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 2005 ms played, 30272 subsamples
    ok   menu  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1686 ms played, 24961 subsamples
    ok   end   home screen expected, got: desktop, no focus
    0 failures

Extra, the toggle while locked. This was a keypad lock only; no PIN was set or chosen.
- 18:18:37, input send up short: sr screen FOCUS NOTE "Lock".
- input send ok short: sr screen showed FOCUS 1/3 "Keypad Lock", "PIN Code Lock", "PIN Lock + OFF".
- 18:18:48, input send ok short locked the device. utterances 36; last 4136 ms; clips 146 to 154,
  that is 8 words: "Locked, press Back three times quickly to unlock". sr screen: NOTE "Locked, press
  Back 3 times quickly to unlock", bignumbers "18:17", "25-09-2026", battery "100".
- The toggle chord, then 4 s: enabled: yes; storage read: screen_reader: true. One utterance came
  with announcements 16 to 17 and clips to 166 in the end. That was a model announcement, the lock
  screen's own response to the key press, which the README documents. The toggle adds no
  announcement, and it did not run.
- sr chord downhold replied "back + downhold: turn the reader off or on", then 4 s: enabled: yes;
  utterances 37 and announcements 17, both unchanged. Ignored.
- Unlock, 18:19:28, with input send back short three times: utterances 40 ("Unlocked", "Home
  screen"; aborted 2, one cut by a Back). sr screen: desktop.
- After the unlock, 18:19:42, sr chord downhold twice: enabled: no, clips +3; then enabled: yes,
  clips +5; storage read: screen_reader: true. So the lock state had cleared.

Check 9, final, 18:19:54:
- sr status: enabled: yes; last crash: at 2001384F in build 9028a849 (the old one); volume 80,
  verbosity 1, change delay 3000 ms; frames 81, dropped 0, announcements 20, suppressed 1; speech:
  idle, queued 0, speaker held: no, utterances 42, aborted 2, dropped 0, underruns 0, queue dropped
  0; voice: on, vocabulary yes, clips 178, fallback 0, missing 0, muted 0; free heap 116560.
- loader info: No application is running.
- sr screen: records 1, content layer desktop, status-right battery "100".
- sr voice status: voice: on, vocabulary yes, clips 178, fallback 0, missing 0, muted 0.
- Log capture restarted from the project root with the brief's nohup command. pgrep showed pid
  86501 running tools/flipper_log.py docs/measurements/logs/2026-09-25-session.txt. The log shows
  "Current log level: debug".

The device is left on the home screen, reader on, voice on, speech idle.

## Self-review

- I read both commit diffs in full. The firmware changes are limited to the brief's files plus the
  canvas_i.h comment. applications/external is not included.
- The off-mode rule. With the reader off, Up, OK and Right while Back is held pass untouched, and
  Back's Short passes (test_off_back_up_passes). OK held long while Back is held passes too
  (test_off_back_alone). Down alone, short or long, passes (test_down_long_without_back and the end
  of test_toggle_changes_mode_mid_chord). Keys without Back held never reach any chord path in
  either mode. The one change from the old "every event passes" is Back itself. Its Long waits for
  the release and its Repeats are dropped, exactly as with the reader on (decision 1). And Down
  while Back is held is held back.
- The announcement order on toggle-on. It is one speech_say_parts call: "Screen reader on. " first,
  then the screen text. On the device this was one utterance of 5 words played in full, with
  nothing aborted.
- Not read twice. The frame is modelled quietly before speaking, so model.prev is the current
  screen. On the device the announcement counter stayed the same, the frame counter rose by one,
  and nothing was said in the next 4 seconds. The supplementary check read the lock menu rather
  than the home screen, so the text comes from a fresh frame, not a stale model.
- The CSV has exactly one new Function entry, canvas_tap_hint_note_at, next to the other
  canvas_tap_hint entries, and "Version,+,87.3,,". The build said "API version 87.3 is up to date"
  (twice).
- The positioned note never becomes a title. A row keeps its first record's note flag, and the
  title rule requires that flag to be clear. So a note alone, or a row a note begins, is never the
  title, even in the primary font at y 12 (tested). There is one nuance. A positioned note that
  joins a row begun by drawn text is part of that row, as drawn text would be. If that row is a
  drawn title (primary font, y 26 or less), the note's words are read as part of the title. The
  Passport's note sits at y 42 on a battery-font row, so it cannot happen there.
- Threads:
  - desktop_locked is written with __atomic_store_n on the desktop thread and read atomically on
    the service thread.
  - The chord state stays owned by the filter, under its lock.
  - The toggle's frame wait holds no mutex, so the GUI thread's 2 ms handover can proceed. It waits
    only for the frame flag, so lock and command flags stay set for the next loop iteration.

## Concerns and follow-ups

1. Decision 1, Back's own Long while the reader is off, needs Robin's yes or no.
2. Decision 2, the total view says "to level 30", is a small refinement of the brief.
3. Not tried on the device: the Accessibility screen's Screen Reader row shows the value it had
   when the screen opened. If the chord changes the setting while that screen is open, the row's
   text is stale until the screen is opened again. The setting itself stays right, and so does
   what the app saves. Example: the reader is off, the Accessibility screen is opened, and the chord
   turns the reader on. The reader would then read the row as "OFF".
4. With the reader off, a short Down pressed while Back is held is lost. This cannot be avoided
   while the chord drops what it drops with the reader on. The README says so.
5. If no frame comes within about 350 ms of the toggle-on, the reader says "Screen reader on" alone.
   That could happen with an app that draws directly. When a frame finally comes, it is announced
   as a new screen and may cut that short utterance. This was not seen on the device.
6. The README still gives /dev/cu.usbmodemflip_R0skie1 in some command examples, the storage.py
   lines under Useful commands and the rollback line. flipper_cli.py finds the port by itself, but
   those commands would fail as written. This is a small follow-up outside this brief.
7. Once, the console tool returned no reply line for a command, though the effect was there
   (check 6 supplementary). This is a quirk of the tool, not of the firmware.

# Fix round 1 (review findings with the controller's rulings)

Status: DONE_WITH_CONCERNS. The concerns are two small things that go past the letter of the rulings,
listed below. Firmware 4a4420439, parent f9f1e168f. Project 5ce5e21, parent 1a42046. Nothing pushed.
applications/external was not touched.

## What changed, per file

Firmware (4a4420439):

- screen_reader.c:
  1. The lock gate is gone: the check in the toggle handler, the desktop_locked field, its store in
     the desktop status callback, and its seeding from desktop_api_is_locked. The toggle now works
     on every screen. Its comment says so, with the reason: a reboot into a PIN lock with the reader
     off.
  2. The loop now calls sr_subscribe_desktop, and also sr_subscribe_dolphin (see "Beyond the
     rulings"), right after every wait, commands included. The frame branch no longer calls them.
     While either subscription is missing, the wait is capped at SR_SUBSCRIBE_POLL_MS, 250 ms. The
     comments that said frames drive the retry now describe the wake-up retry, and so does the
     startup comment. The timeout branch's comment names the new reason for waking.
  3. The input filter's comment (item 7) now says: while the reader is off, Back's own Long is
     delayed to its release and a Down pressed under Back is held back, as with the reader on;
     everything else passes.
  4. The frame handover is shared (item 9). A new helper, sr_model_ready(sr, now, key_recent,
     &count), holds the memcpy, the ready flag, the verbosity, sr_model_process and the frame
     counter. It returns false when no frame waits. sr_process and sr_model_screen_quietly both use
     it. The diff did not grow (42 lines added, 43 removed in this file, at that point), and the
     image shrank by 24 bytes.
  5. The comment on sr_model_screen_quietly now gives its real bound: 300 ms, plus one last 50 ms
     wait.
- sr_chords.h: one sentence on the timing difference (item 2). The chord begins at Down's Press
  with the reader on, but only at Down's Long with it off. So a Short of Back's that comes between
  the two, with Back let go first, is dropped with the reader on and passes with it off.
- canvas.h: the comment on canvas_tap_hint_note_at (item 5). It is never the focus. A row the note
  begins is never the title. A note that joins a row begun by drawn title-font text at the top of
  the screen is read inside that title.
- clang-format: the poll macro is named SR_SUBSCRIBE_POLL_MS, 20 characters. The first name, 21
  characters, made clang-format realign 17 unrelated #define lines.

Project (5ce5e21):

- tests/host/test_sr_chords.c:
  - New test test_off_down_outlives_back (item 2), with the reader off: Back press, Down press
    (dropped), Back Short passes, Back Release passes, then Down Long gives ToggleReader. The rest
    of the chord comes with the reader on and is dropped, and Down is plain again afterwards.
  - The lone Down Release in test_console_toggle_sequence is now checked as passing, && !drop
    (item 6). 208 checks.
- tests/host/test_screen_model.c (item 6): a note with a place at (100, 38) sits between "Level: 2"
  (y 34) and "XP 7/100" (y 42), outside the 2-pixel tolerance of both. It begins a row of its own,
  in reading order, with row.note set and no title. The description is "Level: 2. to level 3. XP
  7/100". 195 checks.
- README.md:
  - The chord line: held "until the long press registers, about a third of a second". Works while
    the reader is off and on every screen, the lock screen and the PIN entry included.
  - The "does nothing while locked" line became: it works on the lock screen too; after a reboot
    into a lock with the reader off, it is the way to get speech back.
  - The Accessibility row: "on any screen, including the lock screen", the same timing, and `sr on`
    "also turns the reader on; it reads the screen, without saying "Screen reader on" first".
  - The device-state and flash-history lines: 4a4420439, 864,396 bytes, 16,244 spare. The flash
    paragraph was rewrapped.
- docs/.../2026-09-22-flipper-screen-reader-design.md, section 18, the three closing paragraphs:
  - the lock gate dropped, and why;
  - the subscription poll, including the special boot, where the loop keeps waking every 250 ms;
  - Back's Short by mode;
  - "about 350 ms at most: 300 ms, then one last 50 ms wait" (item 8);
  - a screen longer than four parts loses its tail, as with Back and Up (item 8);
  - "Screen reader on. Nothing on screen" as a deliberate difference from the brief (item 3);
  - sr_model_ready shared;
  - the new figures, the new host test counts, and the device results below.

## Beyond the rulings, flagged

1. The dolphin's subscription is in the same wake-up retry as the desktop's. It had the same
   weakness: it was retried only on frames, and none come while the reader is off. The toggle-on's
   quiet wait also consumes the first frame's flag. So after a boot with the reader off, a status
   chord right after the toggle could have lacked the level and mood until another frame came. The
   poll condition is "desktop or dolphin missing". In a special boot neither service starts, and the
   loop wakes every 250 ms for the length of the update, as the desktop-only ruling would have made
   it do anyway.
2. The README's device-state and flash-history lines name 4a4420439 and its figures. The ruling
   listed only the wording fixes, but those lines would otherwise have been wrong.

## Tests

The three new cases passed before any code change: they describe behaviour the round-1 code already
had. So there was no RED to watch.

    208 checks, 0 failures   (chords, before any code change of this round)
    195 checks, 0 failures   (model, before any code change of this round)

To show that each can fail, I ran them against mutated scratch copies of the code; the real sources
were not touched.

- Mutation 1: with the reader off, the chord counts as used from Down's Press. Caught by the new
  test's Back Short check:

      FAIL line 227: feed_off(InputKeyBack, InputTypeShort, 200) == SrChordNone && !drop && !elong

- Mutation 2: the chord key is not let go at its Release. Caught by the new test and by the lone
  Release's new !drop:

      FAIL line 232: feed(InputKeyDown, InputTypePress, 700) == SrChordNone && !drop
      FAIL line 372: feed_off(InputKeyDown, InputTypeRelease, 30) == SrChordNone && !drop

- Mutation 3: a row a positioned note begins is not marked as a note's. Caught by the new model
  test, and by the existing Wi-Fi case:

      FAIL tests/host/test_screen_model.c:791: s.rows[1].note
      FAIL tests/host/test_screen_model.c:813: s.title_row == -1

GREEN, tools/run_host_tests.sh, exit 0, run twice (before the build and before the project commit):
model 195, speech text 968, queue 156, PCM 597, voice 4433, chords 208, throttle 119, all with 0
failures; fbt exclusions 0 failures; subghz sources 50/50.

## Build, lint, headroom

- ./fbt: exit 0. "API version 87.3 is up to date". Exactly two warnings, the known cli_bridge and
  mtp manifest ones. "Excluded 45 external apps by configuration".
- ./fbt lint: exit 0.
- tools/flash_headroom.sh: "firmware.bin 864396 bytes, limit 880640, spare 16244 bytes". That is 24
  bytes less than round 1's 864,420, and 752 more than 863,644.
- Static RAM (tools/map_size.py): 5,961, unchanged.
- The Passport fap was not rebuilt: nothing in this round touches it or the API. The card keeps
  round 1's copy.

## Flash

- pkill -f flipper_log.py, then pgrep: exit 1, nothing left. The log's last line: "== log stopped
  18:49:00".
- Before the flash, the device said: enabled: yes; utterances 54, aborted 5; clips 216, fallback 0;
  no application running. The counters had risen since my round-1 final check (utterances 42), so
  the device was used in between.
- ./fbt flash_usb: exit 0, "API version 87.3 is up to date". It sent
  dist/f7-C/f7-update-mntm-screen-reader-4a442043 (firmware.dfu, update.fuf, updater.bin). Its
  script printed "Closing current app, if any"; I sent no loader close myself.
- The port was gone at once, back after 22 s, and stable for 25 s by 47 s.

## Device checks, every reply

After the update, 18:50:43:
- sr screen: records 1, desktop, status-right x=103 y=9 battery inverted "100".
- info device: firmware.commit.hash 4a442043, firmware.commit.dirty true (the submodule),
  firmware.api.major 87, firmware.api.minor 3.
- loader info: No application is running.
- sr status: enabled: yes; last crash: at 2001384F in build 9028a849, the old one; frames 2,
  announcements 1; speech idle, utterances 1, aborted 0; voice on, clips 2, fallback 0.

(a) The home screen, 18:50:50:
- The toggle chord (input send back press, down press, down long, down release, back release). 1.6
  s later: enabled: no; utterances 2, aborted 0; last 1513 ms played; clips 5, that is "Screen
  reader off". storage read /int/.momentum_settings.txt: screen_reader: false.
- The chord again. 2.9 s later: enabled: yes; frames 3, announcements 1; utterances 3, aborted 0;
  last 2820 ms played; clips 10, that is "Screen reader on. Home screen". 4 s later: unchanged (no
  re-read). storage read: screen_reader: true. sr screen: desktop.

(b) Locking and the chord on the lock screen:
- 18:51:22, input send up short: announcements 2, clips 11. sr screen: FOCUS NOTE "Lock".
- input send ok short: announcements 3, clips 13. sr screen: FOCUS 1/3 "Keypad Lock", "PIN Code
  Lock", "PIN Lock + OFF", reads as "PIN Code Lock. PIN Lock + OFF. Keypad Lock, 1 of 3".
- 18:51:31, input send ok short, keypad lock, no PIN. sr status 4.3 s later: utterances 6; last 4135
  ms; clips 21, that is "Locked, press Back three times quickly to unlock"; suppressed 1. 2.5 s
  later, sr screen: records 4, NOTE "Locked, press Back 3 times quickly to unlock", bignumbers
  "18:49", "25-09-2026", battery "100".
- 18:51:38, the toggle chord. 1.6 s later: enabled: no; frames 14, announcements 5; utterances 8,
  aborted 1; last 1505 ms played; clips 25. So the Back press brought up the lock hint, a frame
  whose announcement started (1 clip) and was cut, and then "Screen reader off" played in full (3
  clips). 1 s later: unchanged. storage read: screen_reader: false.
- sr screen then showed 7 records: the NOTE "Locked, press Back 3 times quickly to unlock", "18:49",
  "25-09-2026", the NOTE "Press Back three times quickly to unlock", "Press 3x", "  to unlock!",
  battery "100".
- 18:51:50, the chord again on the lock screen. 19.4 s later: enabled: yes; frames 16,
  announcements 5, unchanged; utterances 9, aborted 1, unchanged; last utterance 19290 ms played,
  19210 ms nominal; clips 25 to 60, that is 35; fallback 0.
- The 35 clips are exactly the words the host's pronunciation layer makes of that 7-record screen,
  after "Screen reader on. ": "Screen reader on. Locked, press Back three times quickly to unlock.
  Press Back three times quickly to unlock. Press three x. to unlock!. twenty five dash zero nine
  dash two thousand twenty six. eighteen fifty". The 4-record screen would have been 23 words.
- sr screen at 18:52:10: the hint had timed out, leaving 4 records: NOTE "Locked, ...", "18:50",
  "25-09-2026", battery. storage read: screen_reader: true. 4 s later: unchanged.
- 18:52:40, input send back short three times in one invocation. 1.9 s later: frames 21,
  announcements 8, that is +3: the hint, "Unlocked", "Home screen"; utterances 12, aborted 2; last
  1098 ms played ("Home screen"); clips 64. 3 s later: unchanged. sr screen: desktop, battery.
  loader info: No application is running.

Extra, a boot with the reader off:
- 18:53:13, sr off replied "screen reader off": enabled: no, nothing said. storage read:
  screen_reader: false.
- power reboot. The port node was recreated at 18:53 and stable from 18:54.
- 18:54:20, sr status: enabled: no; frames 0, announcements 0; utterances 0; voice on, vocabulary
  no (it is loaded at the first utterance), clips 0. sr screen: records 0, desktop. loader info: No
  application is running.
- The toggle chord. 2.9 s later: enabled: yes; frames 1, announcements 0; utterances 1, aborted 0;
  last 2814 ms played; vocabulary yes; clips 5, that is "Screen reader on. Home screen".
- At once, the status chord (back press, down press, down short, down release, back release). 4.2
  s later: frames 1, so no frame came in between; utterances 2; last 4136 ms played; clips 13. That
  is 8 words, "battery one hundred percent, level two, mood happy", with the level and mood. (This
  shows the dolphin was subscribed without frames. It cannot tell the poll from the start-up
  attempt, which may already have found the dolphin's record.)

(c) Final, 18:54:46:
- sr status: enabled: yes; last crash: at 2001384F in build 9028a849, the old one; volume 80,
  verbosity 1, change delay 3000 ms; frames 1, dropped 0, announcements 0, suppressed 0; speech:
  idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped
  0; voice: on, vocabulary yes, clips 13, fallback 0, missing 0, muted 0; free heap 116624.
- loader info: No application is running.
- sr screen: records 1, desktop, battery "100".
- storage read: screen_reader: true, sr_volume: 80.
- info device: 4a442043, API 87.3.
- Log capture restarted with the brief's nohup command, pid 88862, "Press CTRL+C to stop...".

The device is left on the home screen, reader on, voice on, speech idle.

## Remaining concerns

1. The dolphin retry goes past the ruling (see "Beyond the rulings" 1). It is a trivial revert if
   unwanted.
2. On the lock screen the toggle-on reads the lock hint that the chord's own Back press brings up.
   That makes it long: 35 words, about 19 seconds. It is what Back and Up would read at that
   moment. Any key silences it.
3. Not tried on the device, because it needs a PIN, which I must not set: a PIN lock at boot, or the
   PIN entry. The code path is the same as on the keypad lock screen.
