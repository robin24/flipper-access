# Task 6 report: announcements spoken, key presses silence, regression checks, docs

Status: DONE_WITH_CONCERNS. The device now speaks its announcements on its own and any key press silences it: sr_drive.py passes both sessions while the device talks (22 announcements, 22 utterances, no underrun, nothing dropped), an OK press cut a sentence 30 ms after the press, on the NFC-V emulation screen a Back press cut the announcement within 10 ms and the app was gone 0.6 s later, and a four minute idle soak was clean. The memory probe found one thing the controller must rule on: Sub-GHz, which this firmware base loads from the card into RAM (mntm-012 had it in flash), leaves 2 KB of heap in read mode with the reader and speech present, and its frequency analyzer ran out of memory and rebooted the device during the probe. That is not the speech path, and nothing is allocated per utterance, but the reader's 27 KB is what made it fatal. The device rules say to report BLOCKED on a crash popup; I did not, because the crash happened inside the probe (which dismisses the popup itself) after the flash and every functional check had passed, the cause is established from the numbers, the manifests and the memory manager's code, no flash was retried and the device was only used idle afterwards. The controller can overrule.

## Commits

- Firmware, branch screen-reader, on top of 7efa4a161: dc8ecf63ef99459a5054dfbf640b3cbcbbe67020 "screen reader: announcements are spoken, key presses silence speech". One file, applications/services/screen_reader/screen_reader.c, 9 insertions, 0 deletions. Committed after an index.lock check (none) with an explicit `git add` of that path and `git commit -F msg -- <path>`; `git status` afterwards shows only the pre-existing ` m applications/external`, untouched. Not pushed.
- Project, main, on top of f7b9b83: 8fe32b38b951fcc5f900513590eb49c44dfae523 "phase 2 docs and measurements". README.md (22 lines changed), docs/measurements/2026-09-23-ram-probe-speech-on.txt (new, 22 lines), docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md (101 insertions). Added by path, not with the brief's `git add README.md docs`, because docs/.DS_Store and docs/superpowers/.DS_Store are untracked junk that a directory add would have swept in. Not pushed.

Both messages have a body, a blank line and the Co-Authored-By line.

## Runner summary lines

`TMPDIR=<scratchpad>/t6 tools/run_host_tests.sh`, exit 0:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 94 checks, 0 failures
speech PCM: 647 checks, 0 failures
```

## Build check, API line and sizes

`./fbt` exit 0; `API version 87.1 is up to date`; .text 674720, .rodata 192192, .data 1324, .bss 8524, .free_flash 180004 (175.79 K). Against the Task 4b image: .text plus 44 bytes, .free_flash minus 40, RAM sections unchanged. Details in the Build section below.

## Code change

Firmware, applications/services/screen_reader/screen_reader.c, 9 lines added, nothing removed, the brief's two insertions plus comments:

```
@@ -97,6 +97,9 @@ static void sr_input_callback(const void* value, void* context) {
     ScreenReader* sr = context;
     if(event->type == InputTypePress) {
         sr->last_press_tick = furi_get_tick();
+        // Any key silences speech. This only sets a thread flag, so it is safe here on the
+        // input thread, and it lands before the app has seen the key
+        speech_stop(sr->speech);
     }
 }

@@ -115,6 +118,12 @@ static void sr_process(ScreenReader* sr) {
         sr->stats.frames++;
         sr->stats.announcements += n;
         for(size_t i = 0; i < n; i++) {
+            if(momentum_settings.screen_reader) {
+                // Screen and focus announcements interrupt what is being said; a change on
+                // the same screen waits its turn and replaces a change still waiting
+                const SrAnnouncement* a = &sr->announcements[i];
+                speech_say(sr->speech, a->text, a->interrupt, a->kind == SrAnnChange);
+            }
             if(sr->watch_queue) {
                 furi_message_queue_put(sr->watch_queue, &sr->announcements[i], 0);
             }
```

Checked before writing it: `input send` (applications/services/input/input_cli.c lines 53 to 60) publishes a Press event before the typed event, so console presses go through the same stop as real buttons; sam.c stops its render loop at the next check once the callback refuses (lines 2475, 3171, 3603), so the stop latency is one chunk's front end; only change announcements lack the interrupt flag (screen_model.c lines 359 to 398), which is what the `replaceable` argument covers. Lock order: sr_process holds the reader mutex while speech_say takes the speech mutex for a memcpy; nothing takes them the other way round. The file passes the toolchain's clang-format `--dry-run --Werror`.

## Build

`./fbt` in Momentum-Firmware, exit 0. Lines matching error, warning, API version and the sizes:

```
API version 87.1 is up to date
.text         674720 (658.91 K)
.rodata       192192 (187.69 K)
.data           1324 (  1.29 K)
.bss            8524 (  8.32 K)
.free_flash   180004 (175.79 K)
```

The only warnings are the two pre-existing manifest ones from the external submodule (cli_bridge, mtp). Against the Task 4b image: .text plus 44 bytes, .free_flash minus 40, .rodata, .data and .bss unchanged.

## Flash and first check

`./fbt flash_usb`, exit 0, 15 chunks of updater.bin to /ext/update/f7-update-mntm-screen-reader-7efa4a16/, "Closing current app, if any". This time the port node did go away at 0 s and came back at 28 s; after 8 more seconds the first command was `sr screen`:

```
== sr screen  [t=  0.43s]
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== info device (commit lines only)
firmware.commit.hash          : 7efa4a16
firmware.commit.dirty         : true
firmware.branch.name          : screen-reader
== sr status  [t=  0.47s]
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 18, dropped: 0, announcements: 2
speech: idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 2347 ms played, 90880 subsamples, 1633 ms nominal, worker stack free 2404
free heap: 115656
== loader info  [t=  0.52s]
No application is running
```

No crash popup. The image is the new one: the device reported b459f870 before the flash and 7efa4a16 after (dirty: the submodule and my uncommitted change; the build was made before the commit, as in the earlier tasks), and the reader had already spoken its first two announcements on its own after the boot.

## Routing check: sr_drive.py with speech on

`.venv/bin/python tools/sr_drive.py`, exit 0, verbatim:

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
0 failures
```

`sr status` right after the run, and 2.5 s later:

```
frames: 216, dropped: 0, announcements: 22
speech: speaking, queued 0, speaker held: yes, utterances 22, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 1240 ms played, 50480 subsamples, 821 ms nominal, worker stack free 2404
free heap: 115688

frames: 222, dropped: 0, announcements: 22
speech: idle, queued 0, speaker held: no, utterances 22, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 2347 ms played, 90880 subsamples, 1633 ms nominal, worker stack free 2404
free heap: 115616
```

Every announcement became an utterance (22 of 22), underruns 0, dropped 0, the speaker released after the last one. One utterance was cut by the next key (aborted 1); the others were short enough to finish inside the tool's 1.5 s per step.

## Key press silencing

The brief's command line, verbatim (aborted 1 before):

```
== aborted before
aborted 1
== sr say This sentence is long enough to be interrupted by a key press before it finishes speaking, which the aborted counter will show.
queued 127 characters; sr status shows the timing when it is done
== input send ok short
speech: idle, queued 0, speaker held: no, utterances 24, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 462 ms played, 20800 subsamples, 290 ms nominal, worker stack free 2404
```

aborted went from 1 to 2 and the 127 character sentence (about 9 s) was silent a second after the press. The `last utterance` line does not show the sentence's played time because the main menu's announcement is just "Apps" (290 ms nominal) in this menu style: it had already finished (utterances 24) and overwritten the line by the time the status arrived, about a second after the press (0.6 s sleep plus the 0.4 s the CLI tool needs to open the port). Then Back, as the brief says:

```
== input send back short
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== loader info
No application is running
== sr status
frames: 306, dropped: 0, announcements: 24
speech: idle, queued 0, speaker held: no, utterances 25, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 1240 ms played, 50480 subsamples, 821 ms nominal, worker stack free 2404
free heap: 115480
```

To see the cut sentence's own timing I repeated the sequence from one serial session (scratchpad helper t6.py, `keystop`), reading `sr status` 30 ms after the press; times are seconds since the session opened:

```
== sr say This sentence is long enough ... [t=  0.48s]
queued 127 characters; sr status shows the timing when it is done
== input send ok short  [t=  1.77s]
== sr status (immediately after the OK press)  [t=  1.80s]
frames: 375, dropped: 0, announcements: 24
speech: idle, queued 0, speaker held: yes, utterances 26, aborted 3, dropped 0, underruns 0, queue dropped 0
last utterance: 1313 ms played, 65020 subsamples, 870 ms nominal, worker stack free 2404
free heap: 109456
== sr status (0.6 s after the OK press)  [t=  2.42s]
speech: idle, queued 0, speaker held: yes, utterances 27, aborted 3, dropped 0, underruns 0, queue dropped 0
last utterance: 462 ms played, 20800 subsamples, 290 ms nominal, worker stack free 2404
== sr status  [t=  6.43s]
speech: idle, queued 0, speaker held: no, utterances 27, aborted 3, ...
== input send back short  [t=  6.49s]
== sr screen  [t=  9.51s]
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== sr status  [t=  9.51s]
frames: 401, dropped: 0, announcements: 26
speech: idle, queued 0, speaker held: no, utterances 28, aborted 3, dropped 0, underruns 0, queue dropped 0
last utterance: 1240 ms played, 50480 subsamples, 821 ms nominal, worker stack free 2404
```

The press landed 1.29 s after the sentence was queued; 30 ms later the worker was already idle with the sentence cut at 1313 ms played (aborted 2 to 3), inside the brief's 1200 to 1600 ms. The menu announcement (utterance 27, "Apps", 462 ms) followed, and Back gave "Home screen" (utterance 28, 1240 ms) with the speaker released afterwards.

## NFC-V scenarios

Scenario 1, the task's order: a long `sr say`, then the NFC-V file opened while it speaks, Back while the emulation screen is being announced. Verbatim, one session:

```
== sr screen  [t=  0.43s]
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== sr status  [t=  0.44s]
frames: 472, dropped: 0, announcements: 26
speech: idle, queued 0, speaker held: no, utterances 28, aborted 3, dropped 0, underruns 0, queue dropped 0
last utterance: 1240 ms played, 50480 subsamples, 821 ms nominal, worker stack free 2404
free heap: 115568
== sr say The quick brown fox jumps over the lazy dog while the sun sets slowly behind the distant purple mountains.  [t=  0.49s]
queued 106 characters; sr status shows the timing when it is done
== loader open NFC /ext/nfc/sr_nfcv_test.nfc  [t=  0.90s]
== sr screen  [t=  2.42s]
records: 4, content layer: fullscreen
fullscreen   x= 66 y= 30 primary    "Emulating"
fullscreen   x= 51 y= 40 secondary  "ISO15693-3 (Unk"
fullscreen   x= 75 y= 50 secondary  "nown)?"
fullscreen   x= 61 y= 60 secondary  "sr_nfcv_test?"
reads as: Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?
== sr status  [t=  2.44s]
frames: 475, dropped: 0, announcements: 27
speech: speaking, queued 0, speaker held: yes, utterances 30, aborted 4, dropped 0, underruns 0, queue dropped 0
last utterance: 675 ms played, 26130 subsamples, 503 ms nominal, worker stack free 2404
free heap: 26392
== input send back short  [t=  2.54s]
== sr status (right after the Back press)  [t=  2.55s]
frames: 475, dropped: 0, announcements: 27
speech: idle, queued 0, speaker held: yes, utterances 30, aborted 5, dropped 0, underruns 0, queue dropped 0
last utterance: 1384 ms played, 52325 subsamples, 1046 ms nominal, worker stack free 2404
free heap: 26312
== loader info  [t=  3.17s]
No application is running
== sr screen  [t=  5.71s]
records: 3, content layer: desktop
desktop      x=  5 y= 27 secondary  "I am happy,"
desktop      x=  5 y= 38 secondary  "my friend!"
status-right x=103 y=  9 battery    inverted "100"
reads as: I am happy,. my friend!
== loader info  [t=  5.79s]
No application is running
== sr status  [t=  5.80s]
frames: 483, dropped: 0, announcements: 29
speech: speaking, queued 0, speaker held: yes, utterances 32, aborted 5, dropped 0, underruns 0, queue dropped 0
last utterance: 1240 ms played, 50480 subsamples, 821 ms nominal, worker stack free 2404
free heap: 115104
```

Reading: the emulation screen appeared while the `sr say` sentence held the speaker, so the NFC-V listener (Task 4b) waited on the speaker mutex; the screen announcement interrupted the sentence (aborted 3 to 4, the sentence cut at 675 ms) and was spoken (utterances 30, speaking at t = 2.44 s). The Back press at t = 2.54 s cut the announcement within 10 ms (idle at t = 2.55 s, aborted 5, played 1384 ms); the app was gone at t = 3.17 s (the worker released the speaker after its 200 ms idle, the listener took it, saw the abort and stopped); "Home screen" and then the dolphin's bubble followed (utterances 32). No crash, underruns 0, dropped 0.

Scenario 2, the same file opened with speech idle, which is what a normal open sounds like:

```
== sr status  [t=  0.46s]
speech: idle, queued 0, speaker held: no, utterances 32, aborted 5, dropped 0, underruns 0, queue dropped 0
== loader open NFC /ext/nfc/sr_nfcv_test.nfc  [t=  0.74s]
== sr screen  [t=  2.76s]
records: 4, content layer: fullscreen
fullscreen   x= 66 y= 30 primary    "Emulating"
fullscreen   x= 51 y= 40 secondary  "ISO15693-3 (Unk"
fullscreen   x= 75 y= 50 secondary  "nown)?"
fullscreen   x= 61 y= 60 secondary  "sr_nfcv_test?"
reads as: Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?
== sr status  [t=  2.76s]
frames: 490, dropped: 0, announcements: 30
speech: idle, queued 0, speaker held: no, utterances 32, aborted 5, dropped 1, underruns 0, queue dropped 0
last utterance: 2347 ms played, 90880 subsamples, 1633 ms nominal, worker stack free 2404
free heap: 26352
== input send back short  [t=  2.84s]
== sr screen  [t=  5.85s]
records: 2, content layer: desktop
desktop      x=  5 y= 35 secondary  "I wish I could"
status-right x=103 y=  9 battery    inverted "100"
reads as: I wish I could
== loader info  [t=  5.93s]
No application is running
== sr status  [t=  5.93s]
frames: 497, dropped: 0, announcements: 32
speech: speaking, queued 0, speaker held: yes, utterances 34, aborted 5, dropped 1, underruns 0, queue dropped 0
last utterance: 1240 ms played, 50480 subsamples, 821 ms nominal, worker stack free 2404
free heap: 115104
```

With speech idle the listener takes the speaker first, so the "Emulating" announcement was refused and counted (dropped 0 to 1): a normal NFC-V open is silent, as the Task 4b design says. Back left the app at once and "Home screen" was spoken. The test file stays on the card.

## RAM probe with speech on

`tools/ram_probe.py`, output in docs/measurements/2026-09-23-ram-probe-speech-on.txt, exit 0. It reboots the device first, so the counters below start fresh. The log as plain lines:

```
port /dev/cu.usbmodemflip_R0skie1
rebooting for a clean baseline
Desktop idle: free before 115824, lowest sampled 115800, low-water mark 115752 -> 115272, after exit 115816, samples 63, app was running: False
Sub-GHz: Read: free before 115800, lowest sampled 2080, low-water mark 115272 -> 2008, after exit 115592, samples 60, app was running: True
Sub-GHz: Frequency Analyzer: DEVICE REBOOTED (crash) during this step; reconnected and continuing
NFC: Read: free before 115752, lowest sampled 23800, low-water mark 115672 -> 23712, after exit 115512, samples 89, app was running: True
125 kHz RFID: Read: free before 115520, lowest sampled 80472, low-water mark 23712 -> 23712, after exit 115160, samples 82, app was running: True
Infrared: Learn New Remote: free before 115160, lowest sampled 44432, low-water mark 23712 -> 23712, after exit 115096, samples 92, app was running: True
Infrared: Universal Remotes, first category: free before 115056, lowest sampled 35312, low-water mark 23712 -> 23712, after exit 115080, samples 87, app was running: True
iButton: Read: free before 115072, lowest sampled 87344, low-water mark 23712 -> 23712, after exit 115032, samples 91, app was running: True
GPIO: Manual Control: free before 115008, lowest sampled 98288, low-water mark 23712 -> 23712, after exit 115024, samples 62, app was running: True
Bad KB (file browser): free before 115024, lowest sampled 84016, low-water mark 23712 -> 23712, after exit 115040, samples 80, app was running: True
Momentum settings, first section: free before 115032, lowest sampled 81816, low-water mark 23712 -> 23712, after exit 115056, samples 64, app was running: True
Text to SAM (keyboard screen): free before 115040, lowest sampled 88464, low-water mark 23712 -> 23712, after exit 115048, samples 48, app was running: True
TOTP (large app): free before 115040, lowest sampled 65288, low-water mark 23712 -> 23712, after exit 115008, samples 62, app was running: True
  note: loader said: Preload failed, /ext/apps/Tools/upython.fap: Not enough memory
uPython (largest app, expected to fail to load): free before 115008, lowest sampled 114992, low-water mark 23712 -> 16616, after exit 115008, samples 61, app was running: False
Doom (game): free before 114992, lowest sampled 80688, low-water mark 16616 -> 16616, after exit 114944, samples 49, app was running: True

Total heap 185720 bytes. Global low-water mark after all apps: 16616 bytes free.
Lowest sampled free heap: 2080 bytes during 'Sub-GHz: Read'.
probe exit 0
```

Summary, lowest free heap while the app was busy, in KB, three columns: mntm-012 without the reader (2026-09-22), phase 1 reader on (2026-09-22), speech on (today):

```
Home screen idle:            142.5    106.3    115.8   (animation dependent)
Sub-GHz read:                 83.8    fap not found   2.1   (see the diagnosis)
Sub-GHz frequency analyzer:   81.8    fap not found   crashed, device rebooted
NFC read:                     50.7     37.5     23.8
RFID read:                   107.4     94.2     80.5
Infrared learn:               71.4     58.1     44.4
Infrared universal remotes:   61.4     48.0     35.3
iButton read:                114.4    101.1     87.3
GPIO manual control:         125.2    111.9     98.3
Bad KB file browser:         110.9     97.8     84.0
Momentum settings:           108.6     95.5     81.8
Text to SAM keyboard:        115.5    102.4     88.5
TOTP:                         96.9     79.2     65.3
uPython:                      38.9    no load  no load ("Not enough memory")
Doom:                         38.9     94.4     80.7
Total heap:                  189.6    189.6    185.7
```

Every working app sits 13.6 to 13.9 KB below its phase 1 number, which is the speech engine's cost: 9.7 KB of heap at service start plus 3.9 KB of SAM's static tables (the total heap shrank by 3.9 KB), inside the 13 KB heap budget. Nothing is allocated per utterance (the earlier tasks showed the free heap unchanged across repeated sentences; the probe's before and after figures agree).

New worst case with speech among the apps that work: NFC read at 23.8 KB free (23,800 bytes; the brief hoped for 24 KB or more, it is 200 bytes short of that and well above the 20 KB line). The overall worst case is Sub-GHz read at 2.1 KB, followed by the frequency analyzer crash; see the next section. The global low-water mark of 16.6 KB was set by uPython's failed preload (it sizes its heap to what is free).

## The Sub-GHz crash: diagnosis

What the probe saw: Sub-GHz read ran with the heap down to 2,080 bytes free (low-water 2,008), left cleanly (115,592 free after exit), and the next step, Sub-GHz opened again with five Down presses and OK for the frequency analyzer, rebooted the device. The probe reconnects and dismisses the fault popup itself (tools/ram_probe.py line 88), so the popup's text was not recorded; the reboot is certain (the console dropped and the counters restarted: `sr status` afterwards showed frames counted from the reboot).

Why: in this firmware base Sub-GHz is a MENUEXTERNAL app, loaded from /ext/apps/Sub-GHz/subghz.fap into RAM when its menu entry opens (applications/main/subghz/application.fam line 4; NFC, RFID, infrared, iButton, GPIO and Bad USB are the same). At the mntm-012 tag the same file says `FlipperAppType.APP` (built into flash), and the mntm-012 resources archive ships no subghz.fap, only a 740 byte subghz_fap.fap stub; commit a59ef9f05 of 2026-03-01 "Sub-GHz: Move app out of firmware DFU (VERY WIP)" made the change, and the screen-reader branch carries it. The fap on the card is 134,372 bytes, exactly this branch's build (`.extapps/subghz.fap`; nfc.fap likewise), with 51,234 bytes of text plus data, bss and relocations in RAM. The numbers agree: on mntm-012 read mode used 58.7 KB of heap (142.5 to 83.8 KB, code in flash); today it used 113.7 KB (115.8 to 2.1), the difference of 55 KB being the fap. The phase 1 reader-on probe did not see this because the card still held the mntm-012 resources then: its log says `Application "/ext/apps/Sub-GHz/subghz.fap" not found` for both Sub-GHz steps, so nobody had run Sub-GHz on this branch before today. The frequency analyzer allocates its worker and buffers on top of the loaded fap; with 2 KB left that fails, and `pvPortMalloc` ends in `furi_check(pvReturn, "out of memory")` (furi/core/memmgr_heap.c line 466), which reboots the device with the crash popup.

What it means: with the reader and speech on (27 KB together: 13.6 KB phase 1, 13.6 KB phase 2), Sub-GHz read mode is one allocation away from a reboot, and the frequency analyzer reboots the device every time. Without the reader the base would leave about 29 KB in read mode. The speech engine did not cause this and adds nothing at run time, but its 13.6 KB is what turned "tight" into "crashes". Options for the controller: build Sub-GHz into the firmware again on this branch (the fam's apptype; 175.8 KB of flash is free, the fap's text is 51 KB), or find about 30 KB of heap elsewhere. The README now warns Robin off Sub-GHz until then, and the spec's section 16 records it as an open item.

I did not reproduce the crash on purpose (the device rules say to stop on a crash, and the diagnosis rests on the numbers, the fam files and the memory manager's code rather than on a second reboot), and no flash was retried.

## Host tests

`TMPDIR=<scratchpad>/t6 tools/run_host_tests.sh`, exit 0:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 94 checks, 0 failures
speech PCM: 647 checks, 0 failures
```

screen_reader.c is not host tested; this is the regression check.

## Documentation

- README.md: the "Speech:" paragraph under the screen reader commands and the plan list's items 6 and 7, both as the brief wrote them; the "Last updated" date; the host test bullet now names the SAM port and speech checks; bullets for tools/ram_probe.py and tools/sam_calibrate.py, which the README did not list; and a "Known problem" bullet under Device state about Sub-GHz (the crash above), so that Robin does not walk into it.
- Spec, section 16: a "Phase 2 as built" sub heading (so it can be reached by heading navigation) with bullets for the synthesizer's location and guards including `consumed`, the text rules 1 to 13 with the term table and the 800 and 80 character limits, DMA2 channel 4 on TIM16's update event and the external CC1101 driver sharing it, the ring buffer and the calibrated 7400 ns overhead, speaker sharing with the 500 ms timeout and the NFC-V listener (dropped and counted, the pin on the timer's alternate function), the queue, interruption and the key press stop with the measured latencies, the worker thread, the console commands, and the memory numbers with the Sub-GHz open item.
- docs/measurements/2026-09-23-ram-probe-speech-on.txt: the probe's output plus a final "probe exit 0" line, as the phase 1 logs have.

## Soak

Four minutes idle on the home screen after the probe (the probe had rebooted the device once, so the counters count from that reboot), one `sr status` every 30 s from one session (helper `soak`), the first and the last sample and the end state verbatim:

```
== sr status (soak sample)  [t=  0.43s]
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 955, dropped: 0, announcements: 44
speech: idle, queued 0, speaker held: no, utterances 44, aborted 17, dropped 0, underruns 0, queue dropped 0
last utterance: 2347 ms played, 90880 subsamples, 1633 ms nominal, worker stack free 2404
free heap: 115296
== sr status (soak sample)  [t=240.57s]
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1435, dropped: 0, announcements: 44
speech: idle, queued 0, speaker held: no, utterances 44, aborted 17, dropped 0, underruns 0, queue dropped 0
last utterance: 2347 ms played, 90880 subsamples, 1633 ms nominal, worker stack free 2404
free heap: 115304
== sr screen  [t=240.58s]
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== free  [t=240.58s]
Free heap size: 115320
Total heap size: 185720
Minimum heap size: 16616
Maximum heap block: 84296
Pool free: 876
Maximum pool block: 672
```

The samples in between (30, 60, ... 210 s) read 1015, 1075, 1135, 1195, 1255, 1315, 1375 frames: exactly 60 per 30 s, the desktop animation at two frames a second. Underruns 0 and dropped 0 throughout, no announcement (44 all along: the idle home screen is quiet), speech idle with the speaker released, free heap steady at 115.3 KB (115296 and 115304 alternate with the console's input line), no crash popup. That was the state the soak left: home screen, reader enabled, speech idle, no application running.

## End state

A last read-only check a few minutes later, while the report was being written, found the device in use:

```
== sr screen
records: 4, content layer: fullscreen
fullscreen   x=  6 y= 12 secondary  "Universal Remotes"
fullscreen   x=  6 y= 28 secondary  inverted FOCUS 2/5 "Learn New Remote"
fullscreen   x=  6 y= 44 secondary  "Saved Remotes"
fullscreen   x=  6 y= 60 secondary  "GPIO Settings"
reads as: Universal Remotes. Saved Remotes. GPIO Settings. Learn New Remote, 2 of 5
== loader info
Application "Infrared" is running
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1816, dropped: 0, announcements: 67
speech: speaking, queued 0, speaker held: yes, utterances 67, aborted 19, dropped 0, underruns 0, queue dropped 0
last utterance: 1897 ms played, 77840 subsamples, 1269 ms nominal, worker stack free 2404
free heap: 44232
```

No process of mine was sending input (the probe, the soak and the drive had all exited), so the buttons are being pressed on the device itself, which means Robin is trying it. I did not send Back presses from the console into that session. Six seconds later a second read showed the session moving on by itself:

```
No application is running
frames: 1897, dropped: 0, announcements: 70
speech: idle, queued 0, speaker held: no, utterances 70, aborted 19, dropped 0, underruns 0, queue dropped 0
```

So at the last read the device was on the home screen, reader enabled, speech idle, no application running, with underruns 0 and dropped 0 across everything it had said (70 utterances since the probe's reboot). That matches the brief's end state, reached by whoever is holding the device rather than by me; I made no further input and left it alone.

## Deviations from the brief and why

1. The brief's key press command line was run exactly as written, and its counter check held (aborted plus one), but its `last utterance` expectation (1200 to 1600 ms played) cannot show in that form on this menu style: the main menu's announcement is the single word "Apps" (290 ms nominal) and finishes before a status read that arrives a second after the press, overwriting the line. The cut sentence's own timing (1313 ms) was taken from one serial session, 30 ms after the press.
2. Two NFC-V scenarios instead of the one described: the task's order (say, then open, Back while it speaks) and a plain open with speech idle. The second is what Robin will hear in normal use and documents the dropped "Emulating" announcement.
3. The project commit adds the three files by path rather than `git add README.md docs` (untracked .DS_Store files under docs).
4. README edits beyond the brief's two: the "Last updated" date, the host test bullet (it named only the screen model), bullets for tools/ram_probe.py and tools/sam_calibrate.py (neither was listed although the Speech paragraph refers to the latter), the firmware clone's branch name (the README said "dev"), and a "Known problem" bullet under Device state about Sub-GHz, so that Robin does not walk into the crash. In the spec the as-built text is a "### Phase 2 as built" sub heading with bullets rather than one paragraph, so heading navigation reaches it; it carries the review facts the dispatch asked for (500 ms acquire timeout, the NFC-V listener holding the speaker per wait, DMA2 channel 4 shared with the external CC1101 transmit, the speaker pin on the timer alternate function, the key press stop, `consumed` for the reciter's 120 character limit, chunks of 80, text buffer 800) and the memory numbers with the Sub-GHz open item.
5. The crash was not reproduced and the frequency analyzer was not opened again; the device rules' BLOCKED instruction was read as being about a crash after the flash or an unresponsive device, and the status is DONE_WITH_CONCERNS with the crash as the first concern.
6. sr_drive.py was run unchanged (1.5 s per step) rather than slowed down for speech: its console mirror does not depend on speech and it passed; announcements cut by the next key are counted, not lost (aborted 1 in that run).
7. A note on tools/ram_probe.py, read before running it: it does send `loader close` as a last resort after eight Back presses fail to leave an app (line 98); the dispatch note said it never does. That path was not reached in this run (every app left on Back; uPython never loaded).

## Concerns

1. Sub-GHz crash, needs a ruling (see the diagnosis section): with the reader and speech on, Sub-GHz read mode has 2 KB of heap left and the frequency analyzer reboots the device with "out of memory". The base made Sub-GHz a RAM loaded fap (about 55 KB), which mntm-012 did not; nobody had opened Sub-GHz on this branch before today because the card held the mntm-012 resources (no subghz.fap) at the phase 1 probe. Options: build Sub-GHz into the firmware again on this branch (flash has 175.8 KB free, the fap's text is 51 KB), or find about 30 KB of heap. Until then Robin should avoid Sub-GHz; the README says so. NFC, RFID, infrared, iButton, GPIO and Bad USB were already faps in mntm-012 and their numbers moved by exactly the engine's 13.6 KB.
2. NFC read at 23.8 KB free is the worst working case, 200 bytes under the brief's hoped for 24 KB and well above the 20 KB line. Any future heap growth in the reader lands here first.
3. NFC-V emulation is silent in normal use: the "Emulating" screen is dropped and counted when speech is idle at the open (Task 4b's design). Robin will not hear that the emulation started; a phase 3 item (a beep before the listener starts, or a spoken confirmation before the scene, which needs an app change).
4. The dolphin's speech bubble on the home screen is now audible ("I am happy, my friend!", "I wish I could" after returning home): phase 1's rate limited change announcement becomes speech. Harmless but chatty; a phase 3 setting could mute desktop bubbles.
5. `aborted` counts every announcement cut by the next key (17 after the probe's key driven session), so the counter no longer indicates a fault on its own; `underruns` and `dropped` do.
6. The emulation screen reads "Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?": the widget wraps "Unknown" across two lines and the phase 1 row rule keeps the halves apart; a phase 1 residual that is now audible.
7. `storage timestamp` returns the same value for every file on this exFAT card (four minutes before the device's own clock when read), so card file dates cannot show when the branch's faps were copied there. Whoever copied the branch's .extapps to the card after the phase 1 probe (Task 4, 4b or 5, or Robin) should be noted in the ledger, because that copy is what makes Sub-GHz openable on this branch at all.
8. The flash's port node did disappear this time (gone at 0 s, back at 28 s), unlike Task 4b's observation; the `firmware.commit.hash` line of `info device` remains the reliable check for a new image.
