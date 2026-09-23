# Task 4 report: speaker playback, the worker thread, and sr say

Status: DONE_WITH_CONCERNS. The engine plays on the device: the first sentence completes with underruns 0 and dropped 0, the speaker is released after a second, sr stop cuts a long sentence, an interrupting sentence replaces one in progress, and repeating a sentence three times leaves the free heap unchanged. Two things need the controller's attention: the brief's DMA listing lacked the transfer direction (fixed, see deviations), and the device showed a crash popup from the phase 1 image before anything was flashed (see concerns).

## Commits

Firmware, branch screen-reader, on top of 551d457b8:

- 2c6254154405f73d92b87c1b9eeecaab20ee103f "screen reader: speech engine with DMA playback and sr say". Seven files under applications/services/screen_reader: new speech_hw.h, speech_hw.c, speech.h, speech.c; modified screen_reader.h, screen_reader.c, screen_reader_cli.c. 578 insertions, 0 deletions. Committed with an explicit pathspec, so the other agents' work (the dirty applications/external submodule) stayed out. Nothing pushed.

Project repository: no commit. The brief puts the verification helper in the scratchpad, outside both repositories, and no project file changed.

## Host runner

TMPDIR set to a private directory as instructed. Exit 0. Summary lines:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 984 checks, 0 failures
speech queue: 94 checks, 0 failures
speech PCM: 647 checks, 0 failures
```

None of my files is host tested (speech.c and speech_hw.c need the firmware), so this is a regression check only.

## Firmware build

./fbt in Momentum-Firmware, exit 0. The grep for error, warning, API version and the size lines returns only:

```
fbt: warning: Failed parsing manifest '.../applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui' (pre-existing, external submodule, not touched)
fbt: warning: Failed parsing manifest '.../applications/external/mtp/application.fam' : Invalid appid '.f0_mtp' (pre-existing, same)
API version 87.1 is up to date
.text         674612 (658.80 K)
.rodata       192112 (187.61 K)
.data           1324 (  1.29 K)
.bss            8524 (  8.32 K)
.free_flash   180188 (175.96 K)
```

CC lines appeared for screen_reader.c, screen_reader_cli.c, speech.c and speech_hw.c (and for speech_pcm.c and speech_text.c, which had not been rebuilt since the header constants changed). No compiler warning or error from any screen reader source. All seven files pass the toolchain's clang-format --dry-run --Werror with the repository's .clang-format (ColumnLimit 99), which is what ./fbt lint checks.

Sizes versus the previous image (build/f7-firmware-C/firmware.elf as it stood before this task, measured with arm-none-eabi-size; identical to the numbers in the Task 1 report):

- .text 662180 to 674612: plus 12432 bytes
- .rodata 182024 to 192112: plus 10088 bytes
- .data 968 to 1324: plus 356 bytes
- .bss 4972 to 8524: plus 3552 bytes
- .free_flash 203064 to 180188: minus 22876 bytes (22.3 KB), which is the SAM port now being linked (Task 1 predicted 13.8 KB for it) plus the engine, the text and PCM stages and the console code
- Static RAM (.data plus .bss) 5940 to 9848: plus 3908 bytes, which matches the 3885 bytes of SAM tables Task 1 measured. On the device the total heap shrank by the same amount (189632 to 185720).

Heap taken at service start by the phase 2 code (the Speech struct with its 4096 byte ring, 800 byte text buffer, queue, PCM tables and stats, the 3 KB worker stack with its thread records, and the worker's SpeechItem): free heap on the home screen went from 129368 on the phase 1 image to 115792, a drop of 13576, of which 3912 is the smaller heap region, so 9664 bytes of heap. That is inside the 13 KB budget.

## Device verification

Device: Flipper at /dev/cu.usbmodemflip_R0skie1. Flash: ./fbt flash_usb, exit 0 (15 chunks uploaded, "Closing current app, if any"). The wait loop from the constraints saw the port disappear and return after 38 seconds, then slept 6 seconds. First command afterwards, alone:

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as:
```

No crash popup; the home screen, and the sr command answers, so the service came up with the worker thread started.

Then the brief's helper (speech_check.py in the scratchpad, with free readings added before and after the first utterance and a final status and screen). Output verbatim:

```
sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 

>: 
== free before the first utterance ==
free
Free heap size: 115792
Total heap size: 185720
Minimum heap size: 113584
Maximum heap block: 115488
Pool free: 876
Maximum pool block: 672

>: 
sr say Hello Robin. This is your Flipper Zero speaking through the built in piezo.
queued 75 characters; sr status shows the timing when it is done

>: 
sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 69, dropped: 0, announcements: 2
speech: idle, queued 0, speaker held: yes, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 3830 ms played, 222360 subsamples, 3799 ms nominal, worker stack free 2396
free heap: 115472

>: 
finished after 3.9 s
['speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0']
== free after the first utterance ==
free
Free heap size: 115584
Total heap size: 185720
Minimum heap size: 113584
Maximum heap block: 115264
Pool free: 876
Maximum pool block: 672

>: 
sr stop
stopped

>: 
['speech: idle, queued 0, speaker held: no, utterances 2, aborted 1, dropped 0, underruns 0, queue dropped 0', 'last utterance: 1550 ms played, 104295 subsamples, 1597 ms nominal, worker stack free 2396']
['speech: idle, queued 0, speaker held: yes, utterances 4, aborted 2, dropped 0, underruns 0, queue dropped 0', 'last utterance: 1489 ms played, 80840 subsamples, 1474 ms nominal, worker stack free 2396']
== final status ==
sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 81, dropped: 0, announcements: 2
speech: idle, queued 0, speaker held: yes, utterances 4, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 1489 ms played, 80840 subsamples, 1474 ms nominal, worker stack free 2396
free heap: 115160

>: 
== screen at the end ==
sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 

>: 
```

Against the brief's expectations:

- First sentence: finished after 3.9 seconds, 3830 ms played, 222360 subsamples, 3799 ms nominal, underruns 0, dropped 0.
- 1.2 seconds later: speaker held: no.
- sr stop 1.5 seconds into the long sentence: aborted went from 0 to 1, last played 1550 ms (the brief expects 1500 to 1900).
- The interrupting sentence: aborted went to 2 (utterances 4: the long one aborted, the short one complete), and the last utterance is the short one (1489 ms played, 80840 subsamples, 1474 ms nominal). The "speaker held: yes" in that line and in the final status is expected: those readings were taken within the 200 ms idle window after the short sentence ended; the reading taken 1.2 seconds after the first sentence shows the release working.
- Worker stack: 2396 of 3072 bytes never used at that point; the lowest watermark seen in the whole session was 2260 free, so the worker uses at most 812 bytes of its 3 KB.

A second helper (speech_check2.py, same scratchpad) repeated one sentence three times for a leak check, exercised rate and volume, and confirmed the idle home screen at the end. Output verbatim:

```
== leak check: the same sentence three times ==
after 1: ['Free heap size: 115624', 'Minimum heap size: 113008']
after 2: ['Free heap size: 115624', 'Minimum heap size: 113008'] ['speech: idle, queued 0, speaker held: yes, utterances 6, aborted 2, dropped 0, underruns 0, queue dropped 0', 'last utterance: 2475 ms played, 144240 subsamples, 2423 ms nominal, worker stack free 2396']
after 3: ['Free heap size: 115624', 'Minimum heap size: 113008'] ['speech: idle, queued 0, speaker held: yes, utterances 7, aborted 2, dropped 0, underruns 0, queue dropped 0', 'last utterance: 2475 ms played, 144240 subsamples, 2423 ms nominal, worker stack free 2396']
== rate and volume ==
sr rate 200
expected a number from 40 to 120

>:
sr volume 50
volume set to 50

>:
['speech: idle, queued 0, speaker held: yes, utterances 8, aborted 2, dropped 0, underruns 0, queue dropped 0', 'last utterance: 874 ms played, 55120 subsamples, 848 ms nominal, worker stack free 2260']
sr volume 100
volume set to 100

>:
sr rate 72
rate set to 72

>:
['rate: 72, volume: 100, verbosity: 1', 'speech: idle, queued 0, speaker held: yes, utterances 9, aborted 2, dropped 0, underruns 0, queue dropped 0', 'last utterance: 1079 ms played, 60080 subsamples, 1056 ms nominal, worker stack free 2260']
== final ==
sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 229, dropped: 0, announcements: 2
speech: idle, queued 0, speaker held: no, utterances 9, aborted 2, dropped 0, underruns 0, queue dropped 0
last utterance: 1079 ms played, 60080 subsamples, 1056 ms nominal, worker stack free 2260
free heap: 115152

>: 
sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 

>:
```

Nine utterances in total, underruns 0, dropped 0, queue dropped 0 throughout. The device was left idle (speaker held: no, queued 0) on the home screen; no app was opened during the task, so no Back presses were needed to leave one. Settings are back at rate 72 and volume 100 (both saves went through momentum_settings_save, as the command does).

## Free heap

- Phase 1 image, before the flash, on the home screen: Free heap size 129368, Total 189632, Minimum 127208.
- New image, home screen, before the first utterance: Free 115792, Total 185720, Minimum 113584.
- After the first utterance (1.2 seconds later, speaker released): Free 115584, Minimum 113584.
- Leak check, after each of three identical sentences: Free 115624 all three times, Minimum 113008 all three times.
- End of the session: Free 115152.

The 208 byte difference around the first utterance, and the later drift, follow the length of the console command lines, not speech: the console keeps its input line in a FuriString that grows to the longest line typed and never shrinks, and each longer "sr say" line was the longest so far. The three identical repeats, which grow nothing, leave the free heap exactly equal, and the speech path allocates nothing per utterance (its only malloc, the worker's SpeechItem, happens once at thread start). The minimum heap watermark did not move during the first utterance either.

## Deviations from the brief's code, with reasons

1. speech_hw.c: added LL_DMA_SetDataTransferDirection(SPEECH_DMA, SPEECH_DMA_CHANNEL, LL_DMA_DIRECTION_MEMORY_TO_PERIPH) before LL_DMA_ConfigAddresses. The brief's listing relied on LL_DMA_ConfigAddresses to set the direction, but in stm32wbxx_ll_dma.h that function only writes CMAR and CPAR (it uses the direction argument just to decide which address goes where); the DIR bit in CCR stays at its reset value, peripheral to memory. Without the extra call the channel would copy CCR1 into the ring buffer instead of the other way round: silence, and a clobbered ring. The firmware's own DMA users (infrared, SPI, sub-GHz) set the direction through LL_DMA_Init, which is why the omission is easy to make. A comment in the file says why the line is there.
2. speech_hw.c: added #include <furi.h> above <furi_hal.h> for UNUSED and memset. furi_hal.h reaches furi.h only indirectly (through furi_hal_resources.h), so this is explicit rather than new.
3. screen_reader.c: the speech_set_voice call at service start casts momentum_settings.sr_rate and sr_volume to uint8_t, as the console code in the brief already does. No behaviour change (the values are 40..120 and 0..100).
4. Formatting only: clang-format reflowed the furi_thread_flags_wait call in speech_wait_half_played, the one line while loop in speech_alloc, and the long printf in sr_cli_say, to fit the 99 column limit. No token changed.
5. The commit message has a short body under the brief's subject line, plus the Co-Authored-By trailer, as the controller asked.
6. Verification: the brief's helper gained free readings before and after the first utterance and a final status and screen, as the controller asked, and a second helper added the leak check, the rate and volume commands and the end of session confirmation. Both live in the scratchpad.

Everything else is the brief's code as listed: the flag protocol, the exit conditions of every loop in the worker, the speaker rules, the 3 KB high priority thread, the chunk loop over the consumed count, the reset at the start of every utterance and the silence re-read after a volume change.

## Concerns for the controller

1. Pre-existing crash popup. Before anything was flashed, the very first command of this task returned:

```
== sr screen
records: 4, content layer: desktop
desktop      x= 27 y= 26 primary    "Flipper crashed"
desktop      x= 19 y= 37 primary    " and was rebooted"
desktop      x= 30 y= 53 secondary  "furi_check failed"
status-right x=103 y=  9 battery    inverted "100"
reads as: Flipper crashed. and was rebooted. furi_check failed
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1, dropped: 0, announcements: 1
free heap: 129320
```

So the phase 1 image (or something driven against it) hit a furi_check at some point before this task and the device rebooted; frames: 1 means the popup was the only screen processed since that reboot. The popup carries no location. I did not cause it (it was there on my first read) and I do not know what did. I dismissed it with one "input send back short" before flashing, on purpose: desktop_scene_fault.c clears the RTC fault record only when the popup is dismissed, so an undismissed record would have shown the same popup again after the update and looked like a crash of the new image. After the dismissal the device was on the home screen, and it never showed a popup again during this task.
2. The plan's note that the NFC tag emulation path borrows TIM16 did not match the tree: a grep over targets/f7/furi_hal, lib/nfc and lib/drivers finds TIM16 only in furi_hal_speaker.c, so every TIM16 user goes through the speaker mutex. The bus check in speech_take_speaker is kept as the brief lists it; it is a belt and braces guard. Worth knowing because Momentum's furi_hal_bus_enable does furi_check that an APB2 peripheral is not already enabled, so any future direct TIM16 user would crash while we hold the speaker.
3. DMA2 channel 4 is confirmed free: the HAL uses DMA2 channels 1 and 2 (infrared, RFID, sub-GHz), the signal reader 2, 3 and 5, SPI 6 and 7; the serial DMA is on DMA1.
4. The stop flag is observed but not consumed inside an utterance: speech_superseded reads it with furi_thread_flags_get, so after the abort the worker's main wait returns at once with the same flag and applies the stop a second time. Harmless (the queue is already empty), except for a window of well under a millisecond in which a speech_say arriving between the abort and that second application would be dropped. Kept as the brief has it; a one line furi_thread_flags_clear(SPEECH_FLAG_STOP) inside speech_apply_stop would close it if wanted.
5. Every duty byte costs a furi_thread_flags_get call (a FreeRTOS notification query with a critical section) in speech_superseded, about 50,000 per second while rendering. Measured fine: nine utterances, no underrun, and the worker spends most of its time blocked on the half flags, but it is the engine's main CPU cost if that ever matters.
6. For Task 5's calibration: played time exceeds nominal by 25 to 50 ms per utterance (3830 versus 3799, 2475 versus 2423, 1079 versus 1056, 874 versus 848), which is the flush: the partial half is padded with silence and one full silent half is played before the hardware stops, plus the 41 ms of rendering before the DMA starts. A calibration that compares played time with the demo should subtract that constant or compare the nominal figure.
7. Task 5 tooling: a status read within 200 ms after an utterance shows "speaker held: yes"; that is the idle release timer, not a stuck speaker.
8. The worker uses at most 812 bytes of its 3 KB stack in this session (watermark 2260 free). Left at 3 KB as planned.

## Commands run

- Baseline, phase 1 image: tools/flipper_cli.py "sr screen" "sr status" "free"; then "input send back short" and "sr screen" to dismiss the popup.
- Host runner with TMPDIR=/private/tmp/claude-501/-Users-robin-Downloads-flipper-access/7e5c805a-c471-4df7-96ca-14e7ee87ded9/scratchpad/t4.
- Formatter: toolchain/arm64-darwin/bin/clang-format --style=file --dry-run --Werror on the seven files, then -i on speech.c and screen_reader_cli.c.
- cd Momentum-Firmware && ./fbt (log in the scratchpad as build1.log), ./fbt flash_usb (flash1.log), the wait loop, "sr screen".
- .venv/bin/python scratchpad/t4/speech_check.py (verify1.txt) and speech_check2.py (verify2.txt).
- git add of the seven paths and git commit -m ... -- the same seven paths.
