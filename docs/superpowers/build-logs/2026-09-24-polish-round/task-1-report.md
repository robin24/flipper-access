# Task 1 report: change throttle in the reader, setting, console

Status: DONE_WITH_CONCERNS

Everything in the brief is built, tested and verified on the device. There is one deliberate deviation: the model's own 1.5 s drop limiter is removed (see Deviations, item 1). The main concern is the default: at 1500 ms the progress bar is now spoken more often than before (see Concerns, item 1).

## Commits

Firmware, branch screen-reader (base af4ee0952):

- 89b27e897 screen reader: change throttle module (sr_throttle.h, sr_throttle.c)
- f625f9d04 screen reader: same-screen changes spoken at most once per change delay (screen_reader.c, screen_reader_cli.c, screen_model.c, screen_model.h, lib/momentum/settings.h, lib/momentum/settings.c)

Project, main (base 996c82c):

- d5dd1b9 host tests: change throttle (tests/host/test_sr_throttle.c, tools/run_host_tests.sh)
- 8fcfb19 host tests: the model reports every change; the throttle spaces them (tests/host/test_screen_model.c)

Nothing pushed. applications/external was not touched. README.md and tools/voice_build.py belong to Task 3, which runs in parallel, and are not in any of these commits.

## What was built

- sr_throttle: offer, due, wait_ms, clear, init, with the brief's interface. A change is said at once when the delay has passed since the last change was said. Otherwise it is held, a newer change replaces it, and the latest is said when its time comes. Tick differences are unsigned 32 bit, so the wrap is harmless.
- sr_process: after the desktop suppression decision, a change goes to sr_throttle_offer. If the offer is true, it is said as before. If false, it is held and not mirrored yet. Every other kind that is spoken (screen, focus, home, typed) clears the throttle first, and so does sr_say_lock. A key press does not clear it.
- Service loop: the wait is the smaller of today's frame timeout and sr_throttle_wait_ms when a change is held (0 when it is already due). After every wait, sr_say_held_change says a due change with speech_say(text, false, true). That is the same kind of call as any change: it pushes the voice first, counts the announcement and mirrors it to sr watch. A frame still settling when the throttle woke the loop is not processed early.
- Setting: `sr_change_ms`, default 1500, `setting_uint(sr_change_ms, 500, 3000)`, added at the end of MomentumSettings as the other reader fields were.
- Console: `sr status` prints `change delay N ms` on the rate line. `sr delay <ms>` sets and saves it; out of range or missing, it prints the bounds and the current value. The usage text lists it.

## Tests, build, lint, headroom

Host runner (TMPDIR=.../scratchpad/pr1 tools/run_host_tests.sh), exit 0:

```
170 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1022 checks, 0 failures
speech queue: 156 checks, 0 failures
speech PCM: 700 checks, 0 failures
speech voice: 4433 checks, 0 failures
chords: 73 checks, 0 failures
throttle: 88 checks, 0 failures
```

Test first: with the runner block appended and no module yet, the runner stopped with `clang: error: no such file or directory: '.../screen_reader/sr_throttle.c'`, exit 1. The old model test failed against the changed model (`test_screen_model.c:289: n == 0`) before it was rewritten.

`./fbt`, exit 0. Apart from the compile lines, it printed only these:

```
fbt: warning: Failed parsing manifest '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui'. Must match regex 're.compile('^[a-z0-9_]+$')'
fbt: warning: Failed parsing manifest '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/mtp/application.fam' : Invalid appid '.f0_mtp'. Must match regex 're.compile('^[a-z0-9_]+$')'
API version 87.2 is up to date
```

`./fbt lint`: exit 0.

`tools/flash_headroom.sh`: `firmware.bin 876892 bytes, limit 880640, spare 3748 bytes` (was 4,584; this task uses 836 bytes).

## Device verification, numbered as in the brief

Before the flash: the log capture was not running (it had ended at 18:18:20 when the port dropped), so there was nothing to stop. Idle check passed: no application, and announcements flat at 845 from 19:41:24 to 19:41:54. The device ran af4ee095. I made one baseline send with that old firmware (Appendix A). Then `./fbt flash_usb` ran, exit 0, and the device came back on f625f9d0. `sr screen` showed the home screen with no crash popup. `info device` showed commit f625f9d0 with API 87.2. `sr status` showed `rate: 76, volume: 80, verbosity: 1, change delay 1500 ms`, and the bounds of `sr delay` held (Appendix B). Robin's own rate 76 and volume 80 were kept.

In every send below, the TV database had 324 signals, so a send runs for about 100 s, not about ten. Times are measured on the Mac when each sr watch line arrives, so they carry about 20 ms of jitter; the device-side spacing is at least the delay by construction.

(1) Change delay 1500 ms, Infrared, Universal Remotes, TVs, OK on Power (Appendix C, send 1):

- The first change, "Sending.... 0%. stop. pause", came 0.13 s after OK.
- From then on there was one change every 1.50 s: 66 changes in all. Every gap was 1.50 s (one 1.51 s), except one 1.67 s and one 1.99 s, where no newer step was being held at the due time.
- Every change said was the latest step: 2%, 4%, 7%, 9% and so on. The steps were never all spoken; the percentage jumped by 1 to 3 each time.
- The last change was "98%" at 98.29 s. The send ended with the screen announcement "TVs. Power" at 99.72 s, and nothing was said after it.
- Counters over the send: announcements +68, utterances +64, aborted +2, suppressed +0. The +68 includes the TVs panel's own announcement, which arrived as the watch opened.

Baseline, same send with the old firmware (Appendix A): 49 changes. Gaps were 1.55 to 3.05 s, about 2.06 s on average, because the old model dropped changes and then waited for the next step. Counters: announcements +51, utterances +50.

(2) The same send at other delays (Appendix C, sends 2 and 3), then restored to 1500:

- 3000 ms: 33 changes, every gap 3.00 s. Counters: announcements +34, utterances +34, aborted +0. Fewer.
- 500 ms: 100 changes, smallest gap 0.50 s. The early gaps were about 0.6 s (one per step) and the later ones about 1.2 s, because the steps themselves slowed down. Counters: announcements +101, utterances +64, aborted +1. More: speech could not keep up, and a waiting change was replaced by the next one, so no backlog built up.
- Restored: `sr delay 1500` answered `change delay set to 1500 ms`. The settings file holds `sr_change_ms: 1500` (Appendix H).

(3) Announcements during a running bar. The progress popup takes every arrow key while it sends (its input callback consumes Short, Long and Repeat), so no focus can move during this bar. I used the popup's own keys instead: OK pauses, Back resumes, and Back stops. Each of these is announced as a screen, the same kind of path as a focus: the throttle is cleared first and the announcement is said at once.

- Run 1, the full send (Appendix D). "6%" was said at 4.63 s. OK (pause) at 5.89 s gave "screen: TVs. Power" at 6.09 s, 0.20 s after the key. Nothing was said at 6.13 s, when a held change would have been due, so it was dropped. Back (resume) at 8.91 s gave the screen at 9.01 s, 0.10 s after the key. The next change, 10%, came at 9.81 s and was said at once (5.2 s had passed since the last change); after that the gaps were 1.5 s.
- Run 2, short and instrumented, with Back stopping the send at 13 s (Appendix E):
  - "4%" was said at 3.13 s. Tab at 4.29 s printed the screen the reader had just modelled: `TVs. Sending.... 6%. stop. pause. Power`. So "6%" was being held, which shows that the text held is the latest.
  - OK (pause) at 4.38 s. The held "6%" was said at its due time, 4.64 s. The pause screen came at 4.69 s, 0.31 s after the key, and interrupted it. See Concerns, item 2.
  - Tab while paused: `TVs. Paused. 23/324. resume. send 1. select. Power`.
  - Back (resume) at 7.40 s gave the screen at 7.51 s. The changes 8%, 10%, 12% and 14% followed at 1.5 s gaps.
  - Back (stop) at 13.41 s gave "screen: TVs. Power" at 13.62 s.

(4) sr_drive. The default run covers all three sessions: menus, the text2sam keyboard and the chords. It reported `0 failures`, and `--chords` on its own reported `0 failures` too (Appendices F and G).

End state (Appendix H): no application; home screen; reader on; voice on; speech idle with nothing queued; change delay 1500 ms. The log capture was restarted with the brief's command (pid 98127) and is writing to docs/measurements/logs/2026-09-24-session.txt.

## Deviations

1. The model's own spontaneous limiter is removed (screen_model.c and .h, with its host test rewritten in the project repo). Until now, sr_model_process dropped any change without a key press that came within 1.5 s of the last such change. Left in front of the throttle, that drop breaks the throttle in two ways:
   - The delay can never go below 1.5 s, so `sr delay 500` could not give more announcements, which the brief's step (2) requires.
   - The held text goes stale. The model emits only every 1.5 s on its own clock, and the throttle releases 1.5 s after its last release. Worked through for this bar: each spoken percentage would be about a second old.

   The model now reports every change and the throttle does all the spacing. It still cuts a change without a recent key at 80 characters, and a new test covers that. The `now_ms` parameter stays in the signature and is documented as reserved, as sr_chords_feed already does. The `last_spontaneous_ms` field is gone.
2. SrThrottle has one field more than the brief's struct: `bool said`. The brief's first case needs the first change after init to be said at once at tick 1000 with a 1500 ms interval. That cannot be told apart from a change at tick 0 without a flag.
3. Console mirror: a held change reaches sr watch when it is said. A change that is replaced or dropped while held never appears. Spec section 6 says the mirror receives every announcement; even before this task, the model's drop kept changes out of it.
4. Wrap-around test. Read literally, "offer at 0xFFFFFF00, due at 0x00000100 with interval 1000 true" is only true if the last say was at or before 0xFFFFFD18, because the two ticks are just 512 ms apart. The test therefore says "a" at 0xFFFFFC00, 1024 ms before the wrap, and holds "b" at 0xFFFFFF00. It checks that the wait there is 232 ms, that "b" is not due at 0xFFFFFFE0 (992 ms), and that it is due at 0x00000100 (1280 ms), across the wrap.
5. More throttle cases than the brief lists:
   - A due change collected late is still said.
   - A change said at once drops the change held before it.
   - The first change is said at once even at tick 0.
   - A smaller output buffer gets a terminated text.
6. Extra device work:
   - One baseline send with the old firmware before the flash.
   - Two pause runs for item (3); the second stopped the send after 13 s.
   - In total, six sends transmitted the TV power codes: the baseline, 1500, 3000, 500, pause run 1 in full, and pause run 2 for 13 s.
7. The status wording follows the brief literally: `change delay 1500 ms`, with no colon, unlike the other fields on that line.

## Concerns

1. At the default of 1500 ms, this progress bar is spoken more often than before: 66 announcements against 49 with the old firmware over the same 99 s send. The old model dropped changes and then waited for the next step, which gave gaps of about 2 s. The throttle says the latest step exactly at 1.5 s. Each "N percent" takes about 0.8 to 1.1 s to say, so at 1.5 s there is only about half a second of silence between them. At 3000 ms there were 33 announcements with about 2 s of silence between them. If Robin should hear a calmer bar without touching the setting, the default should probably be 3000 ms, or the range should go higher. That is a product decision; changing it is a one-line edit in settings.c, and Task 2's scene covers 0.5 to 3 s.
2. A key press does not clear the throttle, as the brief says. So a held change whose due time falls in the short gap between a key press and the frame that key produces gets said, and the key's own screen or focus announcement interrupts it about 50 ms later. Robin would hear a clipped syllable. Pause run 2 caught this: the key was at 4.38 s, the held "6%" was said at 4.64 s, and the pause screen came at 4.69 s. The gap was 0.10 to 0.31 s in these runs, against a 1.5 s cycle. The old model had a smaller version of the same effect. One possible refinement: do not release a held change within about 300 ms of a key press until a frame after that press has been modelled. That is not in the brief, so I left it for the controller to decide.
3. The universal TV send runs through 324 signals and takes about 100 s, not about ten.
4. Pre-existing, outside this task: pausing is announced as "TVs. Power", because a screen announcement is the title and then the focus. The popup's own "Paused" is never said, and "Paused" plus "23/324" can only be heard by reading the whole screen (Back plus Up). Worth a roadmap note.
5. Docs are not updated; I left them to the controller:
   - The spec's section 5, rule 4 still describes the 1500 ms model limit.
   - Section 6 describes the console mirror.
   - Sections 7 and 10 need `sr delay` and `sr_change_ms`.
6. Flash: 3,748 bytes spare after this task (836 used). About 85 bytes of that is the longer usage and error text, which could be trimmed if flash gets tight.


## Appendix: device logs, verbatim

Each sr watch line has the Mac's time in seconds since OK on Power, or since the watch opened. Lines starting with >> are the keys that the measuring script sent. The script (scratchpad ir_send_watch.py and pause_probe.py) is not committed.


### A. Idle check, flash, and the baseline send with the old firmware af4ee095

```
== loader info
No application is running
== sr status (first reading)
enabled: yes
rate: 76, volume: 80, verbosity: 1
frames: 23961, dropped: 0, announcements: 845, suppressed: 12
speech: idle, queued 0, speaker held: no, utterances 834, aborted 382, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2180
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2596, fallback 61, missing 45, open max 48 ms, last 26 ms
free heap: 105568
== 30 s idle check
19:41:24 announcements 845
19:41:54 announcements 845 (flat)
No application is running
== info device before the flash
firmware.commit.hash          : af4ee095
firmware.commit.dirty         : true
firmware.branch.name          : screen-reader
== flash (./fbt flash_usb, last lines)
2026-09-24 19:45:16,944 [INFO] Using flip_R0skie on /dev/cu.usbmodemflip_R0skie1
2026-09-24 19:45:16,945 [INFO] Installing "f7-update-mntm-screen-reader-f625f9d0" from /ext/update/f7-update-mntm-screen-reader-f625f9d0
2026-09-24 19:45:26,282 [INFO] Closing current app, if any
Touch("build/minusbinstall.flag")
exit 0; the device came back reporting firmware.commit.hash f625f9d0
```

```
== loader open Infrared

     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen: Learn New Remote. Saved Remotes. GPIO Settings. Universal Remotes, 1 of 5
  >> OK (Universal Remotes)
     0.87  screen: TVs
  >> OK (TVs)
     5.33  stopped

######## send 1
== sr status (send 1, before the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1
frames: 24097, dropped: 0, announcements: 847, suppressed: 12
speech: idle, queued 0, speaker held: no, utterances 836, aborted 382, dropped 0, underruns 0, queue dropped 0
last utterance: 849 ms played, 12358 subsamples, 772 ms nominal, worker stack free 2180
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2599, fallback 61, missing 45, open max 48 ms, last 21 ms
free heap: 23048
     0.01  sr watch
     0.01  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen:
     0.51  screen: TVs. Power
     0.00  >> OK on Power
     0.13  change: Sending.... 0%. stop. pause
     0.90  change: 1%
     2.72  change: 4%
     4.61  change: 7%
     6.60  change: 10%
     8.61  change: 13%
    10.45  change: 16%
    12.54  change: 19%
    14.54  change: 22%
    16.27  change: 25%
    17.94  change: 28%
    19.67  change: 30%
    21.62  change: 33%
    24.01  change: 35%
    26.04  change: 37%
    27.65  change: 38%
    29.87  change: 40%
    32.42  change: 42%
    34.06  change: 44%
    36.61  change: 46%
    38.52  change: 48%
    41.01  change: 50%
    43.45  change: 52%
    45.61  change: 54%
    47.31  change: 55%
    48.86  change: 56%
    51.03  change: 58%
    52.61  change: 59%
    54.93  change: 61%
    57.40  change: 63%
    59.50  change: 65%
    61.93  change: 67%
    64.24  change: 69%
    66.06  change: 71%
    68.18  change: 73%
    69.99  change: 75%
    72.08  change: 77%
    73.81  change: 79%
    76.00  change: 81%
    78.76  change: 84%
    80.57  change: 86%
    82.84  change: 88%
    85.07  change: 90%
    87.36  change: 92%
    89.10  change: 93%
    91.17  change: 94%
    94.22  change: 96%
    95.87  change: 97%
    97.84  change: 99%
    98.76  screen: TVs. Power
   101.27  stopped
== sr status (send 1, after the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1
frames: 24425, dropped: 0, announcements: 898, suppressed: 12
speech: idle, queued 0, speaker held: no, utterances 886, aborted 384, dropped 0, underruns 0, queue dropped 0
last utterance: 1586 ms played, 23606 subsamples, 1475 ms nominal, worker stack free 2180
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2737, fallback 61, missing 45, open max 48 ms, last 27 ms
free heap: 25984
-- send 1: send ended; 50 announcements in the watch, 49 changes; change gaps (s): [0.77, 1.82, 1.89, 1.98, 2.02, 1.84, 2.09, 2.0, 1.73, 1.67, 1.73, 1.95, 2.39, 2.04, 1.61, 2.22, 2.54, 1.64, 2.56, 1.91, 2.49, 2.43, 2.16, 1.7, 1.55, 2.17, 1.58, 2.32, 2.47, 2.1, 2.43, 2.31, 1.82, 2.12, 1.81, 2.09, 1.73, 2.19, 2.76, 1.81, 2.28, 2.23, 2.3, 1.73, 2.07, 3.05, 1.65, 1.97]; min gap 0.77
-- last change: '99%' at 97.84 s; last announcement: screen: 'TVs. Power' at 98.76 s
-- counters over the send: announcements +51, suppressed +0, utterances +50, aborted +2
```


### B. After the flash: sr screen, info device, sr status, usage, sr delay bounds

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== info device (lines about the firmware; radio, enclave and hardware detail lines left out)
hardware.model                : Flipper Zero
hardware.uid                  : redacted
hardware.name                 : R0skie
firmware.commit.hash          : f625f9d0
firmware.commit.dirty         : true
firmware.branch.name          : screen-reader
firmware.branch.num           : 0
firmware.version              : mntm-dev
firmware.build.date           : 24-09-2026
firmware.target               : 7
firmware.api.major            : 87
firmware.api.minor            : 2
firmware.origin.fork          : Momentum
firmware.origin.git           : https://github.com/Next-Flip/Momentum-Firmware.git
== sr status
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 1500 ms
frames: 37, dropped: 0, announcements: 1, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1105 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0, open max 26 ms, last 26 ms
free heap: 112560
== sr
Usage: sr <command>
  screen   print the captured screen and how it reads
  watch    stream announcements; arrows, Enter, Backspace drive the device
  on|off   enable or disable the screen reader (saved)
  status   show state and counters
  say <text>   speak text now; sr status shows its timing when done
  stop         stop speaking
  rate <n>     SAM speed 40..120, bigger is slower (saved)
  volume <n>   0..100 (saved)
  delay <ms>   change delay 500..3000: a same-screen change is said at most once per
               delay, the latest (saved)
  play <path> [rate]  raw 8 bit mono clip from the card, 8000..32000 Hz (16000)
  voice on|off|status  recorded word clips from the card, spelled letters for the rest (saved)
  chord up|down|ok|okhold|left|right  what Back plus that key does: screen, status bar,
               focus, focus spelled, volume down, volume up
== sr delay
expected a number of milliseconds from 500 to 3000; the change delay is 1500 ms
== sr delay 499
expected a number of milliseconds from 500 to 3000; the change delay is 1500 ms
== sr delay 3001
expected a number of milliseconds from 500 to 3000; the change delay is 1500 ms
== sr delay abc
expected a number of milliseconds from 500 to 3000; the change delay is 1500 ms
== loader info
No application is running
```


### C. Items (1) and (2): sends at 1500, 3000 and 500 ms

```
== loader open Infrared

     0.00  sr watch
     0.01  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen: Learn New Remote. Saved Remotes. GPIO Settings. Universal Remotes, 1 of 5
  >> OK (Universal Remotes)
     0.89  screen: TVs
  >> OK (TVs)
     5.35  stopped

######## send 1, change delay 1500 ms
== sr delay 1500
change delay set to 1500 ms
== sr status (send 1, change delay 1500 ms, before the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 1500 ms
frames: 77, dropped: 0, announcements: 3, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 3, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 848 ms played, 12358 subsamples, 772 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 5, fallback 0, missing 0, open max 32 ms, last 21 ms
free heap: 30704
     0.00  sr watch
     0.01  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen:
     0.41  screen: TVs. Power
     0.00  >> OK on Power
     0.13  change: Sending.... 0%. stop. pause
     1.64  change: 2%
     3.13  change: 4%
     4.63  change: 7%
     6.14  change: 9%
     7.63  change: 11%
     9.13  change: 13%
    10.64  change: 16%
    12.13  change: 18%
    13.63  change: 20%
    15.13  change: 22%
    16.63  change: 25%
    18.13  change: 28%
    19.63  change: 29%
    21.13  change: 31%
    22.63  change: 33%
    24.13  change: 34%
    25.63  change: 36%
    27.13  change: 37%
    28.63  change: 38%
    30.13  change: 39%
    31.63  change: 41%
    33.13  change: 42%
    34.63  change: 44%
    36.14  change: 45%
    37.63  change: 46%
    39.13  change: 48%
    40.63  change: 49%
    42.13  change: 50%
    43.63  change: 51%
    45.13  change: 53%
    46.63  change: 54%
    48.13  change: 55%
    49.64  change: 56%
    51.13  change: 57%
    52.64  change: 58%
    54.14  change: 59%
    55.63  change: 61%
    57.13  change: 62%
    58.63  change: 63%
    60.14  change: 64%
    61.63  change: 66%
    63.13  change: 67%
    64.64  change: 68%
    66.13  change: 70%
    67.64  change: 71%
    69.13  change: 73%
    70.63  change: 74%
    72.13  change: 76%
    73.64  change: 78%
    75.14  change: 79%
    76.63  change: 80%
    78.13  change: 82%
    79.63  change: 84%
    81.13  change: 85%
    82.63  change: 87%
    84.13  change: 88%
    85.64  change: 89%
    87.13  change: 91%
    88.64  change: 92%
    90.14  change: 93%
    92.12  change: 94%
    93.62  change: 95%
    95.12  change: 96%
    96.79  change: 97%
    98.29  change: 98%
    99.72  screen: TVs. Power
   102.26  stopped
== sr status (send 1, change delay 1500 ms, after the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 1500 ms
frames: 405, dropped: 0, announcements: 71, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 67, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 1580 ms played, 23606 subsamples, 1475 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 185, fallback 0, missing 0, open max 35 ms, last 26 ms
free heap: 32968
-- send 1, change delay 1500 ms: send ended; 67 announcements in the watch, 66 changes; change gaps (s): [1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.51, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.99, 1.5, 1.5, 1.67, 1.5]; min gap 1.5
-- last change: '98%' at 98.29 s; last announcement: screen: 'TVs. Power' at 99.72 s
-- counters over the send: announcements +68, suppressed +0, utterances +64, aborted +2

######## send 2, change delay 3000 ms
== sr delay 3000
change delay set to 3000 ms
== sr status (send 2, change delay 3000 ms, before the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 405, dropped: 0, announcements: 71, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 67, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 1580 ms played, 23606 subsamples, 1475 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 185, fallback 0, missing 0, open max 35 ms, last 26 ms
free heap: 32880
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen: TVs. Power
     0.00  >> OK on Power
     0.14  change: Sending.... 0%. stop. pause
     3.14  change: 4%
     6.14  change: 9%
     9.14  change: 13%
    12.14  change: 18%
    15.14  change: 23%
    18.14  change: 28%
    21.14  change: 32%
    24.14  change: 35%
    27.14  change: 37%
    30.14  change: 40%
    33.15  change: 42%
    36.14  change: 45%
    39.14  change: 48%
    42.14  change: 50%
    45.14  change: 53%
    48.14  change: 55%
    51.15  change: 58%
    54.14  change: 60%
    57.14  change: 62%
    60.14  change: 65%
    63.14  change: 68%
    66.14  change: 71%
    69.14  change: 74%
    72.14  change: 77%
    75.14  change: 80%
    78.14  change: 83%
    81.14  change: 87%
    84.14  change: 89%
    87.14  change: 92%
    90.14  change: 93%
    93.14  change: 95%
    96.14  change: 98%
    98.11  screen: TVs. Power
   100.64  stopped
== sr status (send 2, change delay 3000 ms, after the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 730, dropped: 0, announcements: 105, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 101, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 1586 ms played, 23606 subsamples, 1475 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 280, fallback 0, missing 0, open max 35 ms, last 27 ms
free heap: 32880
-- send 2, change delay 3000 ms: send ended; 34 announcements in the watch, 33 changes; change gaps (s): [3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0]; min gap 3.0
-- last change: '98%' at 96.14 s; last announcement: screen: 'TVs. Power' at 98.11 s
-- counters over the send: announcements +34, suppressed +0, utterances +34, aborted +0

######## send 3, change delay 500 ms
== sr delay 500
change delay set to 500 ms
== sr status (send 3, change delay 500 ms, before the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 500 ms
frames: 730, dropped: 0, announcements: 105, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 101, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 1586 ms played, 23606 subsamples, 1475 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 280, fallback 0, missing 0, open max 35 ms, last 27 ms
free heap: 32784
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen: TVs. Power
     0.00  >> OK on Power
     0.16  change: Sending.... 0%. stop. pause
     0.93  change: 1%
     1.53  change: 2%
     2.15  change: 3%
     2.76  change: 4%
     3.52  change: 5%
     4.07  change: 6%
     4.67  change: 7%
     5.28  change: 8%
     6.09  change: 9%
     6.69  change: 10%
     7.30  change: 11%
     7.87  change: 12%
     8.78  change: 13%
     9.44  change: 14%
    10.04  change: 15%
    10.64  change: 16%
    11.49  change: 17%
    12.09  change: 18%
    12.77  change: 19%
    13.36  change: 20%
    14.17  change: 21%
    14.79  change: 22%
    15.43  change: 23%
    15.92  change: 24%
    16.54  change: 25%
    17.12  change: 26%
    17.71  change: 27%
    18.27  change: 28%
    18.88  change: 29%
    20.00  change: 30%
    20.52  change: 31%
    21.35  change: 32%
    21.97  change: 33%
    23.40  change: 34%
    24.38  change: 35%
    25.23  change: 36%
    26.41  change: 37%
    28.04  change: 38%
    29.08  change: 39%
    30.34  change: 40%
    31.34  change: 41%
    32.88  change: 42%
    33.80  change: 43%
    34.52  change: 44%
    35.64  change: 45%
    37.14  change: 46%
    38.28  change: 47%
    39.09  change: 48%
    40.40  change: 49%
    41.64  change: 50%
    43.09  change: 51%
    44.07  change: 52%
    45.12  change: 53%
    46.25  change: 54%
    47.92  change: 55%
    49.49  change: 56%
    50.47  change: 57%
    51.68  change: 58%
    53.28  change: 59%
    54.44  change: 60%
    55.64  change: 61%
    56.75  change: 62%
    58.16  change: 63%
    59.34  change: 64%
    60.27  change: 65%
    61.48  change: 66%
    62.75  change: 67%
    63.84  change: 68%
    65.07  change: 69%
    65.85  change: 70%
    66.85  change: 71%
    67.83  change: 72%
    68.97  change: 73%
    70.01  change: 74%
    70.80  change: 75%
    72.17  change: 76%
    72.89  change: 77%
    73.51  change: 78%
    74.61  change: 79%
    75.91  change: 80%
    76.79  change: 81%
    77.58  change: 82%
    78.19  change: 83%
    79.59  change: 84%
    80.81  change: 85%
    81.45  change: 86%
    82.24  change: 87%
    83.76  change: 88%
    84.73  change: 89%
    86.00  change: 90%
    86.63  change: 91%
    88.33  change: 92%
    90.04  change: 93%
    92.13  change: 94%
    93.50  change: 95%
    95.19  change: 96%
    96.83  change: 97%
    97.61  change: 98%
    98.82  change: 99%
    99.72  screen: TVs. Power
   102.25  stopped
== sr status (send 3, change delay 500 ms, after the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 500 ms
frames: 1055, dropped: 0, announcements: 206, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 165, aborted 3, dropped 0, underruns 0, queue dropped 0
last utterance: 1585 ms played, 23606 subsamples, 1475 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 461, fallback 0, missing 0, open max 35 ms, last 27 ms
free heap: 32784
-- send 3, change delay 500 ms: send ended; 101 announcements in the watch, 100 changes; change gaps (s): [0.77, 0.61, 0.61, 0.61, 0.76, 0.55, 0.6, 0.61, 0.81, 0.6, 0.61, 0.58, 0.9, 0.66, 0.6, 0.6, 0.85, 0.59, 0.69, 0.58, 0.81, 0.63, 0.63, 0.5, 0.62, 0.58, 0.59, 0.56, 0.61, 1.11, 0.52, 0.82, 0.62, 1.43, 0.98, 0.85, 1.19, 1.63, 1.04, 1.26, 1.0, 1.54, 0.92, 0.72, 1.13, 1.5, 1.13, 0.81, 1.31, 1.24, 1.45, 0.98, 1.05, 1.12, 1.67, 1.56, 0.99, 1.2, 1.61, 1.16, 1.2, 1.11, 1.41, 1.18, 0.93, 1.21, 1.26, 1.09, 1.24, 0.78, 1.0, 0.98, 1.14, 1.03, 0.79, 1.38, 0.72, 0.62, 1.1, 1.3, 0.88, 0.79, 0.62, 1.4, 1.22, 0.65, 0.79, 1.52, 0.97, 1.27, 0.63, 1.71, 1.71, 2.08, 1.38, 1.69, 1.64, 0.77, 1.21]; min gap 0.5
-- last change: '99%' at 98.82 s; last announcement: screen: 'TVs. Power' at 99.72 s
-- counters over the send: announcements +101, suppressed +0, utterances +64, aborted +1
exit: 0
```


### D. Item (3), pause run 1: a full send at 1500 ms, pausing 1.2 s after the fourth change said

```

######## send 1, change delay 1500 ms
== sr delay 1500
change delay set to 1500 ms
== sr status (send 1, change delay 1500 ms, before the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 1500 ms
frames: 1055, dropped: 0, announcements: 206, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 165, aborted 3, dropped 0, underruns 0, queue dropped 0
last utterance: 1585 ms played, 23606 subsamples, 1475 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 461, fallback 0, missing 0, open max 35 ms, last 27 ms
free heap: 33064
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen: TVs. Power
     0.00  >> OK on Power
     0.13  change: Sending.... 0%. stop. pause
     1.64  change: 2%
     3.13  change: 4%
     4.63  change: 6%
     5.89  >> OK (pause)
     6.09  screen: TVs. Power
     8.91  >> Back (resume)
     9.01  screen: TVs. Power
     9.81  change: 10%
    11.31  change: 12%
    12.81  change: 14%
    14.32  change: 16%
    15.82  change: 18%
    17.32  change: 21%
    18.82  change: 23%
    20.31  change: 26%
    21.81  change: 28%
    23.31  change: 30%
    24.81  change: 32%
    26.31  change: 33%
    27.81  change: 35%
    29.31  change: 36%
    30.81  change: 37%
    32.31  change: 39%
    33.81  change: 40%
    35.31  change: 41%
    36.81  change: 42%
    38.31  change: 44%
    39.81  change: 45%
    41.31  change: 46%
    42.81  change: 48%
    44.32  change: 49%
    45.82  change: 50%
    47.32  change: 52%
    48.81  change: 53%
    50.31  change: 54%
    51.81  change: 55%
    53.32  change: 56%
    54.81  change: 57%
    56.32  change: 58%
    57.82  change: 60%
    59.32  change: 61%
    60.82  change: 62%
    62.32  change: 63%
    63.82  change: 65%
    65.32  change: 66%
    66.82  change: 67%
    68.32  change: 69%
    69.82  change: 70%
    71.32  change: 72%
    72.82  change: 73%
    74.32  change: 75%
    75.82  change: 76%
    77.32  change: 78%
    78.81  change: 79%
    80.31  change: 81%
    81.82  change: 83%
    83.32  change: 84%
    84.82  change: 86%
    86.32  change: 87%
    87.82  change: 88%
    89.32  change: 90%
    90.82  change: 91%
    92.32  change: 92%
    93.82  change: 93%
    95.32  change: 94%
    96.82  change: 95%
    98.32  change: 96%
    99.95  change: 97%
   101.45  change: 98%
   102.89  screen: TVs. Power
   105.40  stopped
== sr status (send 1, change delay 1500 ms, after the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 1500 ms
frames: 1382, dropped: 0, announcements: 275, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 230, aborted 4, dropped 0, underruns 0, queue dropped 0
last utterance: 1586 ms played, 23606 subsamples, 1475 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 641, fallback 0, missing 0, open max 39 ms, last 27 ms
free heap: 33000
-- send 1, change delay 1500 ms: send ended; 69 announcements in the watch, 66 changes; change gaps (s): [1.5, 1.49, 1.5, 5.18, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.64, 1.5]; min gap 1.49
-- last change: '98%' at 101.45 s; last announcement: screen: 'TVs. Power' at 102.89 s
-- counters over the send: announcements +69, suppressed +0, utterances +65, aborted +1
exit: 0
```


### E. Item (3), pause run 2: Tab before and during the pause, Back stops the send

```
== sr delay 1500
change delay set to 1500 ms
== sr status (before the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 1500 ms
frames: 1382, dropped: 0, announcements: 275, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 230, aborted 4, dropped 0, underruns 0, queue dropped 0
last utterance: 1586 ms played, 23606 subsamples, 1475 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 641, fallback 0, missing 0, open max 39 ms, last 27 ms
free heap: 33024
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen: TVs. Power
     0.00  >> OK on Power
     0.13  change: Sending.... 0%. stop. pause
     1.63  change: 2%
     3.13  change: 4%
     4.29  >> Tab (the reader's current screen)
     4.32  screen: TVs. Sending.... 6%. stop. pause. Power
     4.38  >> OK (pause)
     4.64  change: 6%
     4.69  screen: TVs. Power
     5.90  >> Tab (the paused screen)
     5.92  screen: TVs. Paused. 23/324. resume. send 1. select. Power
     7.40  >> Back (resume)
     7.51  screen: TVs. Power
     8.35  change: 8%
     9.86  change: 10%
    11.36  change: 12%
    12.86  change: 14%
    13.41  >> Back (stop)
    13.62  screen: TVs. Power
    17.42  stopped
== sr status (after the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 1500 ms
frames: 1437, dropped: 0, announcements: 286, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 240, aborted 7, dropped 0, underruns 0, queue dropped 0
last utterance: 1586 ms played, 23606 subsamples, 1475 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 662, fallback 0, missing 0, open max 39 ms, last 26 ms
free heap: 32968
-- counters: announcements +11, utterances +10, aborted +3
```


### F. Item (4): tools/sr_drive.py (the three sessions)

```
sr watch
Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
letters type into text fields. Ctrl+C stops.
screen: 

ok   ok    expected 'screen:' got: screen: Apps
ok   up    expected 'focus: Settings' got: focus: Settings
ok   ok    expected 'Bluetooth' got: screen: Bluetooth
ok   back  expected 'screen:' got: screen: Settings
ok   back  expected 'home: Home screen' got: home: Home screen
ok   ok    expected 'screen:' got: screen: Apps
ok   down  expected 'focus:' got: focus: Sub-GHz
ok   down  expected 'focus:' got: focus: 125 kHz RFID
ok   back  expected 'home: Home screen' got: home: Home screen
ok   ok    expected 'screen:' got: screen: Apps
ok   ok    expected 'screen:' got: screen: Parent folder
ok   down  expected 'focus:' got: focus: Bluetooth
ok   back  expected 'screen:' got: screen: Apps
ok   back  expected 'home: Home screen' got: home: Home screen
ok   watch expected 'screen: ... Input ...' got: sr watch | Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen, | letters type into text fields. Ctrl+C stops. | screen: Input. All. qwertyuiop 0123. asdfghjkl 456. zxcvbnm_ 789. Save
ok   right expected 'focus: <one character>' got: focus: 7
ok   back  expected 'home: Home screen' got: home: Home screen
     home  desktop, no focus
ok   home  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 1105 ms played, 15972 subsamples
ok   home  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 2175 ms played, 32784 subsamples
ok   home  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 1114 ms played, 16399 subsamples
ok   home  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1107 ms played, 16399 subsamples
     menu  fullscreen, FOCUS 1/11 "Apps", reads as: Settings. Sub-GHz. Apps, 1 of 11
ok   menu  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 4387 ms played, 68392 subsamples
ok   menu  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 1517 ms played, 22825 subsamples
ok   menu  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 2011 ms played, 30272 subsamples
ok   menu  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1673 ms played, 24961 subsamples
ok   end   home screen expected, got: desktop, no focus
0 failures
```


### G. Item (4): tools/sr_drive.py --chords

```
     home  desktop, no focus
ok   home  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 1105 ms played, 15972 subsamples
ok   home  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 2176 ms played, 32784 subsamples
ok   home  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 1120 ms played, 16399 subsamples
ok   home  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1115 ms played, 16399 subsamples
     menu  fullscreen, FOCUS 1/11 "Apps", reads as: Settings. Sub-GHz. Apps, 1 of 11
ok   menu  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 4386 ms played, 68392 subsamples
ok   menu  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 1516 ms played, 22825 subsamples
ok   menu  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 2004 ms played, 30272 subsamples
ok   menu  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1681 ms played, 24961 subsamples
ok   end   home screen expected, got: desktop, no focus
0 failures
```


### H. End state and the restarted log capture

```
== loader info
No application is running
== sr status
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 1500 ms
frames: 1741, dropped: 0, announcements: 314, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 284, aborted 8, dropped 0, underruns 0, queue dropped 0
last utterance: 1101 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 762, fallback 0, missing 0, open max 39 ms, last 26 ms
free heap: 112536
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== storage read /int/.momentum_settings.txt (the reader's lines; the other settings left out)
Size: 965
screen_reader: true
sr_rate: 76
sr_volume: 80
sr_verbosity: 1
sr_voice: true
sr_change_ms: 1500
== log capture restarted
98127 .../Python tools/flipper_log.py docs/measurements/logs/2026-09-24-session.txt
19:57:24 Use <log ?> to list available log levels
19:57:24 Press CTRL+C to stop...
```

---

## Fix round 1 (review findings 1 to 6)

Status: DONE_WITH_CONCERNS. All six items are fixed and tested on the host. Most device checks passed. The bubble check could not be run, because no bubble appeared in 10 tries (Concerns, item 2).

### Commits

- Firmware 70a60c8f5 screen reader: held changes obey the quiet rules; key changes at once; delay default 3 s, up to 10 s (screen_reader.c, screen_reader.h, screen_reader_cli.c, screen_model.c, sr_throttle.c, sr_throttle.h, lib/momentum/settings.c, lib/momentum/settings.h)
- Project 2f12684 host tests: throttle bypass and drop (tests/host/test_sr_throttle.c, tests/host/test_screen_model.c)

Nothing pushed. README.md and tools/voice_build.py belong to Task 3 and are untouched.

### What changed, finding by finding

1. **Held changes obey the quiet rules (Important).** The two desktop rules are now one function, `sr_quiet()`. They are the same expressions as before, moved out of sr_process, and sr_process and the release path both use them:
   - no key press within SR_DESKTOP_KEY_MS, for an unasked announcement;
   - the lock quiet window.

   When a held change comes due, `sr_say_held_change` checks the screen now on show (`model.prev.content_layer`). If the desktop is quiet, the change is dropped and counted as suppressed. It is not mirrored, because it was never announced. Any announcement that sr_process suppresses also drops a held change.
2. **A key's own change is said at once (Important).** In sr_process, a change within 500 ms (SR_KEY_RECENT_MS) of the last key press calls the new `sr_throttle_force(t, now)` and is said at once. This records now as the last change said, so the next unrelated change is spaced from it, and it drops anything held.
3. **A key press drops a held change (ruling).** The input callback sets an atomic `key_pressed` flag on every Press. After each wait, the service thread takes the flag with an atomic exchange and clears the held change. This happens before it models the frame the key causes, and before any release.
4. **Default 3000 ms, range 500 to 10000 (ruling).** `SR_CHANGE_MS_MIN`, `SR_CHANGE_MS_MAX` and `SR_CHANGE_MS_DEFAULT` are defined once, in lib/momentum/settings.h. That header is included by settings.c, the console and the Momentum app, so Task 2 can use them too. They are used by:
   - the default and the table entry in settings.c;
   - the range check in `sr delay`;
   - its error text and the usage text.
5. **A held change waits for a settling frame (minor).** The loop uses the throttle's wait only when no frame is pending. While a frame settles, the old 50 ms settle and 300 ms cap apply unchanged, and a due change is released only after that frame has been modelled. Round 1's rule for a frame cut short by the throttle is gone, so frame timing is exactly as it was before this task.
6. **One helper, one comment, one test (minor).**
   - `sr_announce()` counts every spoken announcement, says it while the reader is on (with the saved voice), and mirrors it. sr_process, sr_say_held_change and sr_say_lock all use it. sr_say_lock keeps its early return when the reader is off, so a lock with the reader off is still not recorded.
   - The model comment now reads: a bubble change "which the service keeps quiet without a recent key and spaces by the change delay".
   - The model test's reset step (test_screen_model.c, around line 320) now checks what it announces. Going back from five rows to two reads as a new screen: kind screen, interrupting, "Wrong PIN!. Timeout: 1s".

### Tests, build, lint, headroom

Host runner on the committed trees, exit 0:

```
174 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1022 checks, 0 failures
speech queue: 156 checks, 0 failures
speech PCM: 700 checks, 0 failures
speech voice: 4433 checks, 0 failures
chords: 73 checks, 0 failures
throttle: 119 checks, 0 failures
```

Test first: the new throttle cases failed to compile before `sr_throttle_force` existed (`call to undeclared function 'sr_throttle_force'`). The new cases are:
- force: the held change is dropped, the next change is spaced from the forced one, a double force, and a force before any change was said;
- the service's sequences: a key press drops the held change and the key's own change is forced; a suppression drops a held bubble change;
- a 10 s delay.

The model gained 4 checks for the reset step.

- `./fbt`: exit 0. It printed only the two known cli_bridge and mtp manifest warnings and `API version 87.2 is up to date`.
- `./fbt lint`: exit 0.
- `tools/flash_headroom.sh`: `firmware.bin 877036 bytes, limit 880640, spare 3604 bytes` (after round 1: 3,748).

### Device verification

Order of events:
- I waited until Task 3's sync had ended (21:15:38, exit 0).
- Idle check at 21:16:23 to 21:16:53: no application, announcements flat at 314.
- `./fbt flash_usb`, exit 0.
- The device came back on 70a60c8f at 21:18:15.
- `sr screen` showed the home screen with no crash popup. `info device` showed 70a60c8f with API 87.2.
- `sr delay 499` and `sr delay 10001` were refused; `sr delay 10000` was accepted (Appendix F1).
- The device had kept round 1's saved 1500, so I set `sr delay 3000`, the new default.

Much of the first 30 minutes was disturbed by other clients on the port (Concerns, item 1). The runs from 21:41 to 21:47 had the port to themselves.

(1) **TV send at the new default, one announcement per 3 s.**
- Run at 21:27 (Appendix F2): "Sending.... 0%" at 0.13 s, then one change every 3.00 s from 4% to 92%. That is 29 gaps: 26 of 3.00 s, one 3.01 s, one 3.03 s and one 3.04 s. Counters: announcements +32, utterances +32.

  At 21:28:39 another agent's log capture started, and the Enter it sends as it starts paused the send. The end of that send was therefore never observed. Round 1 had already shown the end: the screen announcement, with nothing said after it.
- Runs at 21:33 and 21:41: the same 3.00 s cadence (3.01 and 3.00 s; 3.00 s).

(2) **A key's own change is said at once** (Appendix F3, Accessibility list):
- Down to Volume gave "focus: Volume 80".
- Left gave "focus: Volume 70" 0.11 s after the key.
- Right gave "focus: Volume 80" 0.07 s after the key. Robin's volume is back at 80 and saved.

That list announces a value change as focus, not as a change, because the settings list focus-hints both the label and the value. So the change bypass itself was seen in the paused-send run instead (Appendix F4): OK at 13.86 s was followed by "change: 6%" at 13.91 s, said at once. Without the bypass it would have been held until 15.99 s.

In that run's paused popup, Right, Right and Left changed nothing. Tab before and after each key showed "21/324" every time, so there was no change to announce. That is how the Infrared app behaves with these keys, not the reader.

(3) **Bubbles** (Appendix F5).
- 5 tries: Back at 0 s and at 1.9 s on the home screen, then `sr watch` for 30 s.
- 5 more tries, each after OK long (a new idle animation).
- In all 10: no bubble text drawn, 0 watch lines, announcements +0, utterances +0, suppressed +0.

So nothing was ever spoken late, but the bubble case itself was not exercised on the device. The drop logic is covered by the throttle tests and by the due-time quiet check in the code.

(4) **sr_drive** (Appendix F6): the default run (all three sessions) reported `0 failures`, and `--chords` reported `0 failures`.

**End state** (Appendix F7): no application; home screen; reader on; voice on; speech idle, nothing queued; rate 76; volume 80; `sr_change_ms: 3000` saved. My log capture has been running since 21:50:39.

### Deviations

- The device's delay was left at 3000, the new default, rather than "restored" to 1500. The 1500 was round 1's saved test value and would override the new default.
- A held change dropped when it comes due is counted as suppressed but not mirrored.
- sr_say_lock's early return with the reader off is kept (item 6).
- IR sends this round:
  - 21:19, stopped at 42% by Task 3's Enter;
  - 21:27, to 92%;
  - 21:33, to 11%, then 12% to 20% in the probe;
  - 21:41, to 7%.

### Concerns

1. **Device contention.** Several agents used the port at the same time, and it corrupted runs on every side. What happened:
   - **21:19 to 21:22:** Task 3's `loader info`, `sr status` and `sr voice status` ran during my `sr watch` send. Their output contains my watch line ("sreen: TVs. Power"). Their Enter paused my send at 42%.
   - **Task 3's voice counters:** my flash at 21:17 rebooted the device during Task 3's checks (it logged "PORT BACK" at 21:19:06). That reset the voice counters Task 3 compares.
   - **Captures from 21:28 on:** log captures were started during my sessions at 21:28:39, 21:29:47, 21:33:47, 21:34:26 and 21:34:29. From 21:34:25 they came from a loop in terminal tab c2, "flipper log capture (auto-restart)", opened by an agent, which restarted the capture 2 s after each stop. The session log's stamps are in Appendix F8.
   - **Why a capture start hurts:** flipper_log.py writes "\r" and then "log debug\r" when it starts. Inside a running `sr watch` that is OK, letters, and OK again. It paused my sends at 21:28:39 and 21:33:47, and it pressed keys in the Accessibility list at 21:34:26. It also read my lines, so they never reached me.
   - **What I did:** I stopped captures as the protocol says, and left the loop alone, since it is another agent's. I also stopped doing device work until its owner stopped the loop at 21:38:39.
   - **Suggestion:** one device owner at a time, with an explicit hand-off or a lock file, and no auto-restart loop while a task is verifying.
2. **The bubble path is not verified on the device.** No bubble appeared in 10 tries. Worth a manual look when a bubble animation is showing.
3. **The key bypass can clip a word.** It lets a progress step that happens to land within 500 ms after a key be said at once, and the key's own screen can then cut it off. In the paused-send run, "6%" was said 50 ms after OK and was cut by the pause screen 0.2 s later. This is the round-1 clipped-word concern in another form, and it is short.
4. **Task 2's Change delay row needs revisiting.** It was planned as 0.5 to 3 s in 0.5 s steps. The range now goes to 10 s with a default of 3 s.
5. **One scratch file is not mine.** fbt_build_fix1.log in the shared scratchpad is another agent's; I did not use it.


### Fix round 1 appendix: device logs, verbatim

Each sr watch line has the Mac's time in seconds since the first key of the send, or since the watch opened. Lines starting with >> are the keys my scripts sent.


#### F1. After the flash: sr screen, info device, sr status, usage, delay bounds, and the new default set

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== info device
hardware.model                : Flipper Zero
hardware.uid                  : redacted
hardware.name                 : R0skie
firmware.commit.hash          : 70a60c8f
firmware.commit.dirty         : true
firmware.branch.name          : screen-reader
firmware.branch.num           : 0
firmware.version              : mntm-dev
firmware.build.date           : 24-09-2026
firmware.target               : 7
firmware.api.major            : 87
firmware.api.minor            : 2
firmware.origin.fork          : Momentum
firmware.origin.git           : https://github.com/Next-Flip/Momentum-Firmware.git
== sr status
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 1500 ms
frames: 18, dropped: 0, announcements: 1, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1105 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0, open max 26 ms, last 26 ms
free heap: 112544
== sr
Usage: sr <command>
  screen   print the captured screen and how it reads
  watch    stream announcements; arrows, Enter, Backspace drive the device
  on|off   enable or disable the screen reader (saved)
  status   show state and counters
  say <text>   speak text now; sr status shows its timing when done
  stop         stop speaking
  rate <n>     SAM speed 40..120, bigger is slower (saved)
  volume <n>   0..100 (saved)
  delay <ms>   change delay 500..10000: a same-screen change is said at most once per
               delay, the latest (saved)
  play <path> [rate]  raw 8 bit mono clip from the card, 8000..32000 Hz (16000)
  voice on|off|status  recorded word clips from the card, spelled letters for the rest (saved)
  chord up|down|ok|okhold|left|right  what Back plus that key does: screen, status bar,
               focus, focus spelled, volume down, volume up
== sr delay 499
expected a number of milliseconds from 500 to 10000; the change delay is 1500 ms
== sr delay 10001
expected a number of milliseconds from 500 to 10000; the change delay is 1500 ms
== sr delay 10000
change delay set to 10000 ms
== sr delay 3000
change delay set to 3000 ms
== loader info
No application is running
```


#### F2. TV send at 3000 ms, 21:27 (0% to 92%; a capture started at 21:28:39)

```
== loader open Infrared

     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen: Learn New Remote. Saved Remotes. GPIO Settings. Universal Remotes, 1 of 5
  >> OK (Universal Remotes)
     0.87  screen: TVs
  >> OK (TVs)
     5.33  stopped

######## send 1, change delay 3000 ms
== sr delay 3000
change delay set to 3000 ms
== sr status (send 1, change delay 3000 ms, before the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 726, dropped: 0, announcements: 29, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 28, aborted 5, dropped 0, underruns 0, queue dropped 0
last utterance: 849 ms played, 12358 subsamples, 772 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 115, fallback 0, missing 0, open max 46 ms, last 21 ms
free heap: 30744
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.01  screen:
     0.39  screen: TVs. Power
     0.00  >> OK on Power
     0.13  change: Sending.... 0%. stop. pause
     3.14  change: 4%
     6.15  change: 9%
     9.15  change: 13%
    12.14  change: 18%
    15.15  change: 23%
    18.15  change: 28%
    21.15  change: 32%
    24.15  change: 35%
    27.15  change: 37%
    30.18  change: 40%
    33.22  change: 43%
    36.22  change: 45%
    39.22  change: 48%
    42.22  change: 50%
    45.22  change: 53%
    48.22  change: 55%
    51.22  change: 58%
    54.22  change: 60%
    57.22  change: 62%
    60.22  change: 65%
    63.22  change: 68%
    66.22  change: 71%
    69.22  change: 74%
    72.22  change: 77%
    75.22  change: 80%
    78.22  change: 83%
    81.22  change: 87%
    84.22  change: 89%
    87.22  change: 92%
   122.55  stopped
== sr status (send 1, change delay 3000 ms, after the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 1036, dropped: 0, announcements: 61, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 60, aborted 7, dropped 0, underruns 0, queue dropped 0
last utterance: 41 ms played, 1 subsamples, 0 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 201, fallback 0, missing 0, open max 46 ms, last 38 ms
free heap: 30824
-- send 1, change delay 3000 ms: send DID NOT END; 30 announcements in the watch, 30 changes; change gaps (s): [3.01, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.03, 3.04, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0]; min gap 3.0
-- last change: '92%' at 87.22 s; last announcement: change: '92%' at 87.22 s
-- counters over the send: announcements +32, suppressed +0, utterances +32, aborted +2
stopping: the send did not end
```


#### F3. Accessibility list: Volume Left and Right, 21:42

```
== loader open Momentum

== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2592, dropped: 0, announcements: 110, suppressed: 0
speech: speaking, queued 0, speaker held: yes, utterances 109, aborted 23, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 302, fallback 0, missing 0, open max 46 ms, last 16 ms
free heap: 75576
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.01  screen: MNTM-DEV 70A60C8F. Protocols. Misc. Interface, 1 of 4
     0.00  >> down
     0.08  focus: Protocols
     1.02  >> down
     1.08  focus: Misc
     2.02  >> down
     2.08  focus: Accessibility
     3.03  >> ok
     3.10  screen: Screen Reader ON
     5.05  >> down
     5.13  focus: Voice Recorded
     6.06  >> down
     6.13  focus: Rate 76
     7.07  >> down
     7.19  focus: Volume 80
     8.08  >> left
     8.19  focus: Volume 70
     9.29  >> right
     9.36  focus: Volume 80
    10.50  >> back
    10.57  screen: MNTM-DEV 70A60C8F. Accessibility
    12.01  >> back
    12.25  home: Home screen
    14.03  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2643, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112528
== loader info
No application is running
```


#### F4. Paused popup, 21:41: OK pauses, Tab around Right, Right, Left, Back resumes and stops

```
== loader open Infrared

     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen: Learn New Remote. Saved Remotes. GPIO Settings. Universal Remotes, 1 of 5
     0.80  >> ok
     0.89  screen: TVs
     2.82  >> ok
     6.45  screen: TVs. Power
     9.84  >> ok
     9.99  change: Sending.... 0%. stop. pause
    12.99  change: 4%
    13.86  >> ok
    13.91  change: 6%
    14.12  screen: TVs. Power
    15.37  >> tab
    15.38  screen: TVs. Paused. 21/324. resume. send 1. select. Power
    15.89  >> right
    17.39  >> tab
    17.40  screen: TVs. Paused. 21/324. resume. send 1. select. Power
    17.89  >> right
    19.42  >> tab
    19.42  screen: TVs. Paused. 21/324. resume. send 1. select. Power
    19.93  >> left
    21.43  >> tab
    21.44  screen: TVs. Paused. 21/324. resume. send 1. select. Power
    21.96  >> back
    22.05  screen: TVs. Power
    22.67  change: 7%
    23.97  >> back
    24.09  screen: TVs. Power
    25.99  >> back
    26.06  screen: TVs
    27.49  >> back
    27.56  screen: Universal Remotes
    29.01  >> back
    29.17  home: Home screen
    30.53  stopped
== loader info
No application is running
```


#### F5. Bubble tries: 5 with Back at 0 s and 1.9 s, then 5 after OK long (a new idle animation)

```

######## bubble try 1
== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2644, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112600
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen:
     0.00  >> Back (a key press on the home screen)
     1.92  >> Back (a second key press)
    30.03  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2707, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112560
-- try 1: 0 watch lines; counters: announcements +0, suppressed +0, utterances +0, aborted +0; suppressed on arrival (mirrored) 0, held and dropped when due 0; lines more than 2 s after the last key: []

######## bubble try 2
== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2719, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112528
     0.00  sr watch
     0.01  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen:
     0.00  >> Back (a key press on the home screen)
     1.91  >> Back (a second key press)
    30.01  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2782, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112528
-- try 2: 0 watch lines; counters: announcements +0, suppressed +0, utterances +0, aborted +0; suppressed on arrival (mirrored) 0, held and dropped when due 0; lines more than 2 s after the last key: []

######## bubble try 3
== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2794, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112560
     0.00  sr watch
     0.01  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen:
     0.00  >> Back (a key press on the home screen)
     1.91  >> Back (a second key press)
    30.03  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2857, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112560
-- try 3: 0 watch lines; counters: announcements +0, suppressed +0, utterances +0, aborted +0; suppressed on arrival (mirrored) 0, held and dropped when due 0; lines more than 2 s after the last key: []

######## bubble try 4
== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2869, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112528
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen:
     0.00  >> Back (a key press on the home screen)
     1.91  >> Back (a second key press)
    30.02  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2932, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112528
-- try 4: 0 watch lines; counters: announcements +0, suppressed +0, utterances +0, aborted +0; suppressed on arrival (mirrored) 0, held and dropped when due 0; lines more than 2 s after the last key: []

######## bubble try 5
== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 2944, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112560
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen:
     0.00  >> Back (a key press on the home screen)
     1.90  >> Back (a second key press)
    30.04  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3007, dropped: 0, announcements: 121, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 120, aborted 31, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 328, fallback 0, missing 0, open max 46 ms, last 26 ms
free heap: 112560
-- try 5: 0 watch lines; counters: announcements +0, suppressed +0, utterances +0, aborted +0; suppressed on arrival (mirrored) 0, held and dropped when due 0; lines more than 2 s after the last key: []
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
```

```

######## bubble try 1
== input send ok long (a new idle animation)

== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3344, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112520
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen:
     0.00  >> Back (a key press on the home screen)
     1.90  >> Back (a second key press)
    30.02  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3407, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112472
-- try 1: 0 watch lines; counters: announcements +0, suppressed +0, utterances +0, aborted +0; suppressed on arrival (mirrored) 0, held and dropped when due 0; lines more than 2 s after the last key: []

######## bubble try 2
== input send ok long (a new idle animation)

== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3425, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112472
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen:
     0.00  >> Back (a key press on the home screen)
     1.93  >> Back (a second key press)
    30.02  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3488, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112496
-- try 2: 0 watch lines; counters: announcements +0, suppressed +0, utterances +0, aborted +0; suppressed on arrival (mirrored) 0, held and dropped when due 0; lines more than 2 s after the last key: []

######## bubble try 3
== input send ok long (a new idle animation)

== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3506, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112488
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen:
     0.00  >> Back (a key press on the home screen)
     1.92  >> Back (a second key press)
    30.02  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3569, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112488
-- try 3: 0 watch lines; counters: announcements +0, suppressed +0, utterances +0, aborted +0; suppressed on arrival (mirrored) 0, held and dropped when due 0; lines more than 2 s after the last key: []

######## bubble try 4
== input send ok long (a new idle animation)

== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3587, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112488
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen:
     0.00  >> Back (a key press on the home screen)
     1.90  >> Back (a second key press)
    30.02  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3650, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112488
-- try 4: 0 watch lines; counters: announcements +0, suppressed +0, utterances +0, aborted +0; suppressed on arrival (mirrored) 0, held and dropped when due 0; lines more than 2 s after the last key: []

######## bubble try 5
== input send ok long (a new idle animation)

== sr status (before)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3668, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112488
     0.00  sr watch
     0.00  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.00  letters type into text fields. Ctrl+C stops.
     0.00  screen:
     0.00  >> Back (a key press on the home screen)
     1.91  >> Back (a second key press)
    30.04  stopped
== sr status (after)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3731, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112488
-- try 5: 0 watch lines; counters: announcements +0, suppressed +0, utterances +0, aborted +0; suppressed on arrival (mirrored) 0, held and dropped when due 0; lines more than 2 s after the last key: []
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
```


#### F6. tools/sr_drive.py (three sessions) and --chords, 21:45 to 21:47

```
sr watch
Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
letters type into text fields. Ctrl+C stops.
screen: 

ok   ok    expected 'screen:' got: screen: Apps
ok   up    expected 'focus: Settings' got: focus: Settings
ok   ok    expected 'Bluetooth' got: screen: Bluetooth
ok   back  expected 'screen:' got: screen: Settings
ok   back  expected 'home: Home screen' got: home: Home screen
ok   ok    expected 'screen:' got: screen: Apps
ok   down  expected 'focus:' got: focus: Sub-GHz
ok   down  expected 'focus:' got: focus: 125 kHz RFID
ok   back  expected 'home: Home screen' got: home: Home screen
ok   ok    expected 'screen:' got: screen: Apps
ok   ok    expected 'screen:' got: screen: Parent folder
ok   down  expected 'focus:' got: focus: Bluetooth
ok   back  expected 'screen:' got: screen: Apps
ok   back  expected 'home: Home screen' got: home: Home screen
ok   watch expected 'screen: ... Input ...' got: sr watch | Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen, | letters type into text fields. Ctrl+C stops. | screen: Input. All. qwertyuiop 0123. asdfghjkl 456. zxcvbnm_ 789. Save
ok   right expected 'focus: <one character>' got: focus: 7
ok   back  expected 'home: Home screen' got: home: Home screen
     home  desktop, no focus
ok   home  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 1105 ms played, 15972 subsamples
ok   home  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 2168 ms played, 32784 subsamples
ok   home  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 1107 ms played, 16399 subsamples
ok   home  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1108 ms played, 16399 subsamples
     menu  fullscreen, FOCUS 1/11 "Apps", reads as: Settings. Sub-GHz. Apps, 1 of 11
ok   menu  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 4387 ms played, 68392 subsamples
ok   menu  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 1517 ms played, 22825 subsamples
ok   menu  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 2013 ms played, 30272 subsamples
ok   menu  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1673 ms played, 24961 subsamples
ok   end   home screen expected, got: desktop, no focus
0 failures
```

```
     home  desktop, no focus
ok   home  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 1106 ms played, 15972 subsamples
ok   home  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 2169 ms played, 32784 subsamples
ok   home  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 1107 ms played, 16399 subsamples
ok   home  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1108 ms played, 16399 subsamples
     menu  fullscreen, FOCUS 1/11 "Apps", reads as: Settings. Sub-GHz. Apps, 1 of 11
ok   menu  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 4386 ms played, 68392 subsamples
ok   menu  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 1517 ms played, 22825 subsamples
ok   menu  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 2013 ms played, 30272 subsamples
ok   menu  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1673 ms played, 24961 subsamples
ok   end   home screen expected, got: desktop, no focus
0 failures
```


#### F7. End state (21:46), settings file (the reader's lines)

```
== loader info
No application is running
== sr status
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 3276, dropped: 0, announcements: 146, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 161, aborted 32, dropped 0, underruns 0, queue dropped 0
last utterance: 1097 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2468
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 423, fallback 0, missing 0, open max 46 ms, last 27 ms
free heap: 112520
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== storage read /int/.momentum_settings.txt
Size: 965
screen_reader: true
sr_rate: 76
sr_volume: 80
sr_verbosity: 1
sr_voice: true
sr_change_ms: 3000
```


#### F8. Contention evidence: the session log's capture stamps; Task 3's output at 21:20; the second run's steps

```
470:== log started 21:26:02 on /dev/cu.usbmodemflip_R0skie1
478:== log stopped 21:26:19
479:== log started 21:28:39 on /dev/cu.usbmodemflip_R0skie1
481:== port dropped 21:29:11: device reports readiness to read but returned no data (device disconnected or multiple access on port?)
482:== log started 21:29:47 on /dev/cu.usbmodemflip_R0skie1
496:== log stopped 21:32:57
497:== log started 21:33:47 on /dev/cu.usbmodemflip_R0skie1
498:== port dropped 21:33:49: device reports readiness to read but returned no data (device disconnected or multiple access on port?)
499:== log started 21:34:26 on /dev/cu.usbmodemflip_R0skie1
500:== port dropped 21:34:27: device reports readiness to read but returned no data (device disconnected or multiple access on port?)
501:== log started 21:34:29 on /dev/cu.usbmodemflip_R0skie1
508:== log stopped 21:35:30
509:== log started 21:35:33 on /dev/cu.usbmodemflip_R0skie1
514:== log stopped 21:35:53
515:== log started 21:35:56 on /dev/cu.usbmodemflip_R0skie1
529:== log stopped 21:38:39
530:== log started 21:46:45 on /dev/cu.usbmodemflip_R0skie1
538:== log stopped 21:47:14
539:== log started 21:50:39 on /dev/cu.usbmodemflip_R0skie1
```

```
== loader info
sreen: TVs. Power
== sr status
== sr voice status

[exited with code 0]
```

```
21:41:00 step: idle check
21:41:01 No application is running announcements 96
21:41:31 No application is running announcements 96
idle
21:41:31 step: paused arrows
paused arrows exit 0
21:42:04 step: accessibility probe
access exit 0
21:42:22 step: bubble watch
bubble exit 0
21:45:30 step: sr_drive
sr_drive exit 0
21:46:23 step: sr_drive --chords
chords exit 0
21:46:44 step: final state
51810 /opt/homebrew/Cellar/python@3.14/3.14.7/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/Ma
21:46:48 done

[exited with code 0]
```


#### F9. Interrupted runs, for the record: the 21:19 send (Task 3's commands) and the 21:33 send (a capture at 21:33:47)

```
== loader open Infrared

     0.00  sr watch
     0.01  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen: Learn New Remote. Saved Remotes. GPIO Settings. Universal Remotes, 1 of 5
  >> OK (Universal Remotes)
     0.89  screen: TVs
  >> OK (TVs)
     5.35  stopped

######## send 1, change delay 3000 ms
== sr delay 3000
change delay set to 3000 ms
== sr status (send 1, change delay 3000 ms, before the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 60, dropped: 0, announcements: 3, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 3, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 849 ms played, 12358 subsamples, 772 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 5, fallback 0, missing 0, open max 29 ms, last 21 ms
free heap: 30528
     0.00  sr watch
     0.01  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen:
     0.40  screen: TVs. Power
     0.00  >> OK on Power
     0.13  change: Sending.... 0%. stop. pause
     3.13  change: 4%
     6.13  change: 9%
     9.13  change: 13%
    12.13  change: 18%
    15.13  change: 23%
    18.13  change: 28%
    21.13  change: 32%
    24.13  change: 35%
    27.13  change: 37%
    30.16  change: 40%
    32.30  change: 42%
   122.51  csopped
== sr status (send 1, change delay 3000 ms, after the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 211, dropped: 0, announcements: 17, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 16, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 320 ms played, 6554 subsamples, 409 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 37, fallback 0, missing 0, open max 38 ms, last 21 ms
free heap: 30896
-- send 1, change delay 3000 ms: send DID NOT END; 12 announcements in the watch, 12 changes; change gaps (s): [3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.03, 2.14]; min gap 2.14
-- last change: '42%' at 32.30 s; last announcement: change: '42%' at 32.30 s
-- counters over the send: announcements +14, suppressed +0, utterances +13, aborted +2
stopping: the send did not end
exit: 1
```

```
== loader open Infrared

     0.00  sr watch
     0.01  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen: Learn New Remote. Saved Remotes. GPIO Settings. Universal Remotes, 1 of 5
  >> OK (Universal Remotes)
     0.89  screen: TVs
  >> OK (TVs)
     5.38  stopped

######## send 1, change delay 3000 ms
== sr delay 3000
change delay set to 3000 ms
== sr status (send 1, change delay 3000 ms, before the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 1544, dropped: 0, announcements: 71, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 70, aborted 8, dropped 0, underruns 0, queue dropped 0
last utterance: 849 ms played, 12358 subsamples, 772 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 220, fallback 0, missing 0, open max 46 ms, last 21 ms
free heap: 30848
     0.00  sr watch
     0.01  Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,
     0.01  letters type into text fields. Ctrl+C stops.
     0.01  screen:
     0.37  screen: TVs. Power
     0.00  >> OK on Power
     0.13  change: Sending.... 0%. stop. pause
     3.14  change: 4%
     6.14  change: 9%
     7.51  screen: TVs. Power
    10.03  stopped
== sr status (send 1, change delay 3000 ms, after the send)
enabled: yes
rate: 76, volume: 80, verbosity: 1, change delay 3000 ms
frames: 1586, dropped: 0, announcements: 76, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 75, aborted 10, dropped 0, underruns 0, queue dropped 0
last utterance: 143 ms played, 3932 subsamples, 245 ms nominal, worker stack free 2508
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 231, fallback 0, missing 0, open max 46 ms, last 24 ms
free heap: 31168
-- send 1, change delay 3000 ms: send ended; 4 announcements in the watch, 3 changes; change gaps (s): [3.01, 3.0]; min gap 3.0
-- last change: '9%' at 6.14 s; last announcement: screen: 'TVs. Power' at 7.51 s
-- counters over the send: announcements +5, suppressed +0, utterances +5, aborted +2
```
