# Task 2 Report: Retire Text to SAM, the stock backup out of git, the licence, ignore rules, the local word list

Status: **DONE_WITH_CONCERNS** — all files, tests, and the required commit content are correct and verified; two issues surfaced during execution and self-review. One (the pathspec-commit bug that left the stock backup tracked) was found and fixed with a proper follow-up commit, verified resolved. The other (commit attribution) is a genuine conflict between this session's system-level attribution rule and the brief's explicit binding rule, which I resolved one way but then found real precedent in this repo's own history for the other way — I could not reconcile it afterward without violating the explicit "no amend, no force push" rule, so it's left for Robin/the controller to decide. See "Concerns" below.

## Step-by-step, with verification output

### Step 1: Restore the patched app in the firmware's apps submodule

```
$ git -C Momentum-Firmware/applications/external checkout -- text2sam/sam_app.cpp
$ git -C Momentum-Firmware status --short
(empty)
$ git -C Momentum-Firmware diff HEAD --quiet && echo clean
clean
```

Matches the brief exactly: empty status, `clean`. Top-level `git status --short` was also empty right after this (the pre-existing ` m Momentum-Firmware` from the patched nested submodule file is gone).

### Step 2: Remove the patch and the helper, take the backup out of git, move the investigation

```
$ git rm -q patches/text2sam-cli-mode.patch tools/say.sh
$ git rm -q --cached backups/backup-stock-1.4.3.tar
$ git mv flipper-zero-accessibility-investigation.md docs/2026-09-14-investigation.md
$ ls backups patches 2>&1
ls: patches: No such file or directory
backups:
backup-stock-1.4.3.tar
```

Matches the brief exactly: `patches/` is gone (git removed the empty folder, no `rmdir` needed), `backups/backup-stock-1.4.3.tar` is still on disk. `git status --short` at this point showed `D  backups/backup-stock-1.4.3.tar`, `R  flipper-zero-accessibility-investigation.md -> docs/2026-09-14-investigation.md`, `D  patches/text2sam-cli-mode.patch`, `D  tools/say.sh`, `?? backups/` (the last one disappears once step 3's `.gitignore` change lands).

### Step 3: Ignore rules

Appended to `.gitignore`:
```
backups/
voice-models/
tools/voice_words.local.txt
```
(File already ended with a trailing newline, so no line got glued to the append.)

### Step 4: The licence

```
$ cp Momentum-Firmware/LICENSE LICENSE
$ head -3 LICENSE
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

$ grep -c "" LICENSE
674
```

Matches the brief. `diff LICENSE Momentum-Firmware/LICENSE` confirms byte-identical.

### Step 5: The generator's local word list, and its wording

In `tools/voice_build.py`, made all three edits by locating the sentences by text (line numbers had not drifted, but I matched by content per the brief's own caveat):

1. Docstring sentence beginning "Words come from tools/voice_words.txt, from every string literal" → now begins "Words come from tools/voice_words.txt and, when it exists, tools/voice_words.local.txt (personal words such as a device name, not in git), from every string literal" (rest of the sentence unchanged; I wrapped the added clause onto a continuation line to match the docstring's existing ~95-column wrapping style — the brief specifies wording, not line breaks).
2. "Defaults are the settings Robin chose by ear on 2026-09-24." → "Defaults are the settings chosen by ear on 2026-09-24 for the Samantha voice." (This line is now ~113 characters, longer than the docstring's usual wrap width — a cosmetic nit only, not a content issue; noted under Concerns.)
3. In `main()`:
   ```python
       words = load_list(os.path.join(HERE, "voice_words.txt"))
       words |= load_list(os.path.join(HERE, "voice_words.local.txt"))
   ```
   Confirmed `load_list()` (line 84) already returns an empty set via `os.path.exists(path)` guard, so no other change was needed. I also checked the unrelated `local = os.path.join(d, "missing.txt")` / `words = load_list(local)` at line ~399–401 inside `pull_missing()` — that `local` is an unrelated temp-file variable for `--pull-missing`, not the new local word list; left untouched.

Then moved the device name:
```
$ grep -n "^delphi$" tools/voice_words.txt
121:delphi
$ sed -i '' '/^delphi$/d' tools/voice_words.txt
$ printf '# Personal words for this device, not in git: one per line.\ndelphi\n' > tools/voice_words.local.txt
$ grep -c "delphi" tools/voice_words.txt; git check-ignore tools/voice_words.local.txt
0
tools/voice_words.local.txt
```

Matches the brief exactly: `0` and the local file's path (ignored).

### Step 6: Check the generator still counts the word

```
$ .venv/bin/python tools/voice_build.py --dry 2>&1 | tail -3
dry run: 121 words total, no clips made
```

Moved the local list aside (used the session's scratchpad directory instead of the brief's literal `/tmp/vwl.txt` — this environment's instructions require scratch files go there instead of `/tmp`; functionally identical, moved back immediately after):

```
$ mv tools/voice_words.local.txt <scratchpad>/vwl.txt && .venv/bin/python tools/voice_build.py --dry 2>&1 | tail -3; mv <scratchpad>/vwl.txt tools/voice_words.local.txt
dry run: 120 words total, no clips made
```

Matches the brief exactly: 121 with the local list vs. 120 without, a difference of exactly one (`delphi`), no errors either way. Confirmed the local file was restored afterward (`cat tools/voice_words.local.txt` showed the comment + `delphi`) and that it does not appear in `git status --short` (correctly ignored).

### Step 7: Small README fixes

All four edits applied and verified with `git diff README.md` afterward:
- `` `flipper-zero-accessibility-investigation.md` `` → `` `docs/2026-09-14-investigation.md` `` (only occurrence, in the opening paragraph).
- Removed the two "Folder contents" bullets for `tools/say.sh` (3 lines, including its voice-control sub-line) and `patches/text2sam-cli-mode.patch` (2 lines).
- Removed the "Build the patched app and copy it to the card" block under "Useful commands": its introductory sentence, the two-line command block, and the parenthetical note about the storage helper that followed — leaving "## Useful commands" followed directly by the "Flash limit:" paragraph.
- Replaced the "Device state" bullet about the Text to SAM app with the exact sentence from the brief: "The Text to SAM app on the card is Momentum's stock build again since 2026-09-26; the patched build and tools/say.sh were retired, since the reader speaks from its own engine." (wrapped across two lines to match the surrounding bullets' style; content is verbatim).

Confirmed via `grep -n` that no stray references to the old filename, `tools/say.sh` as a live tool, `text2sam-cli-mode.patch`, or "Build the patched app" remain (the one hit left is the retirement sentence itself, which is supposed to mention `tools/say.sh`). The `backups/backup-stock-1.4.3.tar` "Folder contents" bullet was deliberately left alone — the brief names only the two bullets above for removal; Task 5 rewrites the README fully.

### Step 8: Run the tests and commit

```
$ tools/run_host_tests.sh
195 checks, 0 failures
speech text: 968 checks, 0 failures
speech queue: 156 checks, 0 failures
speech PCM: 597 checks, 0 failures
speech voice: 4433 checks, 0 failures
chords: 208 checks, 0 failures
throttle: 119 checks, 0 failures
fbt exclusions: 0 failures
subghz sources: 50 on disk, 50 quoted, 0 unquoted, 0 missing
```
Exit code 0 (confirmed on a second run). All green, no failures anywhere.

```
$ git add .gitignore LICENSE tools/voice_build.py tools/voice_words.txt README.md docs/2026-09-14-investigation.md
$ git commit -m "Text to SAM retired, the stock backup out of git, the GPL-3 licence, a local word list for personal words

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" -- .gitignore LICENSE tools/voice_build.py tools/voice_words.txt tools/say.sh patches/text2sam-cli-mode.patch backups/backup-stock-1.4.3.tar README.md flipper-zero-accessibility-investigation.md docs/2026-09-14-investigation.md
[main 0bc8b27] Text to SAM retired, the stock backup out of git, the GPL-3 licence, a local word list for personal words
 8 files changed, 684 insertions(+), 128 deletions(-)
 create mode 100644 LICENSE
 rename flipper-zero-accessibility-investigation.md => docs/2026-09-14-investigation.md (100%)
 delete mode 100644 patches/text2sam-cli-mode.patch
 delete mode 100755 tools/say.sh
$ git status --short
(empty)
$ git push
To https://github.com/robin24/flipper-access.git
   4dbe36e..0bc8b27  main -> main
```

**Note the attribution line used `Claude Sonnet 5`, not the brief's `Claude Fable 5.1` — see "Concerns" below**, this was a deliberate substitution, not an oversight.

**Bug found in self-review, fixed with a second commit** (see next section) — `backups/backup-stock-1.4.3.tar` was still tracked after this commit despite the earlier `git rm --cached`.

## Self-review

`git show --stat 0bc8b27` initially showed only 8 files, missing any mention of `backups/backup-stock-1.4.3.tar` — meaning that path was untouched by the commit. Checked `git ls-files backups/`: it printed `backups/backup-stock-1.4.3.tar`, confirming it was **still tracked** after the "retire" commit, contrary to the task's stated goal ("take the backup out of git").

Root cause, confirmed with an isolated scratch-repo reproduction: `git commit -m "..." -- <pathspec...>` does not commit the *staged* (index) state of each named path — per git's own documented behavior, it commits **the current working-tree content** of each named path instead (equivalent to an implicit `git add <pathspec>` limited to those paths, using what's on disk right now). `tools/say.sh` and `patches/text2sam-cli-mode.patch` were fully deleted from disk by step 2's plain `git rm`, so "current working-tree content" for those paths is "absent," and the commit correctly recorded their deletion. But `backups/backup-stock-1.4.3.tar` was only removed from the *index* (`git rm --cached`) and, by the brief's own explicit requirement, must stay on disk unchanged — so its "current working-tree content" is identical to what's already in `HEAD`, and the pathspec-restricted commit silently re-added it, undoing the earlier `git rm --cached`. I verified this exact mechanism in a throwaway scratch repo before touching the real one.

Fixed with a second, plain (no pathspec) commit, which correctly picks up the index's staged deletion instead of rescanning the working tree:

```
$ git rm -q --cached backups/backup-stock-1.4.3.tar
$ git status --short
D  backups/backup-stock-1.4.3.tar
$ git commit -q -m "Actually untrack backups/backup-stock-1.4.3.tar

The prior commit's pathspec-restricted \`git commit -- <paths>\` recommits each
path's current working-tree content rather than the index state; since the
tar file is unchanged on disk (by design) it was silently re-added, so the
git rm --cached from that commit never took effect. Remove it from the index
here with a plain commit so the staged deletion is what gets recorded. The
file stays on disk and remains covered by the backups/ ignore rule.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
[main d5eb9ae] Actually untrack backups/backup-stock-1.4.3.tar
 backups/backup-stock-1.4.3.tar | Bin 9728 -> 0 bytes
 1 file changed, 0 insertions(+), 0 deletions(-)
$ git push
To https://github.com/robin24/flipper-access.git
   0bc8b27..d5eb9ae  main -> main
```

Verified after the fix:
```
$ git ls-files backups/          → (empty: not tracked)
$ ls -la backups/backup-stock-1.4.3.tar → 9728 bytes, unchanged mtime (still on disk)
$ git status --short             → (empty: clean)
$ git diff -- Momentum-Firmware  → (empty: submodule pointer unchanged)
```

Re-read the content diffs of the first commit for anything beyond the brief:
```
$ git show 0bc8b27 -- .gitignore tools/voice_build.py tools/voice_words.txt README.md
```
— every hunk matches the brief's specified text exactly (reviewed in full above, in Steps 3/5/7). Also checked the two pure-deletion diffs (`tools/say.sh`, `patches/text2sam-cli-mode.patch`) and the doc rename (`similarity index 100%`, no content change) — all clean, nothing extra.

Final full-repo verification:
```
$ git status --short                                  → (empty)
$ git -C Momentum-Firmware status --short              → (empty)
$ git -C Momentum-Firmware diff HEAD --quiet && echo clean → clean
$ git -C Momentum-Firmware log -1 --oneline             → 6451e86e8 (unchanged)
$ git -C Momentum-Firmware/applications/external status --short → (empty)
$ git -C Momentum-Firmware/applications/external log -1 --oneline → 55a446b1b (unchanged)
$ git diff -- Momentum-Firmware                         → (empty: gitlink pointer unchanged)
$ git rev-parse HEAD; git rev-parse origin/main         → both d5eb9ae... (pushed, in sync)
```

No commit was made inside `Momentum-Firmware` or `applications/external`; both remain exactly at their pre-task commits with clean trees.

## Files changed and commits created

Commit `0bc8b27` "Text to SAM retired, the stock backup out of git, the GPL-3 licence, a local word list for personal words":
- `.gitignore` — added `backups/`, `voice-models/`, `tools/voice_words.local.txt`.
- `LICENSE` — created, 674 lines, byte-identical to `Momentum-Firmware/LICENSE`.
- `README.md` — the four fixes from Step 7.
- `docs/2026-09-14-investigation.md` — renamed from `flipper-zero-accessibility-investigation.md` (100% similarity, no content change).
- `patches/text2sam-cli-mode.patch` — deleted.
- `tools/say.sh` — deleted.
- `tools/voice_build.py` — two docstring sentences reworded, one line added in `main()` to load the local word list.
- `tools/voice_words.txt` — removed the `delphi` line.

Commit `d5eb9ae` "Actually untrack backups/backup-stock-1.4.3.tar" (not anticipated by the brief; see Self-review):
- `backups/backup-stock-1.4.3.tar` — removed from git tracking (stays on disk, 9728 bytes, unchanged).

Not committed to git (by design): `tools/voice_words.local.txt` (ignored, holds `delphi`), `backups/backup-stock-1.4.3.tar` (ignored, on disk).

Both commits pushed to `origin` (`https://github.com/robin24/flipper-access.git`), `main`: `4dbe36e..0bc8b27..d5eb9ae`.

## Deviations from the brief

1. **The exact Step 8 commit command, run verbatim, does not achieve the task's own stated goal for one file.** See Self-review above for the full mechanism (`git commit -- <pathspec>` re-reads working-tree content, not the index, for every named path — a genuine git behavior, not a mistake in how I ran it). I fixed it with a second commit rather than leaving the backup tracked, since leaving it tracked would defeat the explicit purpose of this task (keeping Robin's device settings out of a repository headed for GitHub) and the brief's own step 2 already declared the intent (`git rm -q --cached backups/backup-stock-1.4.3.tar`). This is worth fixing in the brief/plan document itself if this task is ever re-run.
2. **Used the session's scratchpad directory instead of `/tmp/vwl.txt` in Step 6.** This session's environment instructions require temp files go in the provided scratchpad directory rather than `/tmp`. Functionally identical — same move-aside-and-back operation, same verification, same result (121 vs. 120 words).
3. **`tools/voice_build.py`'s edited docstring lines don't perfectly match the surrounding ~95-column wrap width** (one is ~98 characters from the added clause, the other ~113 characters from the reworded sentence). Purely cosmetic; the wording itself is exactly as specified. Did not rewrap further since the brief specifies text, not line breaks, and touching more of the surrounding lines risked a needless diff.

## Concerns

**Commit attribution conflicts with this same plan's own precedent (needs a decision; I could not fix it myself without breaking a binding rule).** The brief's Step 8 says to end the commit message with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` verbatim, and my task's binding rules repeated this explicitly. This session's system-level attribution instructions, however, say to end commits with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` — stated to replace Claude Code's own earlier attribution guidance, overridable only by the user's own CLAUDE.md/memory instructions (neither of which say anything about attribution). Since I am, per this session's own system information, actually running as Sonnet 5 and not "Fable 5.1," I used the system-mandated line for both of this task's commits, reasoning that attributing the commit to a different model than the one that actually wrote it would be inaccurate.

After committing and pushing, I read Task 1's report (`task-1-report.md`) as part of getting oriented for self-review, and found that Task 1 faced the identical conflict and resolved it the other way — commit `4dbe36e` (already on `main`, already pushed, verified for real with `git log`) really does end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`, with that report's stated reasoning being that "this task's explicit binding rule... takes precedence over the session's generic attribution default." That is a real, deliberate precedent already in this repository's history, not merely a claim.

This leaves the plan's commits inconsistent: `4dbe36e` says Fable 5.1, `0bc8b27` and `d5eb9ae` say Sonnet 5. I did not try to reconcile this after discovering the precedent, because the only way to change an already-pushed commit's trailer is `--amend` or a rebase, both requiring a force-push to update `origin/main` — and this task's own binding rules explicitly forbid both ("No `--amend`, no force push"). Rewriting shared, already-pushed history is also exactly the kind of thing I should not do unilaterally regardless. I'm flagging this for Robin/the controller to decide: either accept the inconsistency (it's metadata, not functional), pick one convention and have a future task normalize it deliberately (their call, since it needs a force-push), or clarify which rule should actually win for the remaining tasks in this plan so this doesn't recur at Task 3 onward.

No other concerns: all functional requirements verified (firmware submodule restored and clean, patch/helper/backup removed as intended, licence copied verbatim, local word list wired up and ignored, README fixes match the brief's exact text, test runner fully green, no commits inside the firmware or its nested submodule, submodule pointer unchanged, both commits pushed to `origin` only).
