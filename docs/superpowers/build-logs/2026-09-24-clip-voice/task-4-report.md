# Task 4 report: the vocabulary on the card, verification, documents

Phase A status: DONE. The full vocabulary is built locally: 2,823 clips, 0 failed. Phase B has not started. That means the pull, the sync, the device checks, the documents and the commit. It waits for the controller's "phase B".

## Phase A: the local build

### How it was run

- Directory: /Users/robin/Downloads/flipper-access. Project at a8bc8c73d.
- Firmware tree: Momentum-Firmware on branch screen-reader at 1783e081f. The extraction reads it without changing it.
- Python: the system python3, Homebrew 3.14.7.
- Flags: `--extract` only. No `--pull-missing` and no `--sync`, so the device was not touched.
- Starting state: `voice/` did not exist before the run, so every clip is new.
- Nothing changed in either repository. voice/ is git-ignored, and `git status` shows only the untracked clip-experiment.md that was there before.

One small change to the brief's command: a `tee` into a scratchpad log sits before `tail -25`. It keeps the first lines that the tail cuts off, and changes nothing else. The command ran in the background, from 02:05:39 to 02:27:42.

```
time tools/voice_build.py --extract --jobs 4 2>&1 | tee <scratchpad>/phase-a-build.log | tail -25
```

The first seven lines, from the log (the tail cuts them off):

```
extract: 6182 distinct strings from the firmware sources
extract: 2815 words; longest: getbatterycharge configchangeable hoppingthreshold desktopscenelock subghzchatworker defaulttextclear checksdkfeatures inputtyperelease animationstorage freecreatedelete
2823 words, 2823 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
100 of 2823 clips, 47 s
200 of 2823 clips, 94 s
300 of 2823 clips, 140 s
400 of 2823 clips, 188 s
```

The output of `tail -25`, followed by zsh's `time` lines, verbatim. Exit code 0.

```
500 of 2823 clips, 235 s
600 of 2823 clips, 288 s
700 of 2823 clips, 337 s
800 of 2823 clips, 384 s
900 of 2823 clips, 430 s
1000 of 2823 clips, 477 s
1100 of 2823 clips, 524 s
1200 of 2823 clips, 571 s
1300 of 2823 clips, 615 s
1400 of 2823 clips, 662 s
1500 of 2823 clips, 709 s
1600 of 2823 clips, 755 s
1700 of 2823 clips, 802 s
1800 of 2823 clips, 849 s
1900 of 2823 clips, 895 s
2000 of 2823 clips, 941 s
2100 of 2823 clips, 986 s
2200 of 2823 clips, 1034 s
2300 of 2823 clips, 1081 s
2400 of 2823 clips, 1127 s
2500 of 2823 clips, 1174 s
2600 of 2823 clips, 1220 s
2700 of 2823 clips, 1265 s
2800 of 2823 clips, 1311 s
made 2823 clips, 0 failed, 1322 s; vocabulary 2823 words in /Users/robin/Downloads/flipper-access/voice
tools/voice_build.py --extract --jobs 4 2>&1  586.29s user 237.35s system 62% cpu 22:02.88 total
tee   0.00s user 0.00s system 0% cpu 22:02.89 total
tail -25  0.00s user 0.00s system 0% cpu 22:02.89 total
```

The follow-up command, verbatim:

```
$ du -sh voice; find voice -name '*.raw' | wc -l; cat voice/voice.txt
 31M	voice
    2823
say Samantha rate 175 highpass 500 gain 1.3 soft 16000
```

### The numbers

- Word count: 2,823. The extraction gives 2,815 words from 6,182 distinct strings. The base list tools/voice_words.txt adds 8 more: the digits 0, 1, 3, 6, 7, 8 and 9, and "quote". Its other 110 words are also in the extraction. The counts match Task 3's fix round (6,182 strings, 2,815 words). The total is far below the 12,000 limit.
- Ten longest words: all ten have 16 letters, the filter's limit. There are 20 words of that length. As the tool printed them: getbatterycharge configchangeable hoppingthreshold desktopscenelock subghzchatworker defaulttextclear checksdkfeatures inputtyperelease animationstorage freecreatedelete. The order among words of equal length follows Python's per-process hash seed, so it changes from run to run. The stable list, sorted by length and then alphabetically: animationmanager animationstorage backlightenforce checksdkfeatures configchangeable defaulttextclear desktopscenelock freecreatedelete getbatterycharge hoppingthreshold. All of them are code identifiers in lower case. They are junk that stays, as the brief says.
- Failed: 0, so there is nothing to investigate.
- Total size:
  - `du -sh`: 31M. This counts whole disk blocks.
  - Apparent size (`du -sh -A`): 27M.
  - Clip data: exactly 26,928,695 bytes (26.93 MB). That is 1,683 s (28.1 minutes) of audio at 16 kHz.
  - Other files: manifest.json 86,170 bytes; voice.txt 55 bytes; .build/speech_expand 34,512 bytes.
- Time: 22:02.88 of wall clock, of which the tool counts 1,322 s for the clips. CPU: 586 s user plus 237 s system, 62 percent of one core. That is 0.47 s per clip with four jobs, or about 1.9 s per clip for each job.
- The voice.txt line: `say Samantha rate 175 highpass 500 gain 1.3 soft 16000`. It is 55 bytes with the trailing newline, which fits the device's 63-character status line.

### Checks over every clip

These come from a read-only script in the scratchpad. It applies the `--check` criteria to all 2,823 clips.

- The 2,823 clips match the manifest's 2,823 words one to one. No clip is missing and there is no extra clip.
- Length: the shortest is 0.228 s ("up"). The median is 0.564 s, the mean 0.596 s, and the longest 2.648 s.
- The ten longest clips:
  - ttcfdfdffdfd 2.65 s
  - sshfthptkch 2.62 s
  - fcfcfcfcc 2.08 s
  - tfdfdtc 1.64 s
  - fileordirexists 1.44 s
  - www 1.38 s
  - rrggbb 1.37 s
  - rpcsrv 1.36 s
  - directoryexists 1.33 s
  - https 1.30 s

  The first four are format leftovers that Samantha spells letter by letter.
- Silence:
  - No clip is silence only.
  - In every clip, the first and last 15 ms are silence (128 plus or minus 2).
- Loudness: every clip peaks at least 100 away from 128.
- Folders: 36 in total. The folders 0 to 9 hold one clip each; the rest are a to z. There is no "_" folder, because the filter admits only letters and single digits. The largest folders are s with 315 clips, c with 229, m with 191, p with 188 and d with 170.

### Words the filter drops, which the device will speak with SAM

I ran the same expander over the same 6,182 strings and looked at the tokens the word filter rejects:

- 7 words with an apostrophe: it's, can't, don't, isn't, you're, doesn't, flipper's. The device looks them up with the apostrophe, because speech_voice.c keeps punctuation inside a word. It finds no clip and falls back to SAM every time. `--pull-missing` drops them again. These are real interface words. This was expected from the Task 3 ruling. I list them so that a fallback on them in phase B is not mistaken for a bug.
- 55 tokens of letters only that are longer than 16 letters. All of them are identifiers, for example archiveinfoworker, notificationmessage and buttonpressrelease.
- 147 tokens that mix letters and digits, for example p1, i2c and md5. One of them, 89, comes from the base64 alphabet string.

### Concerns for phase B

None of these blocks phase A.

1. The sync uploads more than the clips. `sync()` calls `recursive_send("/ext/sr/voice", voice/)`. That walks the whole directory, and the generator keeps its work directory inside it (`workdir = <out>/.build`). So the card also gets these two files:
   - /ext/sr/voice/.build/speech_expand, a macOS binary of 34,512 bytes.
   - /ext/sr/voice/manifest.json, 86,170 bytes. It is sent again after every build that changes it.

   The device never opens either file, so playback is not affected. They are clutter, and about 120 KB more per full sync. In total the sync covers 2,826 files in 37 directories. The review of the sync code may want to decide this. I have not changed the generator.
2. The sync will take a while.
   - Transfer: 26.9 MB at the 130 to 135 kB/s measured in phase 2 is about 3.5 minutes on its own. On top of that come several console round trips for each of the 2,826 files.
   - Estimate: 5 to 15 minutes, which can exceed the 10-minute limit on a foreground command. I will run it in the background and watch for the guard's two lines.
   - Later syncs: any sync after the first one hashes every file that is already on the card. FlipperStorageOperations runs `storage md5` per file, because it compares md5 sums, not sizes. So the two-word sync in step 4 will probably take minutes as well.
   - Spec deviation: the spec says the sync compares sizes, but it compares md5 sums. I will note this on the spec's status line in phase B.
3. The build took longer than the dispatch expected.
   - The dispatch assumed 0.5 s per clip for each job, which gave six minutes. Task 3's 0.48 to 0.52 s per clip was already the rate with four jobs.
   - Measured here: 0.47 s per clip with four jobs, about 22 minutes, which matches the ledger's 25-minute estimate.
   - `say` waits more than it computes: each `say` process ran at about 16 percent CPU on this 20-core Mac. More jobs would probably shorten the build. I did not try that, because the brief says four.
4. Something to watch rather than a finding: the largest folders hold 315 clips (s) and 229 (c). Lookups in a FAT directory go through the entries one by one, so opening a clip in s/ scans the most entries. Phase B's underrun counts with the full vocabulary will show whether this matters. I have not measured it.

## Phase B1: the rebuild after voice/ was deleted

### What happened

The coordinator reported that another agent deleted the repo-root `voice/` after phase A. I confirmed this: `ls voice` said "No such file or directory". I rebuilt it as in phase A, with `--jobs 8` as the coordinator asked. Nothing else changed. The device was not touched.

- Run: in the background, with the same `tee` into a scratchpad log, from 02:36:04 to 02:52:23.
- Generator: the run started on 25d7d8c. Commit 76346f6 ("a missing or failed clip does not abort the sync") landed at 02:47:40, during the run. Both commits change only `sync()` and its call in `main()`. The build path is the same as in phase A's a8bc8c7.

```
time tools/voice_build.py --extract --jobs 8 2>&1 | tee <scratchpad>/phase-b1-build.log | tail -8
```

The first three lines, from the log:

```
extract: 6182 distinct strings from the firmware sources
extract: 2815 words; longest: subghzsetcounter desktopscenelock inputsettingsapp freecreatedelete inputtyperelease rpcsessionworker animationmanager subghzchatworker checksdkfeatures getbatterycharge
2823 words, 2823 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
```

The output of `tail -8`, followed by the `time` lines, verbatim. Exit code 0.

```
2200 of 2823 clips, 764 s
2300 of 2823 clips, 798 s
2400 of 2823 clips, 836 s
2500 of 2823 clips, 870 s
2600 of 2823 clips, 902 s
2700 of 2823 clips, 936 s
2800 of 2823 clips, 972 s
made 2823 clips, 0 failed, 979 s; vocabulary 2823 words in /Users/robin/Downloads/flipper-access/voice
tools/voice_build.py --extract --jobs 8 2>&1  640.46s user 293.19s system 95% cpu 16:19.58 total
tee   0.00s user 0.00s system 0% cpu 16:19.58 total
tail -8  0.00s user 0.00s system 0% cpu 16:19.58 total
```

The checks, verbatim:

```
$ find voice -name '*.raw' | wc -l; du -sh voice; cat voice/voice.txt
    2823
 31M	voice
say Samantha rate 175 highpass 500 gain 1.3 soft 16000
```

### The B1 numbers

- Words: 2,823. 0 failed.
- Size: 31M by `du -sh`, 27M apparent. The clip data is 26,928,695 bytes. That is byte for byte the same total as in phase A.
- Time: 16:19.58 of wall clock, of which the tool counts 979 s for the clips. That is 0.35 s per clip with eight jobs, against 0.47 s with four. The full build takes 26 percent less time, but not half: CPU use was 95 percent of one core. So something shared, probably the macOS speech server, limits `say` beyond its start-up time.
- The voice.txt line is the same 55 bytes: `say Samantha rate 175 highpass 500 gain 1.3 soft 16000`.
- The all-clips check gives the same results as in phase A, value for value:
  - 2,823 clips match the manifest's 2,823 words one to one.
  - Audio: 1,683 s. Length: shortest 0.228 s, median 0.564 s, mean 0.596 s, longest 2.648 s. The ten longest clips are the same, with the same lengths.
  - No clip is silence only. The 15 ms edges of every clip are silence, and every clip peaks at least 100 away from 128.
  - The folders are the same 36, with the same counts: s 315, c 229, m 191, p 188, d 170.

  So on this Mac the synthesis repeats, at least in clip lengths. I could not compare the bytes because phase A's clips are gone.
- Only the order among the 16-letter words printed by the tool differs (see phase A). The stable top ten is unchanged.
- The same three non-clip files are in voice/: `.build/speech_expand`, `manifest.json` (86,170 bytes) and `voice.txt`. `synced.json` does not exist yet; the first `--sync` creates it.

### Notes on the new sync() (25d7d8c and 76346f6), read before B2

These replace phase A's concerns 1 and 2. The sync now sends only the clips named in the manifest and voice.txt, with no `.build` and no manifest.json. Later syncs skip every word recorded in voice/synced.json, so step 4's round trip will send two clips and voice.txt, and will not hash every file on the card.

1. The Task 2 clip "office" stays on the card. Of the 17 hand-made clips, `office` is the only word not in the generated vocabulary. The sync overwrites the other 16 and voice.txt, and deletes nothing. So /ext/sr/voice/o/office.raw stays: an untrimmed clip made by clip_make.py. The device will play it if "office" is ever spoken. In B2 I suggest removing it with `storage remove /ext/sr/voice/o/office.raw` after the sync, and I will say so in the report. It is a Task 2 test file, not user data.
2. `--sync-all` does nothing on its own. It only sets `force_all` for `sync()`, which runs only when `--sync` is also given. A wiped card needs `--sync --sync-all`. That is a documentation point for the README.
3. After a transfer fails partway, the console session may still expect the rest of a `write_chunk`. In that case the next words could also fail. They are reported, left out of synced.json and sent again next time, so this is safe, only noisy. This is for the reviewer, not a blocker.

## Phase B2: sync, device verification, documents

Status: DONE_WITH_CONCERNS. The sync, all seven device checks, the documents and the commit are done, and the device is idle as required. One acceptance criterion fails: underruns are not 0. With the full vocabulary, finding a word near the end of a large folder takes longer than the speech ring's half buffer. The cause is measured and shown below. I changed no firmware or generator code.

### Commit

`b5a8090b87ff2feb878bf19ccf0a6b589683e462` "docs: recorded voice as built, rollout measurements". It touches 4 files: README.md, docs/roadmap.md, docs/superpowers/specs/2026-09-24-clip-voice-design.md and docs/measurements/2026-09-24-voice-rollout.txt (new). I staged them with an explicit `git add` and made a pathspec commit, with the Co-Authored-By line. Nothing is pushed. The untracked clip-experiment.md is untouched, and the firmware repository is untouched.

### A deviation before the sync: `sr_drive.py --help` runs the sessions

The dispatch said `.venv/bin/python tools/sr_drive.py --help` shows how to use the tool. It does not: the script has no argument parsing, and any argument other than `--interactive` runs the scripted sessions. So my `--help` call at about 02:55 ran both sessions on the device before the sync. The device then had only the hand-made clips, so most words fell back to SAM.

The run passed and ended on the home screen:
- 0 failures, with the same 17 lines as in check 2 below.
- It also sent `sr on` and opened and closed Text to SAM, as the script always does.

Its only lasting effect was on /ext/sr/missing.txt. It added the words the sessions lacked to the list, so the pull found 17 words instead of 7. Nothing else changed.

The state before the sync, read right after that run:

```
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 9397, dropped: 0, announcements: 21, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 25, aborted 5, dropped 0, underruns 0, queue dropped 0
last utterance: 2230 ms played, 81120 subsamples, 1587 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 32, fallback 14, missing 11
free heap: 114432
== sr voice status
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 32, fallback 14, missing 11
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== storage read /ext/sr/missing.txt
Size: 106
bahncard
quick
i
am
happy
my
friend
cancel
delete
bluetooth
hundred
parent
folder
save
seven
i
wish
could
== storage list /ext/sr/voice
	[D] s
	[D] g
	[D] a
	[D] o
	[D] e
	[D] h
	[D] r
	[D] b
	[D] c
	[F] voice.txt 75b
== storage list /ext/sr
	[D] clips
	[D] voice
	[F] missing.txt 106b
```

### Step 2: sync and card check

The command ran in the background, with a `tee` into a scratchpad log, from 02:57:24 to 03:04:51:

```
time .venv/bin/python tools/voice_build.py --pull-missing --sync 2>&1 | tee <scratchpad>/phase-b2-sync.log | tail -12
```

The output of `tail -12`, then the `time` lines, verbatim. Each progress line of the storage helper has carriage returns in it; each line here shows the last segment, which is what a terminal shows.

```
<100%, chunk  2 of  2 @ 102.94 kb/s
<100%, chunk  1 of  1 @ 115.13 kb/s
<100%, chunk  1 of  1 @ 122.78 kb/s
<100%, chunk  2 of  2 @ 77.55 kb/s
<100%, chunk  2 of  2 @ 95.39 kb/s
<100%, chunk  2 of  2 @ 100.75 kb/s
<100%, chunk  1 of  1 @ 120.01 kb/s
<100%, chunk  2 of  2 @ 76.24 kb/s
<100%, chunk  1 of  1 @ 115.21 kb/s
<100%, chunk  1 of  1 @ 2.06 kb/s
sync: 2828 sent, 0 skipped, 0 missing, 0 failed, 442 s
voice: restored
.venv/bin/python tools/voice_build.py --pull-missing --sync 2>&1  6.16s user 6.92s system 2% cpu 7:26.77 total
tee   0.00s user 0.00s system 0% cpu 7:26.77 total
tail -12  0.05s user 0.14s system 0% cpu 7:26.77 total
exit 0
```

These are all the log lines that are not per-file progress, in order, verbatim. The progress lines are 2,829 in number: 2,828 clips and voice.txt.

```
voice: silenced for the transfer
>100%, chunk  1 of  1 @ 5.87 kb/s
pulled 17 missing words from the device
voice: restored
132 words, 5 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
made 5 clips, 0 failed, 3 s; vocabulary 2828 words in /Users/robin/Downloads/flipper-access/voice
voice: silenced for the transfer
sync: 100 of 2828, 100 sent, 0 skipped, 16 s
sync: 200 of 2828, 200 sent, 0 skipped, 32 s
sync: 300 of 2828, 300 sent, 0 skipped, 45 s
sync: 400 of 2828, 400 sent, 0 skipped, 57 s
sync: 500 of 2828, 500 sent, 0 skipped, 76 s
sync: 600 of 2828, 600 sent, 0 skipped, 93 s
sync: 700 of 2828, 700 sent, 0 skipped, 110 s
sync: 800 of 2828, 800 sent, 0 skipped, 123 s
sync: 900 of 2828, 900 sent, 0 skipped, 138 s
sync: 1000 of 2828, 1000 sent, 0 skipped, 154 s
sync: 1100 of 2828, 1100 sent, 0 skipped, 165 s
sync: 1200 of 2828, 1200 sent, 0 skipped, 179 s
sync: 1300 of 2828, 1300 sent, 0 skipped, 195 s
sync: 1400 of 2828, 1400 sent, 0 skipped, 207 s
sync: 1500 of 2828, 1500 sent, 0 skipped, 222 s
sync: 1600 of 2828, 1600 sent, 0 skipped, 241 s
sync: 1700 of 2828, 1700 sent, 0 skipped, 253 s
sync: 1800 of 2828, 1800 sent, 0 skipped, 266 s
sync: 1900 of 2828, 1900 sent, 0 skipped, 283 s
sync: 2000 of 2828, 2000 sent, 0 skipped, 297 s
sync: 2100 of 2828, 2100 sent, 0 skipped, 315 s
sync: 2200 of 2828, 2200 sent, 0 skipped, 329 s
sync: 2300 of 2828, 2300 sent, 0 skipped, 349 s
sync: 2400 of 2828, 2400 sent, 0 skipped, 377 s
sync: 2500 of 2828, 2500 sent, 0 skipped, 393 s
sync: 2600 of 2828, 2600 sent, 0 skipped, 410 s
sync: 2700 of 2828, 2700 sent, 0 skipped, 424 s
sync: 2800 of 2828, 2800 sent, 0 skipped, 438 s
sync: 2828 sent, 0 skipped, 0 missing, 0 failed, 442 s
voice: restored
```

The numbers from the sync:
- Wall clock: 7:26.77 in all. Of that, 442 s were the transfer of 2,828 clips and voice.txt, or 61 kB/s (6.4 files per second).
- Both guard pairs printed: "voice: silenced for the transfer" and then "voice: restored", once for the pull and once for the sync.
- The pull found 17 distinct words; "i" was in the list twice. 5 of them were new: am, bahncard, friend, my and wish. That makes 2,828 words.
- Exit code 0.

The card afterwards, with the brief's commands and `sr voice status`, verbatim:

```
== storage list /ext/sr/voice
	[D] s
	[D] g
	[D] a
	[D] o
	[D] e
	[D] h
	[D] r
	[D] b
	[D] c
	[F] voice.txt 55b
	[D] 0
	[D] 1
	[D] 2
	[D] 3
	[D] 4
	[D] 5
	[D] 6
	[D] 7
	[D] 8
	[D] 9
	[D] d
	[D] f
	[D] i
	[D] j
	[D] k
	[D] l
	[D] m
	[D] n
	[D] p
	[D] q
	[D] t
	[D] u
	[D] v
	[D] w
	[D] x
	[D] y
	[D] z
== storage read /ext/sr/voice/voice.txt
Size: 55
say Samantha rate 175 highpass 500 gain 1.3 soft 16000
== sr voice status
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 32, fallback 14, missing 11
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 10625, dropped: 0, announcements: 21, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 25, aborted 5, dropped 0, underruns 0, queue dropped 0
last utterance: 2230 ms played, 81120 subsamples, 1587 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 32, fallback 14, missing 11
free heap: 114328
== storage list /ext/sr
	[D] clips
	[D] voice
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== loader info
No application is running
```

What this shows:
- The voice is on and the vocabulary is found.
- missing.txt was removed by the pull.
- The settings line still ends in "(hand ma", the old hand-made voice.txt, although the card now holds the new 55-byte file.

The last point is by design. `speech_voice_ready()` reads voice.txt once, when it first finds the vocabulary, and keeps it while the card stays mounted. The new line shows after the reboot in check 7. I recorded this in the README and on the spec's status line.

Removing the hand-made clip office.raw:

```
== storage remove /ext/sr/voice/o/office.raw
```

That command printed nothing, which means success. Afterwards `storage list /ext/sr/voice/o` listed 68 clips, the same count as the local voice/o, and a search of it for "office" found nothing.

I also compared the whole card against the local files by name and size, with `storage list` of every folder:

```
local clips 2828, card clips 2828, bytes local 26964198, card 26964198
only on the card: []
only local: []
size differs: []
```

After check 4's round trip the comparison gave `local clips 2831, card clips 2831, bytes local 26994139, card 26994139`, with no differences.

### Step 3: device checks

The helper is a scratchpad script that opens one console session and runs the steps given to it. It prints every reply verbatim, stamped with the wall clock and the seconds since the session began.
- "@idle" polls `sr status` quietly every 50 ms until speech is idle and the speaker is released. It then prints both times and the last status.
- "@sleep" waits.

I predicted the nominal times from the local clip sizes and the pauses, using the same word rules as speech_voice.c. The pauses are 40 ms between words, 150 ms after a comma and 300 ms after a period, with none after the last word.

#### 1. The test sentence

The expansion is "Settings. sub gigahertz. Apps, one of eleven. Read RAW. four hundred thirty three point nine two megahertz. U I D, zero four ay two B three C four.". That is 28 words, all in the vocabulary. The prediction was 274,710 samples, or 17,169 ms.

```
[03:06:31 + 0.418s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 32, fallback 14, missing 11
[03:06:31 + 0.424s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 10783, dropped: 0, announcements: 21, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 25, aborted 5, dropped 0, underruns 0, queue dropped 0
last utterance: 2230 ms played, 81120 subsamples, 1587 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 32, fallback 14, missing 11
free heap: 114360
[03:06:31 + 0.433s] == sr say Settings. Sub-GHz. Apps, 1 of 11. Read RAW. 433.92 MHz. UID: 04 A2 B3 C4.   (reply after 0.020s)
queued 73 characters; sr status shows the timing when it is done
[03:06:48 + 17.888s] (waited: idle after 17.242 s, speaker released after 17.434 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 10818, dropped: 0, announcements: 21, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 26, aborted 5, dropped 0, underruns 5, queue dropped 0
last utterance: 17226 ms played, 274710 subsamples, 17169 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 60, fallback 14, missing 11
free heap: 114224
[03:06:48 + 17.888s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 60, fallback 14, missing 11
[03:06:48 + 17.893s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 10818, dropped: 0, announcements: 21, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 26, aborted 5, dropped 0, underruns 5, queue dropped 0
last utterance: 17226 ms played, 274710 subsamples, 17169 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 60, fallback 14, missing 11
free heap: 114216
```

The result:
- Clips: +28, from 32 to 60, which equals the 28 words of the expansion.
- Fallback +0 and missing +0.
- Nominal time: 17,169 ms with 274,710 subsamples, exactly as predicted. 17,226 ms played.
- **Underruns: +5, where 0 was expected.** The cause follows.

#### The cause of the underruns: lookup time grows with the position in a folder

First I timed `storage stat` at the end of large folders and at the front. That is the same exFAT lookup the worker's `storage_file_open` does. Round trips, verbatim:

```
[03:08:00 + 0.427s] == storage stat /ext/sr/voice/0/0.raw   (reply after 0.019s)
[03:08:00 + 0.446s] == storage stat /ext/sr/voice/0/0.raw   (reply after 0.013s)
[03:08:00 + 0.459s] == storage stat /ext/sr/voice/z/zero.raw   (reply after 0.017s)
[03:08:00 + 0.477s] == storage stat /ext/sr/voice/s/settings.raw   (reply after 0.011s)
[03:08:00 + 0.488s] == storage stat /ext/sr/voice/s/safe.raw   (reply after 0.007s)
[03:08:00 + 0.496s] == storage stat /ext/sr/voice/s/safe.raw   (reply after 0.012s)
[03:08:00 + 0.509s] == storage stat /ext/sr/voice/s/sz.raw   (reply after 0.064s)
[03:08:00 + 0.573s] == storage stat /ext/sr/voice/s/sz.raw   (reply after 0.066s)
[03:08:00 + 0.640s] == storage stat /ext/sr/voice/c/cyfral.raw   (reply after 0.069s)
[03:08:00 + 0.710s] == storage stat /ext/sr/voice/c/cyfral.raw   (reply after 0.051s)
[03:08:00 + 0.762s] == storage stat /ext/sr/voice/t/two.raw   (reply after 0.039s)
[03:08:00 + 0.802s] == storage stat /ext/sr/voice/h/hundred.raw   (reply after 0.026s)
[03:08:01 + 0.828s] == storage stat /ext/sr/voice/s/nothere.raw   (reply after 0.065s)
```

Then I compared the same speech path with two groups of nine clips:
- The first group are the Task 2 words, which were re-sent in place and so sit at the front of their folders.
- The second group are the last files in folders of 315, 155 and 229 clips.

```
[03:08:39 + 0.428s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11040, dropped: 0, announcements: 21, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 26, aborted 5, dropped 0, underruns 5, queue dropped 0
last utterance: 17226 ms played, 274710 subsamples, 17169 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 60, fallback 14, missing 11
free heap: 114448
[03:08:39 + 0.437s] == sr say settings apps one of okay home screen back saved   (reply after 0.016s)
queued 48 characters; sr status shows the timing when it is done
[03:08:44 + 5.243s] (waited: idle after 4.599 s, speaker released after 4.79 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11050, dropped: 0, announcements: 21, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 27, aborted 5, dropped 0, underruns 5, queue dropped 0
last utterance: 4569 ms played, 72262 subsamples, 4516 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 69, fallback 14, missing 11
free heap: 114344
[03:08:44 + 5.243s] == sr say systems types cycles systems types cycles systems types cycles   (reply after 0.018s)
queued 62 characters; sr status shows the timing when it is done
[03:08:50 + 11.771s] (waited: idle after 6.305 s, speaker released after 6.51 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11063, dropped: 0, announcements: 21, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 28, aborted 5, dropped 0, underruns 13, queue dropped 0
last utterance: 6262 ms played, 98315 subsamples, 6144 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 78, fallback 14, missing 11
free heap: 114224
```

The result:
- The front group gave underruns +0.
- The end group gave underruns +8, one for every open after the first. The first clip is opened before the DMA starts, so it cannot underrun.
- The end group also played 118 ms longer than its nominal time, against 53 ms for the front group. So each underrun cost about 8 ms of audio.

Finally, lookup time against position in folder s (315 clips), each the median of five `storage stat` round trips:

```
position    1 0            median  12.7 ms, min  12.4, max  13.0  (File, size: 7434b)
position    1 s            median   6.6 ms, min   6.4, max  11.3  (File, size: 13416b)
position   50 sector       median  20.6 ms, min  19.3, max  29.9  (File, size: 9267b)
position  100 sev          median  27.9 ms, min  27.8, max  28.3  (File, size: 6572b)
position  150 sliding      median  37.1 ms, min  36.0, max  53.0  (File, size: 9380b)
position  200 st           median  44.6 ms, min  44.4, max  45.6  (File, size: 9080b)
position  250 stream       median  53.4 ms, min  53.4, max  67.4  (File, size: 8832b)
position  300 supported    median  62.8 ms, min  62.6, max  67.4  (File, size: 10026b)
position  315 sz           median  64.8 ms, min  64.5, max  84.1  (File, size: 8314b)
position miss nothere      median  66.9 ms, min  65.2, max  78.5  (Storage error: file/dir not exist)
```

The first line is folder 0, which holds a single clip, for comparison.

What these numbers mean:
- Each directory entry costs about 0.17 ms: from 20.6 ms at position 50 to 62.8 ms at position 300. The sync writes the files of each folder in alphabetical order, so the position is the word's alphabetical rank in its folder.
- The ring has 4,096 slots at 20 µs each, in two halves of 41 ms. The worker fills one half while the DMA plays the other. `speech_emit` counts an underrun when the DMA has already entered the half being filled. So an open longer than what is left of the playing half, at most about 41 ms, is counted.
- The spec assumed 82 ms, and that a directory of a few hundred entries keeps an open under 10 ms. Both assumptions are wrong.
- Words past about position 150 of their folder are the problem. There are 385 of them in the vocabulary, mostly in s, c, m, p and d. So are newly pulled words, which are appended at the end of their folder, like moonbeam in check 4. So are missing words, which scan the whole folder.

#### 2. sr_drive.py, both sessions, with the voice on

```
[03:09:05 + 0.428s] == sr voice status   (reply after 0.008s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 78, fallback 14, missing 11
[03:09:05 + 0.435s] == storage stat /ext/sr/missing.txt   (reply after 0.015s)
Storage error: file/dir not exist
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
sr_drive exit 0
[03:09:41 + 4.482s] (waited: idle after 3.788 s, speaker released after 4.054 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11224, dropped: 0, announcements: 41, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 48, aborted 6, dropped 0, underruns 16, queue dropped 0
last utterance: 4427 ms played, 89099 subsamples, 4131 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 114, fallback 15, missing 12
free heap: 114368
[03:09:41 + 4.482s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 114, fallback 15, missing 12
[03:09:41 + 4.488s] == storage read /ext/sr/missing.txt   (reply after 0.014s)
Size: 5
fish
[03:09:41 + 4.502s] == sr screen   (reply after 0.007s)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
[03:09:41 + 4.509s] == loader info   (reply after 0.048s)
No application is running
```

The result:
- 0 failures in 17 steps, exit code 0.
- Clips +36, from 78 to 114.
- **Underruns +3, where 0 was expected.**
- Fallback +1 and missing +1. The fallback word is "fish", the only line of missing.txt.

"fish" is not a bug. It comes from the dolphin bubble "So long and thanks for all the fish!" in Momentum-Firmware/assets/dolphin/external/L1_Waves_128x50/meta.txt. The extraction reads only C string literals, so "fish" is not in the manifest. It is spoken because the scripted Back presses unlock the bubble suppression for two seconds. Every other word the sessions spoke is in the vocabulary.

#### 3. A thirty-word announcement

The sentence has 134 characters, under the queue item's 159, and 30 vocabulary words. The prediction was 215,179 samples, or 13,448 ms: 12,289 ms of clips plus 29 pauses of 40 ms.

```
[03:10:07 + 0.428s] == sr status   (reply after 0.008s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11277, dropped: 0, announcements: 41, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 48, aborted 6, dropped 0, underruns 16, queue dropped 0
last utterance: 4427 ms played, 89099 subsamples, 4131 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 114, fallback 15, missing 12
free heap: 114360
[03:10:07 + 0.437s] == sr say Open the saved file to read the new signal from the remote and save it as the key for the next time you go to the menu with your card.   (reply after 0.025s)
queued 134 characters; sr status shows the timing when it is done
[03:10:21 + 14.231s] (waited: idle after 13.562 s, speaker released after 13.769 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11305, dropped: 0, announcements: 41, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 49, aborted 6, dropped 0, underruns 19, queue dropped 0
last utterance: 13504 ms played, 215179 subsamples, 13448 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 144, fallback 15, missing 12
free heap: 114152
[03:10:21 + 14.231s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 144, fallback 15, missing 12
```

The result:
- Clips +30, fallback +0.
- Nominal time: 13,448 ms, exactly as predicted. 13,504 ms played, 56 ms more.
- **Underruns +3, where 0 was expected.**

#### 4. The missing-word round trip

```
[03:10:32 + 0.427s] == sr voice status   (reply after 0.007s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 144, fallback 15, missing 12
[03:10:32 + 0.435s] == sr say Zebrafish moonbeam   (reply after 0.013s)
queued 18 characters; sr status shows the timing when it is done
[03:10:35 + 2.775s] (waited: idle after 2.044 s, speaker released after 2.326 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11332, dropped: 0, announcements: 41, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 50, aborted 6, dropped 0, underruns 20, queue dropped 0
last utterance: 2039 ms played, 79920 subsamples, 1380 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 144, fallback 17, missing 14
free heap: 114344
[03:10:35 + 2.775s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 144, fallback 17, missing 14
[03:10:35 + 2.781s] == storage read /ext/sr/missing.txt   (reply after 0.014s)
Size: 24
fish
zebrafish
moonbeam
```

The first say gave missing +2 and fallback +2. missing.txt lists both words, after the "fish" from check 2.

The round trip:

```
$ time .venv/bin/python tools/voice_build.py --pull-missing --sync
voice: silenced for the transfer
>100%, chunk  1 of  1 @ 1.40 kb/s
pulled 3 missing words from the device
voice: restored
121 words, 3 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
made 3 clips, 0 failed, 2 s; vocabulary 2831 words in /Users/robin/Downloads/flipper-access/voice
voice: silenced for the transfer
<100%, chunk  1 of  1 @ 54.25 kb/s
<100%, chunk  2 of  2 @ 55.22 kb/s
<100%, chunk  2 of  2 @ 92.06 kb/s
<100%, chunk  1 of  1 @ 2.10 kb/s
sync: 3 sent, 2828 skipped, 0 missing, 0 failed, 1 s
voice: restored
.venv/bin/python tools/voice_build.py --pull-missing --sync 2>&1  0.97s user 0.39s system 32% cpu 4.232 total
exit 0
```

That was 4.2 s of wall clock. It made 3 clips, fish, zebrafish and moonbeam, sent those three and voice.txt, and skipped 2,828.

The second say:

```
[03:10:57 + 0.420s] == storage stat /ext/sr/missing.txt   (reply after 0.015s)
Storage error: file/dir not exist
[03:10:57 + 0.435s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 144, fallback 17, missing 14
[03:10:57 + 0.441s] == sr say Zebrafish moonbeam   (reply after 0.015s)
queued 18 characters; sr status shows the timing when it is done
[03:10:58 + 2.220s] (waited: idle after 1.572 s, speaker released after 1.765 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11379, dropped: 0, announcements: 41, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 51, aborted 6, dropped 0, underruns 21, queue dropped 0
last utterance: 1540 ms played, 23614 subsamples, 1475 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 146, fallback 17, missing 14
free heap: 114168
[03:10:58 + 2.220s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 146, fallback 17, missing 14
[03:10:58 + 2.226s] == storage list /ext/sr/voice/z   (reply after 0.029s)
	[F] z.raw 13630b
	[F] zalaz.raw 9582b
	[F] zaw.raw 6747b
	[F] zero.raw 7434b
	[F] zerworker.raw 10218b
	[F] zkteco.raw 11044b
	[F] zolotaya.raw 10956b
	[F] zone.raw 7578b
	[F] zones.raw 9421b
	[F] zoom.raw 7259b
	[F] zebrafish.raw 12716b
```

The result:
- missing.txt is gone.
- Clips +2, from 144 to 146, and fallback +0.
- 23,614 subsamples, exactly as predicted.
- The say gave underruns +1, and so did the first one. On the first, moonbeam's lookup scans all of folder m before SAM speaks it. On the second, moonbeam.raw is the newest, last entry of 193 in m.

#### 5. Interrupt and stop

A long say interrupted by another:

```
[03:11:12 + 0.427s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11406, dropped: 0, announcements: 41, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 51, aborted 6, dropped 0, underruns 21, queue dropped 0
last utterance: 1540 ms played, 23614 subsamples, 1475 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 146, fallback 17, missing 14
free heap: 114472
[03:11:12 + 0.437s] == sr say Open the saved file to read the new signal from the remote and save it as the key for the next time you go to the menu with your card.   (reply after 0.024s)
queued 134 characters; sr status shows the timing when it is done
[03:11:14 + 1.968s] == sr say Home screen   (reply after 0.005s)
queued 11 characters; sr status shows the timing when it is done
[03:11:14 + 1.974s] == sr status   (reply after 0.008s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11410, dropped: 0, announcements: 41, suppressed: 3
speech: speaking, queued 1, speaker held: yes, utterances 52, aborted 6, dropped 0, underruns 21, queue dropped 0
last utterance: 1540 ms played, 23614 subsamples, 1475 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 149, fallback 17, missing 14
free heap: 113456
[03:11:15 + 3.244s] (waited: idle after 1.067 s, speaker released after 1.261 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11412, dropped: 0, announcements: 41, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 53, aborted 7, dropped 0, underruns 21, queue dropped 0
last utterance: 1042 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 152, fallback 17, missing 14
free heap: 114184
[03:11:15 + 3.244s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 152, fallback 17, missing 14
```

The result:
- Utterances +2 and aborted +1.
- The second utterance, "Home screen", played in full: 15,972 subsamples as predicted, 998 ms nominal and 1,042 ms played.
- Underruns +0.

A long say cut with a Back press:

```
[03:11:23 + 0.420s] == sr say Open the saved file to read the new signal from the remote and save it as the key for the next time you go to the menu with your card.   (reply after 0.025s)
queued 134 characters; sr status shows the timing when it is done
[03:11:24 + 1.948s] == input send back short   (reply after 0.058s)
[03:11:24 + 2.007s] == sr status   (reply after 0.034s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11431, dropped: 0, announcements: 41, suppressed: 3
speech: idle, queued 0, speaker held: yes, utterances 54, aborted 8, dropped 0, underruns 21, queue dropped 0
last utterance: 1563 ms played, 25559 subsamples, 1597 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 156, fallback 17, missing 14
free heap: 114088
[03:11:25 + 2.293s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11432, dropped: 0, announcements: 41, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 54, aborted 8, dropped 0, underruns 21, queue dropped 0
last utterance: 1563 ms played, 25559 subsamples, 1597 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 156, fallback 17, missing 14
free heap: 114136
[03:11:25 + 2.311s] (waited: idle after 0.009 s, speaker released after 0.009 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11432, dropped: 0, announcements: 41, suppressed: 3
speech: idle, queued 0, speaker held: no, utterances 54, aborted 8, dropped 0, underruns 21, queue dropped 0
last utterance: 1563 ms played, 25559 subsamples, 1597 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 156, fallback 17, missing 14
free heap: 114112
[03:11:25 + 2.311s] == sr screen   (reply after 0.006s)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
[03:11:25 + 2.318s] == loader info   (reply after 0.054s)
No application is running
```

The result:
- Aborted +1.
- The status read sent as soon as `input send back short` returned already showed speech idle. That was 0.058 s after the Back command was sent, and the read's reply came 0.034 s later.
- At the 0.3 s check, 0.345 s after the Back command, the speaker was also released.
- Underruns +0. The device stayed on the home screen with no app running.

One more thing happened between checks 5 and 6. The home screen spoke one announcement on its own: announcements went from 41 to 42, clips +4, 2,523 ms nominal, underruns +1. It shows in the first `sr status` of check 6.

#### 6. Memory over twenty utterances, and twenty more

There were 20 utterances per round, each waited out to idle. The texts rotated through "Settings. Sub-GHz.", "Apps, 1 of 11.", "Read RAW. 433.92 MHz.", "Home screen" and "Bluetooth. Parent folder. Save.". The full logs are long, so here are the opening `free` and `sr status` of round 1 and the closing `free` and `sr status` of each round, verbatim. After them come the "last utterance" and "underruns" lines of all 40 utterances, taken from the logs with grep.

```
[03:11:37 + 0.425s] == free   (reply after 0.006s)
Free heap size: 114600
Total heap size: 185904
Minimum heap size: 83800
Maximum heap block: 105832
Pool free: 876
Maximum pool block: 672
[03:11:37 + 0.431s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11456, dropped: 0, announcements: 42, suppressed: 4
speech: idle, queued 0, speaker held: no, utterances 55, aborted 8, dropped 0, underruns 22, queue dropped 0
last utterance: 2559 ms played, 40376 subsamples, 2523 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 160, fallback 17, missing 14
free heap: 114424
[03:11:37 + 0.440s] == sr say Settings. Sub-GHz.   (reply after 0.014s)
...
free heap: 114096
[03:12:33 + 56.954s] == free   (reply after 0.006s)
Free heap size: 114192
Total heap size: 185904
Minimum heap size: 83800
Maximum heap block: 105832
Pool free: 876
Maximum pool block: 672
[03:12:33 + 56.960s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11569, dropped: 0, announcements: 42, suppressed: 4
speech: idle, queued 0, speaker held: no, utterances 75, aborted 8, dropped 0, underruns 31, queue dropped 0
last utterance: 2741 ms played, 43172 subsamples, 2698 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 252, fallback 17, missing 14
free heap: 114096
... round 2 ...
[03:12:47 + 0.417s] == free   (reply after 0.006s)
Free heap size: 114480
Total heap size: 185904
Minimum heap size: 83800
Maximum heap block: 105832
Pool free: 876
Maximum pool block: 672
...
free heap: 113968
[03:13:44 + 57.048s] == free   (reply after 0.006s)
Free heap size: 114064
Total heap size: 185904
Minimum heap size: 83800
Maximum heap block: 105832
Pool free: 876
Maximum pool block: 672
[03:13:44 + 57.055s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11711, dropped: 0, announcements: 42, suppressed: 4
speech: idle, queued 0, speaker held: no, utterances 95, aborted 8, dropped 0, underruns 41, queue dropped 0
last utterance: 2741 ms played, 43172 subsamples, 2698 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 344, fallback 17, missing 14
free heap: 113968
```

The "underruns" and "last utterance" lines after each of the 40 utterances, round 1 then round 2. Each row comes from the status printed when that utterance finished:

```
underruns 22 | last utterance: 2119 ms played, 33320 subsamples, 2082 ms nominal
underruns 22 | last utterance: 1948 ms played, 30272 subsamples, 1892 ms nominal
underruns 24 | last utterance: 5060 ms played, 80487 subsamples, 5030 ms nominal
underruns 24 | last utterance: 1046 ms played, 15972 subsamples, 998 ms nominal
underruns 24 | last utterance: 2742 ms played, 43172 subsamples, 2698 ms nominal
underruns 24 | last utterance: 2111 ms played, 33320 subsamples, 2082 ms nominal
underruns 24 | last utterance: 1947 ms played, 30272 subsamples, 1892 ms nominal
underruns 26 | last utterance: 5068 ms played, 80487 subsamples, 5030 ms nominal
underruns 26 | last utterance: 1048 ms played, 15972 subsamples, 998 ms nominal
underruns 27 | last utterance: 2741 ms played, 43172 subsamples, 2698 ms nominal
underruns 27 | last utterance: 2110 ms played, 33320 subsamples, 2082 ms nominal
underruns 27 | last utterance: 1948 ms played, 30272 subsamples, 1892 ms nominal
underruns 30 | last utterance: 5059 ms played, 80487 subsamples, 5030 ms nominal
underruns 30 | last utterance: 1048 ms played, 15972 subsamples, 998 ms nominal
underruns 30 | last utterance: 2741 ms played, 43172 subsamples, 2698 ms nominal
underruns 30 | last utterance: 2112 ms played, 33320 subsamples, 2082 ms nominal
underruns 30 | last utterance: 1949 ms played, 30272 subsamples, 1892 ms nominal
underruns 31 | last utterance: 5059 ms played, 80487 subsamples, 5030 ms nominal
underruns 31 | last utterance: 1048 ms played, 15972 subsamples, 998 ms nominal
underruns 31 | last utterance: 2741 ms played, 43172 subsamples, 2698 ms nominal
underruns 31 | last utterance: 2112 ms played, 33320 subsamples, 2082 ms nominal
underruns 31 | last utterance: 1948 ms played, 30272 subsamples, 1892 ms nominal
underruns 34 | last utterance: 5062 ms played, 80487 subsamples, 5030 ms nominal
underruns 34 | last utterance: 1048 ms played, 15972 subsamples, 998 ms nominal
underruns 34 | last utterance: 2740 ms played, 43172 subsamples, 2698 ms nominal
underruns 34 | last utterance: 2113 ms played, 33320 subsamples, 2082 ms nominal
underruns 34 | last utterance: 1949 ms played, 30272 subsamples, 1892 ms nominal
underruns 36 | last utterance: 5062 ms played, 80487 subsamples, 5030 ms nominal
underruns 36 | last utterance: 1047 ms played, 15972 subsamples, 998 ms nominal
underruns 36 | last utterance: 2740 ms played, 43172 subsamples, 2698 ms nominal
underruns 36 | last utterance: 2112 ms played, 33320 subsamples, 2082 ms nominal
underruns 36 | last utterance: 1948 ms played, 30272 subsamples, 1892 ms nominal
underruns 38 | last utterance: 5059 ms played, 80487 subsamples, 5030 ms nominal
underruns 38 | last utterance: 1046 ms played, 15972 subsamples, 998 ms nominal
underruns 38 | last utterance: 2741 ms played, 43172 subsamples, 2698 ms nominal
underruns 38 | last utterance: 2111 ms played, 33320 subsamples, 2082 ms nominal
underruns 38 | last utterance: 1948 ms played, 30272 subsamples, 1892 ms nominal
underruns 41 | last utterance: 5061 ms played, 80487 subsamples, 5030 ms nominal
underruns 41 | last utterance: 1048 ms played, 15972 subsamples, 998 ms nominal
underruns 41 | last utterance: 2741 ms played, 43172 subsamples, 2698 ms nominal
```

After both rounds and 11 s idle:

```
[03:13:55 + 0.428s] == free   (reply after 0.006s)
Free heap size: 114512
Minimum heap size: 83800
Maximum heap block: 105832
[03:14:05 + 10.445s] == free   (reply after 0.005s)
Free heap size: 114512
Minimum heap size: 83800
Maximum heap block: 105832
```

The heap numbers:
- Free heap at idle went 114,600, then 114,480 between the rounds, then 114,512 at the end.
- Right after speech it is about 400 bytes lower, and it recovers within seconds.
- The largest block stayed at 105,832 and the minimum at 83,800 throughout.

So there is no leak. The minimum of 83,800 was set before these checks, during the sync or the first sr_drive run; it was 84,640 before the sync. Underruns over the 40 utterances: +19, from 22 to 41.

#### 7. Voice off, voice on, and a reboot

```
[03:14:17 + 0.428s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 344, fallback 17, missing 14
[03:14:17 + 0.433s] == sr voice off   (reply after 0.121s)
voice off: SAM speaks everything
[03:14:17 + 0.554s] == sr say Settings. Sub-GHz.   (reply after 0.022s)
queued 18 characters; sr status shows the timing when it is done
[03:14:19 + 3.093s] (waited: idle after 2.294 s, speaker released after 2.517 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 11782, dropped: 0, announcements: 42, suppressed: 4
speech: idle, queued 0, speaker held: no, utterances 96, aborted 8, dropped 0, underruns 41, queue dropped 0
last utterance: 2304 ms played, 97760 subsamples, 1547 ms nominal, worker stack free 2372
voice: off, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 344, fallback 17, missing 14
free heap: 114168
[03:14:19 + 3.093s] == sr voice status   (reply after 0.007s)
voice: off, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 344, fallback 17, missing 14
[03:14:19 + 3.100s] == sr voice on   (reply after 0.083s)
voice on
[03:14:19 + 3.183s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand ma, clips 344, fallback 17, missing 14
[03:14:19 + 3.189s] == power reboot   (sent; the port goes away)
```

My port watcher did not see the port go away; the node may stay for a fast reboot. The device's uptime proves the reboot:

```
[03:14:53 + 0.428s] == uptime   (reply after 0.067s)
Uptime: 0h0m33s
[03:14:54 + 0.495s] == sr screen   (reply after 0.007s)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
[03:14:54 + 0.503s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0
[03:14:54 + 0.509s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 64, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1050 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2684
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0
free heap: 114560
```

The result:
- With the voice off, SAM spoke and the voice counters did not move. That is correct: the voice-off path is the plain SAM path.
- The on setting survived the reboot.
- `sr screen`, read first, shows the desktop.
- After the reboot, `sr voice status` shows the new settings line.
- The boot announcement "Home screen" played from 2 clips with the same 15,972 subsamples, and 0 underruns.

### Final device state

The device is at 03:19:37, 5 minutes after the reboot:
- on the home screen,
- with the reader on and speech idle,
- with the speaker released and the voice on,
- with no app running and no missing.txt.

I did not send `loader close`.

```
[03:19:37 + 0.427s] == uptime   (reply after 0.054s)
Uptime: 0h5m17s
[03:19:37 + 0.482s] == sr screen   (reply after 0.007s)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
[03:19:37 + 0.489s] == sr status   (reply after 0.008s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 631, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1050 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2684
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0
free heap: 114480
[03:19:37 + 0.498s] == loader info   (reply after 0.054s)
No application is running
[03:19:37 + 0.553s] == storage stat /ext/sr/missing.txt   (reply after 0.015s)
Storage error: file/dir not exist
[03:19:37 + 0.568s] == free   (reply after 0.006s)
Free heap size: 114424
Total heap size: 185904
Minimum heap size: 112416
Maximum heap block: 114392
Pool free: 876
Maximum pool block: 672
```

### The measurements file, verbatim

docs/measurements/2026-09-24-voice-rollout.txt as committed:

```
Recorded voice rollout, 2026-09-24

Setup
Device: R0skie on /dev/cu.usbmodemflip_R0skie1, firmware branch screen-reader at 1783e081f, 64 GB exFAT card.
Generator: tools/voice_build.py at 76346f6, settings line "say Samantha rate 175 highpass 500 gain 1.3 soft 16000".
Counters are from sr status and sr voice status. Played and nominal are the "last utterance" line.
Predicted nominal times are the clip sizes plus the pauses. The pauses are 40 ms between words, 150 ms after a comma and 300 ms after a period, with none after the last word.

Build on the Mac: tools/voice_build.py --extract
Strings: 6182 distinct string literals from the firmware's core apps and services, giving 2815 words.
Base list: tools/voice_words.txt adds 8 words, for 2823 in total. 0 failed.
With 4 jobs: 22:02.88 wall clock, of which 1322 s for the clips (0.47 s per clip).
With 8 jobs: 16:19.58 wall clock, of which 979 s for the clips (0.35 s per clip).
The say command is limited by the macOS speech server, not by the CPU: with 8 jobs it used 95 percent of one core.
Clips: 2823 clips, 26,928,695 bytes, or 1683 s of audio. du -sh reports 31M, with an apparent size of 27M.
Clip length: shortest 0.228 s, median 0.564 s, longest 2.648 s.
Every clip has 15 ms of silence at both edges and peaks at least 100 away from 128. None is silent.
Clips per folder: s 315, c 229, m 191, p 188, d 170. The other folders are smaller.

Sync: .venv/bin/python tools/voice_build.py --pull-missing --sync
Wall clock: 7:26.77.
Pulled: 17 missing words from the card. 5 of them were new clips: am, bahncard, friend, my, wish.
Sent: 2828 clips and voice.txt in 442 s. That is 61 kB/s, or 6.4 files per second. 0 missing, 0 failed, exit code 0.
Guard: the voice was silenced and then restored around both the pull and the sync.
Card after the sync: 2828 clips. They match the local files by name and size (26,964,198 bytes). voice.txt is 55 bytes, and missing.txt was removed.
office.raw: the one hand-made Task 2 clip not in the vocabulary. It was removed with storage remove.
sr voice status right after the sync: vocabulary yes, but still with the old hand-made settings line. The device reads voice.txt once per boot, so the new line showed after the reboot in check 7.

Check 1: sr say Settings. Sub-GHz. Apps, 1 of 11. Read RAW. 433.92 MHz. UID: 04 A2 B3 C4.
The expansion has 28 words.
Clips: 32 to 60, which is +28. Fallback +0, missing +0.
Timing: 17226 ms played, 274710 subsamples, 17169 ms nominal. The prediction was 274710 samples, or 17169 ms, an exact match.
Underruns: 0 to 5, which is +5. Expected 0.

Extra check: the same number of clips, taken from the front and from the end of folders.
Front: "settings apps one of okay home screen back saved". These are the Task 2 clips at the front of their folders. Underruns +0. 4569 ms played, 4516 ms nominal.
End: "systems types cycles", three times. These are the last files in folders of 315, 155 and 229 clips. Underruns +8, one for each open after the first. 6262 ms played, 6144 ms nominal.

Lookup time: the console round trip for storage stat, median of 5
Folder s holds 315 clips.
Position 1: 6.6 ms.
Position 50: 20.6 ms.
Position 100: 27.9 ms.
Position 150: 37.1 ms.
Position 200: 44.6 ms.
Position 250: 53.4 ms.
Position 300: 62.8 ms.
Position 315: 64.8 ms.
A word that is not in the folder: 66.9 ms.
Folder 0, which holds one clip: 12.7 ms.
Every directory entry costs about 0.17 ms. One half of the ring holds 41 ms of audio, so an open that takes longer causes an underrun.

Check 2: tools/sr_drive.py, both sessions, with the voice on
Result: 0 failures in 17 steps.
Utterances: 28 to 48. Aborted: 5 to 6.
Clips: 78 to 114, which is +36.
Fallback: 14 to 15, which is +1. Missing: 11 to 12.
The fallback word is "fish", from the dolphin bubble text "So long and thanks for all the fish!". That text is in assets/dolphin/external/L1_Waves_128x50/meta.txt, which the extraction does not read. So this is a gap in the vocabulary, not a bug.
Underruns: 13 to 16, which is +3. Expected 0.

Check 3: thirty words in one sentence of 134 characters
Text: sr say Open the saved file to read the new signal from the remote and save it as the key for the next time you go to the menu with your card.
Clips: 114 to 144, which is +30. Fallback +0.
Timing: 13504 ms played, 215179 subsamples, 13448 ms nominal. That is 12289 ms of clips plus 29 pauses of 40 ms, 1160 ms. The prediction was an exact match.
Underruns: 16 to 19, which is +3. Expected 0.

Check 4: the missing-word round trip
First sr say Zebrafish moonbeam: fallback 15 to 17, which is +2. Missing 12 to 14, which is +2.
missing.txt held 24 bytes: fish, zebrafish, moonbeam.
Underruns +1. 2039 ms played, 1380 ms nominal, with SAM speaking both words.
Round trip: time .venv/bin/python tools/voice_build.py --pull-missing --sync took 4.232 s of wall clock.
It pulled 3 words, made 3 clips and sent 3 clips and voice.txt. 2828 were skipped. Exit code 0.
missing.txt was gone afterwards.
Second sr say Zebrafish moonbeam: clips 144 to 146, which is +2. Fallback +0.
Timing: 1540 ms played, 23614 subsamples, 1475 ms nominal. The prediction was an exact match.
Underruns +1. The new moonbeam.raw is the last of 193 files in folder m.

Check 5: interrupt and stop
A long say interrupted by sr say Home screen after 1.5 s: utterances +2, aborted +1.
Home screen played in full: 15972 subsamples (predicted 15972), 998 ms nominal, 1042 ms played. Underruns +0.
A long say cut by input send back short after 1.5 s: aborted +1.
The first status read, sent as soon as the Back command returned (0.058 s), already showed speech idle.
At 0.345 s after the Back command, the speaker was released.
Underruns +0. Home screen, no app running.
Before check 6, the home screen spoke one announcement by itself: 4 clips, 2523 ms nominal, underruns +1.

Check 6: memory over twenty and forty utterances
Before: free heap 114600, minimum 83800, largest block 105832.
After 20 utterances: 114192.
After 14 s idle: 114480.
After 20 more utterances: 114064.
After 11 s idle: 114512.
The largest block stayed at 105832 and the minimum at 83800 throughout.
The dip of about 400 bytes right after speech recovers within seconds, so there is no leak.
Underruns over the 40 utterances: 22 to 41, which is +19.
The texts used are Settings. Sub-GHz. / Apps, 1 of 11. / Read RAW. 433.92 MHz. / Home screen / Bluetooth. Parent folder. Save.

Check 7: voice off, voice on, reboot
sr voice off replied "voice off: SAM speaks everything".
sr say Settings. Sub-GHz.: clips, fallback and missing unchanged. 2304 ms played, 97760 subsamples, 1547 ms nominal. Underruns +0.
sr voice on replied "voice on". Then power reboot.
After the reboot, with an uptime of 33 s:
sr screen: content layer desktop.
sr voice status: voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0.
sr status: utterances 1, underruns 0, free heap 114560.
The 2 clips are the boot announcement "Home screen".

Summary
All checks behave as specified except underruns.
Every lookup of a word near the end of a large folder takes longer than one half of the ring, 41 ms.
The verification caused 41 underruns before the reboot. From the extra check, each one adds about 8 ms to the played time.
Smaller folders would fix this. That change is not part of this rollout.
```

### Documents

- README.md has a new "Recorded voice" section. It covers:
  - what the voice is, and that SAM remains the fallback;
  - the card layout;
  - the console commands `sr voice on|off|status`, and that the settings line is read once per boot;
  - `tools/voice_build.py` with its defaults and the two backends, say and piper;
  - the build time: about 16 minutes with `--jobs 8` on this Mac, limited by the speech server rather than the CPU;
  - the sync and missing-word workflows, with their times;
  - that `--sync-all` works only with `--sync`, and that `--sync` and `--pull-missing` need the venv Python;
  - the licensing note;
  - that `voice/` must not be deleted;
  - the known limits: apostrophe words and words over 16 letters fall back to SAM, bubble texts are not extracted, and the underrun issue.

  "Folder contents" gains entries for voice_build.py, clip_make.py and voice/, and the date line is now 2026-09-24.
- The spec's status line is now "as built 2026-09-24". It is followed by the six deviations:
  - the word sources,
  - the name filter,
  - the processing order,
  - the sync with synced.json and the voice guard,
  - the settings line read once per boot,
  - the open timing defect, with its numbers.
- In the roadmap, memory plan item 1 is done. It gives 2,831 words, about 3 KB of flash and 700 bytes of idle heap (Task 2's figures), and the open underrun issue.

### Deviations

1. `sr_drive.py --help` ran both sessions before the sync. Details are above; there was no harm.
2. `sr voice status` after the sync showed the old settings line, because the line is cached per boot. The new line was confirmed after the reboot in check 7, not right after the sync.
3. Check 4's round trip also carried "fish" from check 2. So it made and sent 3 clips, not 2. For the say itself, clips +2 and fallback +0 hold as expected.
4. Checks beyond the brief:
   - the size comparison of the whole card;
   - the lookup timings;
   - the front-against-end folder comparison;
   - a second round of 20 utterances in check 6, to tell a transient dip from a leak.
5. Check 6 used rotating short texts rather than one text, so that the clip path covered many folders.

### Concerns

1. **The acceptance test fails on underruns.** Checks 1 to 6 gave 41 underruns in all, for example 5 on the test sentence, 3 over the two sr_drive sessions and 3 on the 30-word sentence. The spec's acceptance test asks for 0.
   - Cause: exFAT lookups are linear, at about 0.17 ms per directory entry, up to 65 ms at the end of folder s. The budget before a stall counts is what is left of the playing half, at most 41 ms.
   - Not the cause: the clip data, the pauses and the fallback path. With words at the front of their folders there were 0 underruns.
   - Size: each underrun costs about 8 ms of audio, a short glitch. I cannot hear it from here.
   - Fix options, for the controller to choose:
     - Smaller folders. With two-letter folders the largest holds 105 words ("re") and the next 85 ("co"), which still reaches about 25 to 30 ms. Hashed buckets, for example 64 folders of about 44 words, give about 10 ms. Either way both speech_voice_path and the generator's initial() change, and the card is re-synced with `--sync --sync-all`.
     - Only reordering the files so that frequent words come first. That is cheaper, but it leaves the tail and every newly pulled word slow.
     - A bigger ring. That costs heap, which is scarce.
2. **Roadmap memory item 4 would make this worse.** It plans to cut the ring from 4096 to 3072 slots, which gives 31 ms halves. It should wait for the folder fix. I did not edit item 4.
3. **Dolphin bubble texts are not in the vocabulary.** They live in assets/dolphin/*/meta.txt as "Text:" lines. "fish" reached the vocabulary through missing.txt. Adding those lines to the extraction would be a small change to the generator.
4. **The status settings line is cached per boot.** This is by design in Task 2, but after a sync `sr voice status` shows the old line, which can mislead. It is documented in the README.
5. **exFAT cluster size:** not measured. On a 64 GB exFAT card each small clip probably takes a whole cluster, typically 128 KB, so the 2,831 clips may take about 350 MB of card space. That is harmless on 64 GB.

## Fix round 1: hashed clip folders, larger ring, open timing

Status: DONE. Every check since the flash showed 0 underruns: 432 clips, including a single 100-word announcement. The longest clip open measured was 39 ms, against halves of 82 ms. The device is idle on the home screen, with the reader on, the voice on and speech idle.

### Commits

Firmware repository, branch screen-reader. Nothing is pushed, and applications/external is untouched.
- `6282541b64dd3f3b6438ca64caf615d5adada450` "screen reader: hashed clip folders, larger ring, open timing". Files, all in applications/services/screen_reader: speech_voice.c, speech_voice.h, speech.c, speech.h and screen_reader_cli.c.

Project repository, main. Nothing is pushed.
- `79bff7beb5fefb7e7108974a4e5168cfd7d75ed5` "host tests: hashed clip folders", with tests/host/test_speech_voice.c.
- `534fcf9dbe4b87fa0a16b09d56e2f09470e91383` "voice_build: hashed clip folders, apostrophe words, dolphin bubble texts, legacy removal", with tools/voice_build.py. tools/voice_names.txt needed no change.
- `ef711511811223e02174159036c6c5e2756ad98b` "docs: hashed clip folders, larger ring, corrected numbers", with README.md, the spec, docs/roadmap.md and the measurements file.

All four commits were made with an explicit `git add` and a pathspec commit, and end with the Co-Authored-By line.

### A. Firmware

- speech_voice.c and .h:
  - `sv_hash` is now the public `uint32_t speech_voice_hash(const char* word)`, the same FNV-1a, and the missing-word set uses it.
  - The clip folder is `speech_voice_hash(word) % SPEECH_VOICE_BUCKETS`, where the new constant `SPEECH_VOICE_BUCKETS` is 64. It is written as two lower case hex digits: `/ext/sr/voice/<hh>/<word>.raw`.
  - `SPEECH_VOICE_PATH_MAX` stays 64. The longest path is 13 + 4 + 31 + 4 + 1 = 53 bytes.
  - `speech_voice_next_word` leaves apostrophes out of the name. The cut at 31 characters counts only the characters kept.
- speech.c:
  - `SPEECH_RING_SIZE` is 8192.
  - `open_max_ms` and `open_last_ms` in the Speech record are set from `furi_get_tick()` around every `storage_file_open` of a clip, whether the file is found or not.
  - `speech_get_voice_stats` copies the two counters.
- speech.h: `SpeechVoiceStats` gains `open_max_ms` and `open_last_ms`.
- screen_reader_cli.c: the voice line ends in `, open max %lu ms, last %lu ms`.
- The generator's voice guard still finds "voice: on" in the new line.

Host runner, with a private TMPDIR in the scratchpad:

```
$ TMPDIR=<scratchpad>/hosttmp tools/run_host_tests.sh 2>&1 | tail -12
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 115 checks, 0 failures
speech PCM: 700 checks, 0 failures
speech voice: 4170 checks, 0 failures
exit 0
```

The voice test now:
- pins "settings" at 08, "7" at 36, "ay" at 0f, "dont" from "don't" at 0e, and returns 0 for "". I computed the pins independently in Python.
- checks the hash and the folder of 14 named words and 2,000 generated words against its own reference FNV-1a, and checks that the generated words use all 64 folders.
- keeps every earlier check. The "'odd" path is now checked against the reference.
- adds the contractions "Don't do it, it's fine. rock'n'roll' '" and a 35-character word with an apostrophe, whose cut must count kept characters only.

Build, lint and headroom:

```
$ ../tools/flash_headroom.sh      (before, the flashed 1783e081f image)
firmware.bin 871744 bytes, limit 880640, spare 8896 bytes
$ ./fbt                            (exit 0, 19.7 s)
fbt: warning: Failed parsing manifest '.../applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui'. ...
fbt: warning: Failed parsing manifest '.../applications/external/mtp/application.fam' : Invalid appid '.f0_mtp'. ...
API version 87.1 is up to date
.free_flash   176704 (172.56 K)
$ ../tools/flash_headroom.sh      (after)
firmware.bin 871872 bytes, limit 880640, spare 8768 bytes
$ ./fbt lint                      (exit 0)
```

The only warnings from the build and from lint are the two manifest warnings that were there before. The change costs 128 bytes of flash.

### B. Generator

- `clip_name` leaves out apostrophes before it applies `WORD_RE`.
- `fnv1a()` is written exactly as ruled. `bucket(word)` returns `f"{fnv1a(word) % 64:02x}"`.
- `extract_words` returns the words and a map from a stripped name to its spoken token.
  - The map records only apostrophes inside a word, not quotes around it.
  - When two tokens give one name, the alphabetically smallest wins, so the result is deterministic.
  - `main` merges it as `names = {**originals, **names}`, so a `voice_names.txt` entry still wins.
- `bubble_texts()` reads the `Text:` lines of every manifest.txt and meta.txt under Momentum-Firmware/assets/dolphin. The key is `Text: ` with literal `\n` line breaks, as in L1_Waves_128x50/meta.txt. They go through the expander together with the firmware strings. That gives 71 distinct texts from 73 lines in 46 files.
- `sync()` sends local `voice/<initial>/<word>.raw` to `/ext/sr/voice/<bucket>/<word>.raw`, and runs `mkpath` once per bucket.
  - I kept the local layout by first letter. The ruling named only the card folder, and a local move would have meant a migration.
- `--remove-legacy` works inside the voice guard.
  - For every word in synced.json it removes `/ext/sr/voice/<initial>/<word>.raw`. A `FlipperStorageException` counts as "not found".
  - It then removes each single-character folder. A folder that is not empty refuses the remove: the storage CLI calls `f_unlink`, which does not delete non-empty folders. That is ignored.
  - It clears synced.json.
  - It prints progress every 500 words and the counts.
  - Without other flags it stops after that.

I tested both device paths against fake storage objects before touching the device. Verbatim:

```
voice: silenced for the transfer
remove-legacy: 3 clips removed, 1 not found, 2 of 3 folders removed, synced.json cleared, 0 s
voice: restored
['sr voice status', 'sr voice off', 'remove /ext/sr/voice/7/7.raw', 'remove /ext/sr/voice/g/gone.raw', 'remove /ext/sr/voice/s/settings.raw', 'remove /ext/sr/voice/s/sub.raw', 'remove /ext/sr/voice/7', 'remove /ext/sr/voice/g', 'remove /ext/sr/voice/s', 'sr voice on', 'stop']
card left: ['/ext/sr/voice/g', '/ext/sr/voice/g/keep.raw']
synced.json: {}
---
voice: silenced for the transfer
sync: 2 sent, 0 skipped, 0 missing, 0 failed, 0 s
voice: restored
returned 0
sr voice status
sr voice off
mkpath /ext/sr/voice/0e
send d/dont.raw -> /ext/sr/voice/0e/dont.raw
mkpath /ext/sr/voice/08
send s/settings.raw -> /ext/sr/voice/08/settings.raw
send voice.txt -> /ext/sr/voice/voice.txt
sr voice on
stop
```

The Python buckets match the firmware's pins: settings 08, 7 36, ay 0f and dont 0e.

`--check`, verbatim: exit 0, 10.9 s.

```
check settings: ok 0.61 s, quiet edges True, peak ok True 
check sub: ok 0.43 s, quiet edges True, peak ok True 
check gigahertz: ok 0.70 s, quiet edges True, peak ok True 
check one: ok 0.41 s, quiet edges True, peak ok True 
check ay: ok 0.79 s, quiet edges True, peak ok True 
check b: ok 0.79 s, quiet edges True, peak ok True 
check 7: ok 0.47 s, quiet edges True, peak ok True 
check okay: ok 0.57 s, quiet edges True, peak ok True 
check home: ok 0.41 s, quiet edges True, peak ok True 
check percent: ok 0.57 s, quiet edges True, peak ok True 
```

A dry run before the build showed which clips it would make. There were 64: 60 new words, and 4 remade because their spoken text changed.

```
new: 60 accidents adios anymore become been best better crxr dance dearest die doesnt dream dude dying everyone feel forever forgot goes gonna good happened hh idk ill im isnt joke lived lookin lucid man mess miss mistakes myself nevermind nothing pill predictable pwned rm rn senpai showtime sick someone something sup swim take today together twist vbba whos ya youre youuuuu
remade (spoken text changed): 4 cant->can't dont->don't flippers->flipper's its->it's
```

The build, `tools/voice_build.py --extract --jobs 8`, verbatim. Exit 0.

```
extract: 6184 distinct strings from the firmware sources, 71 bubble texts
extract: 2880 words; longest: animationmanager animationstorage backlightenforce checksdkfeatures configchangeable defaulttextclear desktopscenelock freecreatedelete getbatterycharge hoppingthreshold
extract: 10 with an apostrophe: can't doesn't don't flipper's i'll i'm isn't it's who's you're
2888 words, 64 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
made 64 clips, 0 failed, 22 s; vocabulary 2891 words in /Users/robin/Downloads/flipper-access/voice
```

The build numbers:
- 64 made in 22.5 s, 0 failed. The vocabulary grew from 2,831 to 2,891 words.
- Firmware strings went from 6,182 to 6,184, because this round's firmware added two literals. The extracted words went from 2,815 to 2,880.
- The all-clips check still passes for all 2,891 clips: no silent clip, silent 15 ms edges, peaks of at least 100, and a one-to-one match with the manifest.
- By hash the 64 folders hold 30 to 65 clips each; 2a is the largest.

### C. Device

The baseline before the flash, verbatim excerpt:

```
[03:45:54 + 0.544s] == sr status   (reply after 0.009s)
...
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0
free heap: 114488
[03:45:54 + 0.554s] == free   (reply after 0.004s)
Free heap size: 114552
Total heap size: 185904
Minimum heap size: 112392
Maximum heap block: 110512
[03:45:54 + 0.558s] == info device   (reply after 0.029s)
firmware.commit.hash          : 1783e081
firmware.commit.dirty         : true
firmware.branch.name          : screen-reader
```

The flash:
- `./fbt flash_usb` ran from 03:46:02 to 03:46:36 with exit 0.
- It built the package f7-update-mntm-screen-reader-6282541b, sent firmware.dfu in 107 chunks and updater.bin in 15, then printed "Closing current app, if any". No app was running.
- The port went away and was back 23 s later, at 03:47:04. I let the device settle for 12 s.

The first command after the flash, sent alone, then `info device` and the rest, verbatim. The `system.*` and hardware lines are filtered out.

```
[03:47:27 + 0.428s] == sr screen   (reply after 0.007s)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
[03:47:27 + 0.425s] == info device   (reply after 0.043s)
firmware.commit.hash          : 6282541b
firmware.commit.dirty         : true
firmware.branch.name          : screen-reader
firmware.branch.num           : 0
firmware.version              : mntm-dev
firmware.build.date           : 24-09-2026
firmware.target               : 7
firmware.api.major            : 87
firmware.api.minor            : 1
firmware.origin.fork          : Momentum
firmware.origin.git           : https://github.com/Next-Flip/Momentum-Firmware.git
[03:47:27 + 0.469s] == uptime   (reply after 0.055s)
Uptime: 0h0m26s
[03:47:28 + 0.524s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 49, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1592 ms played, 61200 subsamples, 1063 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 0, fallback 2, missing 2, open max 17 ms, last 17 ms
free heap: 110480
[03:47:28 + 0.533s] == sr voice status   (reply after 0.007s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 0, fallback 2, missing 2, open max 17 ms, last 17 ms
[03:47:28 + 0.540s] == free   (reply after 0.006s)
Free heap size: 110520
Total heap size: 185904
Minimum heap size: 108432
Maximum heap block: 110344
Pool free: 876
Maximum pool block: 672
[03:47:28 + 0.547s] == loader info   (reply after 0.054s)
No application is running
```

The new image 6282541b runs, and there was no popup.
- The boot "Home screen" fell back to SAM, because the hashed folders did not exist yet: fallback 2, missing 2.
- The failed open of a folder that did not exist took 17 ms.
- Idle heap: 110,520 against 114,552 before, so the larger ring costs 4,032 bytes.

`--remove-legacy`, verbatim: 2,831 words in synced.json, exit 0.

```
voice: silenced for the transfer
remove-legacy: 500 of 2831, 14 s
remove-legacy: 1000 of 2831, 30 s
remove-legacy: 1500 of 2831, 43 s
remove-legacy: 2000 of 2831, 58 s
remove-legacy: 2500 of 2831, 76 s
remove-legacy: 2831 clips removed, 0 not found, 36 of 36 folders removed, synced.json cleared, 87 s
voice: restored
```

```
== storage list /ext/sr/voice
	[F] voice.txt 55b
== sr voice status
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 0, fallback 2, missing 2, open max 17 ms, last 17 ms
== storage read /ext/sr/missing.txt
Size: 12
home
screen
```

`--sync`: every clip resent into the hashed folders. These are the non-progress lines and `time`, verbatim:

```
118 words, 0 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
made 0 clips, 0 failed, 0 s; vocabulary 2891 words in /Users/robin/Downloads/flipper-access/voice
voice: silenced for the transfer
sync: 100 of 2891, 100 sent, 0 skipped, 31 s
sync: 200 of 2891, 200 sent, 0 skipped, 47 s
sync: 300 of 2891, 300 sent, 0 skipped, 58 s
sync: 400 of 2891, 400 sent, 0 skipped, 70 s
sync: 500 of 2891, 500 sent, 0 skipped, 81 s
sync: 600 of 2891, 600 sent, 0 skipped, 93 s
sync: 700 of 2891, 700 sent, 0 skipped, 105 s
sync: 800 of 2891, 800 sent, 0 skipped, 116 s
sync: 900 of 2891, 900 sent, 0 skipped, 129 s
sync: 1000 of 2891, 1000 sent, 0 skipped, 141 s
sync: 1100 of 2891, 1100 sent, 0 skipped, 152 s
sync: 1200 of 2891, 1200 sent, 0 skipped, 164 s
sync: 1300 of 2891, 1300 sent, 0 skipped, 178 s
sync: 1400 of 2891, 1400 sent, 0 skipped, 189 s
sync: 1500 of 2891, 1500 sent, 0 skipped, 202 s
sync: 1600 of 2891, 1600 sent, 0 skipped, 214 s
sync: 1700 of 2891, 1700 sent, 0 skipped, 226 s
sync: 1800 of 2891, 1800 sent, 0 skipped, 238 s
sync: 1900 of 2891, 1900 sent, 0 skipped, 250 s
sync: 2000 of 2891, 2000 sent, 0 skipped, 262 s
sync: 2100 of 2891, 2100 sent, 0 skipped, 276 s
sync: 2200 of 2891, 2200 sent, 0 skipped, 289 s
sync: 2300 of 2891, 2300 sent, 0 skipped, 303 s
sync: 2400 of 2891, 2400 sent, 0 skipped, 318 s
sync: 2500 of 2891, 2500 sent, 0 skipped, 332 s
sync: 2600 of 2891, 2600 sent, 0 skipped, 346 s
sync: 2700 of 2891, 2700 sent, 0 skipped, 360 s
sync: 2800 of 2891, 2800 sent, 0 skipped, 374 s
sync: 2891 sent, 0 skipped, 0 missing, 0 failed, 385 s
voice: restored
.venv/bin/python tools/voice_build.py --sync 2>&1  5.04s user 6.52s system 2% cpu 6:25.93 total
tee   0.02s user 1.07s system 0% cpu 6:25.94 total
awk -F'\r' '{print $NF}'  0.08s user 0.15s system 0% cpu 6:25.94 total
exit 0
```

That is 6:25.93 of wall clock in all, of which 385 s for 2,891 sends plus voice.txt.

`storage list /ext/sr/voice` afterwards, verbatim, in the card's order:

```
== storage list /ext/sr/voice
	[D] 2f
	[D] 1c
	[D] 15
	[D] 02
	[D] 23
	[D] 10
	[D] 09
	[D] 36
	[D] 07
	[F] voice.txt 55b
	[D] 34
	[D] 2c
	[D] 2a
	[D] 16
	[D] 39
	[D] 27
	[D] 3e
	[D] 0a
	[D] 3b
	[D] 1d
	[D] 22
	[D] 2b
	[D] 1f
	[D] 05
	[D] 24
	[D] 13
	[D] 3f
	[D] 3c
	[D] 0b
	[D] 37
	[D] 21
	[D] 25
	[D] 32
	[D] 35
	[D] 0f
	[D] 1b
	[D] 1e
	[D] 29
	[D] 17
	[D] 30
	[D] 1a
	[D] 38
	[D] 04
	[D] 03
	[D] 01
	[D] 3d
	[D] 26
	[D] 11
	[D] 33
	[D] 18
	[D] 19
	[D] 2e
	[D] 14
	[D] 12
	[D] 0d
	[D] 08
	[D] 0c
	[D] 2d
	[D] 31
	[D] 3a
	[D] 28
	[D] 20
	[D] 06
	[D] 0e
	[D] 00
```

That is 64 two-hex-digit folders and voice.txt, nothing else. A comparison of the whole card with the local files by folder, name and size, verbatim:

```
local clips 2891, card clips 2891, bytes local 27477882, card 27477882
only on the card: []
only local: []
size differs: []
clips per folder: min 30, max 65 (2a)
```

#### Verification 1: voice status

```
[03:56:08 + 0.427s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 0, fallback 2, missing 2, open max 17 ms, last 17 ms
[03:56:08 + 0.433s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1090, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1592 ms played, 61200 subsamples, 1063 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 0, fallback 2, missing 2, open max 17 ms, last 17 ms
free heap: 110368
```

The status shows vocabulary yes, the settings line, and open max and last.

#### Verification 2: the former end-of-folder sentence, eight times

The full log, verbatim:

```
[03:56:15 + 0.427s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1104, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1592 ms played, 61200 subsamples, 1063 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 0, fallback 2, missing 2, open max 17 ms, last 17 ms
free heap: 110456
[03:56:15 + 0.437s] == sr say systems types cycles systems types cycles systems types cycles   (reply after 0.018s)
queued 62 characters; sr status shows the timing when it is done
[03:56:22 + 6.974s] (waited: idle after 6.33 s, speaker released after 6.518 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1117, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 6265 ms played, 98315 subsamples, 6144 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 9, fallback 2, missing 2, open max 32 ms, last 22 ms
free heap: 110312
[03:56:22 + 6.974s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 9, fallback 2, missing 2, open max 32 ms, last 22 ms
[03:56:22 + 6.980s] == sr say systems types cycles systems types cycles systems types cycles   (reply after 0.018s)
queued 62 characters; sr status shows the timing when it is done
[03:56:28 + 13.510s] (waited: idle after 6.314 s, speaker released after 6.511 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1130, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 3, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 6265 ms played, 98315 subsamples, 6144 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 18, fallback 2, missing 2, open max 32 ms, last 24 ms
free heap: 110272
[03:56:28 + 13.510s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 18, fallback 2, missing 2, open max 32 ms, last 24 ms
[03:56:28 + 13.516s] == sr say systems types cycles systems types cycles systems types cycles   (reply after 0.018s)
queued 62 characters; sr status shows the timing when it is done
[03:56:35 + 20.000s] (waited: idle after 6.263 s, speaker released after 6.466 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1143, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 4, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 6265 ms played, 98315 subsamples, 6144 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 27, fallback 2, missing 2, open max 32 ms, last 22 ms
free heap: 110272
[03:56:35 + 20.000s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 27, fallback 2, missing 2, open max 32 ms, last 22 ms
[03:56:35 + 20.006s] == sr say systems types cycles systems types cycles systems types cycles   (reply after 0.018s)
queued 62 characters; sr status shows the timing when it is done
[03:56:41 + 26.498s] (waited: idle after 6.271 s, speaker released after 6.474 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1156, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 5, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 6265 ms played, 98315 subsamples, 6144 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 36, fallback 2, missing 2, open max 32 ms, last 21 ms
free heap: 110272
[03:56:41 + 26.499s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 36, fallback 2, missing 2, open max 32 ms, last 21 ms
[03:56:41 + 26.505s] == sr say systems types cycles systems types cycles systems types cycles   (reply after 0.018s)
queued 62 characters; sr status shows the timing when it is done
[03:56:48 + 32.994s] (waited: idle after 6.274 s, speaker released after 6.471 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1169, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 6, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 6265 ms played, 98315 subsamples, 6144 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 45, fallback 2, missing 2, open max 32 ms, last 22 ms
free heap: 110288
[03:56:48 + 32.995s] == sr voice status   (reply after 0.007s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 45, fallback 2, missing 2, open max 32 ms, last 22 ms
[03:56:48 + 33.002s] == sr say systems types cycles systems types cycles systems types cycles   (reply after 0.018s)
queued 62 characters; sr status shows the timing when it is done
[03:56:54 + 39.497s] (waited: idle after 6.272 s, speaker released after 6.477 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1182, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 7, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 6265 ms played, 98315 subsamples, 6144 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 54, fallback 2, missing 2, open max 32 ms, last 22 ms
free heap: 110272
[03:56:54 + 39.498s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 54, fallback 2, missing 2, open max 32 ms, last 22 ms
[03:56:54 + 39.503s] == sr say systems types cycles systems types cycles systems types cycles   (reply after 0.018s)
queued 62 characters; sr status shows the timing when it is done
[03:57:01 + 45.987s] (waited: idle after 6.273 s, speaker released after 6.465 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1195, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 8, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 6265 ms played, 98315 subsamples, 6144 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 63, fallback 2, missing 2, open max 32 ms, last 21 ms
free heap: 110272
[03:57:01 + 45.988s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 63, fallback 2, missing 2, open max 32 ms, last 21 ms
[03:57:01 + 45.993s] == sr say systems types cycles systems types cycles systems types cycles   (reply after 0.018s)
queued 62 characters; sr status shows the timing when it is done
[03:57:07 + 52.499s] (waited: idle after 6.281 s, speaker released after 6.487 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1208, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 9, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 6265 ms played, 98315 subsamples, 6144 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 72, fallback 2, missing 2, open max 32 ms, last 24 ms
free heap: 110288
[03:57:07 + 52.499s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 72, fallback 2, missing 2, open max 32 ms, last 24 ms
```

Underruns stayed at the start value of 0 after every one of the eight runs. Clips went from 0 to 72, and the nominal time matched the prediction every time. The open max is 32 ms, and the latest open after each run was 21 to 24 ms.

Why the opens take 11 to 39 ms and not the roughly 10 ms that 30 to 65 entries would suggest: each open now scans two folders of about 65 entries. The first is /ext/sr/voice, which holds the 64 buckets and voice.txt; the second is the bucket.

#### Verification 3: sr_drive.py, both sessions

```
[03:57:17 + 0.427s] == sr status   (reply after 0.008s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1228, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 9, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 6265 ms played, 98315 subsamples, 6144 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 72, fallback 2, missing 2, open max 32 ms, last 24 ms
free heap: 110456
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
sr_drive exit 0
[03:57:53 + 4.239s] (waited: idle after 3.607 s, speaker released after 3.811 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1358, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 29, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 4291 ms played, 67546 subsamples, 4221 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 109, fallback 2, missing 2, open max 32 ms, last 14 ms
free heap: 110392
[03:57:53 + 4.240s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 109, fallback 2, missing 2, open max 32 ms, last 14 ms
[03:57:53 + 4.245s] == storage read /ext/sr/missing.txt   (reply after 0.017s)
Size: 12
home
screen
[03:57:53 + 4.263s] == sr screen   (reply after 0.006s)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
[03:57:53 + 4.269s] == loader info   (reply after 0.053s)
No application is running
```

The result: 0 failures in 17 steps. Underruns 0, unchanged. Clips +37, from 72 to 109, and fallback +0. missing.txt still holds only home and screen, from before the sync.

#### Verification 4: 30 words and 100 words

The prediction for the 100 words, from the local clips: 100 words and 830,099 samples.

```
input 152 characters: Saved 433.925 MHz, 868.355 MHz, 345.955 MHz, 467.75 MHz, 779.85 MHz, 928.35 MHz, 434.42 MHz, 322.61 MHz, 856.47 MHz, 925.33 MHz, 377.29 MHz, 698.54 MHz.
words 100, clips 100, fallback 0 []
nominal without fallback words: 830099 samples, 51881 ms
```

A queue item holds 159 characters, so 100 plain words cannot be sent in one `sr say`. The 100 are twelve frequencies, whose numbers the pronunciation layer reads out word by word. Every word is in the vocabulary.

```
[03:58:01 + 0.427s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 109, fallback 2, missing 2, open max 32 ms, last 14 ms
[03:58:01 + 0.434s] == sr say Open the saved file to read the new signal from the remote and save it as the key for the next time you go to the menu with your card.   (reply after 0.026s)
queued 134 characters; sr status shows the timing when it is done
[03:58:15 + 14.231s] (waited: idle after 13.564 s, speaker released after 13.771 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1401, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 30, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 13550 ms played, 215179 subsamples, 13448 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 139, fallback 2, missing 2, open max 34 ms, last 11 ms
free heap: 110104
[03:58:15 + 14.232s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 139, fallback 2, missing 2, open max 34 ms, last 11 ms
[03:58:15 + 14.237s] == sr say Saved 433.925 MHz, 868.355 MHz, 345.955 MHz, 467.75 MHz, 779.85 MHz, 928.35 MHz, 434.42 MHz, 322.61 MHz, 856.47 MHz, 925.33 MHz, 377.29 MHz, 698.54 MHz.   (reply after 0.027s)
queued 152 characters; sr status shows the timing when it is done
[03:59:07 + 66.487s] (waited: idle after 52.022 s, speaker released after 52.222 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1506, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 31, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 51976 ms played, 830099 subsamples, 51881 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 239, fallback 2, missing 2, open max 39 ms, last 19 ms
free heap: 109912
[03:59:07 + 66.487s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 239, fallback 2, missing 2, open max 39 ms, last 19 ms
```

The result:
- 30 words: clips +30 and underruns 0. The nominal time was 13,448 ms, as predicted.
- 100 words: clips +100 and underruns 0. 830,099 subsamples, as predicted, and 51,881 ms nominal against 51,976 ms played.
- Open max 39 ms.

#### Verification 5: Don't do it, it's fine.

The first say:

```
[03:59:23 + 0.427s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 239, fallback 2, missing 2, open max 39 ms, last 19 ms
[03:59:23 + 0.434s] == sr say Don't do it, it's fine.   (reply after 0.014s)
queued 23 characters; sr status shows the timing when it is done
[03:59:25 + 3.128s] (waited: idle after 2.477 s, speaker released after 2.681 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1542, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 32, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 2413 ms played, 55821 subsamples, 2091 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 243, fallback 3, missing 3, open max 39 ms, last 29 ms
free heap: 110296
[03:59:25 + 3.129s] == sr voice status   (reply after 0.007s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 243, fallback 3, missing 3, open max 39 ms, last 29 ms
[03:59:25 + 3.136s] == storage read /ext/sr/missing.txt   (reply after 0.014s)
Size: 17
home
screen
fine
```

The result:
- Clips +4: dont, do, it and its all played from clips.
- Fallback +1 and missing +1, for "fine". "fine" is in no firmware string and no bubble text, so it is not in the vocabulary, and the brief's fallback +0 could not hold.

I ran the missing round trip and said the sentence again:

```
voice: silenced for the transfer
>100%, chunk  1 of  1 @ 1.04 kb/s
pulled 3 missing words from the device
voice: restored
119 words, 1 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
made 1 clips, 0 failed, 1 s; vocabulary 2892 words in /Users/robin/Downloads/flipper-access/voice
voice: silenced for the transfer
<100%, chunk  1 of  1 @ 103.77 kb/s
<100%, chunk  1 of  1 @ 1.71 kb/s
sync: 1 sent, 2891 skipped, 0 missing, 0 failed, 0 s
voice: restored
(time: 2.991 s, exit 0)
```
[03:59:37 + 0.427s] == storage stat /ext/sr/missing.txt   (reply after 0.016s)
Storage error: file/dir not exist
[03:59:37 + 0.443s] == sr say Don't do it, it's fine.   (reply after 0.016s)
queued 23 characters; sr status shows the timing when it is done
[03:59:40 + 2.848s] (waited: idle after 2.182 s, speaker released after 2.388 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1571, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 33, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 2165 ms played, 32960 subsamples, 2060 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 248, fallback 3, missing 3, open max 39 ms, last 28 ms
free heap: 110216
[03:59:40 + 2.848s] == sr voice status   (reply after 0.005s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 248, fallback 3, missing 3, open max 39 ms, last 28 ms
```

The second say: clips +5, fallback +0. 32,960 subsamples, as predicted, with "fine" as a clip. Underruns 0. The pull also took home and screen from the list. They were already clips, so it made only one new clip.

#### Verification 6: voice off across a reboot

```
[03:59:47 + 0.428s] == sr voice off   (reply after 0.083s)
voice off: SAM speaks everything
[03:59:47 + 0.512s] == sr voice status   (reply after 0.005s)
voice: off, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 248, fallback 3, missing 3, open max 39 ms, last 28 ms
[03:59:47 + 0.518s] == power reboot   (sent; the port goes away)
port gone seen: yes, present: yes, after 3 s at 03:59:50
[04:00:07 + 0.428s] == sr screen   (reply after 0.007s)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
[04:00:07 + 0.435s] == uptime   (reply after 0.054s)
Uptime: 0h0m19s
[04:00:07 + 0.490s] == sr voice status   (reply after 0.007s)
voice: off, vocabulary no, clips 0, fallback 0, missing 0, open max 0 ms, last 0 ms
[04:00:07 + 0.497s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 35, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1241 ms played, 50480 subsamples, 821 ms nominal, worker stack free 2372
voice: off, vocabulary no, clips 0, fallback 0, missing 0, open max 0 ms, last 0 ms
free heap: 110432
[04:00:07 + 0.506s] == sr voice on   (reply after 0.089s)
voice on
[04:00:07 + 0.595s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary no, clips 0, fallback 0, missing 0, open max 0 ms, last 0 ms
```

The result:
- The off setting survived the reboot. `sr screen`, read first, shows the desktop.
- `sr voice status` says off.
- "vocabulary no" is by design. The vocabulary is looked for only at the first utterance that uses the voice, and the boot announcement took the SAM path.
- `sr voice on` answered "voice on". The next utterance, in verification 7, found the vocabulary.

#### Verification 7: free before and after twenty utterances, twice

Round 1: the first two readings and the last three, verbatim.

```
[04:00:18 + 0.428s] == free   (reply after 0.006s)
Free heap size: 110632
Total heap size: 185904
Minimum heap size: 108424
Maximum heap block: 110304
Pool free: 876
Maximum pool block: 672
[04:00:18 + 0.435s] == sr status   (reply after 0.008s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 56, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1241 ms played, 50480 subsamples, 821 ms nominal, worker stack free 2372
voice: on, vocabulary no, clips 0, fallback 0, missing 0, open max 0 ms, last 0 ms
free heap: 110496
[04:00:18 + 0.444s] == sr say Settings. Sub-GHz.   (reply after 0.013s)
...
free heap: 110160
[04:01:15 + 57.839s] == free   (reply after 0.006s)
Free heap size: 110256
Total heap size: 185904
Minimum heap size: 108424
Maximum heap block: 110080
Pool free: 876
Maximum pool block: 672
[04:01:15 + 57.845s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 171, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 21, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 2734 ms played, 43172 subsamples, 2698 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 92, fallback 0, missing 0, open max 36 ms, last 28 ms
free heap: 110160
[04:01:25 + 67.859s] == free   (reply after 0.006s)
Free heap size: 110256
Total heap size: 185904
Minimum heap size: 108424
Maximum heap block: 110080
Pool free: 876
Maximum pool block: 672
```

Round 2 and a later idle reading:

```
[04:01:39 + 0.428s] == free   (reply after 0.006s)
Free heap size: 110520
Minimum heap size: 108424
Maximum heap block: 109728
[04:02:37 + 58.145s] == free   (reply after 0.006s)
Free heap size: 110120
Minimum heap size: 108392
Maximum heap block: 109728
[04:02:52 + 73.162s] == free   (reply after 0.005s)
Free heap size: 110128
Minimum heap size: 108392
Maximum heap block: 109728
[04:02:52 + 73.168s] == sr status   (reply after 0.008s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 364, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 41, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 2734 ms played, 43172 subsamples, 2698 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 184, fallback 0, missing 0, open max 38 ms, last 28 ms
free heap: 109976
[04:03:05 + 0.427s] == free   (reply after 0.006s)
Free heap size: 110576
Minimum heap size: 108392
Maximum heap block: 110384
[04:03:25 + 20.444s] == free   (reply after 0.006s)
Free heap size: 110576
Minimum heap size: 108392
Maximum heap block: 110384
```

Underruns stayed 0 through all 40 utterances. Open max 38 ms.

Free heap:
- Before round 1, right after the reboot: 110,632.
- After round 1: 110,256.
- Before round 2: 110,520.
- After round 2: 110,120 to 110,128.
- In a new console session afterwards: 110,576.
- The minimum was 108,392 to 108,424, and the largest block 109,728 to 110,384.

The dip of about 400 bytes lasts while a console session runs and is back in the next session, so it is not the reader. It may be the console's command history. There is no leak.

#### Final device state

```
[04:05:47 + 0.428s] == uptime   (reply after 0.055s)
Uptime: 0h5m59s
[04:05:48 + 0.483s] == sr screen   (reply after 0.006s)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
[04:05:48 + 0.490s] == sr status   (reply after 0.035s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 716, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 41, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 2734 ms played, 43172 subsamples, 2698 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 184, fallback 0, missing 0, open max 38 ms, last 28 ms
free heap: 110416
[04:05:48 + 0.525s] == loader info   (reply after 0.054s)
No application is running
[04:05:48 + 0.580s] == storage stat /ext/sr/missing.txt   (reply after 0.015s)
Storage error: file/dir not exist
[04:05:48 + 0.596s] == free   (reply after 0.006s)
Free heap size: 110360
Total heap size: 185904
Minimum heap size: 108344
Maximum heap block: 110048
Pool free: 876
Maximum pool block: 672
```

The device is:
- on the home screen,
- with the reader on and speech idle,
- with the speaker released and the voice on, and the vocabulary found,
- with 0 underruns since the boot,
- with no missing.txt and no app running.

I did not send `loader close`.

### D. Documents

- **README.md, Recorded voice:**
  - It gives the hashed layout and why: about 0.17 ms per directory entry on this exFAT card.
  - It gives the 8192-byte ring and its 82 ms halves.
  - It says `sr voice status` shows the first 63 characters of the settings line, and now the open times.
  - The build sentence now reads "limited by `say` itself, not by CPU count".
  - It now covers apostrophe names, bubble texts, `--remove-legacy`, and that `--sync-all` needs `--sync`.
  - The underrun limit is gone. New known limits: shared clips for words that differ only by an apostrophe, and pulled words lose their apostrophe.
- **README.md, other sections:**
  - A device-state note: the ring holds 4 KB more heap. Idle free heap went from 114,552 to 110,520, measured. So Sub-GHz read is expected to run out of memory, and NFC read to leave about 20 KB; neither was measured.
  - The flash line now gives 871,872 bytes with 8,768 spare, against 869,756 and 10,884 before the voice.
- **Spec status block:** it lists the as-built deviations again with the hashed layout and its reason, the ring, the open timing, the 63-character settings line and the apostrophe names. The underrun defect is now recorded as fixed, with the numbers.
- **Roadmap:**
  - Item 1 has measured numbers: flash +2,116 bytes against the spec's baseline at 54794522b, and heap 4,032 bytes for the ring. The about 700 bytes of voice state is marked as an estimate from Task 2.
  - Item 4 no longer trims the ring, and says why.
- **Measurements file:**
  - A header says which parts are the first rollout.
  - The speech-server sentence is corrected.
  - The "adds about 8 ms" claim is gone. The file now says that an underrun replays old audio, and that opens under 41 ms already underran ("types", about 38 ms, three times out of three).
  - It records that the old settings line was cut at 63 characters.
  - A "Fix round 1" section holds all the numbers above.

### Deviations

1. Check 5's "fallback +0" could not hold on the first say, because "fine" was not in the vocabulary. I recorded the +1, ran the missing round trip, and got fallback +0 on the second say.
2. The 100-word announcement uses numbers read as words. A queue item holds 159 characters, so 100 plain words cannot be sent in one `sr say`.
3. The local layout stays `voice/<first letter>/<word>.raw`, and only the card uses the hashed folders. So nothing local had to be moved or rebuilt, and the build made only the 64 changed clips.
4. Four existing clips were remade because their spoken text now carries the apostrophe: cant, dont, flippers, its. The brief expected new words only.
5. Between the flash and the resend, the boot announcement fell back to SAM and logged home and screen. The pull in check 5 cleared them.
6. My phase B2 report said each underrun cost about 8 ms of audio. That was an inference from played-minus-nominal times, and the review rejected it. I withdraw it: an underrun replays old audio.

### Concerns

1. **Opens take 11 to 39 ms, not the roughly 10 ms the entry count suggests.** Each open scans /ext/sr/voice, with 65 entries, and then the bucket. With 82 ms halves there is room to spare. With the old 41 ms halves, 39 ms would underrun, so the ring must stay at 8192; the roadmap now says so.
   - Two ways to shorten opens further, not built: fewer buckets, which shortens the first scan but lengthens the second, or keeping the voice folder open.
2. **Heap: 4 KB less.** Sub-GHz read with the reader on, which left about 2 KB before, is now expected to fail. I did not test it, because it could crash the device while nobody is watching. The README says so.
3. **Apostrophe collisions.** "ill" now plays the clip recorded as "i'll". Future strings could collide the same way: "well" and "we'll", "were" and "we're". A missing word the device logs has already lost its apostrophe, so `--pull-missing` records "wont" as it is spelled, not as "won't". Both are in the README.
4. **Running `--remove-legacy` again after a sync** would find nothing to remove, but it clears synced.json, so the next sync resends everything. That is harmless but slow, about 6.5 minutes. The README says it is needed once.
