# Task 2 report: the worker plays clips, the setting and the console command

Status: DONE_WITH_CONCERNS

The concerns are about what the brief expected, not about the code. The code went in exactly as the brief gives it and works on the device. Two expectations in the brief do not match its own code or the clips: step 6 expects "fallback +2" and step 1 expects "clips 0". Lint also needed a whitespace-only fix to Task 1's file. Details are under "Deviations" and "Concerns".

## Commits

Firmware repo /Users/robin/Downloads/flipper-access/Momentum-Firmware, branch screen-reader. Nothing pushed. applications/external is untouched: it is still the only entry in `git status --porcelain`.

- c5e6e0e64aff06a7bc846bfceddb073ce345c37b "screen reader: clang-format the voice module". File: applications/services/screen_reader/speech_voice.c. Whitespace only: four one-line `while` loops now put their body on its own line. This was needed for `./fbt lint`; see Deviations.
- c776d48f7e89c3bce4ff477e9dc5d7230ddac592 "screen reader: recorded word clips from the card with SAM as the fallback". This is the Task 2 commit and HEAD. Files: speech.h, speech.c, screen_reader.c and screen_reader_cli.c (all under applications/services/screen_reader), plus lib/momentum/settings.h and lib/momentum/settings.c. 213 insertions.

Both commits used an explicit `git add <files>` followed by `git commit -m "<subject>" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- <files>`. The project repo (main, 5cca139) is unchanged by this task. Its only outstanding entry is the untracked clip-experiment.md that was there before.

## Step 4: build, lint, headroom, host tests

### Build

`./fbt 2>&1 | grep -E "error|warning|API version|free_flash" | head`. The same output came from the build before the commits and the rebuild after them. Exit 0.

```
fbt: warning: Failed parsing manifest '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui'. Must match regex 're.compile('^[a-z0-9_]+$')'
fbt: warning: Failed parsing manifest '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/mtp/application.fam' : Invalid appid '.f0_mtp'. Must match regex 're.compile('^[a-z0-9_]+$')'
API version 87.1 is up to date
.free_flash   176840 (172.70 K)
```

A case-insensitive grep for "error" and "warning" over the whole log finds only those two pre-existing manifest warnings. After the commits, build/f7-firmware-C/toolbox/version.inc.h reads `#define GIT_COMMIT "c776d48f"` with `BUILD_DIRTY 1`; the dirty flag comes from the modified submodule.

### Lint, first run

Exit 2. Every error is in Task 1's committed file; none is in a file of this task:

```
applications/services/screen_reader/speech_voice.c:15:51: error: code should be clang-formatted [-Wclang-format-violations]
    while(text[i] != '\0' && sv_is_space(text[i])) i++;
applications/services/screen_reader/speech_voice.c:21:52: error: code should be clang-formatted [-Wclang-format-violations]
    while(text[i] != '\0' && !sv_is_space(text[i])) i++;
applications/services/screen_reader/speech_voice.c:34:51: error: code should be clang-formatted [-Wclang-format-violations]
    while(start < end && sv_is_punct(text[start])) start++;
applications/services/screen_reader/speech_voice.c:35:53: error: code should be clang-formatted [-Wclang-format-violations]
    while(end > start && sv_is_punct(text[end - 1])) end--;
scons: *** [phony_lint] Error 1
```

### Lint, after the formatting fix

I ran the toolchain's clang-format with `--style=file -i` on speech_voice.c. `./fbt lint` then exited 0. Its last two lines:

```
LoadAppManifest, line 135, in file "/Users/robin/Downloads/flipper-access/Momentum-Firmware/scripts/fbt_tools/fbt_apps.py"
python3 scripts/lint.py check applications !applications/system/js_app/packages !applications/external lib/print lib/toolbox lib/drivers lib/flipper_format lib/one_wire lib/ibutton lib/infrared lib/subghz lib/nfc lib/digital_signal lib/pulse_reader lib/signal_reader lib/u8g2 lib/lfrfid lib/music_worker lib/update_util lib/momentum lib/bit_lib lib/datetime lib/ieee754_parse_wrap targets furi
```

### Flash headroom

`tools/flash_headroom.sh` gave the same result on both builds, exit 0:

```
firmware.bin 871736 bytes, limit 880640, spare 8904 bytes
```

The plan measured 10,884 spare bytes, so this task, including the voice module that is now linked in, costs 1,980 bytes of flash.

### Host tests

`TMPDIR=/private/tmp/claude-501/-Users-robin-Downloads-flipper-access/7e5c805a-c471-4df7-96ca-14e7ee87ded9/scratchpad/v2 tools/run_host_tests.sh 2>&1 | tail -7`, run after the formatting fix, exit 0:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 115 checks, 0 failures
speech PCM: 700 checks, 0 failures
speech voice: 127 checks, 0 failures
```

## Step 5: hand-made clips

The clips were made in scratchpad/v2/handclips. The brief's `ls $D | wc -l` printed `17`: sixteen words plus `ay`, counted before voice.txt was written. Clip sizes range from 6,999 bytes (of) to 15,600 bytes (ay); they are untrimmed, as the brief asks. voice.txt is 75 bytes.

Upload: `mkdir /ext/sr` printed `Error: Storage error: path '/ext/sr': file/dir already exist`, which is expected. Every other mkdir and send was silent.

`storage list /ext/sr/voice/s`:

```
	[F] settings.raw 12678b
	[F] sub.raw 10064b
	[F] screen.raw 11935b
	[F] saved.raw 11192b
```

I also checked the whole tree. `storage tree /ext/sr/voice` shows all 17 clips in the folders s, g, a, o, e, h, r, b and c, each with its local size, plus `/ext/sr/voice/voice.txt 75b`.

`storage read /ext/sr/voice/voice.txt`:

```
Size: 75
say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand made, Task 2)
```

## Step 6: flash and verify on the device

Before the flash the device was idle. `loader info` said "No application is running" and speech was idle. The old image reported `firmware.commit.hash : 77a57c97` with dirty true. That image is the 54794522b tree, flashed before that commit was made. On the old image, `sr status` showed free heap 115248 and `free` showed a minimum heap of 112672.

`./fbt flash_usb` ran from 01:13:51 to 01:14:25 with exit 0. It built package f7-update-mntm-screen-reader-c776d48f, sent firmware.dfu in 107 chunks plus update.fuf and updater.bin in 15 chunks, then printed "Closing current app, if any". The port node was already absent when my poll started at 01:14:37. It was back at 01:14:54. After 12 s of settling, the first command, sent alone, was:

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as:
```

There was no crash popup. Next came `info device`, filtered here to the commit lines, then `sr status` and `free`. These are the heap baseline:

```
firmware.commit.hash          : c776d48f
firmware.commit.dirty         : true
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 63, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1458 ms played, 22781 subsamples, 1423 ms nominal, worker stack free 2684
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 2, fallback 0, missing 0
free heap: 114536
== free
Free heap size: 114616
Total heap size: 185904
Minimum heap size: 112480
Maximum heap block: 114368
Pool free: 876
Maximum pool block: 672
== loader info
No application is running
```

The boot announcement "Home screen" already came from the clips. The card was mounted before the first utterance, so the vocabulary was found then. The subsample count checks out: 9,566 + 11,935 clip samples plus two 40 ms gaps (640 samples each) make 22,781.

The results below come from a helper, scratchpad/v2/vstep.py. It keeps one serial session open and stamps each command with the time since the helper started. For each `sr say`, it reads `sr status` and `sr voice status` at 4 s, then polls until speech is idle and reads both again.

### 1. sr voice status

```
== sr voice status
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 2, fallback 0, missing 0
```

The vocabulary shows yes, so `sr say hello` was not needed. The count is clips 2 rather than the brief's 0, because of the boot announcement. The settings line is cut at 63 characters because the settings field is 64 bytes and the hand-made line is 74 characters long.

I also checked the argument handling. `sr voice` with no argument prints the same status line. `sr voice bogus` prints `sr voice on|off|status`. The `sr` usage now ends with `  voice on|off|status  recorded word clips from the card, SAM for the rest (saved)`.

### 2. sr say Settings. Sub-GHz. Apps, 1 of 11.

```
[01:15:40 + 0.443s] == sr say Settings. Sub-GHz. Apps, 1 of 11.   (reply after 0.015s)
queued 33 characters; sr status shows the timing when it is done
[01:15:44 + 4.443s] == sr status   (reply after 0.010s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 103, dropped: 0, announcements: 1, suppressed: 1
speech: speaking, queued 0, speaker held: yes, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1458 ms played, 22781 subsamples, 1423 ms nominal, worker stack free 2684
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 6, fallback 0, missing 0
free heap: 113760
[01:15:44 + 4.449s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 6, fallback 0, missing 0
[01:15:46 + 6.343s] speech idle
[01:15:46 + 6.352s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 106, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: yes, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 5876 ms played, 93660 subsamples, 5853 ms nominal, worker stack free 2684
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 9, fallback 0, missing 0
free heap: 114424
[01:15:46 + 6.358s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 9, fallback 0, missing 0
```

Result: utterances +1 (1 to 2), underruns 0, clips +7 (2 to 9), fallback +0.

The untrimmed clips make this utterance 5.85 s long, so at the brief's 4 s mark it was still speaking, with 6 clips counted; the final counts came once speech was idle. The subsample count checks out: 74,940 clip samples plus 1,170 ms of pauses (18,720 samples) make 93,660. The played time is 0.4 percent over nominal, the same as `sr play`.

### 3. sr say Bahncard office, twice

```
[01:15:56 + 0.441s] == sr say Bahncard office   (reply after 0.013s)
queued 15 characters; sr status shows the timing when it is done
[01:16:00 + 4.438s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 134, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 3, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1827 ms played, 48897 subsamples, 1526 ms nominal, worker stack free 2428
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 10, fallback 1, missing 1
free heap: 114528
[01:16:00 + 4.471s] == sr voice status   (reply after 0.032s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 10, fallback 1, missing 1
[01:16:00 + 4.480s] speech idle
[01:16:00 + 4.489s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 134, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 3, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1827 ms played, 48897 subsamples, 1526 ms nominal, worker stack free 2428
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 10, fallback 1, missing 1
free heap: 114472
[01:16:00 + 4.495s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 10, fallback 1, missing 1
[01:16:00 + 0.444s] == storage read /ext/sr/missing.txt   (reply after 0.018s)
Size: 9
bahncard
[01:16:01 + 0.441s] == sr say Bahncard office   (reply after 0.013s)
queued 15 characters; sr status shows the timing when it is done
[01:16:05 + 4.447s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 144, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 4, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1824 ms played, 48897 subsamples, 1526 ms nominal, worker stack free 2428
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 11, fallback 2, missing 1
free heap: 114496
[01:16:05 + 4.455s] == sr voice status   (reply after 0.007s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 11, fallback 2, missing 1
[01:16:05 + 4.464s] speech idle
[01:16:05 + 4.473s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 145, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 4, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1824 ms played, 48897 subsamples, 1526 ms nominal, worker stack free 2428
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 11, fallback 2, missing 1
free heap: 114448
[01:16:05 + 4.480s] == sr voice status   (reply after 0.007s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 11, fallback 2, missing 1
[01:16:05 + 0.443s] == storage read /ext/sr/missing.txt   (reply after 0.017s)
Size: 9
bahncard
```

Result: after the first say, clips +1, fallback +1 and missing 1, and the file holds `bahncard`. After the second, missing is still 1 and the file still has one line (9 bytes). The worker stack watermark reached 2428 once SAM had run; phase 2 measured 2396 to 2412.

### 4. sr say A B C

```
[01:16:13 + 0.472s] == sr say A B C   (reply after 0.044s)
queued 5 characters; sr status shows the timing when it is done
[01:16:17 + 4.457s] == sr status   (reply after 0.022s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 168, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 5, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 2192 ms played, 34469 subsamples, 2154 ms nominal, worker stack free 2428
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 14, fallback 2, missing 1
free heap: 114560
[01:16:17 + 4.463s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 14, fallback 2, missing 1
[01:16:17 + 4.472s] speech idle
[01:16:17 + 4.481s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 168, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 5, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 2192 ms played, 34469 subsamples, 2154 ms nominal, worker stack free 2428
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 14, fallback 2, missing 1
free heap: 114520
[01:16:17 + 4.487s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 14, fallback 2, missing 1
```

Result: clips +3 (11 to 14), fallback +0. The subsample count checks out: 15,600 + 7,615 + 9,334 plus three 40 ms gaps make 34,469.

### 5. A long say cut by Back after one second

The text has 30 words, 12 from the vocabulary and 18 from outside it, in 158 characters so that it fits the queue item: "Settings quick home brown screen fox read jumps saved over back lazy okay dog office near apps river one bank of while eleven birds sing every day in the park". I checked on the host that it expands to exactly these 30 words.

```
[01:16:29 + 0.428s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 194, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 5, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 2192 ms played, 34469 subsamples, 2154 ms nominal, worker stack free 2428
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 14, fallback 2, missing 1
free heap: 114616
[01:16:29 + 0.457s] == sr say Settings quick home brown screen fox read jumps saved over back lazy okay dog office near apps river one bank of while eleven birds sing every day in the park   (reply after 0.028s)
queued 158 characters; sr status shows the timing when it is done
[01:16:30 + 1.454s] == sr status   (reply after 0.015s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 196, dropped: 0, announcements: 1, suppressed: 1
speech: speaking, queued 0, speaker held: yes, utterances 6, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 2192 ms played, 34469 subsamples, 2154 ms nominal, worker stack free 2428
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 3, missing 2
free heap: 114328
[01:16:30 + 1.533s] == input send back short   (reply after 0.079s)
[01:16:30 + 1.547s] == sr status   (reply after 0.014s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 196, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: yes, utterances 6, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 1076 ms played, 23303 subsamples, 1032 ms nominal, worker stack free 2428
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 3, missing 2
free heap: 113496
[01:16:31 + 1.795s] == sr status   (reply after 0.037s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 196, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 6, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 1076 ms played, 23303 subsamples, 1032 ms nominal, worker stack free 2428
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 3, missing 2
free heap: 114272
[01:16:31 + 1.795s] (0.3 s check was sent 0.341s after the Back command)
[01:16:31 + 1.801s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 3, missing 2
[01:16:31 + 1.807s] == sr screen   (reply after 0.007s)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
[01:16:31 + 1.860s] == loader info   (reply after 0.054s)
No application is running
```

Result:

- aborted +1.
- Speech was already idle in the status read 14 ms after the Back command returned, and still idle at the 0.3 s check.
- underruns 0, no crash, `sr screen` still the home screen, no app running.
- The cut landed during the SAM word "quick", after the "settings" clip. Clips +1 and fallback +1; "quick" was written to the missing log after the abort.

Afterwards the missing log also held a dolphin bubble:

```
== storage read /ext/sr/missing.txt
Size: 36
bahncard
quick
i
am
happy
my
friend
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 240, dropped: 0, announcements: 2, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 7, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 3459 ms played, 116080 subsamples, 2626 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 8, missing 7
free heap: 114616
```

The Back press opened phase 2's 2 s "key recent" window on the desktop. A dolphin bubble redraw in that window was announced as a change, after the 0.3 s check: announcements went from 1 to 2 and utterances from 6 to 7. Its five words, "I am happy my friend", fell back to SAM and were logged. This is the reader working as designed, not something this change caused. The worker stack watermark after five SAM words in a row was 2372 bytes.

### 6. sr voice off, sr say Settings home, sr voice on

The settings file is filtered here to its sr lines.

```
[01:17:02 + 0.511s] == sr voice off   (reply after 0.084s)
voice off: SAM speaks everything
[01:17:02 + 0.517s] == sr voice status   (reply after 0.006s)
voice: off, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 8, missing 7
[01:17:02 + 0.542s] == storage read /int/.momentum_settings.txt   (reply after 0.025s)
screen_reader: true
sr_rate: 72
sr_volume: 100
sr_verbosity: 1
sr_voice: false
[01:17:02 + 0.447s] == sr say Settings home   (reply after 0.020s)
queued 13 characters; sr status shows the timing when it is done
[01:17:06 + 4.447s] == sr status   (reply after 0.010s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 268, dropped: 0, announcements: 2, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 8, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 1237 ms played, 52720 subsamples, 831 ms nominal, worker stack free 2372
voice: off, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 8, missing 7
free heap: 114568
[01:17:06 + 4.455s] == sr voice status   (reply after 0.007s)
voice: off, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 8, missing 7
[01:17:06 + 4.464s] speech idle
[01:17:06 + 4.473s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 268, dropped: 0, announcements: 2, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 8, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 1237 ms played, 52720 subsamples, 831 ms nominal, worker stack free 2372
voice: off, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 8, missing 7
free heap: 114488
[01:17:06 + 4.480s] == sr voice status   (reply after 0.007s)
voice: off, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 8, missing 7
[01:17:07 + 0.510s] == sr voice on   (reply after 0.084s)
voice on
[01:17:07 + 0.516s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 8, missing 7
[01:17:07 + 0.541s] == storage read /int/.momentum_settings.txt   (reply after 0.025s)
screen_reader: true
sr_rate: 72
sr_volume: 100
sr_verbosity: 1
sr_voice: true
```

Result:

- clips +0, and SAM spoke both words through the phase 2 chunk path. The SAM style numbers show it: 52,720 subsamples, 831 ms nominal, 1,237 ms played.
- The setting is saved: `sr_voice: false`, then `true`.
- fallback stayed at 8, not the brief's +2. The brief's code counts words only in the voice path, so the voice-off path never touches the counters. See Concerns.

### 7. sr status and free at the end of the steps

```
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 288, dropped: 0, announcements: 2, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 8, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 1237 ms played, 52720 subsamples, 831 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 15, fallback 8, missing 7
free heap: 114616
== free
Free heap size: 114696
Total heap size: 185904
Minimum heap size: 112000
Maximum heap block: 114392
Pool free: 876
Maximum pool block: 672
== loader info
No application is running
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as:
```

Result:

- underruns 0 in every reading.
- Heap at the end is 114,616 in `sr status`; it was 114,536 at the start. `free` shows 114,696 against 114,616.
- The minimum heap over the session is 112,000; it was 112,480 at the start. The low points are the file opens and the missing log writes.
- Compared with the previous image at idle, free heap is about 700 bytes lower. That is the voice state kept in the Speech record plus one File handle, as the spec budgets.

## Extra device checks, beyond the brief

These used vocabulary words only, so the missing log gets no more test words.

### A stop that lands inside a clip

```
[01:17:44 + 0.555s] == sr say Settings office gigahertz okay screen saved   (reply after 0.017s)
queued 43 characters; sr status shows the timing when it is done
[01:17:44 + 0.946s] == sr stop   (reply after 0.009s)
stopped
[01:17:44 + 0.957s] == sr status   (reply after 0.009s)
speech: idle, queued 0, speaker held: yes, utterances 9, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 399 ms played, 7209 subsamples, 450 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 16, fallback 8, missing 7
```

Result: aborted +1 and idle 11 ms after the stop returned. The clip was cut at 7,209 of its 12,678 samples; a cut clip still counts as a clip word. Underruns 0.

### A newer utterance interrupts a clip

```
[01:17:53 + 0.547s] == sr say Settings office gigahertz okay   (reply after 0.015s)
queued 30 characters; sr status shows the timing when it is done
[01:17:53 + 1.043s] == sr say Home screen   (reply after 0.006s)
queued 11 characters; sr status shows the timing when it is done
[01:17:53 + 1.064s] == sr status   (reply after 0.015s)
speech: speaking, queued 0, speaker held: yes, utterances 11, aborted 3, dropped 0, underruns 0, queue dropped 0
last utterance: 509 ms played, 8520 subsamples, 532 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 17, fallback 8, missing 7
[01:17:57 + 4.446s] == sr status   (reply after 0.010s)
speech: idle, queued 0, speaker held: no, utterances 11, aborted 3, dropped 0, underruns 0, queue dropped 0
last utterance: 1455 ms played, 22781 subsamples, 1423 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 19, fallback 8, missing 7
```

Result: utterances +2 and aborted +1. The newer utterance played in full, with the same 22,781 subsamples as the boot "Home screen". Clips +3, and the missing log was unchanged at 36 bytes and 7 lines.

### sr play still works

`sr play /ext/sr/voice/o/okay.raw` gave `last utterance: 783 ms played, 11967 subsamples, 747 ms nominal`, with underruns 0. 11,967 is the file's size. The voice counters did not move, which is correct because file items are not words.

## Final device state

At 01:18:14 the device was on the home screen with no popup and no app running. The reader is enabled, speech is idle, the speaker is released and the voice is on:

- `sr screen` shows the desktop with only the battery record.
- `sr status`: utterances 12, aborted 3, dropped 0, underruns 0, free heap 114,592.
- `free`: free heap 114,584, minimum 112,000.

The card keeps the 17 hand-made clips and voice.txt under /ext/sr/voice, and /ext/sr/missing.txt, which holds bahncard, quick, i, am, happy, my, friend. I did not send `loader close`.

## Deviations from the brief

1. **Formatting fix to Task 1's file, as its own commit.** `./fbt lint` failed only on speech_voice.c from Task 1, which Task 1 compiled but never linted. I applied clang-format to that file (whitespace only) and committed it separately as c5e6e0e64, so the Task 2 commit holds exactly the brief's six files. The host runner ran on the formatted file. That file is outside Task 2's file list, so the controller should know about this commit.
2. **Commit before the flash.** The brief puts the commit (Step 7) after the device check (Step 6). But Step 6 says `info device` should show the new commit, and the firmware stamps HEAD at build time. So I committed first, rebuilt (the stamp read c776d48f) and then flashed. The device therefore ran exactly the committed tree, and verification needed no code change afterwards.
3. **clang-format line wraps in the brief's code**, with no semantic change:
   - The `storage_file_read` line in speech_voice_ready.
   - The new usage `printf` in screen_reader_cli.c.
4. **Placement and comments in speech.c.**
   - The three new defines sit after all the other defines, below the flag defines.
   - `voice_enabled` joined the existing "Set by any thread, read by the worker" group.
   - The worker-owned voice fields got their own group comment: "Recorded voice: written by the worker only, speech_get_voice_stats reads a snapshot". "Worker thread only" would be inaccurate, because the status call reads them from the console thread.
5. **Shell mechanics in Step 5.** The Bash tool runs zsh, which does not word-split `$S`. The brief's `$S mkdir ...` lines therefore ran as `eval "$S mkdir ..."`. The commands and paths are the same.
6. **Timing of the reads.**
   - The step 5 phrase was shortened to 158 characters so that it fits the 159-character queue item and keeps all 30 words.
   - In steps 2 to 4 I added a second `sr status` and `sr voice status` once speech was idle. The untrimmed clips make step 2's utterance 5.85 s, longer than the brief's 4 s wait.

## Concerns

1. **Step 6 expects "fallback +2", but the brief's code gives +0.** With the voice off, speech_speak_item takes the phase 2 SAM chunk path, which does not count words. So `fallback` means "words the vocabulary lacked, spoken by SAM while the voice was on". Task 4's check ("fallback only for words outside the vocabulary") needs exactly that meaning, so I left the code as given. If voice-off words should count too, that is a small change in the SAM path, but it would muddy the vocabulary-gap count.
2. **Step 1's "clips 0" cannot hold after a boot on the home screen.** The boot "Home screen" announcement plays from the home and screen clips, which are part of the hand-made set, so the first status reads clips 2.
3. **The settings line in the status is cut at 63 characters.** The hand-made voice.txt line is 74 characters and shows as "... (hand ma". Task 3's `say` line is 54 characters and fits. A `piper` line with a model name such as en_US-lessac-medium would be about 67 characters and would be cut.
4. **The missing log now holds two test words.** Task 4's `--pull-missing` will fetch /ext/sr/missing.txt, which contains "bahncard" (from the brief's step 3) and "quick" (my step 5 phrase), plus the real bubble words "i am happy my friend". The test words would only become two extra clips, but Task 4 may want to delete missing.txt, or drop those two lines, before the pull.
5. **Every utterance ends with its last word's pause.** The code pushes the pause after the last word too, up to 300 ms after a closing period, before the flush. Interrupting announcements are not affected. A queued change announcement waits up to 300 ms longer, and `speaking` stays true for that time. Skipping the pause after the last word would be a small refinement, if wanted.
6. **Voice on is the default, even without a vocabulary.** Until /ext/sr/voice exists, speech_voice_ready asks for the card status and a stat of the voice folder before every utterance. The cost is a few milliseconds of latency before the DMA starts, which is not an underrun risk. I did not measure it, because the card now has a vocabulary.
7. **Card removed after the vocabulary was found.** The "found" state is remembered, so if the card is removed later, every word falls back to SAM. Those words are also marked as already logged for the rest of the boot, even though the log write fails, so they are never logged later. This is an edge case, and not tested.
8. **Opening a file that is being written blocks.** storage_file_open waits indefinitely when another handle has the same file open in a conflicting mode. If Task 4's sync writes a clip while the reader tries to play it, the worker waits until that write finishes. `sr play` already behaves this way, and it is harmless as long as nothing holds a clip or missing.txt open for long.
9. **Directory scan cost at full vocabulary size is not measured here.** Each folder holds one to four files now. Timing with hundreds of files per folder is Task 4's 30-word, 0-underrun acceptance test.

## Fix round 1

Commit: 1783e081f6627142d73fe847550e26eacd736b65 "screen reader: pauses sit between words; a removed card is noticed". The only file is applications/services/screen_reader/speech.c: 32 insertions, 17 deletions. It is a pathspec commit with the Co-Authored-By trailer. Nothing was pushed, and applications/external is untouched.

### What changed

1. **speech_speak_words.** A token's pause is now pushed before the next token, through a `pending_pause_ms` held from one token to the next. So no pause follows the final token, and the play out starts right after the last word.
   - Abort handling is unchanged. The loop condition checks `aborted` before every token, and a refused silence push breaks the loop. speech_item_end is still called exactly once, by speech_speak_item.
   - A punctuation-only token still separates its neighbours. For "A . B" the pause between A and B is 40 + 300 ms, as before.
   - On the host, the pronunciation layer attaches trailing punctuation to the previous word ("Hello ." expands to "Hello."). A punctuation-only token therefore only occurs at the start of a text (". Hello"), where its pause comes before the first word, as it did before. So pushing the pending pause at the top of the loop never leaves a pause at the end.
2. **speech_voice_ready.** It now checks `storage_sd_status` on every call, first. When the card is not OK, it sets `vocabulary` to false, clears `voice_settings` and returns false. The next mounted card is found again through the existing path.
   - This is the coordinator's re-check, done as one check at the top of the function; the behaviour is the same.
   - Clearing `voice_settings` is my small addition. Without it, a card that comes back without voice.txt would show a stale settings line, and the status would show a line for a card that is gone.
   - The cost is one storage message per voice utterance, before the DMA starts.
3. **speech_write_missing.** The log is cleared only when missing.txt was opened. When the open fails, the words stay in the log and a later utterance writes them.

### Build, lint, headroom, runner

The build log below is from the build before the commit. The rebuild after the commit printed the same lines, and its version.inc.h reads `#define GIT_COMMIT "1783e081"`.

```
build exit 0
fbt: warning: Failed parsing manifest '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui'. Must match regex 're.compile('^[a-z0-9_]+$')'
fbt: warning: Failed parsing manifest '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/mtp/application.fam' : Invalid appid '.f0_mtp'. Must match regex 're.compile('^[a-z0-9_]+$')'
API version 87.1 is up to date
.free_flash   176832 (172.69 K)
lint exit 0
firmware.bin 871744 bytes, limit 880640, spare 8896 bytes
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 115 checks, 0 failures
speech PCM: 700 checks, 0 failures
speech voice: 127 checks, 0 failures
runner exit 0
```

The case-insensitive count of "error" and "warning" over the whole build log is 2: the two manifest warnings. The fix costs 8 bytes of flash; spare space went from 8,904 to 8,896 bytes.

### Flash

`./fbt flash_usb` ran from 01:36:14 to 01:36:47 with exit 0. It built package f7-update-mntm-screen-reader-1783e081, sent firmware.dfu in 107 chunks plus update.fuf and updater.bin in 15 chunks, then printed "Closing current app, if any". The port node was absent at 01:36:58 and back at 01:37:16. After 12 s of settling, the first command, sent alone, was:

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as:
```

There was no popup. Then `info device` and `sr status`:

```
firmware.commit.hash          : 1783e081
firmware.commit.dirty         : true
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 46, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1418 ms played, 22141 subsamples, 1383 ms nominal, worker stack free 2684
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 2, fallback 0, missing 0
free heap: 114520
```

The boot "Home screen" already has no trailing gap: 22,141 subsamples, 1,383 ms nominal and 1,418 ms played. Before the fix it was 22,781 subsamples, 1,423 ms nominal and 1,458 ms played.

### Device check 1: sr say Settings. Sub-GHz. Apps, 1 of 11.

```
[01:37:45 + 0.443s] == sr say Settings. Sub-GHz. Apps, 1 of 11.   (reply after 0.016s)
queued 33 characters; sr status shows the timing when it is done
[01:37:49 + 4.447s] == sr status   (reply after 0.010s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 67, dropped: 0, announcements: 1, suppressed: 2
speech: speaking, queued 0, speaker held: yes, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1418 ms played, 22141 subsamples, 1383 ms nominal, worker stack free 2684
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 6, fallback 0, missing 0
free heap: 113680
[01:37:49 + 4.453s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 6, fallback 0, missing 0
[01:37:50 + 6.104s] speech idle
[01:37:50 + 6.113s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 70, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: yes, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 5588 ms played, 88860 subsamples, 5553 ms nominal, worker stack free 2684
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 9, fallback 0, missing 0
free heap: 114344
[01:37:50 + 6.119s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 9, fallback 0, missing 0
```

Result: 5,553 ms nominal, exactly 5,853 − 300. There are 88,860 subsamples, which is 93,660 − 4,800, the samples of the dropped final 300 ms. Played time went from 5,876 to 5,588 ms. Underruns 0, clips +7.

### Device check 2: two vocabulary words, sr say Home screen

```
[01:37:56 + 0.441s] == sr say Home screen   (reply after 0.013s)
queued 11 characters; sr status shows the timing when it is done
[01:38:00 + 4.441s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 91, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 3, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1411 ms played, 22141 subsamples, 1383 ms nominal, worker stack free 2684
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 11, fallback 0, missing 0
free heap: 114408
```

Result: 1,411 ms played, 22,141 subsamples and 1,383 ms nominal. Before the fix, the same words measured 1,455 ms played, 22,781 subsamples and 1,423 ms nominal (the extra "newer utterance" check). The 40 ms gap after "screen" and its 640 samples are gone. Underruns 0.

### Extra device check: a failed missing-log write keeps the words

A card removal cannot be simulated safely. The console has no mount or unmount command, and in Settings → Storage the unmount entry sits next to "Format SD Card". So the vocabulary reset is covered by review only. The log-retention half was tested on the device:

- The existing log was renamed aside, not deleted.
- An empty folder was placed at /ext/sr/missing.txt, so that the append open fails.
- After the test, the empty folder was removed and the log renamed back. `storage remove` is non-recursive and only deletes a file or an empty folder.

```
== storage rename /ext/sr/missing.txt /ext/sr/missing.bak
== storage mkdir /ext/sr/missing.txt
== storage stat /ext/sr/missing.txt
Directory
== storage stat /ext/sr/missing.bak
File, size: 36b
== sr say Cancel office
queued 13 characters; sr status shows the timing when it is done
== sr status   (4 s later)
speech: idle, queued 0, speaker held: no, utterances 4, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1620 ms played, 46737 subsamples, 1330 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 12, fallback 1, missing 1
== storage stat /ext/sr/missing.txt
Directory
== storage stat /ext/sr/missing.bak
File, size: 36b
== storage list /ext/sr/missing.txt
	Empty
== storage remove /ext/sr/missing.txt
== storage rename /ext/sr/missing.bak /ext/sr/missing.txt
== storage stat /ext/sr/missing.txt
File, size: 36b
== storage stat /ext/sr/missing.bak
Storage error: file/dir not exist
== sr say Delete office
queued 13 characters; sr status shows the timing when it is done
== sr status   (4 s later)
speech: idle, queued 0, speaker held: no, utterances 5, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1454 ms played, 37017 subsamples, 1248 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 13, fallback 2, missing 2
== storage read /ext/sr/missing.txt
Size: 50
bahncard
quick
i
am
happy
my
friend
cancel
delete
```

Result:

- "cancel" was counted as missing while the log could not be opened.
- The worker did not block: it was idle 4 s later. The open failed rather than waiting.
- The next utterance wrote the kept "cancel" together with "delete".
- "Cancel" and "Delete" are real firmware UI strings (18 and 16 uses), so these two lines are harmless when Task 4 pulls the log.

### Final device state

At 01:38:41:

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 171, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 5, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1454 ms played, 37017 subsamples, 1248 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 13, fallback 2, missing 2
free heap: 114512
== loader info
No application is running
== free
Free heap size: 114512
Total heap size: 185904
Minimum heap size: 112432
Maximum heap block: 114288
Pool free: 876
Maximum pool block: 672
== storage list /ext/sr
	[D] clips
	[D] voice
	[F] missing.txt 50b
```

The device is on the home screen with the reader on, speech idle, the speaker released and the voice on. `sr_voice: true` is saved.

### Effect on the earlier concerns

- Concern 5, the trailing pause, is resolved.
- Concern 7, a card removed after the vocabulary was found, is resolved in code and not tested on the device. The words of the one utterance in which the card disappears can still be logged as missing, and they stay in the hash set; the coordinator accepted this.
- Concern 4 is updated: missing.txt now also holds "cancel" and "delete". These are real UI words, so they are harmless.
- The other concerns stand.
