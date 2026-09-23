# Task 5 report: timing calibrated against the Text to SAM demo

Status: DONE.

## Commits

- Firmware (Momentum-Firmware, branch screen-reader): b459f8706 "screen reader: speech timing calibrated against the Text to SAM demo". Only applications/services/screen_reader/speech.c changed: SPEECH_OVERHEAD_NS 0 to 7400. The submodule applications/external was not added; it still shows modified content (sam_app.cpp), as intended.
- Project (flipper-access, branch main): 81e90bf "sam_calibrate: timing calibration tool; demo records its duration". Files: tools/sam_calibrate.py (new, executable) and patches/text2sam-cli-mode.patch (regenerated, now command line mode plus the timing record).
- Nothing was pushed. No commit was made inside the text2sam submodule.

## Calibration run (engine at overhead 0)

Tool output, verbatim:

    demo 5436 ms, nominal 3799 ms, subsamples 222360, overhead 7362 ns per value: Hello Robin. This is your Flipper Zero s...
    demo 6001 ms, nominal 4242 ms, subsamples 237000, overhead 7422 ns per value: The quick brown fox jumps over the lazy ...
    mean overhead 7392 ns per value, spread 0.8 percent between sentences
    set SPEECH_OVERHEAD_NS to 7400

Per sentence, with overhead = (D - N) * 1e6 / S:

- Sentence 1 (Hello Robin, 75 characters): demo D 5436 ms, engine nominal N 3799 ms, subsamples S 222360, overhead 7362 ns per value.
- Sentence 2 (quick brown fox, 76 characters): demo D 6001 ms, nominal N 4242 ms, subsamples S 237000, overhead 7422 ns per value.
- Mean 7392 ns, spread 0.8 percent (the brief allows 10 percent before a second run is needed, so one run was used). Rounded to the nearest 100 ns: 7400.

The overhead is positive: the demo is slower than the engine's nominal rate, not faster, so the unsigned constant can express it (see the concerns).

## Verify run (engine at overhead 7400 ns)

Tool output, verbatim:

    demo 5436 ms, engine 5466 ms played, 5426 ms without padding, difference +0.6 percent raw, -0.2 percent corrected: Hello Robin. This is your Flipper Zero s...
    demo 6001 ms, engine 6041 ms played, 6001 ms without padding, difference +0.7 percent raw, +0.0 percent corrected: The quick brown fox jumps over the lazy ...
    worst corrected difference 0.2 percent, ok; worst raw difference 0.7 percent, ok

Per sentence:

- Sentence 1: demo 5436 ms, engine played 5466 ms. Raw difference +0.6 percent; with the 40 ms padding taken off, -0.2 percent.
- Sentence 2: demo 6001 ms, engine played 6041 ms. Raw +0.7 percent; corrected 0.0 percent.
- Acceptance: the corrected differences are within 3 percent; the raw ones pass too. The tool exited 0.

The demo's durations were identical to the millisecond in both runs (5436 and 6001), so its timing record is stable.

Cross check with the engine's own arithmetic instead of the 40 ms constant: the audio the engine plays lasts N + S * 7400 ns, which is 5444.5 ms for sentence 1 (demo 5436, +0.16 percent) and 5995.8 ms for sentence 2 (demo 6001, -0.09 percent). The rest of the played time is the padding: 21.5 ms and 45.2 ms, made of about 18 to 20 ms of rendering before the DMA starts plus the silence that fills the last ring half (3.2 ms and 25.3 ms here, from the slot count modulo 2048). This agrees with Task 4's 22 to 62 ms at overhead 0.

## Build, flash, device

- Demo app: ./fbt fap_text2sam printed "API version 87.1 is up to date"; text2sam.fap is 30200 bytes, uploaded with scripts/storage.py and confirmed on the card with storage stat.
- Firmware: ./fbt printed "API version 87.1 is up to date" (checked again with an incremental rebuild before flashing); ./fbt flash_usb sent f7-update-mntm-screen-reader-5cea830f; the port disappeared and came back after 38 seconds; sr screen right after the flash showed the desktop record only (no crash popup). The flashed image is the code committed as b459f8706 (the commit was made after the flash; the only change is the constant).
- End state: sr screen shows the desktop record only; sr status shows speech idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 0, underruns 0; loader info says no application is running; the screen reader is enabled (the tool turned it off for the run and back on afterwards).
- Host tests: TMPDIR=<scratchpad>/t5 tools/run_host_tests.sh is green: screen model 98 checks, SAM port matches the original on 11 cases, speech text 1006, speech queue 94, speech PCM 647 checks, 0 failures.

## Preflight checks made before measuring

- The engine's expander and chunker leave both sentences whole and unchanged (a small host probe compiled against speech_text.c printed one chunk per sentence, identical to the input), so the engine and the demo render the same text; the demo upper cases all but the first character and both sentences start with a capital, so the reciter sees the same string.
- The demo's hold time divisor is 8 (_STM32SAM_SPEED is 7 in the default constructor), matching the engine's nominal delta / 8.
- furi_hal_speaker_release disables the TIM16 bus, so the engine's bus check accepts the speaker after the demo exits; the run showed dropped 0.
- The screen reader writes nothing to the console on its own (only sr watch does), so nothing interleaves with the tool's parsing.

## Deviations from the brief and why

1. Placement of save_timing in sam_app.cpp: the brief says to add it after save_message and to move say_something below save_message if needed. say_something has two callers above save_message (say_from_args and text_input_callback), so moving it would have needed a forward declaration plus a function move. save_timing was instead inserted directly above say_something, a pure insertion that satisfies the required order (defined before say_something) with the smallest diff. Its body is the brief's, plus a two line comment naming the tool that reads timing.txt. say_something was changed exactly as the brief shows.
2. The tool's utterance regular expression matches the whole status line, including ", worker stack free N", as instructed by the task message (the brief's regex stopped at "ms nominal").
3. The tool rounds the mean overhead to the nearest 100 ns (task message) rather than the nearest 10 ns (brief): 7392 became 7400 rather than 7390.
4. --verify prints both the raw difference and the difference with PADDING_MS (40 ms) taken off, and judges on the corrected one, as the task message asked; the brief judged on the raw difference only. Both passed here.
5. Robustness additions to the tool: it reads the speech counters before sr say and, once the engine is idle, refuses a reading if dropped or aborted increased or utterances did not, so a stale "last utterance" line cannot be taken for a fresh one; error exits include the status output; a negative mean prints that the constant is unsigned and exits 1. No other behaviour changed (same commands, same polling, sr off and on around the run).
6. The comment on SPEECH_OVERHEAD_NS now reads "calibrated against the Text to SAM demo, Task 5" instead of the placeholder text.
7. The commit messages carry a short body with the numbers; the brief gave subjects only.

## Concerns

1. The plan's premise was reversed by the measurement. The plan says the demo "ran faster and higher than SAM's nominal rate"; measured, the demo is about 43 percent slower than the engine's nominal delta / 8 rate: its loop spends 7.4 microseconds per value on top of the 17 microseconds it means to hold. The calibrated engine therefore now sounds lower and slower than the uncalibrated Task 4 engine did, which is what matches the demo Robin approved. Since the point of the task is to reproduce that approved sound, this is correct by definition, but Robin's ear is the final check: if the faster Task 4 voice was preferred, the constant is the one knob to turn (0 gives the Task 4 timing, 7400 gives the demo's).
2. The calibration was made at rate 72 only (the rate Robin approved, and the demo's default). The overhead model is additive per value, so it should carry over to other rates, but that was not measured.
3. The tool's 40 ms padding constant is an approximation of a value that varies between about 20 and 60 ms with the sentence (see the cross check above). For sentences of three seconds or more this is well inside the 3 percent margin; for very short sentences the raw and corrected figures would differ more, but the two reference sentences are the ones the tool uses.
4. While the demo speaks, the tool polls "loader info" about five times a second; each poll costs the demo's busy loop a fraction of a millisecond. The identical durations across both runs show the effect is stable and small, and Robin heard the demo without such polling, so if anything the calibrated engine is a hair slower than what Robin heard (under 0.1 percent by estimate).
5. The demo now leaves an 8 byte timing.txt in /ext/apps_data/text2sam after every utterance, including in its normal text input mode; the tool deletes and rewrites it each run. Harmless, but it is a file the stock app did not create.

## Files

- /Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/services/screen_reader/speech.c (committed)
- /Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/text2sam/sam_app.cpp (uncommitted submodule change, captured in the patch)
- /Users/robin/Downloads/flipper-access/tools/sam_calibrate.py (committed)
- /Users/robin/Downloads/flipper-access/patches/text2sam-cli-mode.patch (committed)
