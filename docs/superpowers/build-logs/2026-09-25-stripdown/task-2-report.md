# Task 2 report: The JavaScript engine out of the firmware

Repo: `/Users/robin/Downloads/flipper-access/Momentum-Firmware`, branch `screen-reader`, started at `b7c94fe36`.
Commit produced: `8fe7f533d`.

## What changed

1. `lib/SConscript` — deleted the line `        "mjs",` from the `BuildModules` list (was line 41), so the JS engine library is no longer linked into the firmware.
2. `fbt_options.py` — deleted the line `        "js_app",` from `FIRMWARE_APPS["unit_tests_min"]` (was line 124, between `"unit_tests"` and `"infrared"`). `EXCLUDE_EXT_APPS`/`EXCLUDE_EXT_CATEGORIES` from Task 1 (lines 53-54) were left untouched.
3. `targets/f7/api_symbols.csv` — ran the brief's Python script to strip all JS-related API entries (82 `Function`/`Variable` rows whose name starts `js_` or `mjs_`, plus 8 `Header,+,lib/mjs/...` rows = 90 lines). `Version,+,87.2,,` untouched.
4. `applications/system/application.fam` (controller's addition, not in the original brief) — deleted the line `        "js_app",` from the `system_apps` metapackage's `provides=[...]` list, so the JS runner's example scripts (`resources/apps/Scripts`) are no longer deployed to the SD card image. Comments and the rest of the file left as-is.

`lib/mjs` and `applications/system/js_app` were left in the tree (verified present after the commit, 49 and 16 entries respectively) — only unlinked, not deleted, per the global constraint.

## Commands and relevant output

### Step 1 — line deletions (verified byte-exact before deleting, via `sed -n 'Np' | cat -et`, then `sed -i '' 'Nd'`)

```
diff --git a/applications/system/application.fam b/applications/system/application.fam
@@ -4,7 +4,6 @@ App(
     provides=[
         "updater_app",
-        "js_app",
         "findmy_startup",
         # "archive",

diff --git a/fbt_options.py b/fbt_options.py
@@ -121,7 +121,6 @@ FIRMWARE_APPS = {
         "unit_tests",
-        "js_app",
         "infrared",

diff --git a/lib/SConscript b/lib/SConscript
@@ -38,7 +38,6 @@ libs = env.BuildModules(
         "uzlib",
-        "mjs",
         "nanopb",
```

### Step 2 — CSV removal (brief's script, verbatim)

```
removed 90
```
```
git diff --stat targets/f7/api_symbols.csv
 targets/f7/api_symbols.csv | 90 ----------------------------------------------
 1 file changed, 90 deletions(-)
```
Confirmed: `Version,+,87.2,,` still present (line 2); `grep -c I_js_script_10px targets/f7/api_symbols.csv` → `1`; a follow-up grep for any remaining `^(Function|Variable),[+-],m?js_` or `^Header,+,lib/mjs/` lines → `0` matches. Spot-checked all 90 removed lines against the pattern: 0 non-matching.

### Step 3 — build and API report

`./fbt 2>&1 | grep -E "API version|warning|error"`:
```
fbt: warning: Failed parsing manifest '.../applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui' ...
fbt: warning: Failed parsing manifest '.../applications/external/mtp/application.fam' : Invalid appid '.f0_mtp' ...
API version 87.2 is up to date
	CC	applications/system/updater/scenes/updater_scene_error.c
```
The fourth line is just a compiled filename containing "error", not a warning/error. Exactly the two known manifest warnings plus the API line, as expected. The "Excluded 44 external apps by configuration: ..." line (checked separately, since it doesn't match the grep filter) was present and includes `js_app` and `cli_js`.

`git status --short | grep -v "^ m applications/external"`:
```
 M applications/system/application.fam
 M fbt_options.py
 M lib/SConscript
 M targets/f7/api_symbols.csv
```
Exactly the four intended files. CSV diff re-checked after the build — still exactly 90 deletions, 0 insertions (the build did not rewrite it).

### Step 4 — measure

`tools/flash_headroom.sh` (from project root):
```
firmware.bin 835748 bytes, limit 880640, spare 44892 bytes
```
Brief's expectation was "about 835,780 bytes, 44,860 spare". Actual is 32 bytes smaller (44,892 spare, 32 more than predicted). See Concerns below — I attribute this to the controller's `application.fam` addition, which the brief's own estimate predates.

`./fbt lint`: exit code `0` (captured explicitly via `./fbt lint; echo $?`, not through a pipe, after an earlier attempt was accidentally measuring `tail`'s exit code instead — corrected before relying on it).

### Resources check (controller's addition, verification)

```
rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps
./fbt resources 2>&1 | grep -E "API version|warning|error|Excluded"
```
Output included the same two manifest warnings, the `Excluded 44 external apps...` line, `API version 87.2 is up to date`, and then many pre-existing compiler warnings from unrelated `applications/external/*` apps (passy, seader, picopass, airmouse, flipboard_*, etc.) plus more "CC ...error....c / ...warning....c" filename matches — expected and unrelated to this change, since `./fbt resources` rebuilds every app from scratch (not just the ones a bare `./fbt` would touch), including ones with pre-existing unrelated warnings. No `Error:`/`ERROR:`/`fatal error`/`scons: ***` build-failure markers anywhere in the log; the build finished ("Manifest updated (2170 new, 0 removed, 0 changed)", "Complete").

```
ls build/f7-firmware-C/resources/apps
Bluetooth  GPIO  Infrared  Media  NFC  RFID  Sub-GHz  Tools  USB  assets  iButton
```
No `Scripts` folder.

```
grep -c 'apps/Scripts/' build/f7-firmware-C/resources/Manifest
0
```
Both checks pass. (Before the wipe, `build/f7-firmware-C/resources/apps/Scripts` still existed from a prior, stale build — confirming the brief's note that a bare `./fbt` does not rebuild resources.)

`git status --short` after the resources rebuild: unchanged, still exactly the four tracked files plus the pre-existing `m applications/external`. `flash_headroom.sh` re-checked afterward: same `835748 bytes ... spare 44892 bytes`.

### Step 5 — commit

```
git add lib/SConscript targets/f7/api_symbols.csv fbt_options.py applications/system/application.fam
git commit -m "JavaScript engine out of the firmware: mjs unlinked, its 82 symbols and 8 headers off the CSV, API 87.2 kept; js_app out of system_apps

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" -- lib/SConscript targets/f7/api_symbols.csv fbt_options.py applications/system/application.fam
```
Result: `[screen-reader 8fe7f533d] ... 4 files changed, 93 deletions(-)`. Not pushed.

## Files changed

- `Momentum-Firmware/lib/SConscript` (1 deletion)
- `Momentum-Firmware/fbt_options.py` (1 deletion)
- `Momentum-Firmware/targets/f7/api_symbols.csv` (90 deletions)
- `Momentum-Firmware/applications/system/application.fam` (1 deletion)

## Self-review

- Completeness: brief Steps 1-5 done exactly as written; the controller's addition (removing `"js_app",` from `system_apps` in `application.fam`, including it in the commit and the extended subject, plus the resources/Manifest verification) done exactly as specified.
- CSV diff is exactly the 90 deletions the brief predicted, 0 insertions; `Version,+,87.2,,` and `I_js_script_10px` both intact; every removed line matched the expected `Function`/`Variable`/`Header` JS/mjs pattern (spot-checked programmatically, 0 stragglers).
- Final `git status --short` is exactly the four modified files (plus the pre-existing, untouched `applications/external` submodule note) before commit, and clean (only the submodule note) after commit.
- `git show 8fe7f533d --name-only` touches no path under `applications/external`.
- `lib/mjs` and `applications/system/js_app` both still present in the working tree post-commit (unlinked, not deleted).
- Read the full diff of all three small files and the CSV removal list before committing; nothing unexpected in any of them.

## Concerns

- Headroom is 32 bytes better than the brief's "about 835,780 bytes, 44,860 spare": measured 835,748 bytes / 44,892 spare, reproduced identically on a second run after the resources rebuild. The brief's figure was written before the controller's `application.fam` addition, and dropping `js_app` from `system_apps`'s `provides` most likely shrinks a small embedded app/metapackage table by 32 bytes — a plausible, benign explanation, but I have not isolated it by rebuilding with only the brief's three original files to confirm the brief's exact number reproduces without the addition (that would need a second ~3-minute rebuild on a reverted `application.fam`). Flagging so the controller can decide whether that confirmation is worth the extra build.
- `./fbt resources` (needed only for the addition's verification) surfaces many pre-existing, unrelated compiler warnings from `applications/external/*` apps not touched by this task (passy, seader, picopass, airmouse, flipboard_*, mp_flipper). None are new or related to the JS removal; noted here only so they aren't mistaken for fallout from this change.

## Fix round 1

Review finding: `applications/debug/unit_tests/application.fam:225-231` defines the `PLUGIN` `test_js` with `requires=["unit_tests", "js_app"]`. `_group_plugins` in `scripts/fbt/appmanifest.py` keeps a plugin when *any* required parent is built (OR across `requires`), so in the `unit_tests`/`unit_tests_min` app sets — where `unit_tests` is always built — `test_js` would still be built even though `js_app` is excluded, and its `tests/js/js_test.c` calls `mjs_*` directly, which would fail to link now that `mjs` is unlinked. Confirmed the cited `application.fam` lines match exactly (`requires=["unit_tests", "js_app"]`).

Controller's ruling: add `"test_js"` to `EXCLUDE_EXT_APPS` in `fbt_options.py` (the exclusion filter runs before plugin grouping, so no app set builds it) and extend the comment to note `test_js` is the JS engine's unit-test plugin. Verify with the default build only — do not build the unit-test app sets, since that would relink the firmware into the same build directory under a different configuration.

### What changed

`Momentum-Firmware/fbt_options.py`:

```diff
 # Left out of the build and of the card by the accessibility fork: app ids, and fap_category
-# values. The plugins of an app left out go with it.
-EXCLUDE_EXT_APPS = ["js_app", "cli_js"]
+# values. The plugins of an app left out go with it. test_js is the JavaScript engine's
+# unit-test plugin; it also requires unit_tests, so it is kept unless named here explicitly.
+EXCLUDE_EXT_APPS = ["js_app", "cli_js", "test_js"]
 EXCLUDE_EXT_CATEGORIES = ["Games"]
```

Nothing else touched; `git status --short` before commit was `M fbt_options.py` plus the pre-existing, untouched ` m applications/external`.

### Verification (default build only, `./fbt`)

`./fbt 2>&1 | grep -E "API version|warning|error|Excluded"`:
```
fbt: warning: Failed parsing manifest '.../applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui' ...
fbt: warning: Failed parsing manifest '.../applications/external/mtp/application.fam' : Invalid appid '.f0_mtp' ...
Excluded 45 external apps by configuration: 4inrow, air_arkanoid, ..., tanks, test_js, tetris, ..., zombiez
API version 87.2 is up to date
```
45 apps excluded (was 44), `test_js` present in the list, only the two known manifest warnings, API line confirms 87.2 up to date. Checked the full log too: no other warning/error lines, build completed and produced `firmware.bin`/`firmware.dfu`/`dist/f7-C` normally.

`./fbt lint`: exit code `0` (checked directly, not through a pipe).

`tools/flash_headroom.sh` (from project root): `firmware.bin 835748 bytes, limit 880640, spare 44892 bytes` — unchanged from before this fix, as expected (test_js was never linked into the firmware image itself, only into the separate unit-test build).

### Commit

```
git add fbt_options.py
git commit -m "fbt: test_js excluded too, the JavaScript engine's unit-test plugin

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" -- fbt_options.py
```
Result: `[screen-reader 954c5aec9] fbt: test_js excluded too, the JavaScript engine's unit-test plugin` — 1 file changed, 3 insertions(+), 2 deletions(-). `git status --short` afterward: clean except the pre-existing ` m applications/external`. Not pushed.

### Concerns carried forward

Same as before: the 32-byte headroom improvement over the original brief's estimate (835,748 vs. "about 835,780") remains unconfirmed in its exact cause, though unaffected by this fix (headroom is identical before and after). No new concerns from this fix round.
