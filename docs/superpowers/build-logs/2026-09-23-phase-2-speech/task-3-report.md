# Task 3 report: speech queue and PCM stage

Status: DONE_WITH_CONCERNS. The code, the tests, the runner and the firmware build are all as the brief asked. Two things need the controller's attention: the project side commit was swept into another agent's commit, and one doc comment in the brief's header had to move to satisfy the firmware's formatter.

## Commits

Firmware, /Users/robin/Downloads/flipper-access/Momentum-Firmware, branch screen-reader:

- 8bdf14dd2bb3af77c87bda145973194181ef6aed "screen reader: speech queue and PCM stage". Four new files under applications/services/screen_reader: speech_queue.h, speech_queue.c, speech_pcm.h, speech_pcm.c. 224 insertions. Committed with a pathspec, so the other agent's uncommitted sam.c was not included; it is still modified in the working tree.

Project, /Users/robin/Downloads/flipper-access, branch main:

- There is no commit titled "host tests: speech queue and PCM stage". My three files are inside 6a119412bcde8c90459709d1bdbffaa166702bcb "Phase 2 plan: spelling by runs, dashes in mixed tokens, upper case A, text buffer 640", which another agent made at 18:31:23. Sequence: I staged tests/host/test_speech_queue.c, tests/host/test_speech_pcm.c and a runner blob equal to HEAD plus my appended block, and my commit command then stopped on a guard (a grep count of zero exits 1). Before I re-ran the commit, the other agent ran a plain git commit, which took everything in the shared index, including my three files. Verified afterwards: HEAD's two test files are byte identical to my working copies, HEAD's runner is exactly its parent plus my 20 appended lines (git diff --stat HEAD~1 HEAD -- tools/run_host_tests.sh: 20 insertions, 0 deletions), and git diff --stat 4ec82d5 6a11941 on my three paths shows 676 insertions and nothing else of mine. I did not rewrite the other agent's commit. If a dedicated commit is wanted, the controller can split 6a11941 (git reset --soft HEAD~1, then commit the plan document and my three files separately).

## Runner summary lines

Final run of tools/run_host_tests.sh with the private TMPDIR, exit 0:

- 98 checks, 0 failures (screen model)
- port checks: 0 failures
- SAM port matches the original on 11 cases
- speech text: 946 checks, 0 failures
- speech queue: 94 checks, 0 failures
- speech PCM: 647 checks, 0 failures

Step 2 was observed as the brief predicted: before the firmware files existed, the runner stopped at the new queue block with "no such file or directory: .../speech_queue.c", and compiling the two tests directly failed with "'speech_queue.h' file not found" and "'speech_pcm.h' file not found".

The two new blocks use the same CFLAGS as the rest plus -fsanitize=address,undefined -fno-sanitize-recover=all, redirect their output like the speech text block, and print "speech queue: ..." and "speech PCM: ..." summary lines. The PCM build links -lm.

## Firmware build

./fbt in Momentum-Firmware, exit 0, run twice: once after writing the code and once after the comment move described below (the second build recompiled only speech_queue.c). Both new sources appear as CC lines. The grep for error, warning and API version returns:

- fbt: warning: Failed parsing manifest '.../applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui' (pre-existing, external submodule, not touched)
- fbt: warning: Failed parsing manifest '.../applications/external/mtp/application.fam' : Invalid appid '.f0_mtp' (pre-existing, same)
- API version 87.1 is up to date

No warning or error comes from the screen reader sources. The firmware's flag set is -Wall -Wextra -Werror -Wredundant-decls -Wdouble-promotion -Wundef with -fsingle-precision-constant; the PCM code is all float with f suffixes and has no conditional macros. All four files also pass the toolchain's clang-format --dry-run --Werror (the firmware's lint step).

## Inconsistencies in the brief and how they were handled

Inside the brief itself I found none. I re-derived every expectation of the brief's PCM tests from the push loop by hand (5 slots for delta 160, 5 for 162, 0 for 4, 7 with 5 us overhead in the order 0 0 1 2 3 4 4, then 6 continuing from 125 us, 3 on abort) and the queue tests from the ring arithmetic; all match the given code.

Between the brief and the firmware's formatting rules: line 29 of the brief's speech_queue.h, the trailing doc comment on the generation member of SpeechQueue, is 108 columns wide, and the firmware's .clang-format has ColumnLimit 99, so ./fbt lint would reject it. clang-format's own reflow splits uint32_t from generation onto two lines, which reads badly. I moved the comment, with the same wording, onto the line above the member as an ordinary Doxygen block. No interface or arithmetic changed.

Between the brief and the controller's notes: the brief's runner snippet has no sanitizers and no summary lines, and its commit commands have no trailer; I followed the controller (sanitizers and summary lines, Co-Authored-By trailer, private TMPDIR).

## Tests beyond the brief

All expectations were derived from the brief's arithmetic before running anything.

Queue (tests/host/test_speech_queue.c):

- Exactly at capacity nothing is dropped; one over drops the oldest, counts one, and the remaining four pop in order; three more over counts three more and keeps the last four.
- Clearing a full queue by interrupt or by stop is not counted as a drop.
- The ring keeps order after the head has moved and the tail wraps; 100 push and pop rounds stay in order with no drops.
- Pop from an empty queue fails and leaves the output item untouched.
- Interrupt while empty bumps the generation and the popped item carries it; stop while empty bumps the generation too; an interrupting replaceable item on an empty queue is appended; an empty text is a valid item.
- Replaceable after non replaceable is appended in order; a non replaceable item never overwrites a replaceable tail; only the tail is considered, a replaceable item deeper in the queue stays; replacing at the tail of a full queue drops nothing; the replacement takes the current generation and flag and a shorter text leaves no remainder.
- A text of exactly 159 characters is kept whole; 160 is cut to 159 and stays terminated.

PCM (tests/host/test_speech_pcm.c):

- delta 0 with no overhead: nothing emitted, no time passes; delta 7 is still 0 us after the division by 8; delta 0 with 5 us overhead: the marks at 0 and 20 us see values 0 and 4, now_ns ends at 25 us, nominal time stays 0.
- Largest delta 65535: 8191 us per value, 40955 us in all, 2048 slots in runs of 410, 410, 409, 410, 409 (ceil(409.55 (k + 1)) minus ceil(409.55 k)); with 1 ms overhead 2298 slots and the same nominal 40955 us.
- Overhead 0 versus 100 us: 5 versus 30 slots (six per value), nominal 100 us in both; overhead 7 us gives 27 us per value and the order 0 0 1 2 2 3 4.
- Carry across pushes: 10,000 pushes with LCG deltas 0 to 4095, once with overhead 0 and once with 3300 ns. The emitted total equals ceil(total_ns / 20000) exactly, now_ns equals the summed time, next_slot_ns equals slots times 20000, and the total is within one slot of the time. With 3300 ns the per push time is never a multiple of the slot, so an implementation that reset its phase at each push would emit about one extra slot per push and fail this.
- Volume 0: all 256 entries equal the silence value 127 and a push emits only silence. Volume 100: the ends clip to 0 and 255, silence equals the demo curve at 128, and 200 and 255 give the same table as 100. The table is non decreasing at 0, 25, 50, 75 and 100. A volume change leaves the timing state alone and the next push uses the new table, which pulls both the loud and the quiet value toward the middle.
- Emit returning false: at the first mark nothing is sent or counted; at the fourth of seven marks with 5 us overhead the push stops with three sent, slots 3, the third byte is value 1, next_slot_ns 60 us and now_ns 50 us; a push with no mark to emit cannot be refused; after reset the counters are zero, the table and overhead are kept, and a willing emitter gets all seven marks.

## Concerns for the controller

1. Commit sweep in the project repository, described above. In a shared working tree a plain git commit takes whatever anyone has staged. The pathspec form (git commit -m ... -- paths) or a private GIT_INDEX_FILE avoids this; I used the pathspec form for the firmware but the project side was hit from the other direction. Worth telling every agent working in these trees.
2. Not mine and still uncommitted in the project tree: the perl alarm hunk in tools/run_host_tests.sh (6 insertions, 2 deletions around the SAM steps) and tests/host/test_sam_port.c. They presumably belong to the SAM agent. My runner commit deliberately left them out.
3. The silence duty depends on the volume: speech_pcm_silence() is lut[128], which is 129 at volume 100, 128 at 50 and 127 at 0, because 128/255 sits just above the curve's middle. That is the brief's own expectation, but the driver should re-read the silence value after every volume change so the idle level and the utterance level agree.
4. After speech_pcm_push returns false, now_ns stays at the end of the last completed value while next_slot_ns has advanced; the brief's design expects speech_pcm_reset before the next utterance, which the queue's generation bump gives a natural place for. The integrator (Task 4 or later) should make sure of that call.
5. hold_ns is 32 bit: (65535 / 8) * 1000 = 8,191,000 ns plus the overhead, so the overhead must stay below about 4.28 seconds. Not a practical limit; noted for completeness. The running clocks are 64 bit.
6. The two manifest warnings from applications/external are pre-existing and unrelated to this task.

## Verification commands

- TMPDIR=/private/tmp/claude-501/-Users-robin-Downloads-flipper-access/7e5c805a-c471-4df7-96ca-14e7ee87ded9/scratchpad/t3 tools/run_host_tests.sh
- cd Momentum-Firmware && ./fbt (output grepped for error, warning, API version)
- Momentum-Firmware/toolchain/current/bin/clang-format --dry-run --Werror on the four new files
