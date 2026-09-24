# Task 1 report: input filter hook and chord state machine

Status: DONE_WITH_CONCERNS. The code works and all checks pass. The concerns are about how Task 2 uses the hook, and about three places where I departed from the brief on purpose.

## Commits

- Firmware, branch screen-reader, base d5b77c219:
  - 90a32bf70 "input: filter hook before every published event". Files: input.h, input.c, input_cli.c, targets/f7/api_symbols.csv.
  - 0e14b0701 "screen reader: chord state machine". Files: sr_chords.h, sr_chords.c.
- Project, main, base 6d2cda2:
  - cc6c6e6 "host tests: chords". Files: tests/host/test_sr_chords.c, tools/run_host_tests.sh.
- Nothing was pushed. The applications/external submodule was not touched: its "modified content" state was already there before I started.
- The device was not flashed or touched.

## Host runner

The runner was run from the project root with TMPDIR set to the scratchpad p3t1 folder.

Test-first run, with the test, header and runner block in place but no sr_chords.c. The earlier blocks pass, then the chord block fails to compile as required (runner exit 1):

    speech voice: 4433 checks, 0 failures
    clang: error: no such file or directory: '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/services/screen_reader/sr_chords.c'

Final run (exit 0):

    98 checks, 0 failures
    port checks: 0 failures
    SAM port matches the original on 11 cases
    speech text: 1006 checks, 0 failures
    speech queue: 115 checks, 0 failures
    speech PCM: 700 checks, 0 failures
    speech voice: 4433 checks, 0 failures
    chords: 58 checks, 0 failures

The 58 checks match the CHECK count in the brief's test: 5, 3, 7, 11, 10, 7, 7 and 8.

The host build does not see the firmware headers. It gets only -I for the screen_reader folder, so `__has_include(<input/input.h>)` is false and the header uses its own enums. The preprocessor output shows SR_CHORDS_HAVE_INPUT undefined on the host.

The firmware build does take the real input.h. I preprocessed sr_chords.c with the command from fbt's compile_commands.json: SR_CHORDS_HAVE_INPUT and RECORD_INPUT_EVENTS are both defined. So Task 2 can include both headers without redefining InputKey.

## Build, lint, headroom

### ./fbt

The final tree (after both firmware commits) builds with exit 0. The only messages are the two known manifest warnings (cli_bridge `.cli_gui`, mtp `.f0_mtp`) and "API version 87.1 is up to date". The log also shows `CC applications/services/screen_reader/sr_chords.c`.

The first build after adding the declarations stopped on purpose: "API version is still WIP: 87.1 ... SDK version is not finalized". input.h is an SDK header (`sdk_headers=["input.h"]`), so fbt added the two new functions to targets/f7/api_symbols.csv with status "?" and waited for them to be marked. I marked them as follows (more under Deviations):

    Function,+,input_publish_event,void,"FuriPubSub*, InputEvent*"
    Function,-,input_set_filter,void,"InputFilterCallback, void*"

fbt's csv writer rewrote the whole file with CRLF line endings. The repo's .gitattributes normalises to LF anyway, and I converted the working copy back to LF, so the commit changes only those two lines. The version stays 87.1. Task 4's planned bump to 87.2 will cover these additions too.

### The console plugin

The input console command is a plugin (cli_input, a FAL on the SD card). Plain `./fbt` does not rebuild it: its .fal was still dated Sep 22. So I built it on its own with `./fbt fap_cli_input`. It passed with exit 0, "API version 87.1 is up to date", and APPCHK showed no "Symbols not resolved" warning. `arm-none-eabi-nm -u` shows that it now imports input_publish_event. It still uses furi_pubsub_publish for the ascii events.

### ./fbt lint

Exit 0, both after step 1 and after step 3.

### tools/flash_headroom.sh

    firmware.bin 872240 bytes, limit 880640, spare 8400 bytes

For comparison I rebuilt base d5b77c219, with the step 1 files stashed by pathspec and then restored byte for byte. It gave 872048 bytes, spare 8592. So:

- The filter hook costs 192 bytes.
- The chord files cost nothing yet. Nothing calls them, so the linker drops them.

## How event_pubsub reached the timer callback

It already did: no file-scope move was needed. `event_pubsub` is a local of input_srv, but the service loop copies it into every `InputPinState.event_pubsub`. The press timer gets its pin state as its context, so the Long and Repeat sites now call `input_publish_event(input_pin->event_pubsub, &event)`. The Short and Press/Release sites call `input_publish_event(event_pubsub, &event)`.

## Deviations and why

The public interface is exactly the brief's:

- `InputFilterResult`
- `InputFilterCallback`
- `input_set_filter`
- `input_publish_event`
- `SrChordCommand`, `SrChords`, `sr_chords_init`, `sr_chords_feed`

The test, sr_chords.h and sr_chords.c are the brief's code. I extracted them from the brief by script and compared them byte for byte. The only change is clang-format wrapping the two long host enum lines in sr_chords.h, which lint requires.

The changes are all inside input.c, plus the doc comments.

### 1. The filter runs under its own mutex, not lock-free

The brief's input_publish called the filter with no lock. The spec and the brief's doc comment say "under the pubsub mutex". That is not what the brief's code did: FuriPubSub's mutex is private and is taken inside furi_pubsub_publish.

Two concrete races follow from the lock-free version:

- Two filter calls at once. The timer service thread (TimersSrv) runs Long and Repeat at FreeRTOS priority 2 (configTIMER_TASK_PRIORITY in FreeRTOSConfig.h). The input service thread runs at FuriThreadPriorityNormal, 16. So the service loop can preempt a Back Long filter call halfway through updating SrChords. That can happen exactly when a user presses a chord key about 300 ms into the Back hold. Console threads call the filter too.
- A crash on removal. The brief's input_set_filter wrote the context first, then the callback. On removal, a publisher could read the old callback and then the new NULL context. Task 2's filter dereferences its context, so that is a crash.

What I did:

- `static FuriMutex* input_filter_mutex` is allocated at the top of input_srv, before `furi_record_create(RECORD_INPUT_EVENTS, ...)`.
- input_publish_event holds it around the filter call only. input_set_filter holds it while swapping the callback and context.
- Once input_set_filter returns, the old filter is not running and will not run again, so its context may be freed.
- The mutex is released before publishing, so it never nests with the pubsub mutex. A subscriber could call input_set_filter without a lock-order deadlock.
- `volatile` is gone, because the mutex orders the accesses.

### 2. input_set_filter waits for the input service

It opens RECORD_INPUT_EVENTS first and closes it again at the end. The service allocates the mutex before it creates that record. So the reader can install the filter at any point in its startup, even before it opens the input record. Without this, a call made too early would furi_check at boot.

### 3. An emitted Long goes before a Release, not after it

gui.c (gui_input, lines 340-354) and view_dispatcher.c (view_dispatcher_handle_input, lines 277-291) both discard any event other than Press or Release for a key that is not held. They log it as "non-complementary input", and the key's Release clears its held bit. The state machine sets emit_long only on Back's Release. So with "right after the original", the delayed Back Long would never reach a view, and "Long on release" would silently do nothing.

input_publish_event now sends the Long:

- right before the event when the event is a Release, and right after it otherwise;
- alone when drop is set too.

It copies the event, so the Long keeps the press's sequence number. The Long does not pass through the filter. Spec section 17 still says "right after the original" and should be updated as built.

### 4. One publish function

There is no separate static input_publish. The public input_publish_event is the one path, used at the four sites and in fake_input. It checks its arguments with furi_check.

### 5. API table status

- input_publish_event is "+". The cli_input plugin is loaded from the card and resolves it through the API table. The brief called it public.
- input_set_filter is "-". The reader is a built-in service and links to it directly. There is a single filter slot: an external app that installed a filter could silently replace the reader's, and would leave a dangling callback after it exits. Switch it to "+" if an app should ever install one.

### 6. Doc comments

The comments in input.h and input.c describe the real lock, the threads involved (input service, timer service, console), and the Long ordering. They no longer say "under the pubsub mutex".

## Concerns for Task 2 and the controller

1. Task 2's filter comment says "under the pubsub mutex". It should say the calls are serialised by the input service's filter lock, and that they run on the input service, timer service or console threads. Task 2's filter:
   - must not block, including taking locks;
   - must not call input_set_filter, because the lock is not recursive and it would deadlock itself;
   - must not publish input events.

   Task 2's planned filter meets all three.
2. Task 2 step 4.3 ("input send back press, wait 0.5 s, input send back release", expecting the power-off dialog) cannot pass. fake_input has no press timer, so a console press followed later by a release never produces a Long for the filter to hold back. Use "input send back long" instead. fake_input then publishes Press, Long, Release: the filter drops the Long and emits it just before the Release, and views receive Press, Long, Release.
3. `input send` goes through the filter only once the rebuilt cli_input.fal is on the card, so Task 2 must flash with the card's resources (`./fbt flash_usb_full`, as the project does).
   - An old plugin on the card calls furi_pubsub_publish directly, so it bypasses the filter.
   - A new plugin on an old firmware would fail to load.
4. Two other publishers still bypass the filter:
   - rpc_gui.c, lines 268 and 522: remote control from qFlipper or the mobile app.
   - The reader's own sr_cli_press in screen_reader_cli.c, lines 324-334.

   Task 2 may want sr_cli_press to call input_publish_event, since it is built into the firmware and can call it directly.
5. Stack use. TimersSrv has 256 words (1 KB) and the input service has 1 KB, and the filter now runs on both. The extra input_publish_event frame is a few dozen bytes. The filter's own call chain (sr_input_filter, sr_chords_feed, furi_thread_flags_set) finishes before the publish, so it does not stack up with the subscribers. It is still worth checking both threads' stack watermarks on the device once Task 2 installs the filter.
6. By design (spec 17), Back Press passes before the chord key is known. Apps that act on Back Press rather than Back Short will still react at the start of a chord.
7. Pre-existing and unchanged: fake_input never sets the event's sequence field, so it is uninitialised.

## Fix round 1

### Commits

- Firmware 1f91f640f "screen reader: chord state trimmed; input filter comment". Files: sr_chords.h, sr_chords.c, input.c.
- Project 35dbf72 "host tests: slow chord and OK long sequences". File: tests/host/test_sr_chords.c.
- Nothing was pushed. The device was not touched.

### Checks

Host runner, with the private TMPDIR as before, exit 0:

    98 checks, 0 failures
    port checks: 0 failures
    SAM port matches the original on 11 cases
    speech text: 1006 checks, 0 failures
    speech queue: 115 checks, 0 failures
    speech PCM: 700 checks, 0 failures
    speech voice: 4433 checks, 0 failures
    chords: 73 checks, 0 failures

- `./fbt`: exit 0. Only the two known manifest warnings and "API version 87.1 is up to date".
- `./fbt lint`: exit 0. The test file is also clean under the firmware's clang-format style.
- `tools/flash_headroom.sh`: "firmware.bin 872240 bytes, limit 880640, spare 8400 bytes", unchanged.

### Item 1: the two new tests

test_chord_after_back_long uses the sequence you asked for:

- Back Press 0.
- Back Long 300, dropped.
- Back Repeat 450, dropped.
- Up Press 500, which returns ReadAll and is dropped.
- Up Release 600, dropped.
- Back Release 700, which passes with no Long emitted.

I added two events the device also sends at 600: the Up Short (input.c publishes it before the Release of a 100 ms press) and a Back Repeat. Both are dropped.

test_chord_ok_long_then_short uses:

- Back Press 0.
- OK Press 100, dropped.
- OK Long 400, which returns Spell and is dropped.
- OK Short 450, which returns None and is dropped.
- OK Release 500, dropped.
- Back Release 600, which passes with no Long emitted.

I added Back Long 300 (dropped, no Long kept): Back is held for 600 ms, so the device sends it. A comment notes that input.c never sends a Short after a Long, so the ok_long_seen guard is defensive.

To make sure the new tests catch real bugs, I ran them against altered copies of sr_chords.c in the scratchpad:

- Removing the `!ok_long_seen` guard fails the new OK test at line 109.
- Removing both guards that stop a chord from emitting an earlier Long (`long_pending = false` at the chord start and `!chord_used` at the release) fails the new slow chord test at line 99. The brief's 58 checks passed that broken copy.
- Removing just one of those two guards changes nothing: either one alone is enough.

### Item 2: a Back Short at 1000 cannot happen either

The requested rewrite keeps a Back Short at 1000 after a Back Press at 0. input.c cannot send that: it publishes a Short only when the key is released before 300 ms, which is when the second 150 ms timer tick would publish the Long.

So test_chord_up_and_down now holds Back for 280 ms:

- Back Press 0.
- Up Press 100, which returns ReadAll and is dropped.
- Up Short and Up Release 150, dropped.
- Down Press 200, which returns Status and is dropped.
- Back Short 280, dropped.
- Back Release 280, which passes with no Long emitted.

Down stays held after Back is released, so its Long 500, Repeat 650 and Release 700 checks are kept, all dropped.

The old test also checked that Back's Long after a chord is dropped. That check moved to test_chord_ok_short_and_long, which had the same flaw: a Back Short at 1100 after an 1100 ms hold. That test now gets Back Long 300 and Back Repeat 450, both dropped with no Long kept, and ends with Back Release 1100, which passes with no Long emitted.

The other tests leave out some Back Long or Repeat events, but contain nothing input.c cannot send, so I left them as they were. The check count went from 58 to 73.

### Item 3: unused threshold and timestamp removed

`SR_CHORD_LONG_MS` and `back_down_ms` are removed. `now_ms` is kept and documented in the header as reserved: the machine keeps no time of its own. sr_chords.c casts it to void. The file comment now says the input service applies the 300 ms threshold before the Long arrives.

### Item 4: lock comment

The comment in input.c now says the publishing threads can preempt one another whatever their priorities. The timer service runs at 2, or at 31 while an app such as NFC or Bad USB raises it through furi_timer_set_thread_priority (archive, nfc and bad_usb call it). The mutex serializes the filter calls, with priority inheritance lending a waiting thread's priority to the holder.

### Concerns

None new. The Task 2 notes in the concerns section above still stand, most importantly the `input send back long` point for step 4.3.
