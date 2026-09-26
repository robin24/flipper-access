# Task 8 report: `tools/upstream_check.sh` and its test

## What I implemented

- `tools/upstream_check.sh` (new, executable, mode `100755`): dry-run merge checker for the
  `Momentum-Firmware` submodule. Fetches `upstream` by default, computes the merge base against
  `--ours` (default `HEAD`) and `--upstream` (default `upstream/dev`), reports commit counts, the
  fork's added/modified footprint since the base, the files changed on both sides, and the result
  of `git merge-tree --write-tree --name-only --no-messages` as a conflict-free/conflicting dry
  run. Exit 0 (nothing to merge, or a clean dry run), 2 (conflicts), 1 (errors: bad ref, unknown
  option, other merge-tree failure).
- `tests/fbt/test_upstream_check.py` (new): builds a throwaway repo under `tempfile.TemporaryDirectory()`
  with a base commit and three branches (`ours`, `theirs` — conflicting on `A` — and `theirs_clean`),
  and drives the script via `bash tools/upstream_check.sh --repo <tmp> ... --no-fetch`. Never
  touches the real submodule or the real repo.
- `tools/run_host_tests.sh` (modified): appended the runner block for the new test, in the shape
  of the block before it (`test_subghz_manifest.py`'s), writing to `upstream_check.txt` and
  failing with `upstream check checks failed`.

Both the test and the script were written verbatim from the task brief
(`.superpowers/sdd/2026-09-26-publishing-plan-a/task-8-brief.md`); no wording needed to change
between them — the script's echo text matched the test's expectations on the first pass.

## TDD evidence

**Step 2 — failing run (script absent), before writing `tools/upstream_check.sh`:**

```
FAIL a conflict exits 2, got 127:
bash: /Users/robin/Downloads/flipper-access/tools/upstream_check.sh: No such file or directory
... (six more FAILs, same cause)
FAIL a bad ref exits 1, got 127
upstream check: 1 of 9 checks passed
exit code: 1
```

Failed for the right reason: `bash` exits 127 because the script does not exist yet, not because
of any test bug.

**Step 4 — passing run, after writing the script and `chmod +x`:**

```
upstream check: 9 of 9 checks passed
exit code: 0
```

**Runner's last lines**, after appending the block to `tools/run_host_tests.sh` and running
`zsh tools/run_host_tests.sh` in full (about a minute, all prior blocks unaffected):

```
card prune: 8 of 8 checks passed
strip js symbols: 14 of 14 checks passed
subghz manifest: 8 of 8 checks passed
upstream check: 9 of 9 checks passed
===RUNNER EXIT: 0===
```

## The real run (Step 5)

Command: `tools/upstream_check.sh` (defaults: repo = submodule, `upstream/dev`, `HEAD`, fetch
enabled — this did fetch `upstream` over the network, read-only, as expected).

Full output:

```
merge base: d3f89dfe2 2026-08-18 ESP Flasher: Quick flash fix (by xMasterX), bump Marauder 1.14.3 (by justcallmekoko)
upstream upstream/dev: 0 new commits; ours HEAD: 80 commits on top
our footprint since the base: 24 added, 53 modified files
nothing to merge
```

Exit code: 0.

This matches the brief's "expected today" (merge base `d3f89dfe2` of 2026-08-18, `0 new commits`,
`nothing to merge`, exit 0) exactly, including the footprint: `24 added, 53 modified files` — the
same as the "earlier rounds'" count the task context cited, confirming Tasks 6 and 7 added nothing
new to the firmware side. Momentum's `dev` genuinely has not moved since the merge base, as
expected.

I confirmed before and after this run that the submodule's working tree stayed clean
(`git status --short --branch` inside `Momentum-Firmware` showed only the branch line) and that
its committed pointer in the outer repo was untouched (`git diff --stat -- Momentum-Firmware` was
empty) — the fetch only updated `upstream`'s remote-tracking refs.

## Files changed and the commit

- `tools/upstream_check.sh` (new, `100755`)
- `tests/fbt/test_upstream_check.py` (new, `100644`)
- `tools/run_host_tests.sh` (modified: +7 lines, the new runner block)

Committed with the explicit pathspec (not `-A`, not inside `Momentum-Firmware`):

```
commit 81071b98a1d4cfd058f440098d0dbd6f9e4dbadd
Author: Robin Kipp <robin@robin-kipp.net>

    upstream_check: what a Momentum merge would meet, from a dry run

    Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

 tests/fbt/test_upstream_check.py | 93 ++++++++++++++++++++++++++++++++++++++++
 tools/run_host_tests.sh          |  7 +++
 tools/upstream_check.sh          | 58 +++++++++++++++++++++++++
 3 files changed, 158 insertions(+)
```

Per the task instructions, the message body is the brief's verbatim, with the harness's own
`Co-Authored-By` line substituted for the brief's placeholder one (`Claude Fable 5.1`).

Pushed: `git push origin main` → `12d415d..81071b9  main -> main`. `git rev-parse HEAD
origin/main` confirms both point at `81071b98a1d4cfd058f440098d0dbd6f9e4dbadd`. No push to
`upstream` (never attempted; the script itself only ever fetches, and the real run used no
`--repo` override).

## Self-review

Re-read `tools/upstream_check.sh` once more against its own comment header:

- **Option names** — header lists `--repo DIR`, `--upstream REF`, `--ours REF`, `--no-fetch`;
  the `case` block implements exactly those four, with the first three consuming a following
  argument (`shift 2`) and `--no-fetch` taking none (`shift`). An unrecognized flag falls to the
  `*)` branch and exits 1, matching "1 on an error".
- **Exit codes** — header says "Exit 0 when there is nothing to merge or the dry run is clean, 2
  on conflicts, 1 on an error." Traced every exit in the script: `AHEAD=0` → 0; `merge-tree`
  status 0 → 0; status 1 (conflicts) → 2; status anything else, or no merge base → 1; unknown
  option → 1. All four consistent with the header, no gaps.

No mismatches found, so no follow-up edits were needed to either the script or the test.

## Concerns

None. The real run's footprint and "nothing to merge" result match the brief's prediction
exactly, the submodule was left untouched, and the runner passes end to end.
