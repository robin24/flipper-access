# Final fix wave report, phase 3

Status: DONE_WITH_CONCERNS. The concerns are listed at the end. The biggest one: the lock screen's own note says "3" instead of "three", because the full sentence does not fit. Nothing was pushed. applications/external was not touched. The repo-root voice/ folder only gained the quickly clip.

## Commits

Firmware, branch screen-reader, base 6c7469a79:
- af4ee0952 "screen reader: lock sentences say quickly, muted volume keeps its level, re-enable reads the screen". It has a body and the Co-Authored-By line.
- Files: applications/services/screen_reader/screen_reader.c, applications/services/screen_reader/screen_reader.h, applications/services/desktop/views/desktop_view_locked.c and applications/services/desktop/views/desktop_view_lock_menu.c. They were added and committed by explicit path.

Project, branch main, base 5230ae5:
- 43fa74b "docs: final review wording; quickly clip". It has a body and the Co-Authored-By line.
- Files: README.md, docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md and tools/voice_words.txt. They were added and committed by explicit path.
- This commit was made after the device checks, so the README could name the commit that was flashed and verified.

## What changed

Item 1, the long idle:
- README Known limits now says: "Twice, after a long idle, the first OK that the scripted driver `tools/sr_drive.py` sent on the home screen opened the lock menu instead of the main menu. It has not been reproduced since and is not explained. Up, not OK, is the default key for the lock menu. Back closes it."
- Known limits in the spec's as-built list has the same content.
- Where it comes from: the phase 2 ledger, line 85, reads "the first synthetic OK after a long idle, which opened the lock menu instead of the main menu", from the sr_drive sessions.

Item 2, turning the reader back on:
- The frame tap now tracks the change. sr_frame_begin keeps the previous value of `capturing`. When the setting goes from off to on, it sets `turned_on`.
- The next frame that sr_frame_end hands over, under the mutex, clears `model.have_prev`. That is the same field `sr on` clears. The model then announces that frame as a new screen.
- The GUI-side flag stays set until a frame is actually handed over, so a missed 2 ms mutex wait does not lose it.
- An addition beyond the brief: screen_reader_set_enabled now clears have_prev before it stores and saves the setting, not after.
  - Without this, `sr on` from off could announce twice. A frame drawn during momentum_settings_save would be announced by the new turn-on path, and then announced again after the save's reset.
  - When the reader was already on, `sr on` behaves as before: it reads the screen again.
- README: "Right turns the reader back on and the screen is read again: you hear "Screen Reader ON"." Those are the words seen on the device. The new-screen announcement is the title plus the focus, and this scene has no title.

Item 3, "quickly":
- The reader's constant SR_LOCKED_TEXT is now "Locked, press Back three times quickly to unlock", exactly as in the brief.
- The lock screen's hint note is now "Press Back three times quickly to unlock", exactly as in the brief.
- The lock screen's base note is now "Locked, press Back 3 times quickly to unlock". This is a deviation from the brief:
  - The brief's sentence has 48 characters. A note keeps 47: CANVAS_TAP_TEXT_MAX and SR_TEXT_MAX are both 48 with the terminator.
  - So the sentence would have been cut to "...quickly to unloc".
  - The digit is spoken as "three". A host check ran speech_text_expand on the digit form and got "Locked, press Back three times quickly to unlock", identical to the constant.
  - The comments in both files say why.
- README: both lock sentences say "quickly". The spec's as-built Lock bullet has both sentences, the 600 ms reason and the digit note.
- tools/voice_words.txt gained "quickly".

Item 4, the muted volume:
- In stealth mode the lock menu's Volume note is now "Volume N, muted", keeping the level. It is built by one snprintf with "%s %d%s".
- The README and the spec's as-built Desktop bullet both give the example "Volume 95, muted".

Item 5, the header comment:
- `suppressed` now reads: "desktop announcements not spoken: its changes, and its text going away, with no key press within 2 s; and for 2 s after a lock announcement, or until a key press, every desktop announcement".

Item 6, the third key:
- README chord paragraph: "A third key pressed while the second is still held goes to the app as a normal key."
- Checked against sr_chords_feed: while chord_key is 0 or more, another key that is not Back falls through with drop false.

Other document lines beyond the six items:
- README Device state now names af4ee0952.
- The README flash paragraph adds "af4ee0952: 876,056 bytes, 4,584 spare".
- The spec's section 17 status paragraph and its Budget bullet carry the same figures.
- The spec's as-built Accessibility scene bullet describes the re-read.
- The spec's as-built Vocabulary bullet names the quickly clip.

## Checks on the Mac

Host runner:

    TMPDIR=/private/tmp/claude-501/-Users-robin-Downloads-flipper-access/7e5c805a-c471-4df7-96ca-14e7ee87ded9/scratchpad/p3fw tools/run_host_tests.sh

It exited with 0:

    159 checks, 0 failures
    port checks: 0 failures
    SAM port matches the original on 11 cases
    speech text: 1022 checks, 0 failures
    speech queue: 156 checks, 0 failures
    speech PCM: 700 checks, 0 failures
    speech voice: 4433 checks, 0 failures
    chords: 73 checks, 0 failures

./fbt, run after the commit, exited with 0:
- Its only warnings are the two known ones: "Failed parsing manifest .../applications/external/cli_bridge/application.fam : Invalid appid '.cli_gui'" and ".../applications/external/mtp/application.fam : Invalid appid '.f0_mtp'".
- It printed "API version 87.2 is up to date".
- It compiled desktop_view_lock_menu.c, desktop_view_locked.c, screen_reader.c and screen_reader_cli.c on the first build, and version.c on the build after the commit.
- It printed "firmware.bin:  214 flash pages (last page 88.09% full)".

./fbt lint exited with 0. Its only warnings are the same two manifest warnings.

tools/flash_headroom.sh:

    firmware.bin 876056 bytes, limit 880640, spare 4584 bytes

That is 128 bytes more than 6c7469a79, which had 875,928 bytes and 4,712 spare.

## Device

Log capture:
- Stopped at 17:55:28 (pid 89649). The log tail showed no crash, and nothing but animation and Bluetooth lines since 17:15.
- Restarted at 18:01:56 (pid 92251), with the command from the project root.

Idle check, 17:55:46 to 17:56:16:

    17:55:46 No application is running | announcements 76 utterances 93 speech ('idle', 0)
    17:56:16 No application is running | announcements 76 utterances 93 speech ('idle', 0)
    IDLE

Flash:
- `./fbt flash_usb` ran from 17:56:22 to 17:56:57 and exited with 0. The package was f7-update-mntm-screen-reader-af4ee095.
- The port was gone at 17:57:06 and back at 17:57:26.

sr screen first, at 17:57:47, showed no popup:

    records: 1, content layer: desktop
    status-right x=103 y=  9 battery    inverted "100"
    reads as:

info device:

    firmware.commit.hash          : af4ee095
    firmware.commit.dirty         : true
    firmware.branch.name          : screen-reader
    firmware.version              : mntm-dev
    firmware.build.date           : 24-09-2026
    firmware.api.major            : 87
    firmware.api.minor            : 2
    system.stealth                : 1

The dirty flag comes from the modified applications/external submodule, which was there before and was left alone.

After boot, at 17:58:04:

    frames: 80, dropped: 0, announcements: 1, suppressed: 2
    speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
    last utterance: 1105 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
    free heap: 110208

### Vocabulary

`.venv/bin/python tools/voice_build.py --extract --pull-missing --sync` ran from 17:58:10 to 17:58:13, 3.1 s:

    extract: 6249 distinct strings from the firmware sources, 71 bubble texts
    extract: 2894 words; longest: animationmanager animationstorage ...
    extract: 10 with an apostrophe: can't doesn't don't flipper's i'll i'm isn't it's who's you're
    voice: silenced for the transfer
    pulled 0 missing words from the device
    voice: restored
    2903 words, 1 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
    made 1 clips, 0 failed, 1 s; vocabulary 2928 words in /Users/robin/Downloads/flipper-access/voice
    voice: silenced for the transfer
    sync: 1 sent, 2927 skipped, 0 missing, 0 failed, 0 s
    voice: restored

The one clip made is "quickly":
- Locally it is voice/q/quickly.raw, 7,876 bytes.
- On the card, `storage stat /ext/sr/voice/2b/quickly.raw` answers "File, size: 7876b".
- At the end of the device work, `sr voice status` showed "clips 91, fallback 0, missing 0", so every word was spoken from a clip, "quickly" included.

### Lock from the lock menu

Up, then OK on Lock, with `input send` and a check at each step:

    17:58:50 start: announcements 1, suppressed 2, utterances 1, aborted 0, dropped 0; last 1105 ms played, 15972 subsamples, 998 ms nominal
    17:58:50 input send up short
    17:58:50 after Up: announcements 2, suppressed 2, utterances 2, aborted 0, dropped 0; last 441 ms played, 6351 subsamples, 396 ms nominal
    desktop      x=  0 y=  0 secondary  FOCUS NOTE "Lock"
    17:58:50 input send ok short
    17:58:52 after OK: announcements 3, suppressed 2, utterances 3, aborted 0, dropped 0; last 1014 ms played, 15690 subsamples, 980 ms nominal
    desktop      x= 38 y= 19 secondary  FOCUS 1/3 "Keypad Lock"
    desktop      x= 35 y= 35 secondary  "PIN Code Lock"
    desktop      x= 32 y= 51 secondary  "PIN Lock + OFF"
    reads as: PIN Code Lock. PIN Lock + OFF. Keypad Lock, 1 of 3

The script would have stopped unless Keypad Lock had the focus.

Then OK, sent through sr watch:

    17:59:04 before the lock: announcements 3, suppressed 2, utterances 3, aborted 0, dropped 0; last 1014 ms played, 15690 subsamples, 980 ms nominal
    screen: PIN Code Lock. PIN Lock + OFF. Keypad Lock, 1 of 3
    17:59:05 sr watch: Enter (OK on Keypad Lock)
    lock: Locked, press Back three times quickly to unlock
    change: Locked, press Back 3 times quickly to unlock. 24-09-2026. 17:58
    change: So long and. thanks for. 24-09-2026 all the fish!
    change: 24-09-2026
    stopped
    17:59:14 after the lock: announcements 4, suppressed 5, utterances 4, aborted 0, dropped 0; last 4132 ms played, 65151 subsamples, 4071 ms nominal
    delta: announcements +1, suppressed +3, utterances +1, aborted +0
    desktop      x=  0 y=  0 secondary  NOTE "Locked, press Back 3 times quickly to unlock"
    desktop      x=  0 y= 64 bignumbers "17:58"
    desktop      x=  0 y= 48 secondary  "24-09-2026"
    reads as: Locked, press Back 3 times quickly to unlock. 24-09-2026. 17:58

The sentence was spoken in full:
- It was one utterance, and aborted stayed at +0.
- It played 4,132 ms against 4,071 ms nominal.
- The three changes after it were suppressed, the lock screen arriving and the bubble behind the cover among them.

### Three quick Backs

Sent through sr watch, 150 ms apart:

    17:59:26 before the unlock: announcements 4, suppressed 5, utterances 4, aborted 0, dropped 0; last 4132 ms played, 65151 subsamples, 4071 ms nominal
    screen: Locked, press Back 3 times quickly to unlock. 24-09-2026. 17:58
    17:59:27 sr watch: Backspace three times, 150 ms apart
    change: Press Back three times quickly to unlock. Press 3x. to unlock!
    lock: Unlocked
    home: Home screen
    change: So long and. thanks for. all the fish!
    home: Home screen
    stopped
    17:59:35 after the unlock: announcements 8, suppressed 6, utterances 8, aborted 1, dropped 0; last 4291 ms played, 67546 subsamples, 4221 ms nominal
    delta: announcements +4, suppressed +1, utterances +4, aborted +1
    records: 1, content layer: desktop

What the lines show:
- The next Back cut the hint, which is the aborted +1, the same as in Task 4.
- Then came "Unlocked" and "Home screen".
- A dolphin bubble followed within 2 s of the key press. Its vanishing "Home screen" was suppressed.

### Lock menu Volume tile, in stealth mode

`info device` showed system.stealth 1.

    17:59:48 input send up short -> desktop      x=  0 y=  0 secondary  FOCUS NOTE "Lock"
    17:59:49 input send right short -> desktop      x=  0 y=  0 secondary  FOCUS NOTE "Momentum"
    17:59:51 input send right short -> desktop      x=  0 y=  0 secondary  FOCUS NOTE "Brightness 100"
    17:59:54 input send right short -> desktop      x=  0 y=  0 secondary  FOCUS NOTE "Volume 95, muted"
    reads as: Volume 95, muted
    17:59:54 counters: announcements 12, suppressed 6, utterances 12, aborted 1, dropped 0; last 2328 ms played, 36373 subsamples, 2273 ms nominal
    17:59:55 input send back short -> records: 1, content layer: desktop | announcements 13, suppressed 6, utterances 13, aborted 1, dropped 0; last 1097 ms played, 15972 subsamples, 998 ms nominal

- Up and Down were not pressed on the slider, so no level changed.
- Back said "Home screen" (15,972 subsamples).

### Accessibility screen, Screen Reader OFF then ON

The path from the home screen, each focus checked before the next key:

    18:00:18 input send ok short -> FOCUS 1/11 "Apps" | reads as: Settings. Sub-GHz. Apps, 1 of 11
    18:00:19 input send up short -> FOCUS 11/11 "Settings" | reads as: Momentum. Apps. Settings, 11 of 11
    18:00:20 input send up short -> FOCUS 10/11 "Momentum" | reads as: U2F. Settings. Momentum, 10 of 11
    18:00:27 input send ok short -> inverted FOCUS 1/4 "Interface" | reads as: MNTM-DEV AF4EE095. Protocols. Misc. Interface, 1 of 4
    18:00:29 input send up short -> inverted FOCUS 4/4 "Accessibility" | reads as: MNTM-DEV AF4EE095. Protocols. Misc. Accessibility, 4 of 4
    18:00:30 input send ok short -> inverted FOCUS 1/5 "Screen Reader" | reads as: Voice Recorded. Rate 72. Volume 70. Screen Reader ON, 1 of 5
    18:00:30 on the Screen Reader row: announcements 20, suppressed 7, utterances 20, aborted 1, dropped 0; last 1509 ms played, 22644 subsamples, 1415 ms nominal

Round 1, with Left and Right both sent by `input send`:

    18:00:47 before Left: announcements 20, suppressed 7, utterances 20, aborted 1, dropped 0; last 1509 ms played, 22644 subsamples, 1415 ms nominal
    18:00:49 input send left short; after 1.5 s: enabled: no | announcements 20, suppressed 7, utterances 20, aborted 1, dropped 0; last 1509 ms played, 22644 subsamples, 1415 ms nominal | delta announcements +0, utterances +0, aborted +0
    18:00:49 sr screen while off (the model's last screen): reads as: Voice Recorded. Rate 72. Volume 70. Screen Reader ON, 1 of 5
    18:00:50 input send right short; when idle: enabled: yes | announcements 21, suppressed 7, utterances 21, aborted 1, dropped 0; last 1509 ms played, 22644 subsamples, 1415 ms nominal | delta announcements +1, utterances +1, aborted +0
    18:00:50 sr screen: fullscreen   x=  6 y= 12 secondary  inverted FOCUS 1/5 "Screen Reader" | reads as: Voice Recorded. Rate 72. Volume 70. Screen Reader ON, 1 of 5

Round 2, with Left sent by `input send` and Right by sr watch, to see the text:

    18:00:50 before Left: announcements 21, suppressed 7, utterances 21, aborted 1, dropped 0; last 1509 ms played, 22644 subsamples, 1415 ms nominal
    18:00:52 input send left short; after 1.5 s: enabled: no | announcements 21, suppressed 7, utterances 21, aborted 1, dropped 0; last 1509 ms played, 22644 subsamples, 1415 ms nominal | delta announcements +0, utterances +0, aborted +0
    screen: Voice Recorded. Rate 72. Volume 70. Screen Reader ON, 1 of 5
    18:00:53 sr watch: Right
    screen: Screen Reader ON
    stopped
    18:01:00 when idle: enabled: yes | announcements 22, suppressed 7, utterances 22, aborted 1, dropped 0; last 1509 ms played, 22644 subsamples, 1415 ms nominal | delta announcements +1, utterances +1, aborted +0

What the rounds show:
- The first "screen:" line in round 2 is the watch printing the current screen as it starts. It is not an announcement.
- The Right press was announced as a new screen, "Screen Reader ON", once in each round: utterances +1, aborted +0.
- Before this fix, that frame equalled the model's stale previous screen, so it was never announced.
- The last-utterance figures (1,509 ms, 22,644 subsamples) did not change. They match the "Screen Reader ON" that was said when the scene opened, which is the same text.

### Back to the home screen

    18:01:36 input send back short -> records: 7, content layer: fullscreen | FOCUS 4/4 "Accessibility" | reads as: MNTM-DEV AF4EE095. Protocols. Misc. Accessibility, 4 of 4
    18:01:38 input send back short -> records: 3, content layer: fullscreen | FOCUS 10/11 "Momentum" | reads as: U2F. Settings. Momentum, 10 of 11
    18:01:41 input send back short -> records: 3, content layer: desktop |  | reads as: I am happy,. my friend!
    No application is running

### Final state, 18:01:49

    No application is running
    enabled: yes
    rate: 72, volume: 70, verbosity: 1
    frames: 853, dropped: 0, announcements: 26, suppressed: 8
    speech: idle, queued 0, speaker held: no, utterances 26, aborted 1, dropped 0, underruns 0, queue dropped 0
    last utterance: 2576 ms played, 39989 subsamples, 2499 ms nominal, worker stack free 2508
    voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 91, fallback 0, missing 0, open max 37 ms, last 37 ms
    free heap: 110248
    records: 1, content layer: desktop

The device ended on the home screen with the reader on, the voice on and speech idle. Stealth mode is unchanged at 1. The settings are unchanged; the app saved ON, which it already was. Log capture is running.

## Concerns

1. The lock screen's note has the digit form "Locked, press Back 3 times quickly to unlock".
   - It is spoken the same as the brief's sentence, but `sr screen` and Back plus Up show "3".
   - The alternative is to raise CANVAS_TAP_TEXT_MAX and SR_TEXT_MAX to 49 or more. That costs heap: about 64 bytes per SrFrame, with three frames in the reader. It also moves where drawn runs are cut. I did not do it before the memory plan.
2. The reorder in screen_reader_set_enabled was not asked for. It prevents a possible double announcement on `sr on` from off, which only the new turn-on path could cause. It was not exercised on the device: the device check used the settings scene, as the brief said.
3. The re-read announces the screen the way arriving on it does. For the Accessibility scene that is only "Screen Reader ON", not the whole list, and the README says so.
4. Some document lines go beyond the six items: the README device state and flash figures, the spec's status paragraph and Budget bullet, and the spec's as-built bullets for the new sentences, the digit note, the muted tile, the re-read and the clip.
   - docs/roadmap.md still says phase 3 left 875,928 bytes and 4,712 spare. It is not in this wave's file list, so I left it.
   - This wave's device outputs are only in this report, which is gitignored. They are not in docs/measurements/2026-09-24-phase-3.txt, which the README cites.
5. Two known limits showed again during the lock check:
   - A dolphin bubble joined the date row under the lock cover: "So long and. thanks for. 24-09-2026 all the fish!". It was suppressed.
   - The hint after a Back is also read with the visual prompt ("Press 3x. to unlock!"). It was cut by the next Back.
