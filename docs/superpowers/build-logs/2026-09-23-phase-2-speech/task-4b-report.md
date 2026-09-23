# Task 4b report: TIM16 arbitration with the NFC-V listener

Status: DONE_WITH_CONCERNS (all steps done; concerns 2 and 5 below need the controller's eye: a Back press during a long announcement on the emulation screen waits for it until Task 6 lands, and the flashed image is one comment wording behind the commit). The crash reproduced on the Task 4 image exactly as the review predicted (speech holding the speaker, then an NFC-V emulation starting: "Flipper crashed and was rebooted, furi_check failed"). With the fix flashed, the same sequence completes the utterance and then emulates; sentences spoken during an emulation are refused and counted as dropped with the NFC app still on its screen; speech plays with underruns 0 after leaving the emulation and after leaving the NFC main menu. The device is idle on the home screen.

## Commit

Firmware, branch screen-reader, on top of b459f8706:

- 7efa4a161221272f38729ac3652492314c11e898 "screen reader: NFC-V listener shares TIM16 through the speaker mutex". Three files: lib/signal_reader/signal_reader.c (10 lines, 2 removed), applications/services/screen_reader/speech.c (3 added), applications/services/screen_reader/screen_reader_cli.c (19 added, 4 removed). 26 insertions, 6 deletions. Committed after an index.lock check (none) with an explicit `git add` of the three paths and `git commit -F msg -- <paths>`; `git status` afterwards shows only the pre-existing ` m applications/external`, which I did not touch. Nothing pushed.

Project repository: no change. The device helper (t4b.py) and the test file live in the scratchpad.

## Step 1: reproduction on the Task 4 image (b459f8706 flashed)

Test file, built from `iso15693_3_save` plus the `nfc_device_save` header (format version 4), uploaded with `Momentum-Firmware/scripts/storage.py -p /dev/cu.usbmodemflip_R0skie1 send` to `/ext/nfc/sr_nfcv_test.nfc` (1157 bytes on both sides):

```
Filetype: Flipper NFC device
Version: 4
# Device type can be ISO14443-3A, ISO14443-3B, ISO14443-4A, ISO14443-4B, ISO15693-3, FeliCa, NTAG/Ultralight, Mifare Classic, Mifare Plus, Mifare DESFire, SLIX, ST25TB, EMV
Device type: ISO15693-3
# UID is common for all formats
UID: E0 04 01 08 53 52 4E 56
# ISO15693-3 specific data
# Data Storage Format Identifier
DSFID: 00
# Application Family Identifier
AFI: 00
# IC Reference - Vendor specific meaning
IC Reference: 00
# Lock Bits
Lock DSFID: false
Lock AFI: false
# Number of memory blocks, valid range = 1..256
Block Count: 28
# Size of a single memory block, valid range = 01...20 (hex)
Block Size: 04
Data Content: <112 times 00 on one line>
# Block Security Status: 01 = locked, 00 = not locked
Security Status: <28 times 00 on one line>
```

`loader open NFC /ext/nfc/sr_nfcv_test.nfc` goes straight to the emulation screen (ISO15693-3 has NfcProtocolFeatureEmulateFull, so `nfc_show_initial_scene_for_device` picks NfcSceneEmulate; no menu navigation was needed).

### The brief's order: open, then say

Output verbatim (the helper prints `== command` then the reply):

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== loader open NFC /ext/nfc/sr_nfcv_test.nfc

== sr screen
records: 4, content layer: fullscreen
fullscreen   x= 66 y= 30 primary    "Emulating"
fullscreen   x= 51 y= 40 secondary  "ISO15693-3 (Unk"
fullscreen   x= 75 y= 50 secondary  "nown)?"
fullscreen   x= 61 y= 60 secondary  "sr_nfcv_test?"
reads as: Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?
== sr say The quick brown fox jumps over the lazy dog while the sun sets slowly behind the distant purple mountains.
queued 106 characters; sr status shows the timing when it is done
== sr screen
records: 4, content layer: fullscreen
fullscreen   x= 66 y= 30 primary    "Emulating"
fullscreen   x= 51 y= 40 secondary  "ISO15693-3 (Unk"
fullscreen   x= 75 y= 50 secondary  "nown)?"
fullscreen   x= 61 y= 60 secondary  "sr_nfcv_test?"
reads as: Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1269, dropped: 0, announcements: 4
speech: idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 1, underruns 0, queue dropped 0
last utterance: 6041 ms played, 237000 subsamples, 4242 ms nominal, worker stack free 2396
free heap: 26272
```

No crash in this order, and the sentence was refused (dropped 1). Reason, from the code: the listener calls `furi_hal_nfc_listener_wait_event(FURI_HAL_NFC_EVENT_WAIT_FOREVER)`, and `furi_hal_nfc_iso15693_wait_event` starts the signal reader once and stops it only when a frame arrives or the listener is aborted. With no reader nearby, TIM16 stays enabled for the whole emulation, and `speech_take_speaker` sees `furi_hal_bus_is_enabled(FuriHalBusTIM16)` and refuses. The crash needs the opposite order: the listener starting while speech holds the speaker.

Leaving the app took one Back press (`input send back short`), after which `sr screen` showed the desktop record only and speech was idle with the speaker released.

### The reverse order: say, then open (the bug)

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== sr say The quick brown fox jumps over the lazy dog while the sun sets slowly behind the distant purple mountains.
queued 106 characters; sr status shows the timing when it is done
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 1274, dropped: 0, announcements: 6
speech: speaking, queued 0, speaker held: yes, utterances 3, aborted 0, dropped 1, underruns 0, queue dropped 0
last utterance: 6041 ms played, 237000 subsamples, 4242 ms nominal, worker stack free 2396
free heap: 115232
== loader open NFC /ext/nfc/sr_nfcv_test.nfc

Traceback (most recent call last):
  ...
termios.error: (6, 'Device not configured')
```

The serial port vanished on the next command (the helper's first version caught only serial exceptions, not termios.error, hence the traceback; fixed afterwards). After reconnecting (the port was back by the time I looked, plus the six second wait):

```
[port present: True after 0.0 s]
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
speech: idle, queued 0, speaker held: no, utterances 0, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 0 ms played, 0 subsamples, 0 ms nominal, worker stack free 2796
free heap: 115656
```

Dismissed with `input send back short`:

```
== input send back short

== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
```

That was the one expected crash. `furi/core/check.c` confirms the behaviour: in a release image with no debugger attached, `__furi_crash_implementation` stores the fault message in the RTC backup registers and calls `furi_hal_power_reset()`, and the desktop shows the popup after the reboot.

## Step 2: the fix

### signal_reader.c, exact diff as committed (b459f8706..7efa4a161)

```diff
diff --git a/lib/signal_reader/signal_reader.c b/lib/signal_reader/signal_reader.c
index 97d56435c..e6187cc34 100644
--- a/lib/signal_reader/signal_reader.c
+++ b/lib/signal_reader/signal_reader.c
@@ -196,7 +196,12 @@ void signal_reader_start(SignalReader* instance, SignalReaderCallback callback,
     instance->cnt_en = SIGNAL_READER_CAPTURE_TIM->CR1;
     instance->cnt_en |= TIM_CR1_CEN;
 
-    furi_hal_bus_enable(FuriHalBusTIM16);
+    // TIM16 is shared with the speaker, and the speaker mutex is its single owner token:
+    // acquiring it enables the timer and parks the speaker pin on the timer's alternate
+    // function; the compare mode below is frozen and the main output is never enabled, so the
+    // speaker stays silent. Speech and beeps wait or skip while the listener holds it; enabling
+    // the bus directly would furi_check against a speaker user that already enabled it.
+    furi_check(furi_hal_speaker_acquire(FuriWaitForever));
 
     // Capture timer config
     LL_TIM_SetPrescaler(SIGNAL_READER_CAPTURE_TIM, 0);
@@ -318,5 +323,6 @@ void signal_reader_stop(SignalReader* instance) {
     // Deinit DMA Trigger timer
     LL_DMA_DeInit(SIGNAL_READER_DMA_TRIGGER_DEF);
 
-    furi_hal_bus_disable(FuriHalBusTIM16);
+    // Stops the timer, disables the bus (which resets the peripheral) and returns the speaker
+    furi_hal_speaker_release();
 }
```

No new include: signal_reader.c already includes `<furi_hal.h>`, and `targets/furi_hal_include/furi_hal.h` line 26 includes `<furi_hal_speaker.h>`. The now unused `<furi_hal_bus.h>` include was left in place to keep the diff to the two calls.

Thread context, checked: `signal_reader_start` and `signal_reader_stop` are reached only through `iso15693_parser_start` / `iso15693_parser_stop` (lib/signal_reader/parsers/iso15693/iso15693_parser.c, the only callers in the tree), which `furi_hal_nfc_iso15693_wait_event` calls at its top and bottom on the NFC worker thread, so the `furi_hal_speaker_is_mine()` check inside the release holds. `iso15693_parser_free` does not call the stop, so there is no release without a matching acquire.

### What furi_hal_speaker_release resets versus what the signal reader configured

`furi_hal_speaker_release` (targets/f7/furi_hal/furi_hal_speaker.c) does, in order: `furi_hal_speaker_stop` (BDTR main output disable and CR1 counter disable), speaker pin back to analog with pull-down, `furi_hal_bus_disable(FuriHalBusTIM16)`, insomnia exit, mutex release. Explicitly it only touches MOE and CEN. But `furi_hal_bus_disable` is `FURI_HAL_BUS_PERIPH_DISABLE`, which asserts the APB2 reset line for TIM16 and then gates its clock (furi_hal_bus.c lines 80 to 82), and the next `furi_hal_bus_enable` enables the clock and releases the reset. So the peripheral is held in reset while disabled and every register the signal reader configured comes back at its reset value before anyone else uses TIM16: PSC (0), CR1 (up counting, DIV1, ARPE off, CEN), ARR (the ISO15693 sample period), SMCR (internal clock, no master/slave), CCMR1 (OC1 frozen, fast mode off), CCER (CC1E set by `LL_TIM_CC_EnableChannel`, which the CC1 DMA request needs), CCR1 (ARR/2), CR2 (TRGO reset), DIER (CC1DE), CNT (0), and the EGR update. This is the same reset the old `signal_reader_stop` got from its own bus disable, so nothing the signal reader set on TIM16 survives the release. Outside TIM16, the signal reader's own stop still de-initialises DMA2 channels 2, 3 and 5 and the EXTI callback; it never disables DMAMUX request generator 0, which is pre-existing, unrelated to the timer and unchanged. The speaker pin is the one thing the old path never touched: the acquire puts it on alternate function 14 (TIM16_CH1) for the duration of the listener's wait, and the release returns it to analog with pull-down.

While the listener holds the timer the compare mode is frozen and BDTR.MOE is never set, so the timer releases the pin (reference manual OSSI = 0: the GPIO logic forces high impedance) with no pull. That is the state every beep passes through between `furi_hal_speaker_stop` and the release; it is just longer here. I could not check the sound by ear; nothing in the counters suggests a problem.

### speech.c

`speech_apply_stop` now begins with `furi_thread_flags_clear(SPEECH_FLAG_STOP)`. The stale flag came from `speech_superseded`, which reads the flags with `furi_thread_flags_get` (no clear) and sets `stop_pending`; the two wait paths already consume the flag (`furi_thread_flags_wait` clears what it returns unless FuriFlagNoClear, furi/core/thread.c line 575). Without the clear, the worker's next `furi_thread_flags_wait` returned immediately with the old STOP and applied the stop again, dropping whatever had been queued after the key press. The clear sits before `speech_queue_stop`, consume then apply, matching the two wait paths; see concerns for the microsecond window either placement has.

### screen_reader_cli.c

`sr say` now reports the queued length against `SPEECH_ITEM_TEXT_MAX - 1` (159, the cut `set_text` applies in speech_queue.c) and prints "queued 159 of 200 characters, cut; sr status shows the timing when it is done" when the text was longer, or the old "queued N characters; ..." otherwise. `speech_queue.h` is now included from the CLI file (speech.h only includes furi.h). Verified on the device with a 200 character text (below).

## Step 3: build, flash, verification

### Build

`./fbt` in Momentum-Firmware, exit 0, twice (once before the flash, once after the final comment wording fix in signal_reader.c). The grep of the first log for error, warning, API version and sizes:

```
fbt: warning: Failed parsing manifest '.../applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui' (pre-existing, external submodule)
fbt: warning: Failed parsing manifest '.../applications/external/mtp/application.fam' : Invalid appid '.f0_mtp' (pre-existing, same)
	CC	lib/signal_reader/signal_reader.c
API version 87.1 is up to date
	CC	applications/services/screen_reader/screen_reader_cli.c
	CC	applications/services/screen_reader/speech.c
.text         674676 (658.86 K)
.rodata       192192 (187.69 K)
.data           1324 (  1.29 K)
.bss            8524 (  8.32 K)
.free_flash   180044 (175.82 K)
```

No compiler warning or error from the three files. Against the Task 4 image: .text plus 64 bytes, .rodata plus 80, .free_flash minus 144, RAM unchanged. All three files pass the toolchain's clang-format `--dry-run --Werror` with the repository's .clang-format.

Note on what is flashed: the device runs the build made before I reworded the comment in `signal_reader_start` (the first wording said "CC1 output stays disabled", which is wrong, `LL_TIM_CC_EnableChannel` sets CC1E; the silence comes from the frozen compare mode and the never enabled main output). The committed tree differs from the flashed one only in that comment; it was rebuilt (fbt exit 0, signal_reader.c recompiled, API version 87.1 is up to date) but not reflashed.

### Flash

`./fbt flash_usb`, exit 0: 15 chunks of updater.bin sent to /ext/update/f7-update-mntm-screen-reader-b459f870/, "Closing current app, if any". My port poll then did not see the port node disappear within 90 seconds (Task 4 saw it go and return in 38 s); after the wait and six more seconds, the first command was `sr screen`:

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 202, dropped: 0, announcements: 2
speech: idle, queued 0, speaker held: no, utterances 0, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 0 ms played, 0 subsamples, 0 ms nominal, worker stack free 2804
free heap: 115640
```

No crash popup. Because the poll had not seen the reboot, I proved the image is the new one before verifying: `info device` reports `firmware.commit.hash: b459f870` (the Task 5 image, flashed before its commit, reported 5cea830f) and `firmware.commit.dirty: true`, and the new `sr say` message appears (A below), which only this build prints.

### A: sr say with 200 characters (new image, speech after the flash)

```
== sr say The device reads a long line of words to check the cut message and the queued count. The device reads a long line of words to check the cut message and the queued count. The device reads a long line o
queued 159 of 200 characters, cut; sr status shows the timing when it is done
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 381, dropped: 0, announcements: 2
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 10259 ms played, 408040 subsamples, 7187 ms nominal, worker stack free 2404
free heap: 115328
```

### B: NFC-V emulation with three sentences, leave, speak

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== loader open NFC /ext/nfc/sr_nfcv_test.nfc

== sr screen
records: 4, content layer: fullscreen
fullscreen   x= 66 y= 30 primary    "Emulating"
fullscreen   x= 51 y= 40 secondary  "ISO15693-3 (Unk"
fullscreen   x= 75 y= 50 secondary  "nown)?"
fullscreen   x= 61 y= 60 secondary  "sr_nfcv_test?"
reads as: Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?
== sr say The quick brown fox jumps over the lazy dog while the sun sets slowly behind the distant purple mountains.
queued 106 characters; sr status shows the timing when it is done
== sr say A gentle river winds through the quiet valley where tall pines whisper softly in the cool evening breeze.
queued 105 characters; sr status shows the timing when it is done
== sr say Bright lanterns swing above the crowded market square as merchants call out the prices of fresh bread.
queued 102 characters; sr status shows the timing when it is done
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 385, dropped: 0, announcements: 3
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 3, underruns 0, queue dropped 0
last utterance: 10259 ms played, 408040 subsamples, 7187 ms nominal, worker stack free 2404
free heap: 26072
== sr screen
records: 4, content layer: fullscreen
fullscreen   x= 66 y= 30 primary    "Emulating"
fullscreen   x= 51 y= 40 secondary  "ISO15693-3 (Unk"
fullscreen   x= 75 y= 50 secondary  "nown)?"
fullscreen   x= 61 y= 60 secondary  "sr_nfcv_test?"
reads as: Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?
== input send back short

== sr screen (home after 1 back presses)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== sr say A gentle river winds through the quiet valley where tall pines whisper softly in the cool evening breeze.
queued 105 characters; sr status shows the timing when it is done
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 405, dropped: 0, announcements: 5
speech: idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 3, underruns 0, queue dropped 0
last utterance: 7803 ms played, 310000 subsamples, 5475 ms nominal, worker stack free 2404
free heap: 114768
```

The three sentences sent one second apart while the listener held the timer were all refused and counted (dropped 1 to 3, utterances unchanged), no crash, the app stayed on the emulation screen, one Back press returned to the home screen, and the next sentence played (utterances 2, 7803 ms, underruns 0).

### C: speech first, then NFC-V emulation (the order that crashed)

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== sr say The quick brown fox jumps over the lazy dog while the sun sets slowly behind the distant purple mountains.
queued 106 characters; sr status shows the timing when it is done
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 408, dropped: 0, announcements: 5
speech: speaking, queued 0, speaker held: yes, utterances 3, aborted 0, dropped 3, underruns 0, queue dropped 0
last utterance: 7803 ms played, 310000 subsamples, 5475 ms nominal, worker stack free 2404
free heap: 115288
== loader open NFC /ext/nfc/sr_nfcv_test.nfc

== sr screen
records: 4, content layer: fullscreen
fullscreen   x= 66 y= 30 primary    "Emulating"
fullscreen   x= 51 y= 40 secondary  "ISO15693-3 (Unk"
fullscreen   x= 75 y= 50 secondary  "nown)?"
fullscreen   x= 61 y= 60 secondary  "sr_nfcv_test?"
reads as: Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 410, dropped: 0, announcements: 6
speech: idle, queued 0, speaker held: no, utterances 3, aborted 0, dropped 3, underruns 0, queue dropped 0
last utterance: 8252 ms played, 346240 subsamples, 5651 ms nominal, worker stack free 2404
free heap: 26320
== input send back short

== sr screen (home after 1 back presses)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== sr say Bright lanterns swing above the crowded market square as merchants call out the prices of fresh bread.
queued 102 characters; sr status shows the timing when it is done
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 430, dropped: 0, announcements: 8
speech: idle, queued 0, speaker held: no, utterances 4, aborted 0, dropped 3, underruns 0, queue dropped 0
last utterance: 7518 ms played, 309320 subsamples, 5174 ms nominal, worker stack free 2404
free heap: 114824
```

Same sequence as the crash, no crash: the sentence played to the end (8252 ms, aborted 0, the same 8252 ms it takes with no NFC app, see D), the listener's acquire waited for the release and the emulation screen was up nine seconds later, one Back press left the app, and speech played afterwards.

### D: NFC main menu with speech, leave, speak

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== loader open NFC

== sr screen
records: 4, content layer: fullscreen
fullscreen   x=  6 y= 12 secondary  inverted FOCUS 1/6 "Read"
fullscreen   x=  6 y= 28 secondary  "Extract MFC Keys"
fullscreen   x=  6 y= 44 secondary  "Saved"
fullscreen   x=  6 y= 60 secondary  "Extra Actions"
reads as: Extract MFC Keys. Saved. Extra Actions. Read, 1 of 6
== sr say A gentle river winds through the quiet valley where tall pines whisper softly in the cool evening breeze.
queued 105 characters; sr status shows the timing when it is done
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 433, dropped: 0, announcements: 9
speech: idle, queued 0, speaker held: no, utterances 5, aborted 0, dropped 3, underruns 0, queue dropped 0
last utterance: 7803 ms played, 310000 subsamples, 5475 ms nominal, worker stack free 2404
free heap: 37952
== input send back short

== sr screen (home after 1 back presses)
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== sr say The quick brown fox jumps over the lazy dog while the sun sets slowly behind the distant purple mountains.
queued 106 characters; sr status shows the timing when it is done
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 453, dropped: 0, announcements: 11
speech: idle, queued 0, speaker held: no, utterances 6, aborted 0, dropped 3, underruns 0, queue dropped 0
last utterance: 8252 ms played, 346240 subsamples, 5651 ms nominal, worker stack free 2404
free heap: 114664
```

Speech in the NFC main menu plays (utterances 5, not dropped), and again after leaving (utterances 6). Underruns stayed 0 throughout; dropped stayed at the 3 from B.

### Final state

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as: 
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 718, dropped: 0, announcements: 11
speech: idle, queued 0, speaker held: no, utterances 6, aborted 0, dropped 3, underruns 0, queue dropped 0
last utterance: 8252 ms played, 346240 subsamples, 5651 ms nominal, worker stack free 2404
free heap: 115264
```

## Host tests

`TMPDIR=<scratchpad>/t4b tools/run_host_tests.sh`, run once at the end, exit 0:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 94 checks, 0 failures
speech PCM: 647 checks, 0 failures
```

None of the three changed files is host tested; regression check only.

## Test file

Kept on the card as `/ext/nfc/sr_nfcv_test.nfc` (1157 bytes; `storage list /ext/nfc` shows it next to RickRoll.nfc). Reason: Task 6 announces the emulation screen at exactly the moment this fix covers, and the final whole branch review will want to repeat B and C; an NFC-V file is the only way to reach the ISO15693 listener without a real tag. It appears in the NFC app's Saved list under its own name. Remove with `storage remove /ext/nfc/sr_nfcv_test.nfc` when no longer wanted; the content is reproduced above.

For Task 6: the emulation screen as the screen model captures it reads "Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?" (the widget wraps "Unknown" across two lines and appends a question mark to the type and to the file name).

## Concerns

1. The brief's reproduction order (open, then say) cannot crash: the listener starts the signal reader once per `wait_event` with an infinite timeout, so the timer stays enabled for the whole emulation and speech refuses it. The crash is deterministic in the other order, which is what Task 6 will produce on every NFC-V emulation (the scene's announcement takes the speaker while the listener thread is starting), so the fix was required for Task 6 to be usable at all.

2. A listener that starts while speech holds the speaker now waits for the utterance to finish (`FuriWaitForever`): the emulation is delayed by up to the length of a full queue item (10.3 s for 159 characters at rate 72, measured in A), and a reader command in that window gets no answer. The NFC worker is blocked inside the mutex acquire, so `nfc_listener_stop` (abort flag plus thread join, on Back) also waits until the utterance ends. Task 6's key press stop shortens both to the stop latency; until it lands, pressing Back during a long announcement on the emulation screen waits for the announcement.

3. Stop flag placement: the clear is before `speech_queue_stop`. A stop request that lands in the microseconds between the clear and the queue drain is applied now and again after the next wait (dropping anything queued in between); clearing after the drain would instead lose such a request. Both windows are a few instructions plus a mutex acquire; I chose the placement that matches the two wait paths (consume, then apply).

4. During an NFC-V emulation the speaker pin sits on the timer alternate function with the main output disabled, high impedance with no pull, for the whole emulation rather than for the moments between a beep's stop and release. I could not listen for artefacts; if any are heard, `signal_reader_start` could put the pin back to analog right after the acquire (`furi_hal_gpio_init(&gpio_speaker, GpioModeAnalog, GpioPullDown, GpioSpeedLow)`, the same call the release makes), which the brief did not ask for.

5. The image on the device was built one comment wording earlier than the commit (code identical). If the controller wants the flashed image to be byte for byte the committed tree, one more `./fbt flash_usb` does it; I did not reflash to avoid another update cycle on the device.

6. The port poll after `./fbt flash_usb` never saw the /dev node disappear (90 s), unlike Task 4's 38 s observation, although the device clearly rebooted into the new image (commit hash and the new message). Either the reboot happened in the second between the fbt exit and the poll start with the node persisting through the updater, or the node is kept by macOS; harmless, but the "wait for the port to go and come back" loop is not a reliable flash detector on this machine. The `firmware.commit.hash` line of `info device` is.

7. Pre-existing and unchanged, outside the task: `signal_reader_start` reads `TIM16->CR1` before the timer is enabled (now before the acquire, previously before the bus enable) to build the DMA written CEN word, and `signal_reader_stop` never disables DMAMUX request generator 0.

8. `speech_take_speaker` uses `SPEECH_ACQUIRE_TIMEOUT_MS` of 500 ms, while the brief's interface text says 200 ms. The bus check in front of the acquire makes it moot for the listener case (refused at once, as B shows); not changed.

## Deviations from the brief

- Step 1 reproduced in both orders, the brief's (no crash, explained) and the reverse (the crash), one crash in total.
- The helper needed one fix mid run (catch termios.error on a port drop); the traceback above is from the helper, not the device.
- No other deviation. `loader close` was never sent; the device was left idle on the home screen.
