# Task 2 report: pronunciation rewriting and chunking

Status: DONE_WITH_CONCERNS.

The rule list is implemented in speech_text.c, the host runner is green with 919 checks and 0 failures for the new suite, and the firmware builds without a compiler warning. The brief's code needed two changes to follow the rule list, and one of the brief's test expectations was inconsistent with rule 8. The concerns at the end are about announcement strings in the current UI that the rule list does not handle well, above all negative numbers such as "-90dBm".

## Commits

Neither repository was pushed. Each message is the brief's subject, a blank line and "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>".

1. Firmware repository, branch screen-reader, on top of d518f4304: 0503ac719bab3872401d51848300696a6b59aa14, "screen reader: pronunciation rewriting and chunking for speech". Adds applications/services/screen_reader/speech_text.h and speech_text.c. Nothing else in the firmware changed; applications/external still shows as a modified submodule, untouched.
2. Project repository, branch main, on top of d4b37b6: 85dd5a3ac75eb8e18b2d4ba48fb7d7282cd07049, "host tests: pronunciation and chunking". Adds tests/host/test_speech_text.c and appends the speech text block to tools/run_host_tests.sh.

sam.c, sam.h and the SAM tests were not touched. No serial command was sent to the device.

## Order of work

1. Wrote tests/host/test_speech_text.c and the runner block first. The runner then stopped with "clang: error: no such file or directory: .../speech_text.c" (the brief expected the missing header; clang reports the missing source first, same effect), after the earlier suites had passed.
2. Wrote speech_text.h and speech_text.c. The runner passed on the first run.
3. Ran the toolchain's clang-format 18.1.8 (toolchain/current/bin/clang-format, the one ./fbt lint uses) with the firmware's .clang-format. The header was already clean; the .c file differed in whitespace and table packing only, and I adopted its output. Both files pass a dry run with --Werror.
4. Ran a mutation check: six deliberate breakages in scratch copies of speech_text.c, each compiled against the committed test. Every one fails the suite: "dot" changed to "point" (7 failures, first at key.sub); pieces of 19 instead of 20 (7 failures, first at Supercalifragilisticexpialidocious); stop list ignored (9 failures, first at ON); the comma cut removed from the chunker (1 failure, the commas case); the colon between digits emitting a comma, with the same edit also hitting the default space branch (218 failures); rule 5's split disabled (12 failures, first at 125kHz).
5. Built the firmware and committed.

## Runner output

The summary lines of ./tools/run_host_tests.sh, exit status 0:

    98 checks, 0 failures
    port checks: 0 failures
    SAM port matches the original on 11 cases
    speech text: 919 checks, 0 failures

The runner block builds test_speech_text with the SAM CFLAGS plus -fsanitize=address,undefined -fno-sanitize-recover=all, sends the test's output to a file, prints it all and exits 1 on failure, and otherwise prints "speech text:" followed by the test's own last line.

## Firmware build

./fbt finished with exit status 0. The brief's check, grep for error, warning or API version, prints three lines: two fbt manifest warnings for applications/external/cli_bridge and applications/external/mtp (invalid appid; they come from the external submodule and were there before this task) and then "API version 87.1 is up to date". The whole log has exactly those two lines matching warning or error and no compiler diagnostic at all; the compile line "CC applications/services/screen_reader/speech_text.c" ran under GCC 12.3.1 with the firmware's flags (-std=gnu2x -Wall -Wextra -Werror -Wstrict-prototypes -Wredundant-decls -Wdouble-promotion -Wundef), and the object is at build/f7-firmware-C/applications/services/screen_reader/speech_text.o.

Sizes after the build: .text 662180, .rodata 182024, .data 968, .bss 4972, .free_flash 203064 (198.30 K). Nothing calls speech_text yet, so with -ffunction-sections the linker drops it and the free flash figure does not move until Task 4 uses it. This is the same situation Task 1 reported for the SAM port.

## Where the brief's code changed to follow the rule list

1. Rule 4, periods. The brief's process_token split at the first period and recursed on the remainder, so a remainder that is a decimal number was read with "point": "1.2.3" became "one dot two point three". Rule 4 says the token is split at the periods with "dot" between the parts, so split_token now cuts at every period and processes each part as a token: "one dot two dot three", and "192.168.1.1" reads "one hundred ninety two dot one hundred sixty eight dot one dot one". Both are tests.
2. Rule 4, hyphens. Same split at every hyphen, each part processed as a token. The brief's recursion on the remainder would have re-matched a hyphenated term sitting at the end of a longer token ("x-Wi-Fi" as "x why fye"); the rule as written gives "x Wi Fi". For "Sub-GHz" suffixes the two readings sound the same, because SAM receives upper case text. No realistic string is affected, and there is no test for it.
3. Rule 9, colon between digits. The brief's code emitted nothing there and relied on the next token to add a space. It now emits the space itself. Same output.
4. Rule 9, everything else. The brief's code listed the characters that become a space. Now every byte not handled by an earlier branch becomes a space, so the printable ASCII output is guaranteed by construction. The test test_rule9_every_byte checks all 255 byte values, alone and between letters.
5. Rule 8 expectation in the brief's own test. The brief expected "Supercalifragilisticexpialidocious" to read "Supercalifragilisti cexpialidocious", pieces of 19 and 15. The word has 34 letters and its first 20 are "Supercalifragilistic"; rule 8 says pieces of at most 20, and the code cuts greedily at 20, as the brief's code did too. The committed test expects "Supercalifragilistic expialidocious". Both splits satisfy "at most 20"; the brief's string looks like a miscount of the prefix. If you meant something else by rule 8, this is the place to say so.
6. Structure only: the duplicated term and number checks in the brief's process_plain are gone (process_token checks rules 3 and 6 once, process_word does rules 5, 7 and 8); rule 5 hands the rest of the token back to process_token, so "125kHz" reaches the term table and "3V3" spells its rest. speech_text_next_chunk returns 0 for a null text, like expand does for a null input. The file starts with a comment listing the ten rules in the order the code applies them.

## Behaviour the rule list does not decide

These come from the brief's code and are kept. The test file pins them in test_beyond_the_rule_list, labelled, so a later change is noticed; strike any you do not want.

1. Rule 1 names beyond the list: backslash, open brace, close brace, less than, greater than, caret, tilde, backtick, bar, dollar. Without them a lone brace or bar would be spoken as nothing.
2. Rule 9 for printable characters the rule does not list: semicolon, a hyphen or apostrophe outside a token, backslash, caret, tilde, backtick, dollar and braces all become a space.
3. A null input gives an empty string. When the expansion does not fit in out_size it is cut where the buffer ends, possibly inside a word, and always terminated. Announcements are at most SR_ANN_TEXT_MAX (160) characters and the buffer holds 400, so only a text made almost entirely of long digit strings can reach the cut.

## Tests added beyond the brief

All in tests/host/test_speech_text.c, one function per rule, with every expectation worked out from the rule list:

1. Rule 1: every listed name, lower case a, a lone byte outside printable ASCII (nothing to say).
2. Rule 3: every term, exact match only ("ok", "khz", "Pin" stay; "HZ" is spelled), a term followed by a colon.
3. Rule 4: "key_1.sub", "1.2.3", an IP address, "my-file.sub", "Sub-GHz.sub", "read-only", "on-the-fly", "1-2", "20-MHz", and the UI string "378-481, 749-962 MHz".
4. Rule 5: "868MHz", "FAAC SLH 868MHz", "2FA", "3V3", "100mAh", "0dBm", "10dBm +", "007px", and "433.92MHz" under the literal rule order (see concern 3).
5. Rule 6: the tens, hundreds and thousands boundaries, six digit words, seven digits one by one, "433920" from the Momentum settings hint, decimals, leading zeros.
6. Rule 7: five letter words in and out of the stop list, a six letter word, digits inside acronyms ("T5577", "AM650"), "EM4100" too long, mixed case, a lone letter after a word.
7. Rule 8: tokens of exactly 20, 21, 40 and 41 characters, two long real words.
8. Rule 9: colons between and around digits, every symbol word, punctuation after a space, tabs and newlines, quotes, control bytes, DEL, 0xFF, a UTF-8 ellipsis, the SAM end marker characters, and a loop over all 255 byte values checking the output is printable ASCII and that every byte outside printable ASCII is a space.
9. Rule 10: leading and trailing spaces, empty and blank text, a sentence end winning over a later comma, a period inside "3.14" not counting as a sentence end, question and exclamation marks, a rest of exactly 80 characters, a sentence end on the last character within the limit, a chunk buffer smaller than SPEECH_CHUNK_MAX + 1.

## Concerns

1. Negative numbers lose their sign. The Sub-GHz receiver config lists the RSSI threshold as "-90dBm" through "-40dBm" (applications/main/subghz/scenes/subghz_scene_receiver_config.c) and the radio settings list the power as "-10dBm" through "-30dBm" next to "0dBm", "5dBm", "7dBm" and "10dBm +" (subghz_scene_radio_settings.c). A hyphen with no alphanumeric before it is outside every token, and rule 9 does not name it, so it becomes a space: "-90dBm" reads "ninety dee bee em", the same as "90dBm" would. A user setting a threshold or a power level cannot hear the sign. Suggested rule: a hyphen directly before a digit, with no alphanumeric before it, reads "minus". This is a small change in speech_text_expand's rule 9 branch plus a test; I did not add it because it is not in the rule list. The current reading is pinned in test_beyond_the_rule_list so the change shows up there.
2. Ranges run two numbers together. "378-481, 749-962 MHz" (momentum_app_scene_protocols.c and the protocols frequency add scene) reads "three hundred seventy eight four hundred eighty one, seven hundred forty nine nine hundred sixty two megahertz". Rule 4 splits the hyphen and drops it. A hyphen between two numbers could read "to".
3. A decimal glued to its unit reads with "dot". Rule 4 runs before rule 5, and "433.92MHz" is not a decimal number token, so it reads "four hundred thirty three dot ninety two megahertz" rather than "point nine two megahertz". The UI strings I found glue only whole numbers to units ("868MHz", "433MHz", the dBm values), so no current screen hits this, and the test pins the literal reading. If rule 5 accepted a decimal number prefix, the reading would be right; that is one condition in process_word.
4. A lone A after digits is read as the article. Rule 5 splits "1A" into "one" and "A", and "A" is a one letter token that rule 8 copies, so SAM says "one uh". NFC and RFID UIDs are shown as spaced hex bytes, so "1A" through "9A" are common: "04 1A 2B" reads "zero four one uh two B". "A2" is fine ("ay 2") because rule 7 handles it. "Type A" has the same root. A fix could be: when rule 5's rest is the single letter A, write "ay"; the general case of a lone "A" token cannot be told from the article.
5. Ordinals: "1st", "2nd", "3rd", "10th" read "one st", "two nd", "three rd", "ten th" under rule 5. I did not find them in the main apps' strings, so this is low priority.
6. Stop list gaps. Short upper case English words missing from the list are spelled: AT, IN, OF, TO, IS, IT, BY, AS, FOR, USE, END, OUT, NOW, TOP. Only matters where the UI writes them in capitals.
7. A comma as a thousands separator: "1,000" reads "one, zero zero zero". I did not see one in the UI strings.
8. Leading sentence punctuation is written at the start when there is no previous word: ".5" gives ". five". SAM treats it as a pause; harmless.
9. Task 1's concern about texts ending in a vowel then T or D was fixed in a7334f20b, so chunks do not need to end with punctuation and I did not add one.

# Fix round 1

Status: DONE.

Rules 5 (amended), 11 and 12 and the 22 new stop words are implemented, every example from the ruling is an expect line with its exact output, the runner is green with 946 checks, and the firmware builds without a compiler diagnostic.

## Commits

Neither repository was pushed. Each message ends with a blank line and "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>".

1. Firmware repository, branch screen-reader: 25c9b6d0b13521156780f04fdb0fbbbc64c0d239, "screen reader: minus, ranges, units after decimals, letters after digits". Changes speech_text.c only.
2. Project repository, branch main: 4ec82d5304765edbd1d3ad60362cde223fdb8ccb, "host tests: minus, ranges, units and letters after digits". Changes tests/host/test_speech_text.c only.

## Changes in speech_text.c

1. Rule 5 as amended. number_before_letters recognises digits, optionally a period and more digits, followed by letters and nothing else, and returns the number's length. process_token applies it after rule 6 and before the period split, so "433.92MHz" is no longer split at its period. process_unit speaks the letters: a rule 3 term, else spelled when one to five upper case letters outside the stop list, else copied in rule 8's pieces.
2. Rule 11. In the between-token branch, a hyphen followed by a digit becomes "minus". That branch is only reached for a hyphen outside every token; since a digit follows, the character before it is not alphanumeric or the hyphen starts the text, which are the rule's conditions.
3. Rule 12. split_token counts the token's hyphens; a hyphen between two digits gets "to" when the count is one and "dash" otherwise; hyphens next to letters get nothing, as before.
4. The stop list gains AT IN OF TO IS AS BY IT AN BE DO IF SO WE FOR NOW END TOP BIT HEX BIN DEC.
5. Structure: the rule 3 lookup (out_term) and the rule 8 pieces (copy_pieces) are helpers shared by the token path and the unit path; process_word is folded into process_token. The file's rule comment now lists rules 11 and 12 and says the order a token goes through.

## Interpretation

Rule 5's "continues with letters" is read as "the rest of the token is letters only". So "3V3" is not rule 5's shape (its rest "V3" holds a digit) and rule 7 spells it "3 V 3", where the previous code said "three V 3"; SAM speaks both as "three vee three". A token like "12ab34" is copied whole. The test for "3V3" pins this and says why. "12.MHz", a period with no digit after it, is not a decimal, so rule 4 gives "twelve dot megahertz".

## Tests

Every example in the ruling has an expect line with the exact output: 433.92MHz, 125kHz, 1A, 9F, 10s, SET AT, "-" alone, "- 90", Ch-3, -90dBm, "TX power -10dBm", "378-481, 749-962 MHz", 2026-09-23. Derived cases beside them: 3.3V, 1.5mAh, 12.MHz, "04 1A 2B" (the pinned case in its corrected form, "zero four one ay two B"), 12AT (letters in the stop list are copied), 4GB, 12ABCDEF (six letters, copied), HEX, IN, ID (still spelled), (-5), -0.5, -5-3, "a -b", "RSSI: -70", 1-2, 1-2-3, a-1-2, 10-20%, on-the-fly. The two pinned cases left the beyond-the-rule-list group for their rule's test.

Evidence the tests bite: compiled against the previous speech_text.c from 0503ac719, the suite reports 946 checks and 22 failures, exactly the amended and new cases: 3V3, 433.92MHz, 3.3V, 1.5mAh, 1A, 04 1A 2B, 12AT, SET AT, HEX, IN, -90dBm, TX power -10dBm, (-5), -0.5, -5-3, RSSI: -70, 378-481 749-962 MHz, 2026-09-23, 1-2, 1-2-3, a-1-2, 10-20%. The other new lines (9F, 10s, 12.MHz, 4GB, 12ABCDEF, ID, "-", "- 90", Ch-3, "a -b", on-the-fly) pass on both versions, as they describe behaviour that did not change.

## Runner output

The summary lines of ./tools/run_host_tests.sh, exit status 0:

    98 checks, 0 failures
    port checks: 0 failures
    SAM port matches the original on 11 cases
    speech text: 946 checks, 0 failures

## Firmware build

./fbt finished with exit status 0. The grep for error, warning or API version prints the same two fbt manifest warnings for applications/external (cli_bridge and mtp, pre-existing) and then "API version 87.1 is up to date". No compiler diagnostic anywhere in the log; "CC applications/services/screen_reader/speech_text.c" compiled; free flash unchanged at 203064 bytes because nothing calls the module yet. The toolchain's clang-format reports both files clean.

## Note on the working tree

After the fix round commit, the firmware working tree shows applications/services/screen_reader/sam/sam.c as modified. That change is not mine: I did not open or edit sam.c in either round, and each of my commits was made with an explicit git add of the speech_text files, so it is in neither commit. It is most likely the reviewer's work in progress on the SAM port.
The change is a three line insertion made at 18:15:24, after my fix round build finished at 18:15:06, so that build did not include it; the runner's SAM checks that ran before it were green.

# Fix round 2

Status: DONE.

Rule 7 spells by runs, rule 12 puts "dash" into mixed tokens, rule 13 turns a lone upper case A into "ay", SPEECH_TEXT_MAX is 640, every pin from the ruling is an expect line with its exact output, the runner is green with 984 checks, and the firmware builds without a compiler diagnostic.

## Commits

Neither repository was pushed. Each message ends with a blank line and "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>". Both were made with an explicit git add of my files only, after checking that no index.lock existed; the other implementer's files were never staged.

1. Firmware repository, branch screen-reader: ee72572109172618d1673800cb1046013f5f988e, "screen reader: spelling by runs, dashes in mixed tokens, upper case A, larger text buffer". Changes speech_text.c and speech_text.h, on top of the other implementer's 8bdf14dd2.
2. Project repository, branch main: e7c10163ee480888c744ed57ab7ea9d64cd91e2e, "host tests: spelling by runs, dashes, upper case A, text buffer". Changes tests/host/test_speech_text.c only, on top of the plan commit 6a11941.

## Changes

1. Rule 7 replaced. is_acronym now accepts any length from two characters; spell_by_runs walks the token's runs: a letter run of one to five is spelled (A as "ay") unless the run is a stop word, in which case it is copied; a longer letter run is copied; a digit run of one to three goes through rule 6's number_token (so "007" inside "X007" is "zero zero seven"); a longer digit run is spoken digit by digit. The whole token is still checked against the stop list first, so "MODE" stays a word and "MODE1" reads "MODE one".
2. Rule 12 amended. split_token records whether every part of the token is a pure digit run. A hyphen with a digit on at least one side gets "to" when the token's parts are all digits and it is the only hyphen, "dash" otherwise; a hyphen between letters gets nothing, as rule 4 says.
3. Rule 13. process_token turns a one character token "A" into "ay" after rule 7 and before rule 8; lower case "a" is untouched.
4. SPEECH_TEXT_MAX is 640, with the plan's reason in the header comment. The header now says that `in` and `out` of speech_text_expand must not overlap and that speech_text_next_chunk returns 0 for a chunk_size below 2; the function returns early for chunk_size 1 (after writing the empty string) instead of running its loops over an empty limit.
5. The file's rule comment covers rules 7, 12 and 13 and gives the order a token goes through: 3, 6, 5, 4 with 12, 7, 13, 8.

## Interpretations

1. Rule 7's "a run of more than five letters is copied as a word" goes through rule 8's pieces of 20 characters, so a run of 26 upper case letters cannot hang the synthesizer. Pinned in the beyond-the-rule-list group: "ABCDEFGHIJKLMNOPQRSTUVWXYZ1" reads "ABCDEFGHIJKLMNOPQRST UVWXYZ one".
2. Two of the brief's original expectations change with the replaced rule 7, because a digit run inside an acronym is now a number: "U2F" reads "U two F" (was "U 2 F") and "04 A2 FF" reads "zero four ay two F F" (was "zero four ay 2 F F"). Both follow the ruling's pins "A1" and "UID: 04 A2 B3 C4".

## Tests

Every pin in the ruling has an expect line: NFC, AM650, T5577, EM4100, DS1990A, NTAG215, ISO14443, MIFARE, MODE1, A1, 3V3, "UID: 04 A2 B3 C4", 1A, 1K, 125kHz, ISO14443-3A, "Tech: ISO 14443-3A (NFC-A)", Ch-3 (now "Ch dash three"), NFC-A, "Type A", "a key", "A" alone, 1ABCDE, the rule 10 space at index 80 (first chunk 39 characters, the cut at the previous space) and the comma at index 79 followed by a space (an 80 character chunk ending in the comma). Derived cases beside them: X007, SET1, "Plan A or B", "A.", "A:B" and "A&B" (now "ay, B" and "ay and B"), "20-MHz" ("twenty dash megahertz"), "a-1-2" ("a dash one dash two"), a chunk buffer of size 1 and 0.

The text buffer pin builds "UID:" followed by 52 hex byte pairs, 160 characters exactly, cycling through 0A 1B 2C 3D 4E 5F 6A 7B 8C 9D 77 33 88 AA FF 00 so that the dump has the pair shapes of a real screen. Each expected word comes from rules 5, 6 and 7 ("zero ay", "seventy seven", "ay ay", "zero zero" and so on). The output is 430 characters: the return value equals its strlen, it equals the expected string, it ends with the last pair's words "three D", and a check that it is longer than 400 records that the previous buffer would have cut it. A dump of "0A 1B 2C" style pairs alone expands to only about 378 characters and would not have shown the change, which is why the cycle includes digit pairs.

Evidence the tests bite: compiled against the previous speech_text.c and speech_text.h from 25c9b6d0b, the suite prints failures for exactly the changed and new cases (04 A2 FF, U2F, 3V3, T5577, AM650, EM4100, DS1990A, NTAG215, ISO14443, MODE1, A1, UID: 04 A2 B3 C4, X007, SET1, A:B, A&B, Ch-3, a-1-2, 20-MHz, ISO14443-3A, Tech: ISO 14443-3A (NFC-A), NFC-A, Type A, Plan A or B, A.) and then aborts in the buffer pin under the address sanitizer, because with the old header's 400 byte SPEECH_TEXT_MAX the test's own expected text buffer cannot hold the 430 character expectation.

## Runner output

Run with TMPDIR set to the scratchpad's t2 directory, exit status 0. The last two lines are the other implementer's suites, which the runner now also builds:

    98 checks, 0 failures
    port checks: 0 failures
    SAM port matches the original on 11 cases
    speech text: 984 checks, 0 failures
    speech queue: 94 checks, 0 failures
    speech PCM: 647 checks, 0 failures

## Firmware build

./fbt finished with exit status 0 on the first try, no lock. The grep for error, warning or API version prints the same two fbt manifest warnings for applications/external and then "API version 87.1 is up to date". No compiler diagnostic anywhere in the log; "CC applications/services/screen_reader/speech_text.c" compiled; the toolchain's clang-format reports both files clean. Free flash is unchanged at 203064 bytes: nothing in the image calls speech_text yet.

## Remaining concern

A 160 character hex dump made only of two digit pairs, for example "77 78 88 33" repeated, expands about 4.7 times (each pair "seventy seven" plus a space, 14 characters for 3), to about 740 characters, beyond 640. The expansion is then cut at 639 characters, possibly inside a word, and the rest of the dump is not spoken. Random byte dumps average well below that and fit; only pages dominated by such pairs are affected. If that matters, the worker could expand and speak an announcement in two halves, or the buffer could grow to 800.

# Fix round 3

Status: DONE.

Rule 6 speaks words only up to four digits, rule 12 distinguishes equal digit runs ("to"), a digit run beside two or more letters (a space) and every other hyphen next to a digit ("dash"), every pin from the ruling is an expect line with its exact output, the runner is green with 1006 checks, and the firmware builds without a compiler diagnostic.

## Working mode

Another implementer was flashing from the working trees, so everything was prepared under the scratchpad's t2r3 directory on copies of speech_text.c, speech_text.h and test_speech_text.c: edits, the toolchain's clang-format, a build and run with the runner's flags (1006 checks, 0 failures on the copies), and a run of the prepared test against the then current speech_text.c (20 failures, exactly the changed and new cases). On "apply" I checked that the working tree files were unchanged since the copies were taken, copied speech_text.c and test_speech_text.c back (the header copy was identical), ran the full runner with my private TMPDIR, checked with pgrep that no other fbt process was running, built, and committed. The device was not touched.

## Commits

Neither repository was pushed. Each message ends with a blank line and "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>", each was made after checking for index.lock, with an explicit git add of my files only.

1. Firmware repository, branch screen-reader: 5cea830fe844e1f58930553e523079bde7eb7fcc, "screen reader: five digit numbers digit by digit, hyphen refinements". Changes speech_text.c only (40 insertions, 13 deletions), on top of the other implementer's 2c6254154.
2. Project repository, branch main: 71fdf88b6aa2c94354e21c478a0d0e7b2b9120e7, "host tests: five digit numbers, hyphen refinements". Changes tests/host/test_speech_text.c only (52 insertions, 12 deletions), on top of the plan commit 99a8fc2.

The header is unchanged in this round: the plan's 800 byte SPEECH_TEXT_MAX (plan commit ca9bafa) had already been committed to the firmware as d64c41548 by someone else after my round 2, with the plan's wording.

## Changes in speech_text.c

1. Rule 6: number_token speaks words for at most four digits without a leading zero; five or more, or a leading zero, go digit by digit. The decimal part is unchanged. The comments say "four" and "below ten thousand".
2. Rule 12: split_token asks a new hyphen_word helper for the word between two parts (periods keep "dot"). hyphen_word returns nothing for letters on both sides (rule 4); when every part is a digit run, "to" only for the sole hyphen that sits exactly in the middle of the token, which is the same digit count on both sides, and "dash" otherwise; in a mixed token, nothing when the digit side faces a run of two or more letters (helpers letters_from and letters_before), and "dash" for every other hyphen next to a digit.
3. The file's rule comment reflects both rules.

## Tests

Changed expectations, each derived from the amended rules: "10000" reads "one zero zero zero zero" (was "ten thousand"); "100000" "one zero zero zero zero zero"; "123456" "one two three four five six"; "999999" "nine nine nine nine nine nine"; "Use kHz values, like 433920" ends "four three three nine two zero"; "Ch-3" reads "Ch three" (was "Ch dash three"); "20-MHz" reads "twenty megahertz" (was "twenty dash megahertz"); "Tech: ISO 14443-3A (NFC-A)" reads "Tech, I S O one four four four three dash three ay N F C ay" (14443 now digit by digit).

New pins from the ruling: 14443, 65535, 2026 and 1000 (already present), 433920000, 14443-3, 1-10, 4-bytes, 1-Day, "NFC-A 4-bytes UID", A-1, 100-200-A, "Tech: ISO 14443-3 (NFC-A)" reading "Tech, I S O one four four four three dash three N F C ay". Derived cases beside them: 9999 (the last four digit word), 12345.6 (a five digit integer part with its decimal), 100-99 (unequal digit runs), ab-12, a-12, 1-A2, 4-bytes-A. Unchanged and still passing: 378-481 and "378-481, 749-962 MHz", 2026-09-23, 1-2, 1-2-3, a-1-2, -5-3, 10-20%, ISO14443-3A, NFC-A, on-the-fly, and rule 7's digit runs.

The extra buffer pin, kept at the coordinator's request: a 160 character "UID:" dump of two digit pairs (77 78 87 88 33 99 66 44 cycling) expands to 660 characters, checked against the exact expected words, with the returned length equal to strlen and above 640; the earlier 430 character pin now says a 400 byte buffer would have cut it.

Evidence the tests bite: against the previous speech_text.c the prepared suite failed on 10000, 14443, 65535, 100000, 123456, 999999, "Use kHz values, like 433920", 12345.6, Ch-3, 20-MHz, 14443-3, 1-10, 100-99, 4-bytes, 1-Day, "NFC-A 4-bytes UID", ab-12, 4-bytes-A, "Tech: ISO 14443-3A (NFC-A)" and "Tech: ISO 14443-3 (NFC-A)": 20 failures, nothing else. A-1, 100-200-A, a-12 and 1-A2 pass on both versions because they read "dash" under the previous rule too.

## Runner output

Run with TMPDIR set to the scratchpad's t2 directory, exit status 0:

    98 checks, 0 failures
    port checks: 0 failures
    SAM port matches the original on 11 cases
    speech text: 1006 checks, 0 failures
    speech queue: 94 checks, 0 failures
    speech PCM: 647 checks, 0 failures

## Firmware build

pgrep found no other fbt process. ./fbt finished with exit status 0 on the first try, no lock. The grep for error, warning or API version prints the same two fbt manifest warnings for applications/external and then "API version 87.1 is up to date"; no compiler diagnostic anywhere in the log; "CC applications/services/screen_reader/speech_text.c" compiled; both files clean under the toolchain's clang-format. Free flash is now 180084 bytes (175.86 K), down from 203064, because the other implementer's speech engine commit 2c6254154 links the speech modules, this one included, for the first time.
