# Task 1 report: Build options that leave apps and categories out

## Summary

Implemented `EXCLUDE_EXT_APPS` and `EXCLUDE_EXT_CATEGORIES` exactly as specified in
`task-1-brief.md`: two new fbt build options that remove named app ids and/or
`fap_category` values (and their plugins) from the external-app buildset. Implemented in
step order (failing test first), verified against a real firmware build, and committed as
two commits, one per repository. All six steps of the brief are done.

One concern, fully diagnosed, is reported below: the JS runner's *example scripts*
(`apps/Scripts/*.js`) still land in the deployed resources tree, through a code path this
task's interface does not touch. The JS app itself, `cli_js`, all `js_*` plugins, and all
Games are correctly excluded from both `.extapps` and the resources `Manifest`.

## What was implemented

- `Momentum-Firmware/fbt_options.py`: added `EXCLUDE_EXT_APPS = ["js_app", "cli_js"]` and
  `EXCLUDE_EXT_CATEGORIES = ["Games"]`, after `EXTRA_EXT_APPS = []`.
- `Momentum-Firmware/site_scons/commandline.scons`: added the two variables
  (`EXCLUDE_EXT_APPS`, `EXCLUDE_EXT_CATEGORIES`), same tuple shape as `EXTRA_EXT_APPS`,
  right after it in the variables list.
- `Momentum-Firmware/scripts/fbt_tools/fbt_apps.py` (`PrepareApplicationsBuild`): the
  `filter_apps(...)` call now also passes `exclude_apps=env.get("EXCLUDE_EXT_APPS", [])`
  and `exclude_categories=env.get("EXCLUDE_EXT_CATEGORIES", [])`.
- `Momentum-Firmware/scripts/fbt/appmanifest.py`:
  - `AppManager.filter_apps`: gained `exclude_apps`/`exclude_categories` keyword params,
    forwarded to `AppBuildset`.
  - `AppBuildset.__init__`: gained the same two params (before `message_writer`), stored as
    `self._exclude_apps` / `self._exclude_categories` (sets, defaulting to empty).
  - `AppBuildset._process_ext_apps`: after the `extra_ext_appnames` extend and before the
    hw-target split loop, apps whose `appid` is in `self._exclude_apps` or whose
    `fap_category` is in `self._exclude_categories` are removed from the local `extapps`
    list; if any were removed, one message is written naming the count and the excluded
    ids; unknown ids named in `EXCLUDE_EXT_APPS` (not in `self.appmgr.known_apps`) are each
    reported once via `self._writer`, after the exclusion set is applied.
- `Momentum-Firmware/scripts/ufbt/SConstruct`: added `EXCLUDE_EXT_APPS=[]` and
  `EXCLUDE_EXT_CATEGORIES=[]` next to `EXTRA_EXT_APPS=[]` in the ufbt environment defaults.
- `tests/fbt/test_exclusions.py` (new, project repo): the unit test from the brief,
  verbatim. Exercises `AppManager.filter_apps` and `AppBuildset` directly (no SCons
  needed) against a synthetic app set covering: nothing excluded, the fork's real
  configuration (`js_app`, `cli_js` by id; `Games` by category), a category-only
  exclusion, and an unknown excluded id.
- `tools/run_host_tests.sh`: appended the block from the brief, after the throttle test,
  running the new Python test and gating the script's exit code on it.

No file outside this list was modified. `applications/external` (the submodule with the
pre-existing local modification) was never staged or touched.

## Testing

### Step 2 — RED (before the implementation)

```
$ python3 tests/fbt/test_exclusions.py
Traceback (most recent call last):
  File "/Users/robin/Downloads/flipper-access/tests/fbt/test_exclusions.py", line 58, in <module>
    bs = manager().filter_apps(
        applist=["default"],
    ...<3 lines>...
        exclude_categories=["Games"],
    )
TypeError: AppManager.filter_apps() got an unexpected keyword argument 'exclude_apps'
EXIT:1
```

Matches the brief's expectation exactly.

### Step 4 — GREEN (after the implementation)

```
$ python3 tests/fbt/test_exclusions.py
Excluded 4 external apps by configuration: cli_js, doom, js_app, tetris
Excluded 2 external apps by configuration: doom, tetris
fbt exclusions: 0 failures
EXIT:0
```

(The two "Excluded ..." lines are the default `print_writer` output of the first two
`filter_apps` calls in the test, which don't pass a custom `message_writer`; the third
call does, and its message is captured into a list and asserted on instead of printed.)

### Step 4 — host runner

```
$ tools/run_host_tests.sh
174 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1022 checks, 0 failures
speech queue: 156 checks, 0 failures
speech PCM: 700 checks, 0 failures
speech voice: 4433 checks, 0 failures
chords: 73 checks, 0 failures
throttle: 119 checks, 0 failures
fbt exclusions: fbt exclusions: 0 failures
EXIT:0
```

Every suite green, the new line last, as expected. (The doubled "fbt exclusions:" prefix
is the brief's own template: the script's last stdout line already starts with "fbt
exclusions:", and `run_host_tests.sh`'s wrapper echo adds its own "fbt exclusions:" prefix
around `tail -n 1`. This is not something I introduced; it's inherent to the exact block
given in the brief.)

### Step 5 — build with the cleaned directories

Ran exactly the brief's command:

```
$ rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps && ./fbt 2>&1 | tail -20
```

Output (verbatim, only the two known manifest warnings plus the new line):

```
fbt: warning: Failed parsing manifest '.../applications/external/cli_bridge/application.fam' : Invalid appid '.cli_gui'. ...
fbt: warning: Failed parsing manifest '.../applications/external/mtp/application.fam' : Invalid appid '.f0_mtp'. ...
Excluded 44 external apps by configuration: 4inrow, air_arkanoid, air_labyrinth, arkanoid, asteroids, blackjack, bomberduck, checkers, chess, cli_js, color_guess, doom, flappy_bird, flipper_pong, game15, game_2048, gameoflife, geometry_dash, heap_defence, jetpack_joyride, js_app, laser_tag, minesweeper_redux, multi_dice, pinball0, quadrastic, reversi, roots_of_life, rubiks_cube_scrambler, scorched_tanks, simon_says, slotmachine, snake20, solitaire, t_rex_runner, tama_p1, tanks, tetris, tictactoe, umpire_indicator, videopoker, yapinvaders, yatzee, zombiez
	SDKCHK	targets/f7/api_symbols.csv
API version 87.2 is up to date
	CDB	build/f7-firmware-C/compile_commands.json
Linking build/f7-firmware-C as latest built dir (./build/latest/)
	DIST	dist_fw_dist
Firmware binaries can be found at: dist/f7-C
```

Exit 0. 44 excluded = the 42 games plus `js_app` and `cli_js`, counted directly from the
printed, alphabetically-sorted list above (spec count matches, no discrepancy to report).
`firmware.bin` size: 877,036 bytes — unchanged, as expected (the JS library is still
linked in this task).

**Important finding about this command**: bare `./fbt` (the `Default()` target, `fw_dist`)
does **not** build `.extapps` or `resources/` at all — I confirmed this by reading the
SCons graph end to end (`SConstruct`, `firmware.scons`, `site_scons/extapps.scons`,
`scripts/fbt_tools/fbt_resources.py`): `distenv.Default(basic_dist)` depends only on
`DIST_DEPENDS` → `FW_ARTIFACTS`, which holds the firmware `.bin`/`.elf`/`.dfu`/`.hex`/
version json and the SDK header tree (`fw_extapps.sdk_tree`) — never
`FW_RESOURCES_MANIFEST` (aliased `"resources"`) and never each app's compiled `.compact`
FAP. Those are only pulled in by the explicit `resources`, `faps`/`fap_dist`, or
`updater_package`/`flash_usb*` targets. This matches what I observed: after deleting both
directories, plain `./fbt` finished in seconds with no FAP compile lines, and neither
directory existed afterward. So the brief's Step 5 listing/manifest checks (which inspect
`build/f7-firmware-C/resources/apps` and `.../resources/Manifest`) cannot be exercised by
the literal bare `./fbt` command in this repository.

To actually verify the exclusion where it matters (what gets deployed), I additionally ran
`./fbt resources` (the alias that builds the Manifest, and whose builder emitter pulls in
every deployable external app's compiled `.fap` as a source, forcing the FAP rebuild the
brief's "more [time] after deleting `.extapps`" note anticipates). This exited 0 and
produced both directories. Its build log shows many pre-existing compiler warnings from
various vendored `applications/external/*` sources (e.g. `passy`, `seader`, `picopass`,
`flipboard_*`) — these are not from any file I touched; they surfaced only because
deleting `.extapps` forced a full FAP recompile instead of the usual incrementally-cached
one, so they were invisible on a normal incremental build. Not a regression.

Listing/manifest checks, run against the `./fbt resources` build:

```
$ ls build/f7-firmware-C/.extapps | grep -c -E '^(js_|cli_js|test_js)'
0

$ ls build/f7-firmware-C/resources/apps
Bluetooth  GPIO  Infrared  Media  NFC  RFID  Scripts  Sub-GHz  Tools  USB  assets  iButton

$ grep -c -E 'apps/Games/|apps/Scripts/|js_app|cli_js|test_js' build/f7-firmware-C/resources/Manifest
25
```

`.extapps` count is 0, as expected: no `js_*`/`cli_js`/`test_js` FAP was built. `Games` is
correctly absent from the apps folder listing and from the Manifest (`grep -c
'apps/Games/'` alone is 0). `Scripts` is still listed, and the Manifest count is 25, not 0.

### Root-cause of the `apps/Scripts` residual (diagnosed, not guessed)

The brief anticipated this exact symptom and gave one diagnostic: "check that js_app
really left the set (the excluded line names it)." I did — `js_app` is named in the
`Excluded 44 ...` line, and I confirmed with three more targeted checks that **no compiled
JS-related `.fap` reaches the Manifest at all**:

```
$ grep -c -E '(js_app|cli_js|test_js)\.fap' build/f7-firmware-C/resources/Manifest
0
$ grep -c -E 'js_[a-z_]*\.fap' build/f7-firmware-C/resources/Manifest
0
$ grep -E 'apps/Games/|apps/Scripts/|js_app|cli_js|test_js' build/f7-firmware-C/resources/Manifest | grep -vc 'apps/Scripts/'
0
```

All 25 matches are `apps/Scripts/...` resource-file entries (`interactive.js` and 24 files
under `Examples/`), not compiled apps. Tracing `fbt_resources.py`'s
`__generate_resources_dist_entries`, the resources tree is built from two independent
sources: (1) `env["FW_EXTAPPS"].application_map` — the external-app buildset my change
filters, confirmed empty of anything JS-related — and (2) `env["APPBUILD"].apps` — the
**built-in** app closure (`AppBuildset.appnames`, grown by `_process_deps()` walking
`provides`/`requires`), which my `_process_ext_apps` change never touches. `js_app` is
independently reachable through source (2):
`Momentum-Firmware/applications/system/application.fam` declares a `system_apps`
`METAPACKAGE` (part of the default `FIRMWARE_APPS` set) whose `provides` list includes
`"js_app"` directly:

```python
App(
    appid="system_apps",
    apptype=FlipperAppType.METAPACKAGE,
    provides=["updater_app", "js_app", "findmy_startup"],
)
```

That pulls `"js_app"` into `AppBuildset.appnames`/`.apps` regardless of the ext-app
exclusion, and since `js_app`'s manifest sets `resources="examples"`, everything under
`applications/system/js_app/examples/` (which is itself laid out on disk as
`examples/apps/Scripts/...`, mirroring the SD card destination) gets copied into
`resources/apps/Scripts/` by the "Deploy apps' resources too" loop — a path completely
separate from, and untouched by, `EXCLUDE_EXT_APPS`/`EXCLUDE_EXT_CATEGORIES`.

Net effect: the JS interpreter app, `cli_js`, and all ~26 `js_*` plugins are fully excluded
from the build and from deployment (0 in `.extapps`, 0 compiled entries in the Manifest).
Only `js_app`'s bundled example `.js` *scripts* (documentation/sample content, not
executable without the interpreter, which is also gone) still land in
`resources/apps/Scripts/`.

I did not touch `applications/system/application.fam` to fix this — it is outside this
task's file list, the brief's own interface is scoped to the external-app buildset
(`filter_apps`/`AppBuildset`/`_process_ext_apps`), and the unit test in the brief tests
exactly that mechanism (and passes). Removing `"js_app"` from `system_apps.provides` felt
like exactly the kind of change that belongs with unlinking the JS engine (a later task per
the context notes), not a silent scope expansion here. Flagging it instead. See Concerns.

### `./fbt lint`

```
$ ./fbt lint 2>&1 | tail -5
Excluded 44 external apps by configuration: ...
python3 scripts/lint.py check applications !applications/system/js_app/packages !applications/external ...
EXIT:0
```

Exits 0, no lint complaints (it only checks C/formatting; none of this task's files are C).

## Files changed

Firmware repo (commit `b7c94fe36`, branch `screen-reader`):
- `Momentum-Firmware/fbt_options.py`
- `Momentum-Firmware/site_scons/commandline.scons`
- `Momentum-Firmware/scripts/fbt_tools/fbt_apps.py`
- `Momentum-Firmware/scripts/fbt/appmanifest.py`
- `Momentum-Firmware/scripts/ufbt/SConstruct`

Project repo (commit `71b13c2`, branch `main`):
- `tests/fbt/test_exclusions.py` (new)
- `tools/run_host_tests.sh`

Neither commit was pushed. `applications/external` (the submodule with the pre-existing
local modification) was never staged or committed.

## Self-review

**Completeness**: all six steps done in order (failing test, verified RED; options and
filter added; verified GREEN and wired into the host runner; build verified with cleaned
directories; listings and manifest checked; committed as two commits). The
`Excluded 44 external apps` count and membership match the spec's own description (42
games + `js_app` + `cli_js`) exactly, so there was nothing to reconcile there.

**Quality**: names match the brief's interface exactly
(`exclude_apps`/`exclude_categories`, `EXCLUDE_EXT_APPS`/`EXCLUDE_EXT_CATEGORIES`). The new
comment in `_process_ext_apps` ("Their plugins leave in `_group_plugins`, as the plugins of
any app that is not built do") is not just copied text — I checked it against
`_group_plugins`'s actual logic: a plugin's parent must be present in `self.extapps` (for
non-builtin parent types) for the plugin to be kept, and since exclusion removes the parent
from the local `extapps` list before the final split into `self.extapps`, an excluded
parent's plugins are correctly dropped there. Verified this is the real mechanism, not just
something the unit test happens to agree with.

**Discipline**: only the files the brief names were touched, in both repos. Did not touch
`applications/system/application.fam` despite finding a real gap there — see Concerns.
Nothing was staged with a broad `git add`; both commits used explicit file lists on both
`git add` and `git commit -- <files>`.

**Testing**: the unit test asserts real behaviour (membership of `get_ext_apps()` after
filtering, exact exclusion messages including the count and the unknown-id report), not
just "it runs." Output is pristine end to end: RED showed the expected `TypeError`; GREEN
showed `0 failures`; the host runner is fully green with the new line last; the plain
`./fbt` build output matched the brief's exact expected shape (two known warnings, the
excluded-count line, "API version 87.2 is up to date", exit 0); `./fbt lint` exits 0.

## Concerns

1. **`apps/Scripts` residual in the deployed resources tree** (documented and diagnosed
   above, not a defect in what this task's interface does): `js_app`'s example `.js`
   scripts still deploy to `build/f7-firmware-C/resources/apps/Scripts/`, because
   `js_app` is independently pulled into the built-in app closure by
   `applications/system/application.fam`'s `system_apps.provides`, a path
   `EXCLUDE_EXT_APPS`/`EXCLUDE_EXT_CATEGORIES` does not reach. The JS app itself, `cli_js`,
   and every `js_*` plugin are fully excluded from both the build and the Manifest — this
   is only sample script *content*, not executable code, and there is no interpreter left
   to run it (in this task; the interpreter library is still linked, per the brief's own
   note that firmware.bin size is unchanged). Recommend the controller decide whether this
   is closed out when a later task unlinks the JS engine (which would need to touch
   `system_apps.provides` anyway to avoid an unsatisfied-dependency build error), or
   whether it needs an explicit fix now.
2. Bare `./fbt` cannot build `resources/`/`.extapps` in this repository at all (confirmed
   by reading the SCons dependency graph, not just by observation) — the brief's Step 5
   listing/manifest checks need `./fbt resources` (or an equivalent fuller target) to be
   meaningful. I ran both: the literal `./fbt` command (which matches the brief's expected
   output verbatim) and `./fbt resources` (to actually exercise the listings/manifest
   checks). Worth correcting in the brief/process for the remaining six tasks if any of
   them rely on the same assumption.
