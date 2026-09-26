# Task 7 report: `tools/subghz_manifest.py` and its test

## What was implemented

1. `tests/fbt/test_subghz_manifest.py` — written verbatim from the brief (Step 1). Diffed
   byte-for-byte against the brief's code block after writing; identical.
2. `tools/subghz_manifest.py` — written verbatim from the brief (Step 3). Diffed byte-for-byte
   against the brief's code block after writing; identical. Left non-executable (644), matching
   the sibling importable tool/test pairs `tools/card_prune.py` and `tools/strip_js_symbols.py`
   (both are imported by their tests and also run via `python3 tools/...`); `tools/run_host_tests.sh`
   keeps its existing 755.
3. `Momentum-Firmware/applications/main/subghz/application.fam` — regenerated once by running the
   new script. The only change is `subghz_i.c` and `subghz_history.c` swapping places; all 36
   filenames are unchanged.
4. `tools/run_host_tests.sh` — appended the runner block for `test_subghz_manifest.py`, in the
   shape of the blocks before it, output `subghz_manifest.txt`, failure message "Sub-GHz manifest
   checks failed".

## TDD evidence

**Step 2 — failing run before the script existed** (`python3 tests/fbt/test_subghz_manifest.py`):

```
Traceback (most recent call last):
  File ".../tests/fbt/test_subghz_manifest.py", line 14, in <module>
    from subghz_manifest import EXCLUDED, rewrite, sources, upstream_excludes  # noqa: E402
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ModuleNotFoundError: No module named 'subghz_manifest'
```
Exit code 1 — failed for the expected reason.

**After writing the script, before regenerating the manifest** (Step 4, first run):

```
FAIL the fork's manifest is what the script writes (run the script once if not)
subghz manifest: 7 of 8 checks passed
```
Exit code 1. Exactly the one predicted failure — the `upstream_excludes` check ran (this checkout
has `upstream/dev`) and passed silently, confirming `EXCLUDED` already matches Momentum's merge-base
list before any regeneration.

**Regeneration** (`python3 tools/subghz_manifest.py --verify-upstream`):

```
the exclude list matches the merge base's manifest
/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/main/subghz/application.fam: rewritten, 36 sources
```

**Manifest diff shape** (`git -C Momentum-Firmware diff --stat` and full diff):

```
 applications/main/subghz/application.fam | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
```
```diff
     sources=[
         "subghz.c",
-        "subghz_i.c",
         "subghz_history.c",
+        "subghz_i.c",
         "subghz_last_settings.c",
```
Only the two lines swap; no file added or removed (36 sources before and after).

**Re-run after regeneration:**

```
$ python3 tests/fbt/test_subghz_manifest.py
subghz manifest: 8 of 8 checks passed          # exit 0

$ python3 tests/fbt/test_subghz_sources.py
subghz sources: 50 on disk, 50 quoted, 0 unquoted, 0 missing   # exit 0
```

**Runner's full output** (`tools/run_host_tests.sh`, exit 0, ran in well under a minute):

```
195 checks, 0 failures
speech text: 968 checks, 0 failures
speech queue: 156 checks, 0 failures
speech PCM: 597 checks, 0 failures
speech voice: 4433 checks, 0 failures
chords: 208 checks, 0 failures
throttle: 119 checks, 0 failures
fbt exclusions: 0 failures
subghz sources: 50 on disk, 50 quoted, 0 unquoted, 0 missing
card prune: 8 of 8 checks passed
strip js symbols: 14 of 14 checks passed
subghz manifest: 8 of 8 checks passed
```

## Commits

**Firmware** (`Momentum-Firmware`, branch `screen-reader`), pathspec-scoped to the one file:

```
f3becdf0b subghz: the built-in app's source list in the order tools/subghz_manifest.py writes it
```
`git show --stat`: `applications/main/subghz/application.fam | 2 +-`, 1 file changed — nothing else
in the submodule touched, `applications/external` untouched. Pushed: `git push origin screen-reader`
→ `c00eed5c9..f3becdf0b  screen-reader -> screen-reader`. `upstream` was never pushed to.

**Project** (`main`), pathspec-scoped to the four intended paths:

```
12d415d subghz_manifest: the built-in Sub-GHz source list is regenerated after a Momentum merge
```
`git show --stat`: `Momentum-Firmware | 2 +-`, `tests/fbt/test_subghz_manifest.py | 76 ++`,
`tools/run_host_tests.sh | 7 +`, `tools/subghz_manifest.py | 101 ++` — 4 files changed, matching
exactly what was staged. Pushed: `git push` → `cda2a01..12d415d  main -> main`.

Both commit messages are the brief's, each ending with `Co-Authored-By: Claude Sonnet 5
<noreply@anthropic.com>` (this harness's own attribution line, per the task's instruction to use
"your own Co-Authored-By line as your harness gives it," which supersedes the brief's literal
"Claude Fable 5.1" text).

## Verification (Step 2 of the job)

```
$ git -C Momentum-Firmware log --oneline -1
f3becdf0b subghz: the built-in app's source list in the order tools/subghz_manifest.py writes it
$ git -C Momentum-Firmware log --oneline -1 origin/screen-reader
f3becdf0b subghz: the built-in app's source list in the order tools/subghz_manifest.py writes it
```
Equal.

```
$ git submodule status
 f3becdf0b1c64651e7975bd5e30464f5cf1efca1 Momentum-Firmware (mntm-012-392-gf3becdf0b)
```
Clean (no `-`/`+` prefix) and matches the firmware HEAD above.

```
$ git -C Momentum-Firmware status --porcelain   → (empty)
$ git status --porcelain                        → (empty)
```
Both trees clean.

```
$ git fetch origin main -q && git log --oneline -1 origin/main
12d415d subghz_manifest: the built-in Sub-GHz source list is regenerated after a Momentum merge
$ git log --oneline -1 HEAD
12d415d subghz_manifest: the built-in Sub-GHz source list is regenerated after a Momentum merge
```
`origin/main` equals the project commit.

## Self-review

- Both new files were diffed byte-for-byte (`diff`) against the brief's embedded code blocks after
  writing them — identical, so the "verbatim" requirement is met exactly, including the `noqa:
  E402` comment, the regex, and the docstrings.
- The independently-fetched merge-base manifest (`git -C Momentum-Firmware show d3f89dfe2:...`) has
  "!" entries that match `EXCLUDED` exactly (same 14 basenames), cross-checked by hand in addition
  to the test's own `--verify-upstream` pass.
- The firmware diff is the minimal two-line swap the brief predicted; no filenames were added,
  removed, or renamed (36 before, 36 after).
- Both commits used explicit trailing pathspecs (`-- <paths>`), no `--amend`, no force push, and
  `upstream` was never touched (`git remote -v` push URL is `no_push`; only `origin` was pushed to
  in the submodule, and only the default remote/branch — the project's `origin main` — in the
  outer repo).
- The runner block was appended in the exact shape of the six blocks before it (same `if ! python3
  ... > "$OUT/....txt"; then / cat / echo "<message>" / exit 1 / fi / echo "$(tail -n 1 ...)"`
  pattern), with the exact output filename and failure message the brief specified.

## Concerns

None. Every check the brief predicted matched exactly (7 of 8 before regeneration, 8 of 8 after,
36 sources, a two-line reorder diff), both trees are clean, both remote branches match local HEAD,
and no out-of-scope files were touched in either repository.
