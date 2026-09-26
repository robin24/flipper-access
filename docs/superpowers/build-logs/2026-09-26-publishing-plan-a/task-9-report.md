# Task 9 report: the test runner in bash, a portable headroom check, the continuous build

Status: BLOCKED, and still blocked after the controller's ruling. The current state is in "Fix
round 1" at the end. First report: steps 1 to 3 are done and pushed. The first CI run failed in the build step
because of a real bug in the firmware: a clean checkout cannot link. The fix is one line in the
firmware submodule. This task's binding rules forbid committing inside `Momentum-Firmware` and
moving the submodule pointer, so I stopped there. No fix round was used. The fix is verified by
a local clean build in a scratch copy; details below.

## The script changes

`tools/run_host_tests.sh`: only the shebang and the ROOT line changed, as the brief says.
`#!/bin/zsh` became `#!/bin/bash`, and `ROOT="${0:A:h:h}"` became
`ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"`. The comment lines, every block and their order
are unchanged. No other zsh-only syntax was left in the file.

`tools/flash_headroom.sh`: replaced word for word with the brief's version. It takes an
optional image path, measures the size with `wc -c` instead of BSD `stat -f %z`, prints a
message and exits 1 when the image is missing, and still exits non-zero above the limit. Mode
100755 is kept for both scripts.

## Local runs

`bash tools/run_host_tests.sh` and `tools/run_host_tests.sh` both passed, exit 0, all 13 lines
green. The last lines were:

```
card prune: 8 of 8 checks passed
strip js symbols: 14 of 14 checks passed
subghz manifest: 8 of 8 checks passed
upstream check: 9 of 9 checks passed
```

It also passed when run by a relative path from another folder, so the new ROOT line resolves
correctly.

Linux preflight, before pushing: I used the `python:3` image already on this Mac (Debian 12,
gcc 12 standing in for clang, git 2.39), with no network. The runner passed both ways. It also
passed on a fresh clone with a depth-1 submodule and no `upstream` remote, which is how CI checks
it out. There, strip js symbols gave 13 of 13 and subghz manifest 7 of 7, and both printed their
skip lines as expected.

`tools/flash_headroom.sh` printed `firmware.bin 864564 bytes, limit 880640, spare 16076 bytes`
and exited 0, which is the expected line. I also tried the edge cases. A missing file gives
`no firmware image at ...` and exit 1. A synthetic 880,641-byte file shows spare -1 and exits 1.
Exactly 880,640 bytes shows spare 0 and exits 0.

## The workflow, and one deviation from the brief

`.github/workflows/build.yml` is the brief's file, with one change. The cache key hashes
`Momentum-Firmware/scripts/toolchain/fbtenv.sh` instead of `Momentum-Firmware/scripts/fbtenv.sh`.
The brief's path does not exist: `./fbt` sources `scripts/toolchain/fbtenv.sh`, and that file
sets `FBT_TOOLCHAIN_VERSION="39"`. With the brief's path, `hashFiles` returns an empty string
and the key is a constant `toolchain-`. That constant key breaks when the toolchain version
changes. The old cache would still be restored, fbt would download the new toolchain on every
run, and the cache would never be saved again. In the run, the key came out as
`toolchain-ca56839b...`, so the real file was hashed.

## The CI run (round 1, failed)

- Run: https://github.com/robin24/flipper-access/actions/runs/36216118222 (Build, push to main,
  commit 016a0b9, runner image ubuntu-24.04 20260920.314.1).
- Duration: 2 min 36 s from creation to completion. The job itself ran 2 min 29 s.
- Steps: the project checkout took 1 s. The firmware submodule took 4 s (depth 1, f3becdf0b
  from the public fork). Naming the build took 1 s (`DIST_SUFFIX=sonar-ci-f3becdf0`). The cache
  step took 0 s: `Cache not found for input keys: toolchain-ca56839b...`, as expected on a first
  run. The host tests took 6 s and all passed.
- Host tests on the runner: all green with the runner's clang. They were the same as the CI
  shape above: strip js symbols 13 of 13 and subghz manifest 7 of 7, with the upstream
  comparisons skipped. There was one harmless stderr line, `fatal: Not a valid object name
  upstream/dev`, from subghz manifest's upstream probe.
- The build step ran 2 min 15 s until it failed. The toolchain download took about 1.8 s and
  unpacking about 7.7 s, so about 9.5 s in all, not the few minutes expected. fbt's nested
  submodule sync took about 28 s. Compiling to the firmware link took about 1 min 34 s.
- Flash headroom and upload: skipped. There is no artifact. The post-job cache save was skipped
  too because the job failed, so there is no toolchain cache yet.

The failing step's log (`gh run view 36216118222 --log-failed`), last lines:

```
.../arm-none-eabi/bin/ld: cannot find -lmjs: No such file or directory
collect2: error: ld returned 1 exit status
scons: *** [build/f7-firmware-C/firmware.elf] Error 1
********** FBT ERRORS **********
build/f7-firmware-C/firmware.elf: Error 1
##[error]Process completed with exit code 2.
```

### The cause

Firmware commit 8fe7f533d ("JavaScript engine out of the firmware: mjs unlinked, ...") removed
`"mjs"` from `lib/SConscript`, so the library is no longer built. It left `"mjs"` in the
firmware's link list: `targets/f7/target.json` line 42, and also `targets/f18/target.json`
line 28. So the link still asks for `-lmjs`.

Local builds never showed this. Robin's build folder still holds a stale `libmjs.a` from
2026-09-22, before the stripdown, in `Momentum-Firmware/build/f7-firmware-C/lib/`. The linker
finds it and pulls nothing from it, since nothing references mjs any more. Any clean checkout,
CI included, fails.

### Verified locally, without touching the submodule or Robin's build folder

I cloned the firmware tree copy-on-write into the session scratchpad, removed `build/`, `dist/`
and `.sconsign.dblite` from the copy, and ran `FBT_NO_SYNC=1 ./fbt COMPACT=1 DEBUG=0
updater_package` there.

- The unmodified f3becdf0b failed after 54 s with the same `cannot find -lmjs`. The diagnosis is
  confirmed.
- I then deleted the `"mjs",` line from `targets/f7/target.json` in the copy and ran the build
  again. It finished in 121 s with exit 0. `firmware.bin` was 864,564 bytes, and
  `tools/flash_headroom.sh <that image>` gave spare 16,076 bytes, exit 0. The package was
  `dist/f7-C/flipper-z-f7-update-sonar-local-clean.tgz`, 12,039,551 bytes. So `DIST_SUFFIX` from
  the environment names the package, and the workflow's upload glob matches it.
- The package holds firmware.dfu, firstboot.bin, radio.bin, resources.tar.gz, splash.bin,
  update.fuf and updater.bin. The 666 KB package from 2026-09-25 in Robin's dist folder held only
  firmware, updater and update.fuf, so it was a minimal package. The CI artifact will be about
  12 MB.
- Afterwards, the submodule's `git status` was clean and Robin's `build/f7-firmware-C/firmware.bin`
  was still the 2026-09-25 image. The scratch copy has been deleted.

### What unblocks it

These steps are outside my permissions for this task:

1. In `Momentum-Firmware` on `screen-reader`, delete the `"mjs",` line from
   `targets/f7/target.json`, and the same line from `targets/f18/target.json` for consistency.
   No f18 build exists anywhere, but an f18 build would fail the same way. A possible commit
   message: "mjs off the firmware's link list too: 8fe7f533d stopped building it, and a clean
   build cannot find libmjs".
2. Push `screen-reader` to robin24/Momentum-Firmware.
3. In the project, commit the new submodule pointer with its path named, and push to main. The
   push runs the workflow again. It should be green: the only other risks were the headroom
   check and the upload path, and the local clean build covered both.

Going by this run and the local build, a whole green run should take about 5 minutes rather
than twenty. The cache hit on a later run is still to be observed.

## Files changed and commits

- `tools/run_host_tests.sh` (bash shebang and ROOT line)
- `tools/flash_headroom.sh` (the brief's portable version)
- `.github/workflows/build.yml` (new)
- Commit 016a0b9, "A continuous build: host tests, the firmware package on Linux, the headroom
  check", with my Co-Authored-By line. It was pushed to origin main (81071b9..016a0b9).
- Nothing was committed inside `Momentum-Firmware`, and the submodule pointer is unchanged.
  SwiftLint does not apply (no Swift). shellcheck and actionlint are not installed. The workflow
  parses as YAML, and its step names match the run's steps.

## Concerns

1. The blocker above. `main` shows a red Build run until the firmware fix lands.
2. The cache key deviation from the brief, explained above. It is deliberate.
3. The toolchain download takes only about 10 s. Restoring a cache of the unpacked toolchain may
   cost about as much as it saves (the macOS toolchain folder is 1.1 GB). This is worth comparing
   on the first two green runs, but it is not worth changing yet.
4. `on: push` with no branch filter plus `on: pull_request`: a PR from a branch of this
   repository runs twice, once per event, because the concurrency groups differ (refs/heads/...
   and refs/pull/.../merge). The runs are short, but minutes on a private repository are metered.
   Limiting `push` to `main` would halve that. I left it as the brief has it.
5. `WORKFLOW_BRANCH_OR_TAG: ${{ github.ref_name }}` makes a CI image name its branch `main`, the
   project's branch, where a local build says `screen-reader`. This is cosmetic, and only in the
   version info.
6. The runner's comment still says "Uses clang from Xcode", kept as the brief asks. On Linux, the
   runner uses the system clang.
7. Robin's local build folder keeps the stale `libmjs.a`, and possibly other leftovers from
   before the stripdown. A local build proves less than a clean one, and this workflow is now
   what shows it.

## Fix round 1, after the controller's ruling

The controller ruled that the link-list defect belongs to this plan and allowed a commit in the
firmware submodule. It asked for four things: the firmware fix, the pointer bump,
`WORKFLOW_BRANCH_OR_TAG: screen-reader`, and a push and watch.

### Done

- Firmware commit c0ba0af07 on `screen-reader`: "The JavaScript engine leaves the link list too:
  a clean build no longer looks for libmjs", with the controller's body and my Co-Authored-By
  line. It has two deletions and nothing else: the `"mjs",` line at `targets/f7/target.json:42`
  and at `targets/f18/target.json:28`. The pathspec was `-- targets/f7/target.json
  targets/f18/target.json`. Both files are still valid JSON, and neither mentions mjs any more.
  Their `linker_dependencies` lists now have 35 entries (f7) and 27 (f18).
- The f7 change is byte-identical to the one in the scratch copy that built cleanly. The blob
  went from 23752fbdc to fa3b26469 both times.
- Pushed with `git push origin screen-reader` from inside the submodule, never `upstream`:
  f3becdf0b..c0ba0af07 on robin24/Momentum-Firmware.
- After the firmware commit, `bash tools/run_host_tests.sh` and `tools/run_host_tests.sh` both
  passed, exit 0, all lines green.
- Project commit f64ce09, "The CI build names its firmware branch screen-reader, the
  submodule's branch, instead of the project's branch". It is its own plain commit with the
  pathspec `-- .github/workflows/build.yml`, and the one-line change is
  `WORKFLOW_BRANCH_OR_TAG: screen-reader`. The YAML still parses. The corrected cache-key path
  is unchanged. It is committed but not pushed; see below.

### Refused: the pointer bump

I ran `git add Momentum-Firmware` and then a commit with `-- Momentum-Firmware` and the message
"Firmware without the JavaScript engine in its link list". The Claude Code permission system
refused it: the auto-mode classifier said "Blocked by classifier". Git never ran. The refusal
covers the outcome, not only that command, so I did not try it any other way.

The state now:

- The project still records f3becdf0b.
- The submodule's working tree is at c0ba0af07, so `git status` shows ` M Momentum-Firmware`.
  Nothing is staged.
- `main` is one commit ahead of origin (f64ce09).

I did not push f64ce09. A push without the pointer bump would build f3becdf0b again and fail
at the same `-lmjs` link step. That would spend a fix round and Actions minutes for nothing. So
there has been no CI run in this round, and 0 of the 3 fix rounds are used.

### Evidence that the fix works: the local clean build (from the first report)

I built in a copy-on-write copy of the firmware tree in the session scratchpad, with no `build/`,
no `dist/` and no `.sconsign.dblite`, using `FBT_NO_SYNC=1 ./fbt COMPACT=1 DEBUG=0
updater_package`.

- f3becdf0b as it was: it failed after 54 s with `ld: cannot find -lmjs`, the same as CI.
- With the f7 `"mjs",` line deleted: exit 0 after 121 s.
  - firmware.bin was 864,564 bytes. `tools/flash_headroom.sh` gave spare 16,076 bytes, exit 0.
  - The package was `dist/f7-C/flipper-z-f7-update-sonar-local-clean.tgz`, 12,039,551 bytes.
    It holds firmware.dfu, firstboot.bin, radio.bin, resources.tar.gz, splash.bin, update.fuf
    and updater.bin.
  - `DIST_SUFFIX` from the environment named the package, so the upload glob matches.
- Robin's build folder was not touched. The copy has been deleted.

### What finishes the task

Someone with permission runs this from the project root:

```
git add Momentum-Firmware
git commit -m "Firmware without the JavaScript engine in its link list" -- Momentum-Firmware
git push
gh run watch --exit-status $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')
```

The commit message should end with the committer's own Co-Authored-By line. The push also sends
f64ce09. Alternatively, a permission rule lets me run the same steps.

That run is fix round 1 of 3. Going by the first run and the local build, it should be green in
about 5 minutes. The artifact should be `sonar-ci-c0ba0af0`, holding
`flipper-z-f7-update-sonar-ci-c0ba0af0.tgz` of about 12 MB.

### Commits so far

- Project: 016a0b9 (pushed), f64ce09 (local, not pushed).
- Firmware: c0ba0af07 (pushed to robin24/Momentum-Firmware `screen-reader`).
