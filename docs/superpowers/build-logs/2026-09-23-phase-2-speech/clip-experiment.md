# Clip experiment: sr play for recorded 8 bit clips

Implementer report, 2026-09-23, on firmware 77a57c979 plus this change. Status: DONE.

## What was built

- speech_pcm_push_raw (speech_pcm.h/.c): every sample held for exactly hold_ns, no overhead, through the same slot accumulator and loudness table as SAM values. subsamples grows by every sample entered; nominal_us by the exact time of the completed samples, computed as the difference of the microsecond floors of now_ns before and after the call, so the 62.5 us samples of a 16 kHz clip add up to a whole second across calls instead of 992 ms. A refusal returns false with the stage inside the refused sample, as speech_pcm_push does.
- SpeechItem gains file and rate; speech_queue_push_file clears the queue, bumps the generation and stores the path in text with file true, through a shared push_item; speech_queue_push leaves file false and rate 0.
- speech_play(speech, path, rate) (speech.h/.c): queues a file item and wakes the worker; rates outside 8000..32000 are clamped (the console refuses them first). speech_alloc opens the Storage record and allocates a 512 byte read buffer. The common start and end of an item (take the speaker, refresh the table, reset the PCM stage and the ring, count; play out or stop, record the timing) moved out of speech_speak_item into speech_item_begin and speech_item_end, and speech_play_item reuses them: it opens the file first (a file that cannot be opened is counted as dropped with a warning in the log), then reads 512 bytes at a time into speech_pcm_push_raw with speech_emit, until end of file, a refusal (superseded, stopped, or no DMA event) or an abort, then closes and frees the file. Speaker held and released exactly as for speech; the worker dispatches on item->file.
- sr play <path> [rate] (screen_reader_cli.c): quoted paths accepted, rate 16000 by default, 8000..32000 enforced, storage_common_stat must find the path and it must not be a folder; prints "playing <path> at <rate> Hz; sr status shows the timing when it is done". Help line added.

## Commits

- Firmware, branch screen-reader: 54794522bdf2588fa1916562030389efcb8e418b "screen reader: sr play for recorded clips from the card" (speech_pcm.h/.c, speech_queue.h/.c, speech.h/.c, screen_reader_cli.c; 211 insertions, 23 deletions; pathspec commit, the dirty applications/external submodule untouched).
- Project, main: eb36405d40925853f5d585f98666c07b934b2368 "host tests: raw sample push and file items" (tests/host/test_speech_pcm.c, tests/host/test_speech_queue.c; 167 insertions).

Nothing pushed. This log file is not committed by me.

## Host runner

Private TMPDIR, exit 0:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 115 checks, 0 failures
speech PCM: 700 checks, 0 failures
```

Queue went from 94 to 115 checks, PCM from 647 to 700. The new PCM checks: 16000 samples at 62500 ns give exactly 50000 slots, 16000 subsamples and 1,000,000 us nominal (with a 7400 ns SAM overhead configured, which must not apply); the loudness table applies (three samples cover marks 4, 3, 3 and 187.5 us floor to 187); a refusal after five marks stops inside sample 1 with the refused mark pending and the same push goes through whole after a reset; five different splits over two calls and 512 byte chunks give the same 50000 slots and 1,000,000 us; 31250 ns (32 kHz) gives 25000 slots, 125000 ns (8 kHz) 100000, 90702 ns (11025 Hz) ceil(1451232000 / 20000) with the exact nominal; zero samples do nothing; volume 0 gives all silence. The new queue checks: one file after two texts leaves one item with file, path, rate 16000 and a new generation; texts carry file false and rate 0; a file never merges with a replaceable tail and a replaceable text after a file is appended; a file clears a full queue without counting drops and a stop drops a waiting file; a long path is cut like text.

## Firmware build

./fbt exit 0; only the two pre-existing manifest warnings (cli_bridge, mtp); API version 87.1 is up to date. Sizes: .text 675612, .rodata 192664, .data 1140, .bss 8524, .free_flash 178820. All seven files pass clang-format --dry-run --Werror; ./fbt lint exit 0. Flash headroom (tools/flash_headroom.sh): firmware.bin 869756 bytes, limit 880640, spare 10884 bytes; the previous image was 868668 bytes, so this change costs 1088 bytes of flash. RAM: the queue items grow by 8 bytes each (4 in the queue plus the worker's copy), plus the 512 byte read buffer and one 4 byte pointer at service start, plus a File object while a clip plays.

## Device

./fbt flash_usb exit 0; the port left and returned after 35 seconds; sr screen first and alone:

```
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as:
```

No crash popup, home screen. Before the flash the device had been sitting in the main menu (Settings, 11 of 11) with speech idle; the update reboot brought it to the home screen.

Upload: scripts/storage.py mkdir /ext/sr, mkdir /ext/sr/clips, send of the scratchpad clips folder to /ext/sr/clips (1.6 MB at about 135 kB/s). storage stat on each file afterwards:

```
1_samantha.raw 182276b, 2_samantha_hp.raw 182276b, 3_samantha_slow_hp.raw 200257b,
4_samantha_hp_loud.raw 182276b, 5_alex_hp.raw 219669b, 6_daniel_hp.raw 202897b,
7_fred_hp.raw 224502b, 8_fred.raw 224502b
```

all equal to the local sizes.

Argument checks, verbatim: "sr play" gives "play what? sr play <path> [rate]"; a missing file gives "cannot play /ext/sr/clips/nothing.raw: file/dir not exist"; "sr play <clip> 44100" gives "expected a sample rate from 8000 to 32000"; "sr play /ext/sr/clips" gives "cannot play /ext/sr/clips: it is a folder".

The one clip played, verbatim:

```
sr play /ext/sr/clips/2_samantha_hp.raw 16000
playing /ext/sr/clips/2_samantha_hp.raw at 16000 Hz; sr status shows the timing when it is done
while playing: speech: speaking, queued 0, speaker held: yes, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
speech: idle, queued 0, speaker held: yes, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 11439 ms played, 182276 subsamples, 11392 ms nominal, worker stack free 2412
after 1.2 s: speech: idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
```

182276 bytes at 16 kHz are 11.392 s; played 11439 ms is 0.4 percent over, which is the flush (the partial last half padded with silence plus one silent half), underruns 0, dropped 0, every byte of the file counted as a subsample. The speaker was released within 1.2 s. Free heap 114728 before the clip and 114880 after (minimum 113288 before, 113280 after: the File object while the clip played, freed afterwards).

sr stop on a replay of the same clip, 2.0 s in, verbatim:

```
sr stop
stopped
speech: idle, queued 0, speaker held: no, utterances 3, aborted 1, dropped 0, underruns 0, queue dropped 0
last utterance: 2019 ms played, 32769 subsamples, 2048 ms nominal, worker stack free 2412
```

The other seven clips were not played. Final state: sr status shows enabled: yes, speech idle, queued 0, speaker held: no, underruns 0; sr screen shows the home screen. Worker stack: at most 660 bytes of the 3 KB used in this session.

## Notes

- nominal_us for a refused push counts only the samples completed, where speech_pcm_push counts its whole group up front; on the device that is at most one sample of difference on an aborted clip.
- speech_play_item opens the file before taking the speaker, so a missing file never touches the timer; a file that opens but whose speaker cannot be taken is closed and counted as before (aborted or dropped).
- Reads go through the storage service thread, 512 bytes (32 ms of audio at 16 kHz) per request against a 41 ms ring half; no underrun in 11.4 s. At 32 kHz a chunk is 16 ms, which should still hold, but that rate was not exercised on the device.
- Helpers used, in the scratchpad: clip_check.py (verify_clip.txt holds the full output).
