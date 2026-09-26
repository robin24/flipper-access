# Plan A fix wave: report

Implementer's report for `fix-wave-brief.md`. Everything in the brief was done in its order, A to E. Deviations and judgment calls are listed at the end, under "Not as written".

## A. Firmware

A1, commit 3bdcca70c on `screen-reader`, pushed; pointer bump aefa6b0 in the project.
`lib/momentum/settings.c`, `momentum_settings_save()`: the brief's comment, word for word, then `if(!furi_hal_is_normal_boot()) { FURI_LOG_I(TAG, "settings not saved: not a normal boot"); return; }` before anything else. The file already includes `<furi_hal.h>`. The log tag is the file's own `TAG`, "MomentumSettings", not the literal "Momentum" of the brief: the file defines `TAG` for exactly this and every file in `lib/momentum/` logs through its own `TAG`. The message is the brief's. clang-format (the toolchain's, `--dry-run --Werror`) is clean. Build check: an incremental `./fbt COMPACT=1 DEBUG=0 firmware_all` compiled `lib/momentum/settings.c` with no warning; the wiped release build of section E has no warning outside `applications/external` either (the same four fbt manifest warnings and twenty external-app compiler warnings as the build of a0dea0841).

A2, commit a5c2ed7d9 on `screen-reader`, pushed; pointer bump 73acc18 in the project.
`git checkout c0ba0af07^ -- targets/f18/target.json`: the one line `"mjs",` is back. `git diff d3f89dfe2 -- targets/f18/target.json` (the merge base) is now empty, so the file is upstream's. Message as the brief gives it, with one sentence of body.

## B. Tools and tests (project commit 16b5931)

Each of B1 to B4 went test first: the test was extended, run against the unchanged tool and seen to fail, then the tool was changed and the test passed. The runs are below, verbatim apart from long tracebacks shortened where marked.

B1, `tools/subghz_manifest.py` and `tests/fbt/test_subghz_manifest.py`.
- `rewrite()` now finds the App block with appid "subghz" up to the `)` that starts a line, and inside it rewrites two things: the sources list, found only where `sources=[` starts a line after leading spaces (regex `^([ \t]*sources=\[)(.*?)(\n[ \t]*\],)` with `re.M`), and the apptype line, `^([ \t]*)apptype=FlipperAppType\.\w+,` replaced with `apptype=FlipperAppType.APP,`. A block without a sources list, or with other than exactly one apptype line, ends in one sentence (`sys.exit`) rather than a wrong file. A helper `parts()` is shared with `upstream_excludes()`.
- `--verify-upstream`: the git calls go through a `git()` helper with `stderr=DEVNULL`; `upstream_excludes()` catches `CalledProcessError` and `OSError` and exits with one sentence: "no merge base with upstream/dev in the firmware checkout: fetch the upstream remote, then run --verify-upstream again" (or "the merge base <hash> has no <file> to compare with" when only the `git show` fails). Checked by hand in a checkout without upstream/dev: that one line, exit 1.
- The docstring says all of this: the apptype, why (Momentum's MENUEXTERNAL loads the app from the card), the line anchoring, the one-sentence failure.
- The test: the synthetic block has `apptype=FlipperAppType.MENUEXTERNAL,` and a comment `# a comment that mentions sources=[ before the list`; checks that the apptype becomes APP, that the other block keeps PLUGIN, and that the comment and the real `sources=[` line survive. New: the fork's current subghz block has `apptype=FlipperAppType.APP,` (runs on CI); `--verify-upstream` run from a copy of the script beside an empty `git init` firmware checkout must exit 1 with one line on stderr, no traceback, naming upstream/dev; the golden check (skipped without upstream/dev): the merge base's manifest through `rewrite()` equals the fork's file with comment lines (stripped lines starting with `#`) dropped on both sides, with a diff printed on failure; the EXCLUDED check kept. One skip line covers both merge-base checks. Counts stay dynamic.

Failing run, before the tool change:

```
FAIL the subghz block's apptype becomes APP
FAIL the rest of the block is untouched, the comment that mentions sources=[ included
FAIL --verify-upstream without upstream/dev: one sentence and exit 1, got exit 1:
fatal: Not a valid object name upstream/dev
Traceback (most recent call last):
  (14 traceback lines, ending:)
subprocess.CalledProcessError: Command '['git', '-C', '/var/folders/.../Momentum-Firmware', 'merge-base', 'upstream/dev', 'HEAD']' returned non-zero exit status 128.
--- script
+++ fork
@@ -1,7 +1,7 @@
 App(
     appid="subghz",
     name="Sub-GHz",
-    apptype=FlipperAppType.MENUEXTERNAL,
+    apptype=FlipperAppType.APP,
     targets=["f7"],
     entry_point="subghz_app",
     icon="A_Sub1ghz_14",
FAIL golden: the merge base's manifest through the script is the fork's file, comment lines aside
subghz manifest: 8 of 12 checks passed
exit 1
```

Passing run, after it:

```
subghz manifest: 12 of 12 checks passed
exit 0
```

The tool for real on the fork's checkout: `tools/subghz_manifest.py --check --verify-upstream` printed "the exclude list matches the merge base's manifest" and "...application.fam: unchanged, 36 sources", exit 0.

B2, `tools/card_prune.py` and `tests/fbt/test_card_prune.py`.
- Candidates are only names starting with `OWN_PREFIXES = ("f7-update-sonar-", "f7-update-mntm-screen-reader-", "f7-update-mntm-HEAD-")`; every other folder is never touched, so `DEFAULT_KEEP` is gone and `--keep` stays for explicit names.
- The running build: the name ends with "-" plus the lower-case `firmware.commit.hash`, or, when `firmware.version` is not `mntm-dev` (the constant `DEV_VERSION`), the name is `f7-update-<firmware.version>`. `running_hash()` became `running_build()`, which returns the hash and the version from one `info device`.
- New signature `plan(folders, running_hash, running_version, keep)`. The import guard is `except (SystemExit, ImportError)`, and `main()` now exits with flipper_cli's pyserial sentence when the import failed, instead of calling `None`. The summary line printed by the tool also names the version: "running build <hash>, version <version>; ...". The test's summary line keeps its form ("card prune: N of N checks passed"), so the runner needed no change for it.
- The docstring gives the rule and why a foreign package is never touched.
- The test: eleven checks, counted as they run (it was a fixed "of 8"). New cases: foreign packages (`f7-update-1.4.3`, `f7-update-mntm-012`, `f7-update-1.5.0`, `f7-update-unlshd-080e`, `other`) never candidates, also when the device runs the Unleashed one; a tagged running build `f7-update-sonar-0.1.0` with version `sonar-0.1.0` stays while `f7-update-sonar-0.0.9` goes, and a same-commit CI folder `f7-update-sonar-ci-b1c2d3e4` stays by its hash; with `mntm-dev` running the tagged folders go; an `mntm-HEAD` pair, the running one staying. The old cases are adapted (a CI folder `f7-update-sonar-ci-1234abcd` in place of `f7-update-sonar-0.1.0` as the "other build").

Failing run, before the tool change (the new signature):

```
Traceback (most recent call last):
  File "/Users/robin/Downloads/flipper-access/tests/fbt/test_card_prune.py", line 40, in <module>
    plan(FOLDERS, "6451e86e", "mntm-dev", set()) == ["f7-update-mntm-screen-reader-a9e4e7b9", "f7-update-sonar-ci-1234abcd"],
    ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: plan() takes 3 positional arguments but 4 were given
exit 1
```

Since that failure is only the signature, the same checks were also run against the old rule through a scratch shim that gives the old `plan()` the new signature (old rule plus `DEFAULT_KEEP`); it fails on the rule itself:

```
FAIL a foreign package or a folder that is not a package is never a candidate
FAIL a foreign package stays whatever the device runs
FAIL a tagged running build is recognised by its version: f7-update-sonar-0.1.0 stays, f7-update-sonar-0.0.9 goes, and the same commit's build named by its hash stays too
card prune: 8 of 11 checks passed
```

Passing run, after the change:

```
card prune: 11 of 11 checks passed
exit 0
```

B3, `tools/strip_js_symbols.py` and `tests/fbt/test_strip_js_symbols.py`.
- The docstring names the step: after a merge that conflicts on this file, take upstream's side and run the script, with the two commands on their own lines (`git checkout --theirs targets/f7/api_symbols.csv`, then `../tools/strip_js_symbols.py`, in the firmware checkout). It also says the presence check keys on kind and name.
- `present` is now a set of `(kind, name)`, and our line is added when its `(kind, name)` is missing.
- The test: the version expectation is the literal `Version,+,90.6,,` (and `FORK_MINOR_STEP` is no longer imported); a new check adds `Variable,+,input_set_filter,int,` to the synthetic file and requires our `Function,-,input_set_filter,...` line in the output; git's stderr goes to DEVNULL.

Failing run, before the tool change:

```
FAIL our line is added when only a row of another kind has its name
strip js symbols: 14 of 15 checks passed
exit 1
```

Passing run, after it:

```
strip js symbols: 15 of 15 checks passed
exit 0
```

`tools/strip_js_symbols.py --check` on the fork's file: "unchanged", exit 0.

B4, `tools/upstream_check.sh` and `tests/fbt/test_upstream_check.py`.
- The fetch is `git fetch --quiet --tags "$REMOTE"`, where `REMOTE` is the part before the first slash when the ref has one, else `upstream`. `--repo`, `--upstream` and `--ours` given last without a value print "<option> needs a value after it" on stderr and exit 1 (a small `no_value` function), instead of tripping `set -u`. The header says both, and points to the merge routine in the device notes.
- The test: `-c commit.gpgsign=false` on every throwaway git call; a probe `git merge-tree --write-tree base base` right after the first commit, and on failure the line "skipped the upstream check tests: git merge-tree --write-tree needs git 2.38 or newer" and exit 0. New checks: two remotes cloned from the throwaway repository with one new commit each, "upstream" carrying the tag `mntm-013` and "other" the branch `newer`; with the fetch on, `--upstream mntm-013` must fetch the tag from `upstream` (2 new commits, clean dry run, exit 0) and `--upstream other/newer` must fetch from `other`; each of the three options given last must give one line, naming the option, without "unbound", and exit 1. Counts are dynamic (it was a fixed "of 9").

Failing run, before the script change:

```
FAIL a tag is fetched from the remote upstream with its tags:
fatal: 'mntm-013' does not appear to be a git repository
fatal: Could not read from remote repository.

Please make sure you have the correct access rights
and the repository exists.

FAIL --repo given last without a value: one sentence and exit 1, got 1:
/Users/robin/Downloads/flipper-access/tools/upstream_check.sh: line 22: $2: unbound variable
FAIL --upstream given last without a value: one sentence and exit 1, got 1:
/Users/robin/Downloads/flipper-access/tools/upstream_check.sh: line 23: $2: unbound variable
FAIL --ours given last without a value: one sentence and exit 1, got 1:
/Users/robin/Downloads/flipper-access/tools/upstream_check.sh: line 24: $2: unbound variable
upstream check: 10 of 14 checks passed
exit 1
```

Passing run, after it:

```
upstream check: 14 of 14 checks passed
exit 0
```

The script for real: `tools/upstream_check.sh` fetched Momentum with its tags and printed merge base d3f89dfe2, 0 new commits, 84 of ours on top, footprint 24 added and 54 modified (53 at Task 8, plus c0ba0af07's f7 `target.json`; the f18 one is upstream's again), "nothing to merge", exit 0. `--upstream mntm-012` worked too (mntm-013 does not exist yet; mntm-012 is the newest tag), and `--upstream` alone printed "--upstream needs a value after it", exit 1.

B5, the runner and the tests' output.
- `tools/run_host_tests.sh`: the header names the four tool tests, says clang without "from Xcode", and says the skip lines are printed. A `summary` function (awk) prints a Python check's lines that start with "skipped", then its last line unless that was a skip line itself; all six Python blocks use it in place of `echo "$(tail -n 1 ...)"`.
- `test_strip_js_symbols.py` and `test_subghz_manifest.py` send git's stderr to DEVNULL (and the manifest tool's own git calls do too). This removes the "fatal: Not a valid object name upstream/dev" line that the continuous build printed in its host tests step.
- `tests/fbt/test_subghz_sources.py`: "rebase" is "merge".
- A CI-like run on this Mac before the commit: a scratch copy of `tools/` and `tests/` beside a `git clone --depth 1` of the firmware (no upstream remote, no upstream/dev) ran the whole runner green, printing the two skip lines and no git error line. The real CI run (section C) shows the same.

B6: `chmod +x` on `tools/card_prune.py`, `tools/strip_js_symbols.py` and `tools/subghz_manifest.py`; the commit records mode 100644 to 100755 for all three.

B7: `tools/flash_headroom.sh` prints "too large by N bytes" on its own line and exits 1 when the image is over the limit. It has no test, so it was checked by hand with dummy images: 880,700 bytes gave the size line then "too large by 60 bytes", exit 1 (before the change: the size line alone, exit 1); 880,640 bytes, spare 0, exit 0; the real image, exit 0; a missing file, the old message, exit 1.

The runner's last lines, on the commit (16b5931), on this Mac:

```
throttle: 119 checks, 0 failures
fbt exclusions: 0 failures
subghz sources: 50 on disk, 50 quoted, 0 unquoted, 0 missing
card prune: 11 of 11 checks passed
strip js symbols: 15 of 15 checks passed
subghz manifest: 12 of 12 checks passed
upstream check: 14 of 14 checks passed
exit 0
```

## C. Workflow (project commit e7f0626)

`.github/workflows/build.yml`: `permissions: contents: read` at the top level; `on: push: branches: ["**"]` with a one-line comment that a tag push is for the release workflow; `runs-on: ubuntu-24.04`.
`gh api repos/actions/<name>/releases/latest --jq .tag_name` gave checkout v7.0.1, cache v6.1.0 and upload-artifact v7.0.1, so the workflow uses `actions/checkout@v7`, `actions/cache@v6` and `actions/upload-artifact@v7`. The release notes of every major in between were read: the changes are the Node 24 runtime, ESM, checkout's credentials in a separate file and its block on fork checkouts for `pull_request_target`, and upload-artifact's new opt-in `archive: false`. None touches the inputs this workflow uses. The major tags v7, v6 and v7 exist.

The push (263dfd7..e7f0626: the two pointer bumps, the tools commit and the workflow commit) started run 36222517024:
https://github.com/robin24/flipper-access/actions/runs/36222517024
Result: success, in 11 min 32 s (06:01:47 to 06:13:19 UTC), on image ubuntu-24.04 20260920.314.1, with the actions downloaded as checkout@v7, cache@v6 and upload-artifact@v7.
- The cache hit: "Cache hit for: toolchain-ca56839b...", "Cache restored from key", and in the post step "Cache hit occurred on the primary key ..., not saving cache."
- The host tests step shows the skip lines and no git error line: "skipped the golden check: no upstream/dev in this checkout" before "strip js symbols: 14 of 14 checks passed", and "skipped the golden check and the exclude list check: no upstream/dev in this checkout" before "subghz manifest: 10 of 10 checks passed"; card prune 11 of 11, upstream check 14 of 14.
- Headroom: "firmware.bin 864648 bytes, limit 880640, spare 15992 bytes".
- Artifact sonar-ci-a5c2ed7d, 12,043,834 bytes.
- The run has no annotations at all: the Node 20 warning of the v4 majors and the ubuntu-latest migration notice of the run before are both gone.
One push, one run, no fix round.

The later pushes of this wave (the documentation and the measurements, at the end of E) start one more run each time they are pushed; they were pushed once, together, after this run had finished, so the concurrency rule could not cancel it.

## D. Documentation (project commits f251d88 and 450ff9c)

D1, `README.md`:
- Title area: "Flipper Access is the project behind Sonar, a firmware for the Flipper Zero that a blind person can use without sight." Momentum is linked where first named: `[Momentum](https://github.com/Next-Flip/Momentum-Firmware)`.
- What changed: a new "Changed:" list after "Removed:": the reader on from the first boot; the main menu in the List style, the only style whose focus the reader can name, the other styles read by their inverted highlight where possible; FreeRTOS's stack overflow check, off in Momentum, crashing at once and naming the thread.
- Back chords: `sr watch` keeps its sentence and gets its command, `.venv/bin/python tools/sr_drive.py --interactive`, in a code block inside the list item. The volume bullet ends: "During a firmware update a volume change is heard but not kept, since no settings are saved while the device updates."
- The toggle chord, in First boot and in Back chords: "the lock screen included, and by design also in the PIN entry, which has not been tried on a device". The Locking section's remark about locking Robin out is cut; the sentence is now "The PIN entry has not been tried on a device yet."
- The voice: "skipped and noted, like a word"; "The Piper backend has not been run yet, so its output is untested."; then its own paragraph: the tools look for the serial port under the name it has on a Mac, and on any other system the port is given with `--port`, or in `FLIPPER_PORT` for the console tools such as `tools/flipper_cli.py`. No port or device is named.
- Code blocks: `sr on` (in the Screen Reader row), `sr voice off` and `sr voice on` (Voice commands), `sr voice on` after a dead transfer and `--sync --sync-all` (Making a vocabulary).
- The Delete prompt: "Delete asks `Delete <name>?`, naming the entry, ..." (the firmware's string is "Delete %s?").
- "loads nothing from the card" in both places.
- Building from source: after the clone block, the detached HEAD, the `f7-update-mntm-HEAD-<hash>` name and the HEAD branch, and `git -C Momentum-Firmware checkout screen-reader` in its own block; "Only the Flipper Zero target, f7, is built."; the host tests need clang, which a Mac has with Xcode's command line tools and Linux installs from its packages. The paragraph after it was rewrapped.
- One sentence more than the brief asks, in Following Momentum: the whole routine is under Merging Momentum in `docs/device-notes.md`.
- Checked: no em-dash or en-dash, no table, no line over 100 characters, no device name and no port (`grep` for Delphi, R0skie, usbmodem and /dev/ finds nothing); "Robin" remains only in How it was made.

D2, `docs/device-notes.md`:
- The List-style fact once: the first copy (Device state) gains "the other styles are read by inversion where possible"; the Phase 1 paragraph under Useful commands, with its promise of hints, is gone.
- The settings paragraph: the file has lock on boot off, dark mode on and volume 40; the update of 2026-09-26 left it at its defaults because keys pressed during the update saved the RAM settings over the restored file; the three values were restored from that update's `backup.tar` and the device rebooted; since 3bdcca70c the firmware saves no settings in an update boot.
- Routine step 1: the full wipe, `rm -rf Momentum-Firmware/build`, before a release build and after a merge from Momentum, with the stale `libmjs.a` as the reason; the narrower wipe for everyday builds.
- Crash diagnosis: builds of one commit on this Mac give the same image, but the continuous build's image differs by a few bytes, so a release's own `firmware.elf` must be kept. The E commit makes the numbers exact (12 more for a0dea0841, 4 fewer for a5c2ed7d9; see "Not as written").
- New section "Merging Momentum", between Routine and The voice on this card, ten numbered steps with the commands in code blocks: fetch with tags; `tools/upstream_check.sh --upstream mntm-013`; `git merge --no-commit mntm-013`; the API table (`checkout --theirs`, `tools/strip_js_symbols.py`, `add`), run in any case; the Sub-GHz manifest the same way; commit "Merge Momentum mntm-013", then `tools/subghz_manifest.py --verify-upstream`; host tests; full wipe, build, headroom; flash with Routine steps 4 to 7, RAM probe and `tools/sr_drive.py`, the README's chords by hand; push, bump, tag both repositories as section 7 of the spec says.
- Also brought in line with B2: the `tools/card_prune.py` entry now says it keeps every other firmware's package.
- `docs/superpowers/specs/2026-09-26-github-release-design.md` section 3: "Its blob stays in the history, since it holds only those, and no keys and no PIN." (the sentence before names settings, dolphin state and region data). Also section 4's `card_prune.py` paragraph, whose "the two rollback packages are kept by default" no longer matched the tool: it now names the `mntm-HEAD` builds, the version rule for a tagged release, and that no other firmware's package is touched.

D3, privacy (commit 450ff9c):
- `docs/superpowers/build-logs/2026-09-24-clip-voice-spelling/task-1-report.md`: line 187 `hardware.uid : redacted (identifier redacted before publication)`, line 228 `radio.ble.mac : redacted`.
- `docs/superpowers/build-logs/2026-09-24-polish-round/task-1-report.md`: line 264 `hardware.uid : redacted (identifier redacted before publication)`, line 1004 `hardware.uid : redacted`.
- The grep of the brief, `git grep -n -E "redacted|redacted|hardware.uid|radio.ble.mac"` over the project without the firmware, found exactly those four lines before the change and nothing else; after it, the same four lines with "redacted" in place of the values. A wider, case-insensitive grep for the two values (also as a colon-separated MAC, and over the working tree's docs, README, tools and tests) finds nothing. The history still holds the values; rewriting it is Robin's decision, as the controller ruled.
- The measurements appended in E carry only the firmware lines of `info device`; the scratch copies of the full replies had the two identifier lines stripped.

## E. Flash and verify

Order as the brief gives it: A pushed and pointer-bumped, B and D committed, then the build. The full outputs are appended verbatim to `docs/measurements/2026-09-26-plan-a.txt` under "After the fix wave" (commit a50c72d), with `info device` cut to its firmware lines. The essentials:

Build: `rm -rf Momentum-Firmware/build`, then `./fbt COMPACT=1 DEBUG=0 updater_package` from 08:06:45 to 08:09:19, 154 s, exit 0; the firmware tree clean before and after; "API version 87.3 is up to date"; no warning outside `applications/external` (4 fbt manifest warnings, 20 external-app compiler warnings, as for a0dea0841).
Headroom: `firmware.bin 864652 bytes, limit 880640, spare 15988 bytes`, exit 0; 88 bytes more than a0dea0841. md5 f593cc5e02b7029df1cc02e3c5f3b228, unchanged by the flash command.

Before the flash, [08:09:38]: no application running; `/ext/update` held f7-update-1.4.3, f7-update-mntm-012 and f7-update-mntm-screen-reader-a0dea084; `sr status` volume 40, last crash 2001384F in build 9028a849; `info device` a0dea084, dirty false, Sonar, system.debug 1, log level 5; `storage read /int/.momentum_settings.txt`: Size 959, 45 keys, among them `lock_on_boot: false`, `dark_mode: true`, `sr_volume: 40`, `menu_style: 0`, `screen_reader: true`.

Flash: `./fbt COMPACT=1 DEBUG=0 flash_usb_full` from 08:10:11 to 08:12:23, 132 s, exit 0. Port watch: gone at 08:12:21, back at 08:19:06 (405 s), steady by 08:19:36. The UART capture logged the RAM updater to stage 11 at 08:12:44 and then nothing, as the updater turns logging off.

After the flash, before any key, [08:19:37]:

```
== sr screen
records: 0, content layer: desktop
reads as: 
== info device
(the firmware lines only)
firmware.commit.hash          : a5c2ed7d
firmware.commit.dirty         : false
firmware.branch.name          : screen-reader
firmware.branch.num           : 0
firmware.version              : mntm-dev
firmware.build.date           : 26-09-2026
firmware.target               : 7
firmware.api.major            : 87
firmware.api.minor            : 3
firmware.origin.fork          : Sonar
firmware.origin.git           : https://github.com/robin24/Momentum-Firmware.git
== sr status
enabled: yes
last crash: at 2001384F in build 9028a849
volume: 40, verbosity: 1, change delay: 3000 ms
frames: 2, dropped: 0, announcements: 1, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1089 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2516
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0, muted 0, open max 27 ms, last 27 ms
free heap: 115808
```

The hash is the firmware HEAD, a5c2ed7d912b222f2d82f563dfea2a92a97bf793; dirty false; origin Sonar. `sr screen` found the post-update slideshow on the desktop layer, as after every flash, not a crash popup. The same reply had system.debug 0 and system.log.level 1: the updater cleared them again.

The settings file comparison: `storage read /int/.momentum_settings.txt` after the flash is identical to the copy from before it. `diff` printed nothing, and both copies (the size line and all 45 keys) have the md5 1716b05d87cd5de935cfd2cf5d1d3592: `lock_on_boot: false`, `dark_mode: true`, `sr_volume: 40`. Whether anyone pressed a key on the device during the update is not known (nothing was sent from the Mac, and the console is gone then), so this flash shows that the file survives an update of this firmware, but it did not exercise the new guard itself; nothing can, from the Mac.

Then [08:19:53] `sysctl debug 1` ("Debug enabled.") and `sysctl log_level debug` ("Set log level to debug"); `info device` then read system.debug 1 and system.log.level 5, and the UART capture received lines again from 08:19:54.

The prune:

```
[08:20:04] card_prune.py --dry
running build a5c2ed7d, version mntm-dev; 4 folders in /ext/update; keeping 3: f7-update-1.4.3, f7-update-mntm-012, f7-update-mntm-screen-reader-a5c2ed7d
would remove f7-update-mntm-screen-reader-a0dea084
would remove 1 folders
exit 0

[08:20:05] card_prune.py
running build a5c2ed7d, version mntm-dev; 4 folders in /ext/update; keeping 3: f7-update-1.4.3, f7-update-mntm-012, f7-update-mntm-screen-reader-a5c2ed7d
removing f7-update-mntm-screen-reader-a0dea084
removed 1 folders
real 0.71
exit 0
== storage list /ext/update
	[D] f7-update-1.4.3
	[D] f7-update-mntm-012
	[D] f7-update-mntm-screen-reader-a5c2ed7d
```

The previous build's folder went; the two rollback packages stayed by the new rule, without a keep list.

The chord session: first `input send back short` closed the post-update splash (then `sr screen`: the battery alone on the desktop; `loader info`: no application), as in the earlier flashes, since `sr_drive.py` starts on the home screen. Then:

```
[08:20:22] sr_drive.py --chords
     home  desktop, no focus
ok   home  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 1106 ms played, 15972 subsamples
ok   home  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 4135 ms played, 65194 subsamples
ok   home  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 1108 ms played, 16399 subsamples
ok   home  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1107 ms played, 16399 subsamples
     menu  fullscreen, FOCUS 1/11 "Apps", reads as: Settings. Sub-GHz. Apps, 1 of 11
ok   menu  back + up       utterances +1, aborted +0, dropped +0, announcements +0; last 4389 ms played, 68392 subsamples
ok   menu  back + down     utterances +1, aborted +0, dropped +0, announcements +0; last 1935 ms played, 30010 subsamples
ok   menu  back + ok       utterances +1, aborted +0, dropped +0, announcements +0; last 2004 ms played, 30272 subsamples
ok   menu  back + ok long  utterances +1, aborted +0, dropped +0, announcements +0; last 1673 ms played, 24961 subsamples
ok   end   home screen expected, got: desktop, no focus
0 failures
exit 0
```

After it: `sr status` volume 40, frames 42 dropped 0, utterances 12 with 0 aborted, dropped or underrun; `free` 116,560 bytes, minimum 107,856, largest block 116,208; no application running. The device was left on its home screen, reader on at volume 40, Debug on at log level debug. It never got `loader close`, and `/ext/sr/voice` was not touched. The UART capture (`tools/uart_log.py`, pid 90851) kept running throughout.

Docs from E, in a50c72d: the device notes' firmware line (a5c2ed7d9, 864,652 bytes, 15,988 spare) and size history (a new top entry, with the CI image's 864,648), the Measurements entry, and the corrected size-difference sentence; `docs/roadmap.md`'s status sentence names a5c2ed7d9 instead of a0dea0841.

The final push (e7f0626..a50c72d: the two documentation commits and a50c72d) started run 36223572673: https://github.com/robin24/flipper-access/actions/runs/36223572673. Result: success, in 11 min 27 s (06:22:48 to 06:34:15 UTC), cache hit, the same two skip lines, the same headroom line (864648 bytes, spare 15992), no annotations, artifact sonar-ci-a5c2ed7d of 12,043,382 bytes.

## Commits

Firmware, `screen-reader` on robin24/Momentum-Firmware, both pushed (a0dea0841..a5c2ed7d9):
- 3bdcca70c The settings are not saved outside a normal boot, so a volume chord during an update no longer overwrites the restored file
- a5c2ed7d9 f18's link list as upstream has it: the fork builds only the Flipper Zero target

Project, `main` on robin24/flipper-access, all pushed (263dfd7..a50c72d):
- aefa6b0 Firmware that saves no settings during an update boot (pointer to 3bdcca70c)
- 73acc18 Firmware with f18's link list as upstream has it (pointer to a5c2ed7d9)
- 16b5931 The tools after the final review: upstream's Sub-GHz file becomes a built-in app, and only the fork's own packages leave the card
- e7f0626 The Build workflow reads the repository only, runs on branch pushes and a pinned Ubuntu, with the Node 24 majors of its actions
- f251d88 Documentation after the final review: the changed defaults, the merge routine, and the commands in their own blocks
- 450ff9c Two build logs no longer carry the device's hardware.uid and radio.ble.mac
- a50c72d Plan A's fix wave on the device: a5c2ed7d9 flashed clean, the settings file kept across the update, the card pruned by the new rule

Every commit named its paths explicitly and ends with the Co-Authored-By line; no amend, no force push, nothing pushed to `upstream`, `applications/external` untouched. Both trees are clean and level with their remotes.

## The runner's last lines, on a50c72d

```
chords: 208 checks, 0 failures
throttle: 119 checks, 0 failures
fbt exclusions: 0 failures
subghz sources: 50 on disk, 50 quoted, 0 unquoted, 0 missing
card prune: 11 of 11 checks passed
strip js symbols: 15 of 15 checks passed
subghz manifest: 12 of 12 checks passed
upstream check: 14 of 14 checks passed
exit 0
```

## Not as written, and judgment calls

- A1's log tag is the file's `TAG` ("MomentumSettings"), not the literal "Momentum": `lib/momentum/settings.c` defines `TAG` and had not used it, and every file of `lib/momentum/` logs through its own tag. The message text is the brief's. A one-word change if the literal is wanted, but it would need another flash to be seen on the device.
- B2's first failing run is the signature change (a `TypeError`), since the test calls the new four-argument `plan()`. To show the rule itself failing, the same checks were also run against the old rule through a scratch shim; three checks failed there, as quoted above.
- B2 also makes `main()` exit with the pyserial sentence when the guarded import failed; before, a Mac without pyserial got "'NoneType' object is not callable".
- B4's test checks the fetch with real throwaway remotes (a tag `mntm-013` on "upstream", a branch on "other"), which needs no network; the tag lives only on "upstream", because `--tags` would refuse the same tag name from a second remote.
- B7 has no test file; it was checked by hand with dummy images, as quoted.
- D1: one extra sentence in Following Momentum pointing to the new routine. D2: the `card_prune.py` entry in the device notes and the spec's section 4 paragraph were brought in line with B2, since both still said the rollback packages were kept by default.
- D2's reproducible-builds sentence: the brief says CI's image differs by 12 bytes. That held for a0dea0841 (864,576 against 864,564); for a5c2ed7d9 CI's image is 864,648 against this Mac's 864,652, 4 bytes fewer. The docs commit said "12 bytes larger"; the E commit corrects it to "a few bytes: 12 more for a0dea0841, 4 fewer for a5c2ed7d9", since commits are never amended here.
- C: pushing the documentation right after writing it would have cancelled run 36222517024 through the workflow's concurrency rule, so the documentation commits waited and went out with the measurements at the end, in one push.
- E: `docs/roadmap.md`'s status sentence named a0dea0841 as the device's firmware; it now names a5c2ed7d9. A one-phrase change beyond the brief, so the status does not go stale.
- E: the settings file came through the update byte for byte, but whether a key was pressed during the update is unknown, so the guard of A1 was not itself exercised by this flash; the Mac cannot press keys while the console is gone.
