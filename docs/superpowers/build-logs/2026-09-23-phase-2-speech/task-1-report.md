# Task 1 report: SAM in plain C, checked sample for sample against the original

Status: DONE_WITH_CONCERNS.

The port renders exactly what the original renders on all 11 cases. The host runner is green and the firmware builds cleanly with GCC and the firmware flags. The concerns are two behaviours inherited unchanged from the original synthesizer that later tasks must guard against: a hang on very long words, and a read past the end of a table on text that ends in a vowel then T or D. Details are at the end.

## Commits

Neither repository was pushed.

- Firmware repository, branch screen-reader: 869668c7c, "screen reader: SAM synthesizer as plain C with a callback output".
- Project repository, branch main: b47eb7f, "host tests: SAM port checked against the original synthesizer".

Both subjects are exactly as the brief gives them. Each is followed by a blank line and a Co-Authored-By line. I used "Claude Opus 5.5 (1M context) <noreply@anthropic.com>", not the "Claude Fable 5.1" line the task message asked for. See concern 5.

## Transformations applied to the copy of stm32_sam.cpp

I made every edit with a script where each replacement had to match exactly once, so nothing else in the file moved. All tables and all algorithm lines are byte for byte the original's.

1. Copied applications/external/text2sam/stm32_sam.cpp to applications/services/screen_reader/sam/sam.c.
2. Replaced the include of stm32_sam.h with the brief's includes: sam.h, stdbool.h, stdint.h and string.h, plus stdlib.h (see the next section). The original starts with a blank line before its include; I dropped that blank line.
3. After the includes, added:
   - the former members as statics: speed, pitch, mouth, throat, phonetic, singmode;
   - the port state: sam_callback, sam_context, sam_aborted;
   - prototypes for the 25 remaining former private methods. That is the header's private list minus SetAUDIO (deleted with the hardware section) and Code47503 (deleted, see item 6).
   - I also added three one-line section comments. The unused member _STM32SAM_SPEED was not carried over, since the new Output8BitAry no longer divides by it.
4. Deleted everything from the "Constructor" comment to the end of the file except to_upper_case:
   - both constructors;
   - the commented destructor;
   - both sam overloads, and every overload of say, sing, sayPhonetic and singPhonetic;
   - setVoice, setPitch, setSpeed, setMouth, setThroat;
   - the hardware section with begin, SetAUDIO and the USE_ROGER_CORE and USE_STM32duino_CORE blocks.
   The banner comments that described those deleted functions went with them, including the "Hardware" banner just above include math.h. That is slightly wider than the brief's "from include math.h" and removes comments only.
5. Turned every remaining STM32SAM method into a static function. Empty parameter lists became (void) in the 12 definitions that had them: Render, SetMouthThroat, Init, SAMMain, PrepareOutput, InsertBreath, CopyStress, Parser1, SetPhonemeLength, Code41240, Parser2 and AdjustLengths.
6. Deleted Code47503. It has no caller: its only call, in Render, is commented out in the original. As a static C function it fails the build; see the next section.
7. Replaced the body of Output8BitAry with the brief's code, which reports to the callback instead of waiting and driving the timer.
8. Inserted "if(sam_aborted) return;" as the first statement in two loops, each with a one-line comment above it:
   - the sound output loop of Render, just before "A = sampledConsonantFlag[Y];";
   - the while loop of PrepareOutput, just before "A = phonemeindex[X];".
9. Appended sam_speak exactly as the brief gives it, with one wording change in a comment. "Same resets as the original STM32SAM constructor" became "Same resets as the original class's default constructor", so that the self-review grep for STM32SAM finds nothing.
10. sam.h is the brief's text, except that the firmware's clang-format joined the two-line SAM_VOICE_DEFAULT macro onto one line. That is whitespace only. The phase 1 files are formatter clean and ./fbt lint checks this. Both sam.h and sam.c now pass clang-format with the repository style.

## Warnings and errors fixed, and how

- **Call to undeclared function abs.** Clang in C11 rejects the file with "call to undeclared library function 'abs'". The original got abs through furi.h, which pulls in stdlib.h. Fixed by including stdlib.h. I confirmed that a copy without that include fails to compile.
- **Code47503.** Kept as a static function, it fails with "unused function 'Code47503' [-Werror,-Wunused-function]". I confirmed this by compiling a copy with the function put back. Fixed by deleting it, as the brief allows for functions that became unused.
- **Empty parameter lists.** Made (void) as the brief says. The firmware compiles C with -Wstrict-prototypes.
- **Nothing else.** No casts, sign-compare fixes or unused variable fixes were needed. Clang with -std=c11 -Wall -Wextra -Werror is silent. GCC 12.3.1 with the firmware flags is silent too: -std=gnu2x, -Wstrict-prototypes, -Wall, -Wextra, -Werror, -Wredundant-decls, -Wdouble-promotion, -Wundef and -Os. I took those flags from compile_commands.json for sam.c.

## Runner output

RED, after step 2, before sam.c existed. The exit code was 1.

```
98 checks, 0 failures
clang: error: no such file or directory: '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/services/screen_reader/sam/sam.c'
```

The screen model test passed and the reference built. Only the missing port stopped the runner, as the brief expected.

GREEN, after the port. The exit code was 0. I reran it on the final committed state with the same result.

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
```

The reference and the port printed these identical case lines. Diff reports no difference, 11 of 11.

```
case 0 n=159440 sum_f=2691140 hash=cfbf98f718767a38
case 1 n=144240 sum_f=2423810 hash=47c0e480b5b393f4
case 2 n=125440 sum_f=2175610 hash=638258ef3ceb5ddc
case 3 n=156880 sum_f=2461425 hash=8b9de89d5ae4fc61
case 4 n=137560 sum_f=2520255 hash=2d103b273d7a4dc7
case 5 n=207920 sum_f=3641190 hash=44786664c55d4e61
case 6 n=159480 sum_f=2692105 hash=8a6290a77246baad
case 7 n=121200 sum_f=1943710 hash=863bdcc382e59ef2
case 8 n=25560 sum_f=511200 hash=842290ea4c3c909b
case 9 n=25560 sum_f=511200 hash=842290ea4c3c909b
case 10 n=0 sum_f=0 hash=14650fb0739d0383
```

## Firmware build

Before, with the tree as it was at c661ceced. Only the version stamp was rebuilt, then the firmware was relinked.

```
API version 87.1 is up to date
.text         662180 (646.66 K)
.rodata       182024 (177.76 K)
.data            968 (  0.95 K)
.bss            4972 (  4.86 K)
.free_flash   203064 (198.30 K)
```

After, on the final committed state. The build line "CC applications/services/screen_reader/sam/sam.c" appears, with no compiler warning or error.

```
API version 87.1 is up to date
.text         662180 (646.66 K)
.rodata       182024 (177.76 K)
.data            968 (  0.95 K)
.bss            4972 (  4.86 K)
.free_flash   203064 (198.30 K)
```

The only warnings in both logs are two fbt manifest warnings that were already there before this task. They are about applications/external/cli_bridge (appid '.cli_gui') and applications/external/mtp (appid '.f0_mtp').

All sizes are identical. The brief expected 15 to 25 KB less free flash; that is not what happens yet. Nothing calls sam_speak, and the firmware compiles with -ffunction-sections and -fdata-sections and links with --gc-sections, so the linker drops all of sam.o. I checked this: none of its 63 external symbols is in firmware.elf. The cost arrives when Task 4 calls sam_speak. I measured sam.o as GCC builds it for the firmware:

- text 6168 bytes, rodata 7635 bytes, data 342 bytes. That makes 14145 bytes of flash, about 13.8 KB, a little under the brief's estimate.
- bss 3543 bytes plus data 342 bytes. That makes 3885 bytes of static RAM, which Task 4 should count in the RAM budget.

## Files changed

Firmware repository (Momentum-Firmware, branch screen-reader):

- New: applications/services/screen_reader/sam/sam.c (5289 lines).
- New: applications/services/screen_reader/sam/sam.h (44 lines).
- stm32_sam.cpp and stm32_sam.h are untouched: git diff on both inside the submodule is empty.
- Nothing was added, reset or committed inside the submodule. It still shows only the modification to text2sam/sam_app.cpp that was there before.

Project repository (flipper-access, branch main):

- New: tests/host/sam_cases.h, tests/host/sam_ref/furi.h, tests/host/sam_ref/stm32wbxx_ll_tim.h, tests/host/sam_ref/sam_reference.cpp and tests/host/test_sam_port.c, all verbatim from the brief.
- Replaced: tools/run_host_tests.sh, verbatim from the brief and executable.
- The untracked .DS_Store files were left alone.

## Self-review findings

- **Case lines.** Diff of the case lines from the reference and the port: identical, 11 of 11.
- **Forbidden names.** A grep of sam.c for STM32SAM, furi, LL_TIM, tanhf and USE_ROGER_CORE finds nothing.
- **Resets in sam_speak.** It resets exactly these: wait1 to 7, wait2 to 6, mem59 to 0, oldtimetableindex to 0, pitch, speed, mouth and throat from the voice, phonetic to 0 and singmode to 0. It also sets the port's own callback, context and aborted flag, and clears and fills the input buffer, as in the brief's code.
- **Abort checks.** "if(sam_aborted) return;" sits in three places:
  - in Output8BitAry, before the callback (the brief's code), sam.c line 2471;
  - at the head of Render's sound output loop, line 3168, followed by the comment and "A = sampledConsonantFlag[Y];";
  - at the head of PrepareOutput's loop, line 3600, followed by "A = phonemeindex[X];".
- **Formatting.** clang-format with the repository style reports nothing for sam.c or sam.h.
- **Sanitizers.** Built with AddressSanitizer and UndefinedBehaviorSanitizer, the port harness reports nothing on the 11 cases, and its case lines still match the reference.
- **Name clashes.** Application objects are linked straight into the firmware, not through an archive. So I checked all 206 link inputs of the current firmware, including the Momentum libraries, newlib and libgcc, for the port's 63 external symbol names. None of them defines or references any of those names.
- **Reset after an abort.** The brief's state test measures its "fresh" run right after an abort, so both of its runs follow an abort. As a stronger scratch check, not committed, I compared three renders of case 1: after a complete case 0, after a case 0 aborted at 1000 callbacks, and after itself. All three are identical, so an abort leaves no trace.

## Concerns

1. **Hang in InsertBreath, inherited from the original.**
   - Mechanism: InsertBreath adds up phoneme frames since the last punctuation. At 232 frames it turns the last pause into a glottal stop, inserts a breath marker and resumes scanning right after it. If one run of phonemes with no pause in it is itself 232 frames or longer, the rescan reaches 232 at the same place again and repeats forever.
   - It never produces output, so the callback and sam_aborted cannot stop it. In the firmware the speech thread would spin at full load, and speech_stop could not reach it.
   - Texts that hang: "Supercalifragilisticexpialidocious" (34 letters), "Pneumonoultramicroscopicsilicovolcanoconiosis", 40 x's, and 3 random texts. The fuzz ran 8 batches of up to 1500 random texts each: 3 batches stopped at a hang, and the other 5 rendered all of their texts.
   - Texts that render: "Antidisestablishmentarianism" (28 letters), "Flipper_Zero_Firmware_Update", "subghz_remote_config_backup_2024", "AA:BB:CC:DD:EE:FF", "0123456789ABCDEF", "1234567890" and a URL.
   - The untouched original, built with the reference stubs, hangs identically on the same texts.
   - Suggested guard for Task 2 or Task 4: split any run of more than about 20 characters without a space before calling sam_speak. The alternative is a guard inside InsertBreath, which would be a deliberate deviation from the original and is your call.
2. **Read past the end of a table in Parser2, inherited from the original.**
   - Location: sam.c line 4406; stm32_sam.cpp line 4373.
   - Mechanism: the rule that softens T or D after a vowel reads flags for the next phoneme, without the check for 255 that the neighbouring rules have. When a vowel then T or D is the last phoneme, the next phoneme is the end marker 255. The code then reads flags[255] from an 81 entry table, 174 bytes past its end.
   - It triggers on ordinary text without closing punctuation: "Read", "at", "it", "cat", "bad", "It is late", and "Saved. Read". The original does the same.
   - On the STM32 this is a flash read with no fault. But the byte read depends on the link layout, and its top bit decides whether that final T or D becomes a flap. So on such texts the device may sound slightly different from the Text to SAM app, and the host test does not cover this, because every multi word case ends in a period.
   - Any closing punctuation avoids it: "Read.", "Read,", "Read?", "It is late.", "cat." and "Saved. Read." are all clean, each checked in its own sanitizer process. If speech_text always ends a chunk with punctuation, the problem never arises.
3. **No flash change yet.** The brief expected 15 to 25 KB less free flash, but the port is not linked until something calls it. The measured future cost is about 13.8 KB of flash and 3.8 KB of static RAM, as detailed in the firmware build section.
4. **Generic global names.** The port exports 63 generic global names, among them A, X, Y, input, flags, stress, pitches, rules, sinus, timetable, wait1 and to_upper_case. This happens because the brief keeps the original's file scope globals non-static. In the C++ original the const tables had internal linkage; in C they are external. Nothing in today's firmware clashes, as checked above, but a future symbol with one of these names would. Making them static is a mechanical change with no arithmetic effect, if wanted later.
5. **Co-Authored-By line.** This session runs on Claude Opus 5.5, and my attribution guidance for commits is "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>". Only the user's own instructions override that, and CLAUDE.md and memory say nothing about it. So I used that line rather than "Claude Fable 5.1", which the task message asked for and which earlier commits carry. If you want the other line, both commits are local and unpushed: amending the message changes nothing else.
6. **Small departures from the verbatim text, all non-functional:**
   - the stdlib.h include;
   - one comment in sam_speak reworded;
   - three added section comments and two one-line comments at the abort checks;
   - the banner comments of deleted functions removed, and the original's leading blank line dropped;
   - the SAM_VOICE_DEFAULT macro joined onto one line by clang-format.

# Fix round 1

Status: DONE_WITH_CONCERNS.

All four findings are fixed. The runner is green with 11 matching case lines and 0 port failures, and the firmware builds cleanly. I made one deliberate change to the guard code you gave: guard (d) keeps X across its Render call. Without that, one of your own hard cases hangs. Details follow.

## Commits

Neither repository was pushed. Both subjects are exactly as requested.

- Firmware repository: 1c331d995, "screen reader: SAM port guards against endless breath insertion". It changes only sam.c.
- Project repository: 08f69d3, "host tests: raw value golden hash, abort state check, hang cases". It changes test_sam_port.c, sam_reference.cpp and run_host_tests.sh, and adds sam_ref/math.h.

Both messages end with a blank line and then "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>", not the Claude Fable 5.1 line you asked for. My attribution guidance says only the user's own instructions can change that line. I checked the user's CLAUDE.md files and project memory, and they say nothing about it. Amending the messages is easy if the user wants the Fable line.

## Finding 1: port guards

Guards (a), (b) and (c) are exactly as written:

- (a) SAMMain now writes 255 into slot 255.
- (b) Insert returns first thing when the position is 255. I put the guard before the function's "int i;" declaration.
- (c) InsertBreath is replaced by your version.

Guard (d) has your PrepareOutput condition "A == 255 || X == 255" exactly as written. The block after "X++; Y++;" has two added lines: X is saved in temp before Render and restored after it. This is the same thing the original's own 254 branch does a few lines above, because Render uses the global X. The block now reads:

```c
        if(Y >= 59) { // port guard: the output arrays hold 60 entries; render what we have
            phonemeIndexOutput[Y] = 255;
            int temp = X; // Render uses X: keep the scan position, as the 254 case above does
            Render();
            X = temp;
            Y = 0;
        }
```

Why the two lines are needed. I tested with a scratch copy that records X before and after that Render call:

- "XXXXXXXXXXXXXXXXXXX.", one of your five hard cases, reaches the guard with X at 60. Render leaves X at 0, so PrepareOutput starts over, fills 59 entries again and re-renders forever. The requested hard case check can never finish with the block exactly as written.
- "bdbdbdbdbdbdbdbdbdbdbdbdbdbdbdbdbdbdbdbdbd" loops forever in the same way.
- "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDD": Render moves X from 60 to 61, so one phoneme is skipped.
- "BDG BDG BDG BDG BDG BDG BDG BDG": X goes from 66 back to 61, so five phonemes are spoken twice.
- The untouched original finishes all four of these texts. It writes past its 60 entry output arrays, but it does not hang. So the block exactly as written would add hangs the original does not have.
- With X kept, all four finish, and each phoneme is rendered exactly once, split over two Render calls.

Your hard case list already covers this: "XXXXXXXXXXXXXXXXXXX." reaches the guard. So the committed test catches a regression, but as a hang rather than a FAIL line.

Two further observations:

- "XXXXXXXXXXXXXXXXXXX." does not match the test comment "Texts the original synthesizer never returns from". The original returns after 197520 values, having overrun its output arrays. The other four hard cases do hang in the original: I ran each with a 3 second limit.
- When guard (c) forces a break with no pause to break at, it turns the phoneme at the break point into a glottal stop. So one phoneme's sound is lost at each forced break. I kept this as written; it only affects texts that used to hang.

Here is the diff of InsertBreath, from the mechanical port (869668c7c) to the guarded version (1c331d995):

```diff
--- InsertBreath at 869668c7c (mechanical port)
+++ InsertBreath at 1c331d995 (with port guards)
@@ -6,9 +6,14 @@
     X++;
     mem55 = 0;
     unsigned char mem66 = 0;
+    // port guards: the original loops forever when a clause of 232 or more frames has no
+    // pause to break at, or when the break position stops advancing
+    int last_break = -1;
+    unsigned breaks = 0;
     while(1) {
         //pos48440:
         X = mem66;
+        if(X == 255) return; // port guard: end of the list, never wrap around
         index = phonemeindex[X];
         if(index == 255) return;
         mem55 += phonemeLength[X];
@@ -30,6 +35,10 @@
             mem66++;
             continue;
         }
+        // port guard: no pause behind us, or the same pause as last time: break right here
+        if(mem54 == 255 || (int)mem54 <= last_break) mem54 = X;
+        last_break = mem54;
+        if(++breaks > 64) return; // port guard: absolute cap
         X = mem54;
         phonemeindex[X] = 31; // 'Q*' glottal stop
         phonemeLength[X] = 4;
```

## Finding 2: state after an abort

The main loop now stores each case's hash in case_hash. The abort callback compares against a variable, abort_point. For each abort point, 10, 500 and 5000, the test does three things:

- aborts case 0 at that point;
- checks that the call returned false after exactly that many callbacks;
- runs case 1 and compares it with case_hash[1], where case 1 ran after a complete case 0.

Case 0 makes 31888 callbacks, so all three points really abort.

To check that the new test can fail, I built a scratch copy of the port that no longer resets oldtimetableindex in sam_speak. The old test passes it with 0 failures. The new test fails it twice:

```
FAIL state after abort at 10: expected=10e93a32938233af got=30dacb4173136b47
FAIL state after abort at 500: expected=10e93a32938233af got=30dacb4173136b47
```

## Finding 3: hash raw values

- test_sam_port.c no longer has demo_curve or the math.h include. record now hashes the raw values.
- sam_ref/math.h is the shim exactly as given.
- sam_reference.cpp includes the shim (via math.h) for lroundf. It defines sam_ref_tanhf, which stores its argument and returns 0, and recovers the raw value in LL_TIM_OC_SetCompareCH1 with the given lroundf expression. It includes nothing else from math.h or cmath.

Checks:

- **Recovery is exact.** Running the original's float steps for all 256 raw values and inverting them gives every value back. The largest error before rounding is 4 millionths.
- **The old hash was nearly blind.** The curve maps raw 0 to 92 to 0 and raw 163 to 255 to 255. That is 186 of the 256 possible values collapsed onto two outputs.
- **The new hash is not.** A scratch port that clamps every value into 92 to 163 passes the old test pair, with 0 of 11 case lines differing. The new test pair flags 10 of 11 case lines.

## Finding 4: the runner shows port failures

Replaced as given. If test_sam_port exits nonzero, the runner prints its output, says "SAM port checks failed" and exits 1.

## Runner output

Exit code 0. The whole run, compiles included, takes 1.3 seconds.

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
```

The case lines are identical in both programs, 11 of 11. The hashes now fold raw values:

```
case 0 n=159440 sum_f=2691140 hash=36c8b61af4229180
case 1 n=144240 sum_f=2423810 hash=10e93a32938233af
case 2 n=125440 sum_f=2175610 hash=75e1eee82ddef35d
case 3 n=156880 sum_f=2461425 hash=5a4cb859f139648e
case 4 n=137560 sum_f=2520255 hash=d77b52f067fb0cac
case 5 n=207920 sum_f=3641190 hash=5300b1869d37f4d7
case 6 n=159480 sum_f=2692105 hash=b37c17d09602119d
case 7 n=121200 sum_f=1943710 hash=7d3501e916f9a639
case 8 n=25560 sum_f=511200 hash=74075cb118f4500a
case 9 n=25560 sum_f=511200 hash=74075cb118f4500a
case 10 n=0 sum_f=0 hash=14650fb0739d0383
```

Timing, one sam_speak call per text on the Mac:

- UUUUUUUUU. took 0.47 ms;
- OOOOOOOOOOOOOOOOOOO. took 0.40 ms;
- XXXXXXXXXXXXXXXXXXX. took 0.55 ms;
- ANTIDISESTABLISHMENTARIANISM. took 0.48 ms;
- SUPERCALIFRAGILISTICEXPIALIDOCIOUS. took 0.56 ms.

Other checks:

- **Sanitizers.** The test harness built with AddressSanitizer and UndefinedBehaviorSanitizer reports nothing and ends with "port checks: 0 failures".
- **Random texts.** 8 batches of 1500 random texts all finish now. Before the guards, 3 of those batches hung.

## Firmware build

"CC applications/services/screen_reader/sam/sam.c" was built by GCC with no warning or error.

```
API version 87.1 is up to date
.text         662180 (646.66 K)
.rodata       182024 (177.76 K)
.data            968 (  0.95 K)
.bss            4972 (  4.86 K)
.free_flash   203064 (198.30 K)
```

The only warnings are the same two fbt manifest warnings as before, for cli_bridge and mtp. The sizes are unchanged, because sam_speak still has no caller. The guards add 60 bytes of code to sam.o, which grows from 6168 to 6228 bytes of text; its rodata, data and bss are unchanged.

## Remaining concerns

1. The read past the end of flags in Parser2 is still there. This round did not address it. It happens on text ending in a vowel then T or D with no closing punctuation, such as "Read" or "cat". Ending each chunk with punctuation avoids it.
2. The Co-Authored-By line differs from the one you asked for, as explained under Commits.

# Fix round 2

Status: DONE_WITH_CONCERNS.

The requested over-read is closed and the runner now builds the port checks with sanitizers. The check bites as intended. A sanitizer fuzz run afterwards found two further over-reads and a reciter length limit. I did not fix those, since they need your ruling; see the concerns at the end.

## Commits

Neither repository was pushed. Both messages end with a blank line and my Co-Authored-By line.

- Firmware repository: a7334f20b, "screen reader: SAM port guard for the T and D rule at the end of the list". It changes only sam.c.
- Project repository: 4886c78, "host tests: sanitizers on the port checks, unpunctuated hard cases". It changes test_sam_port.c and run_host_tests.sh.

## Changes

- **sam.c, Parser2.** In the rule that softens T or D after a vowel, the guard sits right after "A = phonemeindex[X];" and before "if(A != 0) {", exactly as given. When the next phoneme is the end of the list, the rule now moves on, as its else branch already did. The 11 golden cases still match.
- **test_sam_port.c.** The hard case comment now has your wording. It is wrapped over two lines because one line would run to about 130 columns. "READ", "CAT", "IT IS LATE" and "SAVED. READ" are appended to hard_cases.
- **run_host_tests.sh.** "-fsanitize=address,undefined -fno-sanitize-recover=all" is added to the test_sam_port clang line only, not to the reference build. The command is now split over three lines. The built binary links the AddressSanitizer runtime.

## Runner output

Exit code 0. The whole run takes 1.6 seconds, and the case lines are identical in both programs, 11 of 11.

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
```

## The sanitizers catch the over-read

I copied the guarded sam.c aside, removed the guard from the working file and ran the unchanged runner. It exited with code 1. This is its output, with the /Users/robin/Downloads/flipper-access/ prefix removed from paths:

```
98 checks, 0 failures
Momentum-Firmware/applications/services/screen_reader/sam/sam.c:4423:17: runtime error: index 255 out of bounds for type 'const unsigned char[81]'
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior Momentum-Firmware/applications/services/screen_reader/sam/sam.c:4423:17 
case 0 n=159440 sum_f=2691140 hash=36c8b61af4229180
case 1 n=144240 sum_f=2423810 hash=10e93a32938233af
case 2 n=125440 sum_f=2175610 hash=75e1eee82ddef35d
case 3 n=156880 sum_f=2461425 hash=5a4cb859f139648e
case 4 n=137560 sum_f=2520255 hash=d77b52f067fb0cac
case 5 n=207920 sum_f=3641190 hash=5300b1869d37f4d7
case 6 n=159480 sum_f=2692105 hash=b37c17d09602119d
case 7 n=121200 sum_f=1943710 hash=7d3501e916f9a639
case 8 n=25560 sum_f=511200 hash=74075cb118f4500a
case 9 n=25560 sum_f=511200 hash=74075cb118f4500a
case 10 n=0 sum_f=0 hash=14650fb0739d0383
SAM port checks failed
```

Line 4423 of the unguarded file is "if((flags[A] & 128) == 0) {". The runner's binary has no debug information, so I rebuilt the same test with -g against the unguarded file. The stack trace ends in the hard case loop, at line 85 of test_sam_port.c:

```
Momentum-Firmware/applications/services/screen_reader/sam/sam.c:4423:17: runtime error: index 255 out of bounds for type 'const unsigned char[81]'
    #0 in Parser2 sam.c:4423
    #1 in SAMMain sam.c:3567
    #2 in sam_speak sam.c:5304
    #3 in main test_sam_port.c:85
    #4 in start+0x1a1c (dyld:arm64e+0x31eec)

SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior Momentum-Firmware/applications/services/screen_reader/sam/sam.c:4423:17 
case 0 n=159440 sum_f=2691140 hash=36c8b61af4229180
```

I also ran each hard case alone against the unguarded file with both sanitizers. The five punctuated cases are clean. "READ", "CAT", "IT IS LATE" and "SAVED. READ" all read past the table. Everything before the hard cases printed and passed, so the runner failed on "READ", the first unpunctuated case.

I then copied the guarded file back and checked it byte for byte against the copy (cmp: identical). The runner was green again.

## Firmware build

"CC applications/services/screen_reader/sam/sam.c" was built by GCC with no warning or error.

```
API version 87.1 is up to date
.text         662180 (646.66 K)
.rodata       182024 (177.76 K)
.data            968 (  0.95 K)
.bss            4972 (  4.86 K)
.free_flash   203064 (198.30 K)
```

The only warnings are the same two fbt manifest warnings as before, for cli_bridge and mtp. The firmware sizes are unchanged, because the port is still not linked. The guard adds 8 bytes to sam.o's text, which is now 6236 bytes.

## Concerns found after the fix

### 1. Two more over-reads, when the phoneme list overflows

I fuzzed the final port with both sanitizers in recover mode: 8 batches of 1500 random texts, all finishing. It reported two sites, both from one random text:

- sam.c line 3685 in InsertBreath: "index 78 out of bounds for type 'const unsigned char[78]'", in "A = flags2[index] & 1;".
- sam.c line 3146 in Render: "index 19 out of bounds for type 'const unsigned char[17]'", in the amplitudeRescale lookup.

The text is 251 bytes of dense symbols. It reproduces on its own in a fresh process. The original hangs on this text, so these reads sit on a path only the guards reach.

Cause, traced step by step:

- The reciter turns the symbols into 252 phoneme characters.
- Parser2 leaves 184 phonemes, 42 of them stop consonants.
- Code41240 adds two parts per stop consonant. That would make 268 entries, so the 255-slot list overflows.
- Code41240 scans with an unsigned char position, which wraps twice (254 + 3 to 1, and 253 + 3 to 0). It starts again at the front and expands parts that were already expanded. That produces phoneme codes 78 and 79, which InsertBreath then looks up in the 78-entry flags2 table.
- The frames built from those codes give Render an amplitude of 19, and its rescale table has only 17 entries.

On the device both are reads of a byte or two of neighbouring flash, not a crash. But the runner does not cover them. Suggested guard for a later round, which I did not apply: stop Code41240 before its position can wrap, for example "if(pos >= 253) return;" at its loop head. The last stop consonant then stays unexpanded, and the tail is lost anyway because the list is full.

### 2. The reciter's length limits, for Task 2's chunking

This is inherited from the original. When the reciter emits a plain space after its output has passed 120 characters, it ends the text there. Everything after that is silently dropped.

- "The quick brown fox jumps over the lazy dog and keeps running across the wide green field until night falls on the quiet town" (125 characters) is spoken only up to "night". The phoneme text ends "NAY4T".
- Three sentences of 95 to 98 characters became 117, 121 and 126 phoneme characters and just survived.

So chunks of about 100 characters sit right at the edge, and SPEECH_CHUNK_MAX 100 will sometimes lose a chunk's last words. Chunks of about 80 characters would leave margin.

Separately, runs of symbols without spaces go past 255 reciter characters, and the reciter's output position wraps. For example, 28 percent signs in a row produce PERCENT fragments cut by an end marker in the middle, and only that garbled fragment is spoken. The speech text layer should break or limit such runs.

# Fix round 3

Status: DONE_WITH_CONCERNS.

All four items are done. The runner is green, the fuzz finds nothing, and the firmware builds cleanly. One concern needs a ruling: a bracket in the text silently ends speech while consumed still reports the whole length. It is at the end of this section.

## Commits

Neither repository was pushed. Both messages end with a blank line and my Co-Authored-By line.

- Firmware repository: 987ebf1e4, "screen reader: sam_speak reports the text it used; guards for full phoneme lists". It changes sam.c and sam.h.
- Project repository: bdd0381, "host tests: consumed count, full list and maximum length cases". It changes test_sam_port.c.

## Changes

- **sam.h.** sam_speak takes "size_t* consumed" last, and sam.h now includes stddef.h for size_t. The consumed sentence of the documentation is exactly as given. I also had to reword the sentence about the return value, because it said "true when the whole text was rendered". It now says true when the text was rendered, up to consumed. SAM_MAX_INPUT is 250.
- **reciter_stop.** This is a file scope static, with your comment moved onto two lines above it to keep the line short. TextToPhonemes clears it first thing, and sets it to mem61 at pos36654, just before "input[X] = 155;".
- **sam_speak.** It sets *consumed to 0 first, when the pointer is given, before any check. After TextToPhonemes succeeds, it sets it to reciter_stop if that is nonzero, and to the text length otherwise.
- **Guards, as given, each with a port guard comment:**
  - "if(pos >= 253) return;" at the head of Code41240's loop;
  - "if(position >= 254) { phonemeindex[254] = 255; return 1; }" at the head of Parser1's loop.

## Checking the consumed reasoning

I checked this by running the code, not only by reading it. For "The quick brown fox jumps over the lazy dog and keeps running across the wide green field until night falls on the quiet town" (125 characters):

- The first call returns true with consumed 102. The phonemes end at "NAY4T", which is "night".
- text[101] is the space after "night", and the rest is "falls on the quiet town".
- A second call on that rest returns true with consumed 23, which is all of it.

So the boundary character is input[mem61 - 1], and the rest starts at text + mem61, as you reasoned. The fuzz below confirms this at scale.

## The 254 character claim

I tested this on the build before this round (a7334f20b), where 254 characters were still accepted. I compared 253 and 254 characters of five patterns, counting how often the reciter went back to the start of its input:

- **"HELLO" repeated as one word.** At 253 characters, sam_speak was rejected. At 254, the reciter went through the text twice and spoke 420800 values of garbled repeats.
- **"BAT" repeated as one word.** At 253 characters it spoke 124920 values. At 254 the reciter went through twice and the call was rejected.
- **"A" repeated, and periods.** Both lengths were rejected. The reciter's 255 character output already overflows at 253.
- **English with spaces.** 253 and 254 behaved identically, because the 120 character cut-off stops the reciter long before the end.

There was no hang within 5 seconds. The claim holds. At 254 characters the "[" lands in inputtemp[255], where the reciter's 27 overwrites it, so the reciter scans on round to the start. Any length up to 253 would keep the marker, so 250 leaves 3 characters of margin.

## Do the new checks catch mistakes?

I built the sanitized port test, with the runner's flags, against four scratch copies of sam.c:

- **Code41240 guard removed:** it stops with "index 78 out of bounds for type 'const unsigned char[78]'" on the dense symbol case.
- **consumed never set:** "FAIL case N consumed 0 of M" for all 10 golden cases that have text.
- **consumed always the full length:** "FAIL reciter overflow, first call".
- **Parser1 guard removed:** everything passes, because I believe no input can reach that guard:
  - Parser1 uses at least one character per phoneme.
  - SetInput keeps at most 254 characters and writes a 0 at index 254.
  - A phoneme string with no end marker in input[0..253] reaches that 0, and the parse fails.
  - So position is at most 253 when the end marker is found. The guard is defensive only, and no test can reach it.

## Runner output

Exit code 0. The whole run takes 1.7 seconds, and the case lines are identical in both programs, 11 of 11.

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
```

## Fuzz result

The fuzz ran with AddressSanitizer and UndefinedBehaviorSanitizer in recover mode, so every distinct site would be reported. It ran 8 batches of 1500 random texts, with lengths up to 250, from the same character pool as before, including bytes above 127. Each text was spoken to the end, calling again with text + consumed, as the Task 4 worker will.

The results:

- 12000 texts took 16717 calls, and 4717 calls ended at a word boundary before the end of their text. No text needed more than 6 calls.
- Sanitizer findings: none. The two over-reads from round 2 are gone.
- Hangs: none. consumed never exceeded the remaining length, and no call ended with nothing consumed.
- About 3 percent of texts made no sound: 351 of 12000. All the examples I looked at are explained by the concern below.

## Concern: a bracket ends the speech early

This is inherited from the original, and it needs a ruling. The reciter uses "[" as its end marker. It keeps only the low 7 bits of each byte and folds the range from "p" upward down to capitals, so these also become "[":

- "{" (0x7b);
- the bytes 0xdb and 0xfb, which occur in UTF-8 text.

Speech stops at the first such character, and sam_speak still returns true with consumed equal to the whole length. So the worker would never speak the rest. Two examples:

- "Option [x] enabled" speaks only "Option". It returns true with consumed 18 of 18.
- "Hello {user}, welcome" speaks only "Hello". It returns true with consumed 21 of 21.

Two possible fixes:

1. Task 2's speech text layer maps "[" and "{", and bytes above 127, to something safe, such as a space or a spoken word.
2. The port treats a bracket inside the text like a word boundary. It would report consumed as the position after the bracket, so the next call speaks the rest.

# Fix round 4

Status: DONE.

## Commits

Neither repository was pushed. Both messages end with a blank line and my Co-Authored-By line.

- Firmware repository: d518f4304, "screen reader: sam_speak keeps bracket characters from ending the text". It changes only sam.c.
- Project repository: d4b37b6, "host tests: bracket characters do not cut speech short". It changes only test_sam_port.c.

## Change in sam_speak

The copy loop now starts at index 0. It turns every byte whose low 7 bits are "[" (0x5b) or "{" (0x7b) into a space, with the comment as given. That covers "[", "{", 0xdb and 0xfb, which are exactly the bytes the reciter turns into its end marker. Upper casing is guarded by "i != 0", so it still starts at index 1 as before, and nothing else in the byte handling changed.

A closing bracket needs no replacement. In the reciter's character flags table, "]" (0x5d) has flags 0, the same as a space. "}" (0x7d) becomes "]" in the reciter. Characters with flags 0 take the same path as a space, and rule contexts test them only through their flags. So "Option [x] enabled." renders exactly like "Option  x  enabled.", and the test confirms it.

## Test

Each pair must report consumed equal to the bracketed text's length, and must render with exactly the same hash as its spaced twin, which must itself produce values:

- "Option [x] enabled." against "Option  x  enabled.";
- "Option {x} enabled." against the same;
- "Option " then the bytes 0xdb, "x", 0xfb, then " enabled." against the same;
- "[x] enabled." against " x] enabled.". I added this pair. The loop was extended to index 0 for this replacement, and nothing else tests that.

None of the golden texts contains any of these characters, and their case lines still match.

The test catches all three scratch mutants I tried:

- **No replacement:** all four pairs fail. The leading-bracket text is silent, its hash left at the starting value.
- **Replacement from index 1 only:** the leading-bracket pair fails.
- **"[" only:** the "{" pair and the 0xfb pair fail.

## Runner output

Exit code 0. The whole run takes 1.6 seconds, and the case lines are identical in both programs, 11 of 11.

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
```

## Firmware build

"CC applications/services/screen_reader/sam/sam.c" was built by GCC with no warning or error.

```
API version 87.1 is up to date
.text         662180 (646.66 K)
.rodata       182024 (177.76 K)
.data            968 (  0.95 K)
.bss            4972 (  4.86 K)
.free_flash   203064 (198.30 K)
```

The only warnings are the same two fbt manifest warnings as before, for cli_bridge and mtp. The firmware sizes are unchanged, because the port is still not linked. The change adds 28 bytes to sam.o's text, which is now 6372 bytes.

# Fix round 5

Status: DONE_WITH_CONCERNS.

Everything requested is done. The one concern: the pinned table cannot catch the removal of Insert's slot 255 guard. Nothing observable depends on that guard any more; see "The three mutants".

## Commits

I followed this round's working rules: no git add, commits by pathspec, the runner run with its private output directory, and no ./fbt. Neither repository was pushed. Both messages end with a blank line and my Co-Authored-By line.

- Firmware repository: 7bcbdf7bb, "screen reader: SAM port refuses phoneme strings that wrapped the buffer". It changes only sam.c.
- Project repository: 031a17a, "host tests: pinned outputs for the hard cases, runner timeout". It changes test_sam_port.c and run_host_tests.sh.

Before committing I checked that the diffs of these files held only my changes. The other implementer's files were not touched.

## Important 1: guard S

On the build before this round, both reproducers read at index -1, each returning true with the whole length consumed:

- "x" 129 times: "index -1 out of bounds for type 'unsigned char[256]'" at sam.c line 4336, in Parser2.
- "1234567890" four times with no spaces: the same error at line 4740, in AdjustLengths.

Guard S is exactly as given. It sits after the line that sets consumed, not directly after TextToPhonemes, so that consumed keeps the value already set as ruled. With the guard, both reproducers return false with consumed equal to the whole length, and the sanitizers report nothing.

- "x" 128 times also wraps and is refused.
- "x" 127 times is still spoken.

Both reproducers are now hard cases. The run of x is built at run time, like the spaced letters, and the digits are a literal.

## Important 2: pinned outputs for the hard cases

Each hard case is now a row with its text, the expected return value, the value count and the hash. The return value is pinned too, because the two new cases return false. The comment says these are the port's own outputs, with no original to compare with, to be regenerated deliberately when a guard changes. The loop resets the count, the sum and the hash before each case. It prints a FAIL line with both the actual and the pinned values, so a deliberate regeneration can be read off the output.

How the values were filled:

- I ran the test with placeholder values and copied in what the FAIL lines reported.
- I checked that none of these values depends on the order the cases run in: each of the 14 cases run alone in a fresh process gives exactly the same count and hash as in the full test run.

## The three mutants

Each was a scratch copy of sam.c, built with the runner's sanitizer flags against the new test:

- **Original InsertBreath restored, other guards kept:** caught. Hard cases 0, 1, 3 and 4 fail. "UUUUUUUUU." gives 81720 values instead of the pinned 89640, as you found.
- **last_break check weakened from <= to <:** caught. The same four hard cases fail; SUPERCALIFRAGILISTICEXPIALIDOCIOUS drops from 159520 to 18280 values.
- **Insert's slot 255 guard removed:** not caught. Every check passes.

Why the third cannot be caught:

- I searched 1.7 million random texts from eight character pools, with a scratch build that records which stage calls Insert with position 255.
- Only InsertBreath ever did: 324 texts. Parser2 and Code41240 never did; Code41240's own guard now stops it at position 252.
- I ran 80 of those 324 texts through both builds under the sanitizers: 20 dense symbol texts and 60 letter texts. The output is identical with and without the guard, with no sanitizer report.
- The reason: without the guard, InsertBreath's extra write only changes slot 255 from 255 to 254. Every later reader stops at slot 255 by its position, through the X == 255 checks in InsertBreath and PrepareOutput, not by its value.
- The guard would matter only if Parser2 met a completely full list. Parser1 yields at most 253 phonemes, guard S refuses strings that wrapped, and Parser2's inserts add at most about one phoneme per character. So the list should never fill during Parser2, and none of the 1.7 million texts made it fill.

So this guard is defensive only, like the Parser1 guard, and no test through sam_speak can catch its removal.

## Minor: the runner fails on a hang

The reference run and the port test run now go through "perl -e 'alarm 120; exec @ARGV'". The port run stays inside its existing if statement. I also put the reference run in an if statement with the message "SAM reference failed or hung", because under "set -e" a killed reference would otherwise end the script without saying why. The speech text, queue and PCM runs belong to the other implementer and were left unchanged.

I checked that the mechanism works: a 10 second sleep run this way ends after 2 seconds with status 142, which is 128 plus the SIGALRM signal number, when given "alarm 2".

## Runner output

This is the committed state, run with TMPDIR set to the private directory. Exit code 0.

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 946 checks, 0 failures
speech queue: 94 checks, 0 failures
speech PCM: 647 checks, 0 failures
```

The case lines are identical in both programs, 11 of 11. The speech lines come from the other implementer's tests, which the runner now also builds.

## Firmware compile check

I did not run ./fbt. I took the exact command for sam.c from build/f7-firmware-C/compile_commands.json, changed only the output path to the scratchpad, and ran it from the firmware directory:

- The compiler is arm-none-eabi-gcc. The flags are -std=gnu2x, -Wstrict-prototypes, -mcpu=cortex-m4, -mfloat-abi=hard, -mfpu=fpv4-sp-d16, -mthumb, -Wall, -Wextra, -Werror, -Wno-error=deprecated-declarations, -Wno-address-of-packed-member, -Wredundant-decls, -Wdouble-promotion, -Wundef and -Os.
- It exited with code 0 and printed nothing at all: 0 lines of diagnostics.
- The object has 6348 bytes of text, 7635 of rodata, 342 of data and 3544 of bss.

The text is 24 bytes smaller than in round 4. GCC at -Os evidently compiled around the new early return differently.

## Sanitizer fuzz of this build

18000 random texts ran under both sanitizers in recover mode: 4 seeds of 1500 texts from each of three pools. The pools were the earlier mixed one, letters with digits and a few symbols but no spaces, and "xyz1234567890" with no spaces. Each text was spoken to the end through consumed.

- No sanitizer finding, no hang, no bad consumed value.
- In the two pools without spaces, 15 to 25 percent of texts are now silent, because their phoneme strings wrap and guard S refuses them. The mixed pool leaves 0 to 9 silent texts per 1500.
- For Task 2: a run of about 128 characters without spaces is enough to be refused. So the text layer's word breaking must keep runs well below that.

# Fix round 6

Status: DONE.

## Commit

Project repository only, by pathspec, not pushed: ec7b985, "host tests: pin the Insert slot 255 guard". It ends with a blank line and my Co-Authored-By line, and it changes only test_sam_port.c.

## Correction to round 5

My round 5 claim that Insert's slot 255 guard could not be reached was wrong, as the reviewer showed. "x" repeated 126 times followed by "jj" is 128 characters. In Parser2, the J rule calls Insert at slot 255 from position 254, on a list that is already full.

My argument failed at its last step. I reasoned that Parser2's inserts add at most about one phoneme per character, so the list could not fill. But a run of single-character phonemes, as a run of x's produces, already reaches about one phoneme per character in Parser1. After that, any insert fills the list. My random search simply never produced such a run followed by a J.

## Change

- hard_x_run_jj is filled in main, like hard_x_run.
- Its row sits just before the two refused cases, so the comment "The last two wrap the phoneme buffer and are refused" stays true.
- A comment above the row names the guard it pins.
- Pinned values, from the current build: true, 807200 values, hash f84d1359d5e6545e. These match the reviewer's count, and the same text run alone in a fresh process gives the same values.

## The check catches the mutant

I took a scratch copy of the committed sam.c with only Insert's slot 255 guard removed, and built the test with the runner's flags. Run through the runner's own step, with "perl -e 'alarm 120; exec @ARGV'", the test hung. The alarm killed it after 120 seconds with status 142, and the step printed "SAM port checks failed" and exited 1. The same test built against the committed sam.c passes.

## Runner output

This is the committed state, run with TMPDIR set to the private directory. Exit code 0. The speech lines come from the other implementer's tests.

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 984 checks, 0 failures
speech queue: 94 checks, 0 failures
speech PCM: 647 checks, 0 failures
```
