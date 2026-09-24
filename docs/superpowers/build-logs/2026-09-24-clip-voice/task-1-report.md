# Task 1 report: voice module (pure C) and its host test

Status: DONE

## Commits

**Project repo** (`/Users/robin/Downloads/flipper-access`, branch `main`)
- `5cca139fece067e2602081f709466b0cc85b9693` — "host tests: voice module"
  - `tests/host/test_speech_voice.c` (new)
  - `tools/run_host_tests.sh` (modified: appended the speech voice block after the speech PCM block)

**Firmware repo** (`/Users/robin/Downloads/flipper-access/Momentum-Firmware`, branch `screen-reader`)
- `e140c5aeca09990bce085909da9b16b5cb523b5d` — "screen reader: voice module maps words to clips and remembers missing ones"
  - `applications/services/screen_reader/speech_voice.h` (new)
  - `applications/services/screen_reader/speech_voice.c` (new)
  - Parent: `54794522b` (screen reader: sr play for recorded clips from the card), as expected.

Both commits used explicit `git add <files>` followed by `git commit -m "<subject>" -- <the same files>` (pathspec commit), so the pre-existing dirty `applications/external` submodule pointer in the firmware repo and the pre-existing untracked `docs/superpowers/build-logs/2026-09-23-phase-2-speech/clip-experiment.md` in the project repo were left untouched, not staged, and not committed. Confirmed with `git status --porcelain` after each commit — only that one file/pointer remains outstanding in each repo, unchanged from the session's starting `gitStatus`.

## Step 2: runner before the module existed (expected failure)

Ran `TMPDIR=/private/tmp/claude-501/-Users-robin-Downloads-flipper-access/7e5c805a-c471-4df7-96ca-14e7ee87ded9/scratchpad/v1 tools/run_host_tests.sh` after adding the test file and the runner block, before creating `speech_voice.h`/`.c`:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 115 checks, 0 failures
speech PCM: 700 checks, 0 failures
clang: error: no such file or directory: '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/services/screen_reader/speech_voice.c'
```
Exit code 1. Confirms the earlier blocks (screen model, SAM port, speech text, speech queue, speech PCM) still pass and only the new speech voice block fails, for the expected reason (module not created yet).

## Step 4: runner after the module was written (expected pass)

Same command, after creating `speech_voice.h`/`.c`:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 115 checks, 0 failures
speech PCM: 700 checks, 0 failures
speech voice: 127 checks, 0 failures
```
Exit code 0. Every block, including the new one, passes with 0 failures.

## Step 5: firmware compile check

`cd Momentum-Firmware && ./fbt 2>&1 | grep -E "error|warning|API version" | head`:

```
fbt: warning: Failed parsing manifest '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui'. Must match regex 're.compile('^[a-z0-9_]+$')'
fbt: warning: Failed parsing manifest '/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/external/mtp/application.fam' : Invalid appid '.f0_mtp'. Must match regex 're.compile('^[a-z0-9_]+$')'
API version 87.1 is up to date
```

Exactly the two pre-existing `applications/external` manifest warnings (cli_bridge, mtp) plus the API version line, nothing else. I also checked the full unfiltered build log: the build completed successfully end to end (firmware.hex/.bin/.dfu produced, `Firmware binaries can be found at: dist/f7-C`), and a case-insensitive `grep -iE "error|warning"` over the full log turned up the same two lines and nothing more — no hidden errors/warnings from a different casing. The new module compiled cleanly under the firmware's `-Wall -Wextra -Werror` (GCC 12) even though nothing references it yet, as expected since `./fbt` compiles every source in the service directory.

## Deviations from the brief

None in the code, test, or runner script — `speech_voice.h`, `speech_voice.c`, `test_speech_voice.c`, and the `run_host_tests.sh` block were transcribed verbatim from the brief. The only difference from the brief's literal Step 5 commit snippet is procedural: I used the pathspec commit form (`git add <files>` then `git commit ... -- <files>`) instead of the brief's plain `git add && git commit`, per the controller's explicit instruction for this session — this was necessary because both repos had pre-existing uncommitted content unrelated to this task (see above) that a plain `git add`/whole-tree commit could otherwise have risked pulling in. Commit subjects match the brief's exactly; I appended the blank line + `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer per this session's attribution instructions, which the brief itself doesn't specify one way or the other.

## Concerns

None. Both host-test runs and the firmware compile check match the brief's expected output exactly. `applications/external` (pre-existing dirty submodule pointer) and the unrelated build-log doc were not touched, per instructions. The device was not touched.
