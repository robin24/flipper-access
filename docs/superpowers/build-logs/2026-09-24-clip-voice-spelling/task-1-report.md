# Task 1 report: spelled fallback and letter names

Status: DONE_WITH_CONCERNS

Everything in the brief is implemented, built, committed, flashed, synced and verified on the device. Every expected number in step 4 came out exactly. There are two deviations from the brief's verbatim code and values, each for a ruling:

1. Letter clips count in the "clips" counter. I added one line, because the brief's code could not produce its own expected "clips +3" and "clips +5".
2. The letter A is recorded from "a", not from "ay". The brief's `ay	ay` made the letter A's clip byte-identical to the letter I's clip, because `say` reads "ay" as "aye", the same as "eye". Evidence below.

## Commits

Firmware repo, branch screen-reader, parent 6282541b6:
- d5b77c219dd607bb78ad6f1b6ca62a25ac64dba7 "screen reader: missing words are spelled with the letter clips"
  - Files: applications/services/screen_reader/speech_voice.h, speech_voice.c, speech.c and speech.h.
  - speech.h is not in the brief's file list. It holds SpeechVoiceStats, whose comment the brief asks to update.

Project repo, branch main, parent abbf898:
- 5ccbd2f1c2c5779252d72fee4c604563c30adaf1 "voice_build: letters by their names; host tests: letter clips"
  - Files: tools/voice_names.txt, tools/voice_build.py, tests/host/test_speech_voice.c.
- 88ea67eac2d04e6deae90c21b66edfa7ab9125a4 "docs: missing words are spelled with the recorded letters"
  - File: README.md.
- d0c3676468d71e10d0f51488e3f602a1640b6e42 "voice_names: the letter A from a, because say reads ay as aye"
  - Files: tools/voice_names.txt, README.md. This is deviation 2.

About the commits:
- Every commit used `git add <files>` and then `git commit -m ... -- <the same files>`.
- Every message ends with a blank line and the Co-Authored-By trailer.
- Nothing was pushed.
- applications/external was not touched. It is still the only dirty entry in the firmware repo, and it is why info device reports firmware.commit.dirty true, as in the last round.
- The project repo is clean.
- The voice/ folder was updated in place by the generator. It now holds 2,899 words, and manifest.json and synced.json agree.

## Deviations, for a ruling

### 1. Letter clips count as clips

In speech_spell_word, one line was added before `continue`, where a letter clip has played:

```c
        if(speech_voice_path(name, speech->path, sizeof(speech->path)) > 0 &&
           speech_play_clip(speech, speech->path)) {
            speech->voice.clip_words++;
            continue;
        }
```

- The reason: step 4 expects `sr say u2f` to give clips +3 ("you, two, eff: the clips u, 2, f") and `sr say zzyzx` to give clips +5.
- The verbatim code never increments clip_words for a letter, so both would read +0.
- Without the counter, the status cannot show whether a spelled word used the letter clips or SAM.
- The doc comments on clip_words in speech_voice.h and speech.h now say "words and spelled letters spoken from a clip since boot". The README's status list matches.
- A letter spoken by SAM, because its clip is missing, counts nothing. The word was already counted as fallback.
- To revert: remove the line and the comment wording, then flash again. No sync is needed.

### 2. The letter A is recorded from "a"

The brief's `ay	ay` was applied first, synced and verified. Then the clips were compared on the Mac:

- After the rebuild, voice/a/ay.raw was byte-identical to voice/i/i.raw (the letter I, spoken "eye"). Both had md5 bd9731229a6eb485ba117bf59c6d8dd0.
- It was also byte-identical to fresh renders, with the same settings, of "aye", "eye" and "Ay".
- `say` reads "ay" as "aye". So a spelled A sounded exactly like I.
- That clip is also the expander's word for every upper case A: the keyboard's letter a, "A2" in a UID, and the single character "A". All of them would have said "eye".
- A lone lower case "a" renders byte-identical to "eh" and to "a.".
- Its formant track is the letter-name vowel of "eight" and "bait", with a high F2 of about 2,250 to 2,500 Hz. It is not the "eye" glide, which rises from an F2 of about 1,300 Hz with an open F1 of about 950 Hz. It is not "uh" either (F2 about 1,250 Hz).
- `say` given the bare letter "a" produces exactly this audio. For 23 of the 25 letters b to z, the bare letter renders byte-identical to the clip made from the brief's name for it. So the bare letter is how Samantha names a letter.

The change is one value: `ay	a`. The clip "ay" is now byte-identical to the clip "a" (md5 860afb20b4ffcfb689f380c3a151cc7a). It was remade and synced with `--extract --sync`, and checked on the card (below).

The README's fallback paragraph gained one sentence that says why.

The article "a" now sounds the same as the letter A. That is Samantha's reading of a lone "a". Before this round it was "capital A": the old a.raw and ay.raw had the same hash, 0.788 s long.

To revert: set the line back to `ay	ay` and run `--extract --sync`, which takes seconds.

### Smaller deviations

- SPEECH_VOICE_LETTER_GAP_MS sits after a blank line, with a one-line doc comment. That keeps clang-format from re-aligning the existing ten-line macro block.
- Doc comments now match the new behaviour:
  - speech_sam_word: "SAM speaks a word ...: the last resort for a spelled character whose clip is missing too".
  - speech_speak_words: "spelled with the letter clips when not".
  - The speech_voice.h file header.
  - speech_spell_word keeps the brief's comment, plus one sentence about the counter.
- The comment on fallback_words changed in both places it lives: SpeechVoiceState in speech_voice.h and SpeechVoiceStats in speech.h.
- README: besides the fallback paragraph, I corrected two more passages that said "spoken by SAM":
  - The `sr voice status` count list.
  - Two known limits: words over 16 letters and letter-digit tokens are now spelled. `md5` is "em dee five".
- voice_build.py:
  - spoken_text got a docstring.
  - The single-letter rule is `return word`, with a comment on why. The brief names it, so it stays, even though it now matches the fall-through.
  - The module docstring mentions voice_names.txt.
- The host test has the brief's eight named checks, plus a sweep of all 256 character values against the stated rule. That is 263 checks.

## Build and host runner

Host runner, `TMPDIR=<scratchpad>/sp1 tools/run_host_tests.sh`, on the committed state:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 115 checks, 0 failures
speech PCM: 700 checks, 0 failures
speech voice: 4433 checks, 0 failures
exit 0
```

- Before the change, the speech voice block had 4,170 checks. Now it has 4,433: the 8 named checks plus 255 swept values.
- A mutation check compiled the test against altered copies of speech_voice.c:
  - 'a' giving "a" was caught (1 failure).
  - 'A' accepted was caught (2 failures).
  - Widening b..z to a..z is equivalent, because the 'a' branch returns first, so there was nothing to catch.

`./fbt`: exit 0. The only matches for error, warning or API version were:

```
fbt: warning: Failed parsing manifest '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui'. Must match regex 're.compile('^[a-z0-9_]+$')'
fbt: warning: Failed parsing manifest '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/mtp/application.fam' : Invalid appid '.f0_mtp'. Must match regex 're.compile('^[a-z0-9_]+$')'
API version 87.1 is up to date
```

- `./fbt lint`: exit 0. The log holds only the same two manifest warnings and the lint.py command line.
- The toolchain's clang-format 18.1.8 reports all four touched files clean.
- No touched line is longer than 99 columns.

`tools/flash_headroom.sh`:

```
firmware.bin 872048 bytes, limit 880640, spare 8592 bytes
```

## Device

### Before the flash

This was read-only, at the start:

```
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 62192, dropped: 0, announcements: 203, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 238, aborted 88, dropped 1, underruns 0, queue dropped 0
last utterance: 3473 ms played, 53839 subsamples, 3364 ms nominal, worker stack free 2372
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 579, fallback 23, missing 8, open max 38 ms, last 27 ms
free heap: 98008
== storage read /ext/sr/missing.txt
Size: 57
rickroll
nfcv
u2f
notifications
packs
fuzzer
tesla
stock
== free
Free heap size: 97984
Total heap size: 185904
Minimum heap size: 17384
Maximum heap block: 60064
Pool free: 876
Maximum pool block: 672
```

### Flash

- `./fbt flash_usb` ran from 12:05:18 to 12:05:53, exit 0. The log ends with the upload of firmware.dfu (107 chunks), update.fuf and updater.bin, then "Closing current app, if any".
- The port went away at once and came back 17 s later, at 12:06:21.
- The first command afterwards was `sr screen`. There was no crash popup:

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as:
```

The empty "reads as" is the desktop's usual reading. The Task 2 report of the last round shows the same.

`info device`, in full:

```
== info device
format.major                  : 3
format.minor                  : 3
hardware.model                : Flipper Zero
hardware.uid                  : redacted
hardware.otp.ver              : 2
hardware.timestamp            : 1720072856
hardware.ver                  : 12
hardware.target               : 7
hardware.body                 : 9
hardware.connect              : 6
hardware.display              : 2
hardware.color                : 2
hardware.region.builtin       : 4
hardware.region.provisioned   : DE
hardware.name                 : R0skie
firmware.commit.hash          : d5b77c21
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
radio.alive                   : true
radio.mode                    : Stack
radio.fus.major               : 1
radio.fus.minor               : 2
radio.fus.sub                 : 0
radio.fus.sram2b              : 16K
radio.fus.sram2a              : 0K
radio.fus.flash               : 24K
radio.stack.type              : 3
radio.stack.major             : 1
radio.stack.minor             : 20
radio.stack.sub               : 0
radio.stack.branch            : 0
radio.stack.release           : 2
radio.stack.sram2b            : 19K
radio.stack.sram2a            : 14K
radio.stack.sram1             : 0K
radio.stack.flash             : 116K
radio.ble.mac                 : redacted
enclave.keys.valid            : 10
enclave.valid                 : true
system.debug                  : 0
system.lock                   : 0
system.orient                 : 0
system.sleep.legacy           : 0
system.stealth                : 1
system.heap.track             : 0
system.boot                   : 0
system.locale.time            : 0
system.locale.date            : 0
system.locale.unit            : 0
system.log.level              : 1
protobuf.version.major        : 0
protobuf.version.minor        : 25
```

Right after boot, before the sync:

```
[12:07:09 + 0.431s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 99, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1105 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2628
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0, open max 26 ms, last 26 ms
free heap: 110416
[12:07:09 + 0.449s] == storage read /ext/sr/missing.txt   (reply after 0.018s)
Size: 57
rickroll
nfcv
u2f
notifications
packs
fuzzer
tesla
stock
[12:07:09 + 0.455s] == free   (reply after 0.006s)
Free heap size: 110416
Total heap size: 185904
Minimum heap size: 108400
Maximum heap block: 109664
Pool free: 876
Maximum pool block: 672
```

### Sync: `.venv/bin/python tools/voice_build.py --extract --pull-missing --sync 2>&1 | tail -8`

It ran from 12:07:17 to 12:07:40 and exited 0. The tail, as printed (the transfer progress uses carriage returns):

```
<100%, chunk  1 of  1 @ 88.19 kb/s
< 90%, chunk  1 of  2 @ 112.47 kb/s<100%, chunk  2 of  2 @ 86.36 kb/s
<100%, chunk  1 of  1 @ 103.39 kb/s
<100%, chunk  1 of  1 @ 96.85 kb/s
<100%, chunk  1 of  1 @ 89.27 kb/s
<100%, chunk  1 of  1 @ 1.65 kb/s
sync: 34 sent, 2865 skipped, 0 missing, 0 failed, 5 s
voice: restored
```

The same run in full, without the 43 transfer progress lines:

```
extract: 6184 distinct strings from the firmware sources, 71 bubble texts
extract: 2880 words; longest: animationmanager animationstorage backlightenforce checksdkfeatures configchangeable defaulttextclear desktopscenelock freecreatedelete getbatterycharge hoppingthreshold
extract: 10 with an apostrophe: can't doesn't don't flipper's i'll i'm isn't it's who's you're
voice: silenced for the transfer
skipped 1 words that cannot be clips
pulled 7 missing words from the device
voice: restored
2895 words, 34 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
made 34 clips, 0 failed, 16 s; vocabulary 2899 words in /Users/robin/Downloads/flipper-access/voice
voice: silenced for the transfer
sync: 34 sent, 2865 skipped, 0 missing, 0 failed, 5 s
voice: restored
```

What the run did:
- It made 34 clips: the 27 letter clips (a to z and ay) and the 7 pulled words.
- u2f was dropped by the filter ("skipped 1 words that cannot be clips").
- 34 clips were sent in 5 s.
- Both device steps printed the guard lines.
- The extraction matches the last round's exactly: 6,184 strings and 71 bubble texts. So the new comments added no words.
- manifest.json and synced.json both hold 2,899 words, with 0 unsynced.
- missing.txt was removed from the card by the pull.

Letter clip lengths before this round and now, from the local files: name, spoken text, seconds before, seconds now. Only the ay row changed again later, as noted on it.

```
 a a            0.788 -> 0.336
 b bee          0.792 -> 0.294
 c see          0.847 -> 0.406
 d dee          0.779 -> 0.302
 e ee           0.735 -> 0.396
 f eff          0.802 -> 0.328
 g gee          0.803 -> 0.345
 h aitch        0.903 -> 0.441
 i eye          0.820 -> 0.364
 j jay          0.858 -> 0.401
 k kay          0.886 -> 0.409
 l ell          0.834 -> 0.362
 m em           0.789 -> 0.317
 n en           0.788 -> 0.317
 o oh           0.805 -> 0.344
 p pee          0.818 -> 0.339
 q cue          0.794 -> 0.330
 r are          0.795 -> 0.323
 s ess          0.839 -> 0.366
 t tee          0.834 -> 0.363
 u you          0.736 -> 0.315
 v vee          0.770 -> 0.342
 w double you   0.990 -> 0.575
 x ex           0.913 -> 0.440
 y why          0.908 -> 0.439
 z zee          0.852 -> 0.413
ay a            0.788 -> 0.336  (0.364 s, the same audio as i, after this run; 0.336 s after the fix commit)
 0 (digit word) 0.465 -> 0.465
 1 (digit word) 0.411 -> 0.411
 2 (digit word) 0.366 -> 0.366
 3 (digit word) 0.413 -> 0.413
 4 (digit word) 0.374 -> 0.374
 5 (digit word) 0.383 -> 0.383
 6 (digit word) 0.523 -> 0.523
 7 (digit word) 0.471 -> 0.471
 8 (digit word) 0.354 -> 0.354
 9 (digit word) 0.460 -> 0.460
pulled words: rickroll 0.479, nfcv 0.871, notifications 1.078, packs 0.532, fuzzer 0.453, tesla 0.528, stock 0.531
```

- Every letter is about half as long as before: 0.29 to 0.58 s, where it was 0.74 to 0.99 s. That fits "capital" being gone.
- The digits are unchanged.
- A spelled letter averages 0.37 s plus the 60 ms gap, so about 0.43 s per letter.

### Verification (step 4)

Predictions came first. Each is the sum of the local clip sizes plus 640 samples for each 40 ms word gap and 960 samples for each 60 ms letter gap, with nothing after the last item:

```
NFC GPIO LCD: 61965 subsamples, 3872 ms nominal
u2f: 18062 subsamples, 1128 ms nominal
zzyzx: 37715 subsamples, 2357 ms nominal
Tesla stock fuzzer: 25484 subsamples, 1592 ms nominal
```

The driver is a scratchpad script (scratchpad/sr_seq.py). It opens one console session and prints every reply verbatim, stamped with the wall clock and the seconds since the session began. "@idle" polls `sr status` quietly every 50 ms until speech is idle, nothing is queued and the speaker is released, then prints both times and the last status. "@sleep" waits.

```
[12:08:49 + 0.428s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0, open max 26 ms, last 26 ms
[12:08:49 + 0.437s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 298, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1105 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2628
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0, open max 26 ms, last 26 ms
free heap: 110312
[12:08:49 + 0.444s] == free   (reply after 0.007s)
Free heap size: 110360
Total heap size: 185904
Minimum heap size: 105216
Maximum heap block: 110248
Pool free: 876
Maximum pool block: 672
[12:08:49 + 0.458s] == sr say NFC GPIO LCD   (reply after 0.014s)
queued 12 characters; sr status shows the timing when it is done
[12:08:53 + 4.643s] (waited: idle after 3.978 s, speaker released after 4.185 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 307, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 3973 ms played, 61965 subsamples, 3872 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 12, fallback 0, missing 0, open max 33 ms, last 22 ms
free heap: 110248
[12:08:53 + 4.649s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 12, fallback 0, missing 0, open max 33 ms, last 22 ms
[12:08:53 + 4.663s] == sr say u2f   (reply after 0.014s)
queued 3 characters; sr status shows the timing when it is done
[12:08:55 + 6.113s] (waited: idle after 1.263 s, speaker released after 1.449 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 310, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 3, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1208 ms played, 18062 subsamples, 1128 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 15, fallback 1, missing 1, open max 38 ms, last 23 ms
free heap: 110192
[12:08:55 + 6.120s] == sr voice status   (reply after 0.007s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 15, fallback 1, missing 1, open max 38 ms, last 23 ms
[12:08:55 + 6.135s] == sr say zzyzx   (reply after 0.015s)
queued 5 characters; sr status shows the timing when it is done
[12:08:57 + 8.841s] (waited: idle after 2.456 s, speaker released after 2.705 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 315, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 4, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 2436 ms played, 37715 subsamples, 2357 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 20, fallback 2, missing 2, open max 38 ms, last 23 ms
free heap: 110120
[12:08:57 + 8.847s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 20, fallback 2, missing 2, open max 38 ms, last 23 ms
[12:08:57 + 8.863s] == sr say Tesla stock fuzzer   (reply after 0.016s)
queued 18 characters; sr status shows the timing when it is done
[12:08:59 + 10.772s] (waited: idle after 1.711 s, speaker released after 1.909 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 319, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 5, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1674 ms played, 25484 subsamples, 1592 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 23, fallback 2, missing 2, open max 38 ms, last 22 ms
free heap: 110064
[12:08:59 + 10.778s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 23, fallback 2, missing 2, open max 38 ms, last 22 ms
[12:08:59 + 10.784s] == free   (reply after 0.006s)
Free heap size: 110176
Total heap size: 185904
Minimum heap size: 105216
Maximum heap block: 110104
Pool free: 876
Maximum pool block: 672
```

Results:
- `sr say NFC GPIO LCD`:
  - Clips went from 2 to 12 (+10). Fallback +0.
  - 61,965 subsamples and 3,872 ms nominal, exactly as predicted.
- `sr say u2f`:
  - Clips went from 12 to 15 (+3). Fallback +1, missing +1.
  - 18,062 subsamples, exactly as predicted. That is the u, 2 and f clips with two 60 ms gaps.
- `sr say zzyzx`:
  - Clips went from 15 to 20 (+5). Fallback +1, missing +1.
  - 37,715 subsamples, as predicted.
- `sr say Tesla stock fuzzer`:
  - Clips went from 20 to 23 (+3). Fallback +0.
  - 25,484 subsamples, as predicted. These are the three words pulled and synced a minute earlier.
- Underruns stayed at 0 throughout. The longest clip open was 38 ms.
- The worker stack had 2,628 bytes free at boot and 2,616 after the spelled words.
- Free heap was 110,360 bytes before and 110,176 after. The sr_drive session below shows it back at 110,504, so this was not a leak.

### sr_drive, one scripted session

```
[12:09:22 + 0.431s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 364, dropped: 0, announcements: 1, suppressed: 1
speech: idle, queued 0, speaker held: no, utterances 5, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1674 ms played, 25484 subsamples, 1592 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 23, fallback 2, missing 2, open max 38 ms, last 22 ms
free heap: 110408
[12:09:22 + 0.439s] == free   (reply after 0.007s)
Free heap size: 110480
Total heap size: 185904
Minimum heap size: 105216
Maximum heap block: 109944
Pool free: 876
Maximum pool block: 672
== tools/sr_drive.py (12:09:22)
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
[12:09:55 + 1.776s] (waited: idle after 1.152 s, speaker released after 1.354 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 489, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 25, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 1668 ms played, 25784 subsamples, 1611 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 56, fallback 2, missing 2, open max 38 ms, last 17 ms
free heap: 110424
[12:09:55 + 1.811s] == sr status   (reply after 0.035s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 489, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 25, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 1668 ms played, 25784 subsamples, 1611 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 56, fallback 2, missing 2, open max 38 ms, last 17 ms
free heap: 110440
[12:09:55 + 1.817s] == free   (reply after 0.006s)
Free heap size: 110504
Total heap size: 185904
Minimum heap size: 80512
Maximum heap block: 101752
Pool free: 876
Maximum pool block: 672
[12:09:55 + 1.824s] == sr screen   (reply after 0.007s)
records: 2, content layer: desktop
desktop      x=  5 y= 35 secondary  "swim all day"
status-right x=103 y=  9 battery    inverted "100"
reads as: swim all day
```

Results:
- 0 failures, exit 0.
- Underruns were 0 before and 0 after.
- The whole session spoke from clips: +33 clips and +0 fallback.
- Free heap was 110,480 bytes before and 110,504 after. The low watermark was 80,512 bytes, during the text2sam keyboard session.

### Extra: a stop in the middle of a spelled word

This was not asked for. It checks that the new loop ends promptly. "zzyzx" was already logged this boot, so it adds no missing entry.

```
[12:10:19 + 0.426s] == sr voice status   (reply after 0.007s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 56, fallback 2, missing 2, open max 38 ms, last 17 ms
[12:10:19 + 0.440s] == sr say zzyzx zzyzx zzyzx   (reply after 0.013s)
queued 17 characters; sr status shows the timing when it is done
[12:10:21 + 1.942s] (slept 1.5 s)
[12:10:21 + 1.948s] == sr stop   (reply after 0.006s)
stopped
[12:10:21 + 2.201s] (waited: idle after 0.009 s, speaker released after 0.253 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 541, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 26, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 1514 ms played, 24904 subsamples, 1556 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 60, fallback 3, missing 2, open max 38 ms, last 28 ms
free heap: 110240
[12:10:21 + 2.208s] == sr voice status   (reply after 0.007s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 60, fallback 3, missing 2, open max 38 ms, last 28 ms
[12:10:21 + 2.225s] == storage read /ext/sr/missing.txt   (reply after 0.017s)
Size: 10
u2f
zzyzx
```

Results:
- Speech was idle 9 ms after `sr stop`. Aborted went up by 1, and underruns stayed at 0.
- Four letter clips had started, the last of them cut off, so clips +4.
- The first zzyzx counted as fallback +1. It was not logged again.

### The letter A fix on the device

After commit d0c3676, the command `.venv/bin/python tools/voice_build.py --extract --sync` exited 0. Without the transfer progress lines, its output was:

```
extract: 6184 distinct strings from the firmware sources, 71 bubble texts
extract: 2880 words; longest: animationmanager animationstorage backlightenforce checksdkfeatures configchangeable defaulttextclear desktopscenelock freecreatedelete getbatterycharge hoppingthreshold
extract: 10 with an apostrophe: can't doesn't don't flipper's i'll i'm isn't it's who's you're
2888 words, 1 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
made 1 clips, 0 failed, 1 s; vocabulary 2899 words in /Users/robin/Downloads/flipper-access/voice
voice: silenced for the transfer
sync: 1 sent, 2898 skipped, 0 missing, 0 failed, 0 s
voice: restored
```

`--pull-missing` was left out on purpose, so the verification's test words were not pulled into the vocabulary.

Local md5 after the run:
- ay.raw: 860afb20b4ffcfb689f380c3a151cc7a
- a.raw: 860afb20b4ffcfb689f380c3a151cc7a
- i.raw: bd9731229a6eb485ba117bf59c6d8dd0

The predictions:
- `sr say A` plays the ay clip, 5,376 samples.
- `sr say a2b` is 17,859 subsamples. a2b is a letter-digit token, so the pull filter drops it and it can never pollute the vocabulary.

```
[12:14:48 + 0.459s] == storage md5 /ext/sr/voice/0f/ay.raw   (reply after 0.036s)
860afb20b4ffcfb689f380c3a151cc7a
[12:14:48 + 0.494s] == storage md5 /ext/sr/voice/04/i.raw   (reply after 0.035s)
bd9731229a6eb485ba117bf59c6d8dd0
[12:14:48 + 0.529s] == sr voice status   (reply after 0.035s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 60, fallback 3, missing 2, open max 38 ms, last 28 ms
[12:14:48 + 0.543s] == sr say A   (reply after 0.013s)
queued 1 characters; sr status shows the timing when it is done
[12:14:49 + 1.223s] (waited: idle after 0.488 s, speaker released after 0.680 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1077, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 27, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 441 ms played, 5376 subsamples, 336 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 61, fallback 3, missing 2, open max 38 ms, last 21 ms
free heap: 110048
[12:14:49 + 1.229s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 61, fallback 3, missing 2, open max 38 ms, last 21 ms
[12:14:49 + 1.241s] == sr say a2b   (reply after 0.012s)
queued 3 characters; sr status shows the timing when it is done
[12:14:50 + 2.661s] (waited: idle after 1.215 s, speaker released after 1.419 s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1080, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 28, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 1203 ms played, 17859 subsamples, 1116 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 64, fallback 4, missing 3, open max 38 ms, last 17 ms
free heap: 110016
[12:14:50 + 2.667s] == sr voice status   (reply after 0.006s)
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 64, fallback 4, missing 3, open max 38 ms, last 17 ms
[12:14:50 + 2.681s] == storage read /ext/sr/missing.txt   (reply after 0.014s)
Size: 14
u2f
zzyzx
a2b
```

Results:
- The card holds the new ay clip (same md5), and i is unchanged.
- `sr say A` played exactly the ay clip: 5,376 subsamples, clips +1.
- `sr say a2b` came out exactly as predicted: 17,859 subsamples, clips +3, fallback +1, missing +1.
- Underruns stayed at 0.

### Final state

```
[12:15:02 + 0.431s] == sr screen   (reply after 0.008s)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
[12:15:02 + 0.441s] == sr status   (reply after 0.009s)
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1104, dropped: 0, announcements: 21, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 28, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 1203 ms played, 17859 subsamples, 1116 ms nominal, worker stack free 2616
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 64, fallback 4, missing 3, open max 38 ms, last 17 ms
free heap: 110320
[12:15:02 + 0.446s] == free   (reply after 0.005s)
Free heap size: 110376
Total heap size: 185904
Minimum heap size: 80512
Maximum heap block: 101752
Pool free: 876
Maximum pool block: 672
```

The device is idle on the home screen. The reader is on, the voice is on, speech is idle, nothing is queued, the speaker is released and there are 0 underruns. `loader close` was never used.

## Evidence on the letter names

These checks were done on the Mac, with the vocabulary's settings (say Samantha rate 175 highpass 500 gain 1.3 soft 16000):
- The phoneme API (NSSpeechSynthesizer phonemesFromText) fails with error -50 for the compact Samantha voice. `[[inpt PHON]]` is not honoured either: it renders the literal text, 1.5 s long.
- Byte identity, by md5 of the finished clips:
  - "ay", "Ay", "aye" and "eye" give the same audio as the i clip.
  - "a", "a." and "eh" give the same audio as each other.
- LPC formant tracks, as F1/F2 in Hz at the start, middle and end of the voiced part:
  - "a" (the new A): 665/2257, 670/2192, 597/2500.
  - "eight": 566/2516, 590/2550, 383/2863.
  - "bait": 480/2416, 606/2546, 380/2836.
  - "bite": 765/1230, 950/2105, 735/2155.
  - "ay" (the old A, which is "eye"): 970/1300, 950/2980, 900/2940.
  - "uh": 854/1234, 824/1318, 774/1254.
- All 36 spelling clips (ay, b to z, 0 to 9) are now distinct audio.
- For 23 of the 25 letters b to z, `say` given the bare lower case letter renders byte-identical to the clip made from its name in voice_names.txt. The bare "a" matches the new A clip. The two exceptions:
  - e: "ee" is 0.40 s against 0.28 s for the bare "e". It is one continuous /i/ vowel, with F1 about 400 and F2 about 2,500 to 2,900 Hz, the same as the bare "e" and the end of "bee". It is correct, only drawn out.
  - w: "double you" is 0.57 s against 0.52 s for the bare "w".

## Concerns

1. The two deviations above need a ruling: the letter clip counter, and `ay	a` in place of `ay	ay`. Each reverts in seconds (the counter needs a flash).
2. missing.txt on the card now holds u2f, zzyzx and a2b from the checks. The pull filter drops u2f and a2b. The next routine run will make a clip for zzyzx, which is harmless, unless that line is removed first. I did not delete anything on the card.
3. The console help line in screen_reader_cli.c still says "voice on|off|status  recorded word clips from the card, SAM for the rest (saved)". That file is outside the brief, and changing the string also changes what `--extract` reads. It is a one-line follow-up.
4. The article "a" now sounds like the letter name A, which is how Samantha reads a lone "a". Before this round it was "capital A" (0.788 s, the same hash as the old ay clip), so it is better either way. It is worth a listen in a sentence, for example `sr say Hold a card`.
5. Spelling costs about 0.43 s per letter. An unknown word of the maximum 31 characters would take about 13 s. `sr stop` ended a spelled word within 9 ms (the stop check above). It is the same speech_stop call a key press makes, but a physical key press was not tested.
   - The extraction has 55 tokens longer than 16 letters, which can never be clips. Nearly all are internal identifiers, such as notificationmessage and subghzscenereceiver, and are not UI text.
   - The 153 letter-digit tokens, such as md5 and 128x64, are spelled every time. That reads better than SAM did ("em dee five").
6. An optional tweak: `e	e` would make E 0.28 s, where "ee" makes it 0.40 s. The sound is right either way.
