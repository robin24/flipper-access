# Firmware Stripdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sub-GHz works with the reader on, the firmware keeps a flash margin, and the build stops producing what serves no blind user: the games, the JavaScript runner, SAM; the home screen loads no animation by default.

**Architecture:** Removals happen through build configuration and manifests: two new fbt options leave apps and categories out of the external app set (games, the JS apps), the JavaScript library leaves the firmware and the CSV with the API version unchanged at 87.2, and Sub-GHz becomes a built-in app again through the manifest of commit 1c113c28a. SAM leaves the speech engine, which then plays clips and spelled letters only and completes an item silently when the voice is muted or the card has no vocabulary. A Momentum setting, off by default, keeps the desktop's animation manager from ever loading an animation, through early returns at its entry points. The updater removes the card files that leave the resource manifest.

**Tech Stack:** Momentum firmware (fbt/SCons, GCC 12, `-Wall -Wextra -Werror`, release configuration), Python 3 for the build scripts and the tools, C11 host tests with clang and sanitizers, the device over its USB console.

**Spec:** docs/superpowers/specs/2026-09-25-firmware-stripdown-design.md (all sections). Section 2 has the measured figures every task compares against.

## Global Constraints

- Firmware repo /Users/robin/Downloads/flipper-access/Momentum-Firmware, branch screen-reader (head 22ae265ef); project repo /Users/robin/Downloads/flipper-access, main (head after this plan's commit). Commit only your own files with explicit `git add` then `git commit -m "<subject>" -- <the same files>`; do not push; never commit inside applications/external (its text2sam change is a known local patch); never delete or move the repo-root `voice/`; never delete `lib/mjs`, `applications/system/js_app` or the Games sources.
- Image under 880,640 bytes: `tools/flash_headroom.sh` after every firmware build; report the figure. `./fbt` prints only "API version 87.2 is up to date" and the two pre-existing external manifest warnings (cli_bridge, mtp); `./fbt lint` exit 0; the host runner green.
- The build never deletes stale outputs: before any build whose result reaches the card, `rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps` in the firmware repo, then check the new `build/f7-firmware-C/resources/Manifest` as Task 1 describes.
- Device: /dev/cu.usbmodemflip_R0skie1, console via `.venv/bin/python tools/flipper_cli.py "<command>"` from the project root. No log capture is running (it lost the port at 00:35 on 2026-09-25); restart it only at the very end of the round with `nohup .venv/bin/python tools/flipper_log.py docs/measurements/logs/2026-09-25-session.txt > /dev/null 2>&1 &`. One agent on the device at a time. Never `loader close`; leave apps with Back presses. Never set a PIN. `sr screen` first after every flash (a post-update splash may show; Back closes it). Leave the device idle on the home screen, reader on, voice on, speech idle.
- Robin is asleep and asked for no interruptions: decide, record the decision in the task report, and go on.

---

### Task 1: Build options that leave apps and categories out

**Files:**
- Modify: `Momentum-Firmware/fbt_options.py` (after `EXTRA_EXT_APPS = []`, line 49)
- Modify: `Momentum-Firmware/site_scons/commandline.scons` (after the `EXTRA_EXT_APPS` tuple, about line 235)
- Modify: `Momentum-Firmware/scripts/fbt_tools/fbt_apps.py:139-146` (`PrepareApplicationsBuild`)
- Modify: `Momentum-Firmware/scripts/fbt/appmanifest.py` (`filter_apps` at 225, `AppBuildset.__init__` at 274, `_process_ext_apps` at 342)
- Modify: `Momentum-Firmware/scripts/ufbt/SConstruct:100` (defaults)
- Create: `tests/fbt/test_exclusions.py` (project repo)
- Modify: `tools/run_host_tests.sh` (run the new test at the end)

**Interfaces:**
- Produces: `AppManager.filter_apps(..., exclude_apps: list[str] | None = None, exclude_categories: list[str] | None = None)`; `AppBuildset(..., exclude_apps=..., exclude_categories=...)`; the options `EXCLUDE_EXT_APPS` and `EXCLUDE_EXT_CATEGORIES` in `fbt_options.py`, read by `PrepareApplicationsBuild` with `env.get(name, [])`.

- [ ] **Step 1: Write the failing unit test**

`appmanifest.py` runs outside SCons (its import of `fbt.util` falls back when SCons is absent), so synthetic apps exercise the filter without a build. Create `tests/fbt/test_exclusions.py`:

```python
#!/usr/bin/env python3
"""The build configuration's exclusions (fbt_options.py EXCLUDE_EXT_APPS and
EXCLUDE_EXT_CATEGORIES): an excluded app leaves the external app set, a plugin whose parent
is excluded goes with it, a plugin of a built app stays unless named itself, an unknown id is
reported and nothing else. Run from the project root: python3 tests/fbt/test_exclusions.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "Momentum-Firmware", "scripts"))
from fbt.appmanifest import AppBuildset, AppManager, FlipperApplication, FlipperAppType  # noqa: E402

failures = 0


def check(cond, what):
    global failures
    if not cond:
        failures += 1
        print("FAIL", what)


def app(appid, apptype, **kw):
    return FlipperApplication(appid=appid, apptype=apptype, _apppath=appid, _appdir=appid, **kw)


def manager():
    mgr = AppManager()
    for a in [
        app("default", FlipperAppType.METAPACKAGE, provides=["cli", "gui", "subghz"]),
        app("cli", FlipperAppType.SERVICE),
        app("gui", FlipperAppType.SERVICE),
        app("subghz", FlipperAppType.MENUEXTERNAL, fap_category="Sub-GHz"),
        app("js_app", FlipperAppType.EXTERNAL, fap_category="assets"),
        app("js_gui", FlipperAppType.PLUGIN, requires=["js_app"]),
        app("cli_js", FlipperAppType.PLUGIN, requires=["cli"]),
        app("doom", FlipperAppType.EXTERNAL, fap_category="Games"),
        app("tetris", FlipperAppType.EXTERNAL, fap_category="Games"),
        app("nfc_tool", FlipperAppType.EXTERNAL, fap_category="NFC"),
        app("nfc_plugin", FlipperAppType.PLUGIN, requires=["nfc_tool"]),
    ]:
        mgr._add_known_app(a)
    return mgr


def ids(buildset):
    return sorted(a.appid for a in buildset.get_ext_apps())


# Nothing excluded: every external app and plugin with a built parent is in the set
bs = manager().filter_apps(applist=["default"], ext_applist=[], hw_target="f7")
check(
    ids(bs) == ["cli_js", "doom", "js_app", "js_gui", "nfc_plugin", "nfc_tool", "subghz", "tetris"],
    f"nothing excluded: {ids(bs)}",
)

# The fork's configuration: js_app and cli_js by id, Games by category; js_gui follows js_app
bs = manager().filter_apps(
    applist=["default"],
    ext_applist=[],
    hw_target="f7",
    exclude_apps=["js_app", "cli_js"],
    exclude_categories=["Games"],
)
check(ids(bs) == ["nfc_plugin", "nfc_tool", "subghz"], f"fork configuration: {ids(bs)}")

# A category exclusion alone leaves the JS apps alone
bs = manager().filter_apps(
    applist=["default"], ext_applist=[], hw_target="f7", exclude_categories=["Games"]
)
check(
    ids(bs) == ["cli_js", "js_app", "js_gui", "nfc_plugin", "nfc_tool", "subghz"],
    f"category only: {ids(bs)}",
)

# An unknown id is reported once, and does not fail the build; the count names what went
messages = []
bs = AppBuildset(
    manager(),
    hw_target="f7",
    appnames=["default"],
    extra_ext_appnames=[],
    exclude_apps=["js_app", "cli_js", "nope"],
    exclude_categories=["Games"],
    message_writer=messages.append,
)
check(ids(bs) == ["nfc_plugin", "nfc_tool", "subghz"], f"unknown id: {ids(bs)}")
check(any("nope" in m and "unknown" in m for m in messages), f"unknown id reported: {messages}")
check(any(m.startswith("Excluded 4 external apps") for m in messages), f"count reported: {messages}")

print(f"fbt exclusions: {failures} failures")
sys.exit(1 if failures else 0)
```

- [ ] **Step 2: Run it to verify it fails**

Run from the project root: `python3 tests/fbt/test_exclusions.py`
Expected: a `TypeError` about an unexpected keyword argument `exclude_apps` (the filter does not take it yet).

- [ ] **Step 3: Add the options and the filter**

`Momentum-Firmware/fbt_options.py`, after `EXTRA_EXT_APPS = []`:

```python
# Left out of the build and of the card by the accessibility fork: app ids, and fap_category
# values. The plugins of an app left out go with it.
EXCLUDE_EXT_APPS = ["js_app", "cli_js"]
EXCLUDE_EXT_CATEGORIES = ["Games"]
```

`Momentum-Firmware/site_scons/commandline.scons`, after the `EXTRA_EXT_APPS` tuple in the variables list (same shape):

```python
    (
        "EXCLUDE_EXT_APPS",
        "List of app ids to leave out of the build and the resources",
        [],
    ),
    (
        "EXCLUDE_EXT_CATEGORIES",
        "List of fap_category values whose apps are left out of the build and the resources",
        [],
    ),
```

`Momentum-Firmware/scripts/fbt_tools/fbt_apps.py`, in `PrepareApplicationsBuild`:

```python
        appbuild = env["APPBUILD"] = env["APPMGR"].filter_apps(
            applist=env["APPS"],
            ext_applist=env["EXTRA_EXT_APPS"],
            hw_target=env.subst("f${TARGET_HW}"),
            skip_external=env.get("SKIP_EXTERNAL"),
            exclude_apps=env.get("EXCLUDE_EXT_APPS", []),
            exclude_categories=env.get("EXCLUDE_EXT_CATEGORIES", []),
        )
```

`Momentum-Firmware/scripts/fbt/appmanifest.py`, `filter_apps`:

```python
    def filter_apps(
        self,
        *,
        applist: List[str],
        ext_applist: List[str],
        hw_target: str,
        skip_external: bool = False,
        exclude_apps: Optional[List[str]] = None,
        exclude_categories: Optional[List[str]] = None,
    ):
        return AppBuildset(
            self,
            hw_target=hw_target,
            appnames=applist,
            extra_ext_appnames=ext_applist,
            skip_external=skip_external,
            exclude_apps=exclude_apps,
            exclude_categories=exclude_categories,
        )
```

`AppBuildset.__init__` gains two keyword parameters before `message_writer` and stores them:

```python
        *,
        extra_ext_appnames: List[str],
        skip_external: bool = False,
        exclude_apps: Optional[List[str]] = None,
        exclude_categories: Optional[List[str]] = None,
        message_writer: Callable | None = None,
    ):
        self.appmgr = appmgr
        self.appnames = set(appnames)
        self.incompatible_extapps, self.extapps = [], []
        self._extra_ext_appnames = extra_ext_appnames
        self._skip_external = skip_external
        self._exclude_apps = set(exclude_apps or [])
        self._exclude_categories = set(exclude_categories or [])
```

`_process_ext_apps`, after `extapps.extend(map(self.appmgr.get, self._extra_ext_appnames))` and before the target loop:

```python
        # Left out by the build configuration (EXCLUDE_EXT_APPS, EXCLUDE_EXT_CATEGORIES). Their
        # plugins leave in _group_plugins, as the plugins of any app that is not built do
        excluded = [
            app
            for app in extapps
            if app.appid in self._exclude_apps or app.fap_category in self._exclude_categories
        ]
        if excluded:
            extapps = [app for app in extapps if app not in excluded]
            self._writer(
                f"Excluded {len(excluded)} external apps by configuration: "
                + ", ".join(sorted(app.appid for app in excluded))
            )
        for appid in sorted(self._exclude_apps - set(self.appmgr.known_apps)):
            self._writer(f"EXCLUDE_EXT_APPS names an unknown app: {appid}")
```

`Momentum-Firmware/scripts/ufbt/SConstruct`, next to `EXTRA_EXT_APPS=[]`: add `EXCLUDE_EXT_APPS=[]` and `EXCLUDE_EXT_CATEGORIES=[]`.

- [ ] **Step 4: Run the unit test, then wire it into the host runner**

Run: `python3 tests/fbt/test_exclusions.py`
Expected: `fbt exclusions: 0 failures`, exit 0.

Append to `tools/run_host_tests.sh` (after the throttle block):

```zsh
if ! python3 "$ROOT/tests/fbt/test_exclusions.py" > "$OUT/fbt_exclusions.txt"; then
  cat "$OUT/fbt_exclusions.txt"
  echo "fbt exclusion checks failed"
  exit 1
fi
echo "fbt exclusions: $(tail -n 1 "$OUT/fbt_exclusions.txt")"
```

Run: `tools/run_host_tests.sh`. Expected: every suite green, the new line last.

- [ ] **Step 5: Build and check what the card would get**

In the firmware repo:

```bash
rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps && ./fbt 2>&1 | tail -20
```

Expected in the output: `Excluded 44 external apps by configuration: ...` (42 games plus js_app and cli_js; a different count means the external tree's games differ from the spec's count: list the names in the report, it is not a failure), "API version 87.2 is up to date", the two known manifest warnings, exit 0. Then:

```bash
ls build/f7-firmware-C/.extapps | grep -c -E '^(js_|cli_js|test_js)' ; ls build/f7-firmware-C/resources/apps
grep -c -E 'apps/Games/|apps/Scripts/|js_app|cli_js|test_js' build/f7-firmware-C/resources/Manifest
```

Expected: the first count 0; the folder list without `Games` and without `Scripts`; the manifest count 0. If `apps/Scripts` is still listed, the JS runner's `resources="examples"` is still deployed: check that `js_app` really left the set (the excluded line names it).

Note the firmware.bin size (unchanged, 877,036: the JS library is still linked in this task).

- [ ] **Step 6: Commit**

Firmware repo: `git add fbt_options.py site_scons/commandline.scons scripts/fbt_tools/fbt_apps.py scripts/fbt/appmanifest.py scripts/ufbt/SConstruct` then `git commit -m "fbt: EXCLUDE_EXT_APPS and EXCLUDE_EXT_CATEGORIES leave apps out of the build; games and the JS apps left out" -- <the same files>`.
Project repo: `git add tests/fbt/test_exclusions.py tools/run_host_tests.sh` then commit `-- <the same files>` with "Host tests: the fbt exclusion filter".

---

### Task 2: The JavaScript engine out of the firmware

**Files:**
- Modify: `Momentum-Firmware/lib/SConscript:41` (the `"mjs",` line)
- Modify: `Momentum-Firmware/targets/f7/api_symbols.csv` (90 lines removed)
- Modify: `Momentum-Firmware/fbt_options.py` (`"js_app",` in `FIRMWARE_APPS["unit_tests_min"]`)

**Interfaces:**
- Consumes: Task 1's exclusions (the JS apps are no longer built, so nothing links against the library).
- Produces: a firmware without `lib/mjs`, CSV version still 87.2.

- [ ] **Step 1: Remove the library from the firmware**

Delete the line `        "mjs",` from `lib/SConscript`. Delete the line `        "js_app",` from the `unit_tests_min` list in `fbt_options.py`.

- [ ] **Step 2: Remove the JS entries from the CSV**

In the firmware repo:

```bash
python3 - <<'PY'
import re
p = 'targets/f7/api_symbols.csv'
lines = open(p).read().splitlines(True)
keep = [l for l in lines
        if not re.match(r'^(Function|Variable),[+-],m?js_', l)
        and not l.startswith('Header,+,lib/mjs/')]
removed = len(lines) - len(keep)
assert removed == 90, removed
open(p, 'w').write(''.join(keep))
print('removed', removed)
PY
git diff --stat targets/f7/api_symbols.csv
```

Expected: `removed 90`; the diff is 90 deletions and 0 insertions; the line `Version,+,87.2,,` is untouched; `grep -c I_js_script_10px targets/f7/api_symbols.csv` is still 1.

- [ ] **Step 3: Build and check the API report**

```bash
./fbt 2>&1 | grep -E "API version|warning|error" ; git status --short | grep -v "^ m applications/external"
```

Expected: "API version 87.2 is up to date", the two known manifest warnings only, and `git status` shows exactly the three modified files (the build did not rewrite the CSV: if it did, the diff grew and something in the CSV was still referring to the library; stop and look).

- [ ] **Step 4: Measure**

Run from the project root: `tools/flash_headroom.sh`
Expected: about 835,780 bytes, 44,860 spare (the spec measured exactly this at the same base). `./fbt lint` exit 0.

- [ ] **Step 5: Commit**

`git add lib/SConscript targets/f7/api_symbols.csv fbt_options.py` then `git commit -m "JavaScript engine out of the firmware: mjs unlinked, its 82 symbols and 8 headers off the CSV, API 87.2 kept" -- lib/SConscript targets/f7/api_symbols.csv fbt_options.py`.

---

### Task 3: Sub-GHz built into the firmware

**Files:**
- Modify: `Momentum-Firmware/applications/main/subghz/application.fam` (the version of commit 1c113c28a)

**Interfaces:**
- Consumes: Task 2's flash saving.
- Produces: `subghz` as `FlipperAppType.APP`; no `subghz.fap` built or deployed.

- [ ] **Step 1: Restore the manifest of the earlier attempt**

```bash
git checkout 1c113c28a -- applications/main/subghz/application.fam
git diff --cached --stat
```

Expected: 1 file, 45 insertions, 17 deletions. The base has not moved since that commit, so the explicit source list matches the tree; verify that every quoted source exists:

```bash
for f in $(grep -oE '"[a-z_/0-9]+\.c"' applications/main/subghz/application.fam | tr -d '"'); do test -f applications/main/subghz/$f || echo MISSING $f; done
```

Expected: nothing printed.

Then reword the first comment line inside the `subghz` App: `# Built into the firmware on the screen-reader branch: as a fap it costs about 55 KB of` becomes `# Built into the firmware by the accessibility fork: as a fap it costs about 55 KB of`. Nothing else in the file changes.

- [ ] **Step 2: Build clean and check the card view**

```bash
rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps && ./fbt 2>&1 | grep -E "API version|warning|error|Excluded"
ls build/f7-firmware-C/.extapps | grep -E '^subghz(\.|_d)' ; ls build/f7-firmware-C/resources/apps/Sub-GHz | grep -c '^subghz.fap$'
grep -c 'apps/Sub-GHz/subghz.fap' build/f7-firmware-C/resources/Manifest
```

Expected: the API line and the known warnings; no `subghz.fap` in `.extapps` (only `subghz_add_manually`, `subghz_gps`, `subghz_bruteforcer` and the other Sub-GHz apps); both counts 0.

- [ ] **Step 3: Measure**

`tools/flash_headroom.sh`: about 877,800 bytes, 2,840 spare (the spec's measurement); the margin comes back in Task 4. `./fbt lint` exit 0.

- [ ] **Step 4: Commit**

`git add applications/main/subghz/application.fam` then `git commit -m "Sub-GHz built into the firmware again: the manifest of 1c113c28a, no subghz.fap" -- applications/main/subghz/application.fam`.

---

### Task 4: SAM out of the speech engine, the settings, the console, the tests and the tools

**Files:**
- Delete: `Momentum-Firmware/applications/services/screen_reader/sam/` (sam.c, sam.h)
- Modify: `Momentum-Firmware/applications/services/screen_reader/speech.c`, `speech.h`
- Modify: `Momentum-Firmware/applications/services/screen_reader/speech_pcm.c`, `speech_pcm.h`
- Modify: `Momentum-Firmware/applications/services/screen_reader/speech_text.c:577-619`, `speech_text.h`
- Modify: `Momentum-Firmware/applications/services/screen_reader/screen_reader.c:181-186, 384, 466-468`
- Modify: `Momentum-Firmware/applications/services/screen_reader/screen_reader_cli.c` (usage 80-100, voice 137-171, status 173-181, set_number 300-319, dispatch 363-371)
- Modify: `Momentum-Firmware/lib/momentum/settings.h:113-118`, `settings.c:50-55, 130-135`
- Rewrite: `Momentum-Firmware/applications/main/momentum_app/scenes/momentum_app_scene_accessibility.c`
- Delete: `tests/host/test_sam_port.c`, `tests/host/sam_cases.h`, `tests/host/sam_ref/`, `tools/sam_calibrate.py`
- Modify: `tests/host/test_speech_pcm.c`, `tests/host/test_speech_text.c`, `tools/run_host_tests.sh`

**Interfaces:**
- Produces: `void speech_set_volume(Speech* speech, uint8_t volume)` replaces `speech_set_voice(speech, rate, volume)`; `void speech_pcm_init(SpeechPcm* pcm, uint8_t volume_percent)`; `SpeechVoiceStats.muted` (uint32_t); `MomentumSettings` without `sr_rate` and `sr_voice`; `speech_set_voice_clips(speech, false)` means mute.

- [ ] **Step 1: Host tests first: the PCM stage without SAM**

In `tests/host/test_speech_pcm.c` delete the SAM value tests: `test_delta_zero`, `test_largest_delta`, `test_overhead`, `test_carry`, `test_stop`, and the `emitted`/`collect`/`abort_at` collector. Rewrite `test_volume` to use raw pushes, and `main` to keep the table checks:

```c
static void test_volume(void) {
    SpeechPcm pcm;
    const uint8_t v[5] = {100, 115, 128, 140, 155};

    // Volume 0: every entry is the silence value, so a push emits nothing but silence
    speech_pcm_init(&pcm, 0);
    uint8_t silence = speech_pcm_silence(&pcm);
    CHECK(silence == 127);
    bool all_silent = true;
    for(int x = 0; x < 256; x++) {
        if(pcm.lut[x] != silence) all_silent = false;
    }
    CHECK(all_silent);
    seq_count = 0;
    CHECK(speech_pcm_push_raw(&pcm, v, 5, 20000, collect_seq, NULL));
    CHECK(seq_count == 5);
    CHECK(run_is(0, 5, silence));

    // Volume 100 reproduces the demo curve, clips at both ends, and is what anything above
    // 100 is treated as
    speech_pcm_init(&pcm, 100);
    uint8_t full[256];
    memcpy(full, pcm.lut, sizeof(full));
    CHECK(full[0] == 0 && full[255] == 255);
    CHECK(speech_pcm_silence(&pcm) == demo_curve(128));
    speech_pcm_set_volume(&pcm, 200);
    CHECK(memcmp(full, pcm.lut, sizeof(full)) == 0);
    speech_pcm_set_volume(&pcm, 255);
    CHECK(memcmp(full, pcm.lut, sizeof(full)) == 0);

    // Every volume keeps the curve non decreasing
    for(int volume = 0; volume <= 100; volume += 25) {
        speech_pcm_set_volume(&pcm, (uint8_t)volume);
        CHECK(lut_is_monotone(&pcm));
    }

    // A volume change leaves the timing alone, and the next push uses the new table, which
    // pulls the loud and the quiet value toward the middle
    speech_pcm_set_volume(&pcm, 100);
    seq_count = 0;
    CHECK(speech_pcm_push_raw(&pcm, v, 5, 20000, collect_seq, NULL));
    speech_pcm_set_volume(&pcm, 50);
    CHECK(pcm.now_ns == 100000 && pcm.next_slot_ns == 100000 && pcm.slots == 5);
    CHECK(pcm.subsamples == 5 && pcm.nominal_us == 100);
    seq_count = 0;
    CHECK(speech_pcm_push_raw(&pcm, v, 5, 20000, collect_seq, NULL));
    CHECK(seq_count == 5);
    for(int k = 0; k < 5; k++) CHECK(seq[k] == pcm.lut[v[k]]);
    CHECK(pcm.lut[v[4]] < full[v[4]]);
    CHECK(pcm.lut[v[0]] > full[v[0]]);

    // A reset starts the timing over and keeps the table
    speech_pcm_reset(&pcm);
    CHECK(pcm.slots == 0 && pcm.now_ns == 0 && pcm.next_slot_ns == 0);
    CHECK(pcm.subsamples == 0 && pcm.nominal_us == 0);
    CHECK(pcm.lut[v[0]] == full[v[0]] || pcm.lut[v[0]] > full[v[0]]);
}

int main(void) {
    SpeechPcm pcm;

    // Full volume reproduces the demo curve exactly, zero volume is the mid level
    speech_pcm_init(&pcm, 100);
    for(int x = 0; x < 256; x++) CHECK(pcm.lut[x] == demo_curve((uint8_t)x));
    CHECK(speech_pcm_silence(&pcm) == demo_curve(128));
    speech_pcm_set_volume(&pcm, 0);
    for(int x = 0; x < 256; x++) CHECK(pcm.lut[x] == 127);
    speech_pcm_set_volume(&pcm, 50);
    CHECK(pcm.lut[0] < pcm.lut[128] && pcm.lut[128] < pcm.lut[255]);
    CHECK(pcm.lut[255] < demo_curve(255));

    test_volume();
    test_push_raw();

    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
```

In `test_push_raw`, every `speech_pcm_init(&pcm, X, Y)` becomes `speech_pcm_init(&pcm, X)`, and the comment "The overhead belongs to SAM values and must not apply" goes. The file's remaining comment "The Text to SAM app's SetAUDIO curve" stays: the curve is the demo's, that is a fact.

In `tests/host/test_speech_text.c` delete `test_chunks` and its call; `expect("Text to SAM", "Text to SAM")` stays (text, not the synthesizer).

Run `tools/run_host_tests.sh`. Expected: the PCM and text suites fail to compile (`speech_pcm_init` still takes three arguments; `speech_text_next_chunk` still exists but that is not an error); at least the PCM compile error.

- [ ] **Step 2: The PCM stage and the text layer**

`speech_pcm.h`: header comment becomes "Turns the recorded voice's 8 bit samples into PWM duty bytes, one per 20 microsecond carrier period, each sample held for its time at the clip's rate. Pure C, host tested."; delete `uint32_t overhead_ns;` from the struct; `void speech_pcm_init(SpeechPcm* pcm, uint8_t volume_percent);`; delete the `speech_pcm_push` declaration and its comment. `speech_pcm.c`: `speech_pcm_init` without the overhead argument and assignment; delete `speech_pcm_push`.

`speech_text.h`: comment "Rewrites announcement text into words SAM pronounces well, and splits it into chunks short enough for one synthesizer call." becomes "Rewrites announcement text into the words the recorded voice has clips for, and copies the characters of a text to be spelled."; delete `SPEECH_CHUNK_MAX` and the `speech_text_next_chunk` declaration with its comment. `speech_text.c`: delete `speech_text_next_chunk` (lines 577 to 619). Read the file's other comments: where one says the rewriting serves SAM's pronunciation, say the clips' names instead; the rules themselves do not change.

Run `tools/run_host_tests.sh`. Expected: the PCM and text suites green (the SAM suite still runs and passes; it goes in Step 6).

- [ ] **Step 3: The engine**

`speech.c`:

1. Delete `#include "sam/sam.h"`, `#define SPEECH_OVERHEAD_NS ...`, the struct fields `volatile uint8_t rate;` and `char chunk[SPEECH_CHUNK_MAX + 2];`. Add to the recorded-voice block of the struct: `uint32_t muted; /* items completed silently: voice off, or no vocabulary on the card */`.
2. Delete `speech_sam_output`, `speech_sam_chunk`, `speech_sam_word`, `speech_sam_spell`.
3. `speech_spell_word` loses the `voice` parameter; a letter whose clip is missing is recorded like a word:

```c
/**
 * A word the vocabulary lacks is spelled with the letter and digit clips, a short gap between
 * them. A character whose clip is missing too is skipped after the gap and its clip name is
 * recorded as missing, once per boot, like a word. Each letter played from a clip counts as a
 * clip in the voice status.
 */
static void speech_spell_word(Speech* speech, const char* word) {
    char name[3];
    for(const char* p = word; *p != '\0' && !speech->aborted; p++) {
        if(!speech_voice_letter_clip(*p, name)) continue;
        if(p != word && !speech_push_silence(speech, SPEECH_VOICE_LETTER_GAP_MS)) return;
        if(speech_voice_path(name, speech->path, sizeof(speech->path)) > 0 &&
           speech_play_clip(speech, speech->path)) {
            speech->voice.clip_words++;
            continue;
        }
        speech_voice_missing(&speech->voice, name);
    }
}
```

4. `speech_speak_words(Speech* speech, bool spell)`: the same body without the `voice` argument in its two `speech_spell_word` calls.
5. `speech_speak_item`:

```c
static void speech_speak_item(Speech* speech, const SpeechItem* item) {
    // Muted (sr voice off), or no vocabulary on the card: the item completes at once, without
    // the speaker, a file or the missing list; the voice status counts it
    if(!speech->voice_enabled || !speech_voice_ready(speech)) {
        speech->muted++;
        speech_lock(speech);
        speech->stats.speaking = false;
        speech_unlock(speech);
        return;
    }
    if(!speech_item_begin(speech, item)) return;

    // A spelled item keeps its own letters and digits; one without any is said instead
    bool spell = false;
    if(item->spell) {
        spell = speech_text_spell_copy(item->text, speech->expanded, sizeof(speech->expanded)) > 0;
    }
    if(!spell) speech_text_expand(item->text, speech->expanded, sizeof(speech->expanded));
    speech->started = furi_get_tick();
    speech_speak_words(speech, spell);
    speech_item_end(speech);
    speech_write_missing(speech);
}
```

6. `speech_alloc`: delete `speech->rate = 72;`, and `speech_pcm_init(&speech->pcm, 100);`.
7. Replace `speech_set_voice` with:

```c
void speech_set_volume(Speech* speech, uint8_t volume) {
    furi_check(speech);
    speech->volume = volume;
}
```

8. `speech_get_voice_stats`: add `out->muted = *(volatile uint32_t*)&speech->muted;`.
9. Comments that mention SAM in this file (the file header if any, `speech_speak_words`, the worker) now describe the clips; grep `SAM` and `sam` in the file afterwards: no hit.

`speech.h`: the file comment becomes "Speech engine: a worker thread that plays queued utterances from the recorded voice's clips on the card, through the speaker with DMA. Announcements come from the screen reader service; the console command "sr say" uses it too."; the `speech_say_spelled` comment loses "SAM says the letters one by one when the recorded voice is off or missing" and says "With the voice off, or without a vocabulary on the card, nothing is played."; `speech_set_voice` is replaced by `/** volume 0..100, applied from the next utterance on. */ void speech_set_volume(Speech* speech, uint8_t volume);`; `SpeechVoiceStats` gains `uint32_t muted; /**< items completed silently since boot: the voice off, or no vocabulary */`; the `speech_set_voice_clips` comment becomes "Recorded voice on or off, from the next utterance on. Off mutes: an item completes at once, no file is opened, nothing is played, until on again or a reboot; it is the guard the generator sets around a sync."

- [ ] **Step 4: The reader, the console, the settings**

`screen_reader.c`: `sr_push_voice` becomes

```c
// The volume as saved, pushed before the reader speaks: the settings app writes
// momentum_settings and its change applies from the next announcement on (one cheap store)
static void sr_push_volume(ScreenReader* sr) {
    speech_set_volume(sr->speech, (uint8_t)momentum_settings.sr_volume);
}
```

and its callers are renamed; the volume chord at line 384 calls `speech_set_volume(sr->speech, (uint8_t)v);`; the init at 466 becomes `speech_set_volume(sr->speech, (uint8_t)momentum_settings.sr_volume);` and the `speech_set_voice_clips(sr->speech, momentum_settings.sr_voice);` line goes (the engine starts with the voice on).

`screen_reader_cli.c`: delete the usage line for `rate`; the `voice` usage line becomes `"  voice on|off|status  recorded word clips from the card; off mutes speech until on or a reboot\r\n"`. `sr_cli_voice` no longer touches `momentum_settings` nor saves: `on` prints "voice on", `off` prints "voice off: muted until sr voice on or a reboot". `sr_cli_print_voice` prints `muted %lu` after `missing %lu` (add `(unsigned long)v.muted` in the same order). `sr_cli_status` prints `"volume: %lu, verbosity: %lu, change delay: %lu ms\r\n"` with the three values. Replace `sr_cli_set_number` with:

```c
static void sr_cli_set_volume(ScreenReader* sr, FuriString* args) {
    int value = 0;
    if(!args_read_int_and_trim(args, &value) || value < 0 || value > 100) {
        printf("expected a number from 0 to 100\r\n");
        return;
    }
    momentum_settings.sr_volume = (uint32_t)value;
    momentum_settings_save();
    speech_set_volume(screen_reader_get_speech(sr), (uint8_t)value);
    printf("volume set to %d\r\n", value);
}
```

and in the dispatcher delete the `rate` branch and make `volume` call `sr_cli_set_volume(sr, args)`.

`lib/momentum/settings.h`: delete `uint32_t sr_rate;` and `bool sr_voice;`. `settings.c`: delete the two default lines and the two table rows `{setting_uint(sr_rate, 40, 120)},` and `{setting_bool(sr_voice)},`.

Grep the firmware for the two names afterwards: `grep -rn "sr_rate\|sr_voice\b\|speech_set_voice(" applications lib` gives only the Accessibility scene (next step).

- [ ] **Step 5: The Accessibility scene**

Replace the whole of `applications/main/momentum_app/scenes/momentum_app_scene_accessibility.c` with:

```c
#include "../momentum_app.h"

enum VarItemListIndex {
    VarItemListIndexScreenReader,
    VarItemListIndexVolume,
    VarItemListIndexVerbosity,
    VarItemListIndexChangeDelay,
    VarItemListIndexCount,
};

#define SR_VOLUME_MIN   0
#define SR_VOLUME_MAX   100
#define SR_VOLUME_STEP  10
#define SR_VOLUME_COUNT (((SR_VOLUME_MAX - SR_VOLUME_MIN) / SR_VOLUME_STEP) + 1)

void momentum_app_scene_accessibility_var_item_list_callback(void* context, uint32_t index) {
    MomentumApp* app = context;
    view_dispatcher_send_custom_event(app->view_dispatcher, index);
}

static void momentum_app_scene_accessibility_screen_reader_changed(VariableItem* item) {
    MomentumApp* app = variable_item_get_context(item);
    bool value = variable_item_get_current_value_index(item);
    variable_item_set_current_value_text(item, value ? "ON" : "OFF");
    momentum_settings.screen_reader = value;
    app->save_settings = true;
}

static void momentum_app_scene_accessibility_volume_changed(VariableItem* item) {
    MomentumApp* app = variable_item_get_context(item);
    uint8_t index = variable_item_get_current_value_index(item);
    uint32_t value = SR_VOLUME_MIN + (index * SR_VOLUME_STEP);
    char str[6];
    snprintf(str, sizeof(str), "%lu", value);
    variable_item_set_current_value_text(item, str);
    momentum_settings.sr_volume = value;
    app->save_settings = true;
}

static const char* const sr_verbosity_names[] = {
    "Terse",
    "Normal",
    "Verbose",
};
static void momentum_app_scene_accessibility_verbosity_changed(VariableItem* item) {
    MomentumApp* app = variable_item_get_context(item);
    uint8_t index = variable_item_get_current_value_index(item);
    variable_item_set_current_value_text(item, sr_verbosity_names[index]);
    momentum_settings.sr_verbosity = index;
    app->save_settings = true;
}

// A table, not uniform steps.
static const uint32_t sr_change_ms_values[] = {
    SR_CHANGE_MS_MIN, // 500
    1000,
    1500,
    2000,
    SR_CHANGE_MS_DEFAULT, // 3000
    5000,
    SR_CHANGE_MS_MAX, // 10000
};
static const char* const sr_change_ms_labels[] = {
    "0.5 s",
    "1 s",
    "1.5 s",
    "2 s",
    "3 s",
    "5 s",
    "10 s",
};
// Nearest table entry to a saved value that may be off-table (from an older build): scan for
// the smallest absolute difference; a tie goes to the lower value.
static uint8_t momentum_app_scene_accessibility_change_delay_nearest_index(uint32_t ms) {
    uint8_t nearest = 0;
    uint32_t nearest_diff = UINT32_MAX;
    for(uint8_t i = 0; i < COUNT_OF(sr_change_ms_values); i++) {
        uint32_t diff = (ms > sr_change_ms_values[i]) ? (ms - sr_change_ms_values[i]) :
                                                        (sr_change_ms_values[i] - ms);
        if(diff < nearest_diff) {
            nearest_diff = diff;
            nearest = i;
        }
    }
    return nearest;
}
static void momentum_app_scene_accessibility_change_delay_changed(VariableItem* item) {
    MomentumApp* app = variable_item_get_context(item);
    uint8_t index = variable_item_get_current_value_index(item);
    variable_item_set_current_value_text(item, sr_change_ms_labels[index]);
    momentum_settings.sr_change_ms = sr_change_ms_values[index];
    app->save_settings = true;
}

void momentum_app_scene_accessibility_on_enter(void* context) {
    MomentumApp* app = context;
    VariableItemList* var_item_list = app->var_item_list;
    VariableItem* item;
    uint8_t value_index;

    item = variable_item_list_add(
        var_item_list,
        "Screen Reader",
        2,
        momentum_app_scene_accessibility_screen_reader_changed,
        app);
    value_index = momentum_settings.screen_reader;
    variable_item_set_current_value_index(item, value_index);
    variable_item_set_current_value_text(item, value_index ? "ON" : "OFF");

    item = variable_item_list_add(
        var_item_list,
        "Volume",
        SR_VOLUME_COUNT,
        momentum_app_scene_accessibility_volume_changed,
        app);
    // Round to the nearest step so the label matches the index; sr_volume can be off-grid.
    value_index =
        (momentum_settings.sr_volume - SR_VOLUME_MIN + (SR_VOLUME_STEP / 2)) / SR_VOLUME_STEP;
    if(value_index > SR_VOLUME_COUNT - 1) value_index = SR_VOLUME_COUNT - 1;
    variable_item_set_current_value_index(item, value_index);
    uint32_t volume_value = SR_VOLUME_MIN + (value_index * SR_VOLUME_STEP);
    char volume_str[6];
    snprintf(volume_str, sizeof(volume_str), "%lu", volume_value);
    variable_item_set_current_value_text(item, volume_str);

    item = variable_item_list_add(
        var_item_list,
        "Verbosity",
        COUNT_OF(sr_verbosity_names),
        momentum_app_scene_accessibility_verbosity_changed,
        app);
    value_index = momentum_settings.sr_verbosity;
    variable_item_set_current_value_index(item, value_index);
    variable_item_set_current_value_text(item, sr_verbosity_names[value_index]);

    item = variable_item_list_add(
        var_item_list,
        "Change delay",
        COUNT_OF(sr_change_ms_values),
        momentum_app_scene_accessibility_change_delay_changed,
        app);
    value_index = momentum_app_scene_accessibility_change_delay_nearest_index(
        momentum_settings.sr_change_ms);
    variable_item_set_current_value_index(item, value_index);
    variable_item_set_current_value_text(item, sr_change_ms_labels[value_index]);

    variable_item_list_set_enter_callback(
        var_item_list, momentum_app_scene_accessibility_var_item_list_callback, app);

    variable_item_list_set_selected_item(
        var_item_list,
        scene_manager_get_scene_state(app->scene_manager, MomentumAppSceneAccessibility));

    view_dispatcher_switch_to_view(app->view_dispatcher, MomentumAppViewVarItemList);
}

bool momentum_app_scene_accessibility_on_event(void* context, SceneManagerEvent event) {
    MomentumApp* app = context;
    bool consumed = false;

    if(event.type == SceneManagerEventTypeCustom) {
        scene_manager_set_scene_state(
            app->scene_manager, MomentumAppSceneAccessibility, event.event);
        consumed = true;
    }

    return consumed;
}

void momentum_app_scene_accessibility_on_exit(void* context) {
    MomentumApp* app = context;
    variable_item_list_reset(app->var_item_list);
}
```

- [ ] **Step 6: Delete SAM and its tests and tool**

In the firmware repo: `git rm -r -q applications/services/screen_reader/sam`. In the project repo: `git rm -r -q tests/host/test_sam_port.c tests/host/sam_cases.h tests/host/sam_ref tools/sam_calibrate.py`.

`tools/run_host_tests.sh`: the header comment becomes "Build and run the host tests for the screen reader: the screen model, the speech helpers, the chords, the throttle and the build's exclusion filter. Uses clang from Xcode."; delete the `SAM_ORIG=` line and the whole SAM block (from `clang++ -std=c++17 ...` through `echo "SAM port matches the original on ..."`).

Run `tools/run_host_tests.sh`: green, no SAM line. Then `grep -rn -i "\bsam\b" tests tools --include=*.c --include=*.h --include=*.py --include=*.sh` lists only `tools/say.sh` and `tools/ram_probe.py` (the external Text to SAM demo app) and `tests/host/test_speech_text.c`'s "Text to SAM" expectation.

- [ ] **Step 7: Build, lint, measure**

Firmware repo: `./fbt 2>&1 | grep -E "API version|warning|error"`, expected the usual lines and no error; `./fbt lint` exit 0; `grep -rn "sam\.h\|sam_speak\|SamVoice\|sr_rate\|sr_voice\b" applications lib` empty. `tools/flash_headroom.sh`: about 862 KB, at least 16 KB spare; record the exact figure. `git status --short` in the firmware repo lists the engine files, the reader, the console, the settings, the scene, and the deleted `sam/` (nothing else).

- [ ] **Step 8: Commit**

Firmware repo: `git add applications/services/screen_reader lib/momentum/settings.h lib/momentum/settings.c applications/main/momentum_app/scenes/momentum_app_scene_accessibility.c` then `git commit -m "SAM out: the engine plays clips and spelled letters only, mutes when the voice is off or no vocabulary is on the card; rate and the Voice setting removed" -- <the same paths>`.
Project repo: `git add tests/host tools/run_host_tests.sh tools/sam_calibrate.py` then `git commit -m "Host tests without SAM: PCM raw path only, chunking gone" -- tests/host tools/run_host_tests.sh tools/sam_calibrate.py`.

- [ ] **Step 9: Flash and check the engine on the device**

You are the only agent on the device. Confirm it is idle: `.venv/bin/python tools/flipper_cli.py "loader info"` says no application, and two `sr status` 30 s apart show the same announcements count. Then in the firmware repo:

```bash
rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps && ./fbt flash_usb_full 2>&1 | tail -5
```

Wait for the port to come back (about 7 minutes in all). Then, from the project root, each through `tools/flipper_cli.py`:

1. `sr screen` (Back if it is the post-update screen), `sr status`: the second line starts with "volume:" and has no rate; note "enabled: yes".
2. `sr say hello world` then `sr status` after 2 s: utterances up by one, last utterance played; `sr voice status`: "voice: on", vocabulary yes, clips up by two, muted 0.
3. `sr voice off`, `sr say hello`, wait 1 s, `sr voice status`: muted 1, clips unchanged, `sr status` utterances unchanged; `sr voice on`.
4. `sr chord up` on the home screen: "Home screen" spoken (clips up). `input send ok short` opens the main menu; `sr chord okhold`: the focus spelled (four letter clips for Apps); `sr chord right` then `sr chord left`: "Volume" spoken and `sr status` shows the volume back where it was. `input send back short`.
5. `loader open Momentum`, then `input send up short` (Accessibility is the last of the four), `input send ok short`, `sr screen`: four rows, Screen Reader, Volume, Verbosity, Change delay, no Voice and no Rate. Leave with `input send back short` three times; `sr screen` shows the home screen.
6. `storage list /ext/apps`: no Games and no Scripts folder; `storage list /ext/apps/assets`: no js_app.fap; `storage list /ext/apps/Sub-GHz`: no subghz.fap; `storage list /ext/apps_data/js_app` reports that it does not exist. If any of these is still there, the updater's cleanup did not run: check `storage list /ext/Manifest` and report; do not delete by hand.
7. `input send ok short`, then Down until `sr screen` shows Sub-GHz focused, `input send ok short`: the Sub-GHz menu is read; `loader info` names Sub-GHz; `free` reports the heap; `input send back short` twice.

Record every reply in the task report. Leave the device on the home screen, reader on, voice on.

---

### Task 5: Animations off by default

**Files:**
- Modify: `Momentum-Firmware/lib/momentum/settings.h` (end of the struct), `settings.c` (defaults after `sr_change_ms`, table after `sr_change_ms`)
- Modify: `Momentum-Firmware/applications/services/desktop/animations/animation_manager.c` (alloc at 301, the process functions at 153, 176, 185, unload at 495, load at 532)
- Modify: `Momentum-Firmware/applications/main/momentum_app/scenes/momentum_app_scene_interface_graphics.c` (enum at 3, a callback, the first row in `on_enter` at 120)

**Interfaces:**
- Produces: `bool desktop_anims` in `MomentumSettings`, file key `desktop_anims`, default false.

- [ ] **Step 1: The setting**

`settings.h`: after `uint32_t sr_change_ms;` add `bool desktop_anims;`. `settings.c`: after the `sr_change_ms` default add `.desktop_anims = false, // OFF: the home screen loads no animation`; after the `sr_change_ms` table row add `{setting_bool(desktop_anims)},`.

- [ ] **Step 2: The guards**

`animation_manager.c`. Add, above `animation_manager_check_blocking_process`:

```c
// Animations off (momentum_settings.desktop_anims false): nothing is ever loaded, so the
// "new mail" animation that grants a pending level up on a key press never shows; the level
// is granted here instead, whenever the manager is asked to look at the dolphin's state
static void animation_manager_grant_pending_levelup(void) {
    Dolphin* dolphin = furi_record_open(RECORD_DOLPHIN);
    DolphinStats stats = dolphin_stats(dolphin);
    if(stats.level_up_is_pending) dolphin_upgrade_level(dolphin);
    furi_record_close(RECORD_DOLPHIN);
}
```

Then, each as the first statement after the `furi_assert(animation_manager);` line:

- `animation_manager_check_blocking_process`: `if(!momentum_settings.desktop_anims) { animation_manager_grant_pending_levelup(); return; }`
- `animation_manager_new_idle_process`: `if(!momentum_settings.desktop_anims) return;`
- `animation_manager_interact_process`: `if(!momentum_settings.desktop_anims) return false;`
- `animation_manager_unload_and_stall_animation`: `if(!momentum_settings.desktop_anims) return;` (before the other asserts)
- `animation_manager_load_and_continue_animation`: `if(!momentum_settings.desktop_anims) return;` (before the other asserts)

And in `animation_manager_alloc`, replace the last block:

```c
    animation_manager->blocking_shown_sd_ok = true;
    if(momentum_settings.desktop_anims) {
        if(!animation_manager_check_blocking(animation_manager)) {
            animation_manager_start_new_idle(animation_manager);
        }
    }

    return animation_manager;
```

`desktop.c` needs nothing: its two unload calls test `animation_manager_is_animation_loaded`, which stays false. The bubble view draws nothing while its animation is NULL (bubble_animation_view.c, the `model->current == NULL` branches).

- [ ] **Step 3: The settings row**

`momentum_app_scene_interface_graphics.c`: the enum becomes

```c
enum VarItemListIndex {
    VarItemListIndexAnimations,
    VarItemListIndexAssetPack,
    VarItemListIndexAnimSpeed,
    VarItemListIndexCycleAnims,
    VarItemListIndexUnlockAnims,
};
```

(the `case VarItemListIndexAssetPack:` in `on_event` keeps working because the row is also the second one). Add a callback:

```c
// The animation manager has no state for "never loaded", so the change applies at the next
// boot: the app shows its "Rebooting..." popup on exit like its other reboot-bound settings
static void momentum_app_scene_interface_graphics_animations_changed(VariableItem* item) {
    MomentumApp* app = variable_item_get_context(item);
    bool value = variable_item_get_current_value_index(item);
    variable_item_set_current_value_text(item, value ? "ON" : "OFF");
    momentum_settings.desktop_anims = value;
    app->save_settings = true;
    app->require_reboot = true;
}
```

and in `on_enter`, before the Asset Pack row:

```c
    item = variable_item_list_add(
        var_item_list,
        "Animations",
        2,
        momentum_app_scene_interface_graphics_animations_changed,
        app);
    variable_item_set_current_value_index(item, momentum_settings.desktop_anims);
    variable_item_set_current_value_text(item, momentum_settings.desktop_anims ? "ON" : "OFF");
```

- [ ] **Step 4: Build, lint, measure, commit**

`./fbt` clean of errors, `./fbt lint` exit 0, `tools/flash_headroom.sh` (a few hundred bytes more than Task 4's figure; record it). Commit in the firmware repo: `git add lib/momentum/settings.h lib/momentum/settings.c applications/services/desktop/animations/animation_manager.c applications/main/momentum_app/scenes/momentum_app_scene_interface_graphics.c` then `git commit -m "Animations off by default: desktop_anims setting, the animation manager loads nothing when it is off, a pending level up is granted without the animation" -- <the same paths>`.

No flash in this task: Task 6 flashes and measures.

---

### Task 6: Clean release build, full flash, device pass, measurements

**Files:**
- Modify: `tools/ram_probe.py:32` (the Doom row goes)
- Create: `tools/map_size.py` (flash and static RAM per library from the linker map)
- Create: `docs/measurements/2026-09-25-stripdown.txt`

**Interfaces:**
- Consumes: everything above. Produces the figures Task 7 quotes.

- [ ] **Step 1: The probe without the game**

Delete the line `    ("Doom (game)", "/ext/apps/Games/doom.fap", [], 4),` from `tools/ram_probe.py`. Commit in the project repo: `git add tools/ram_probe.py`, `git commit -m "ram_probe: no Doom row, the games are gone" -- tools/ram_probe.py`.

- [ ] **Step 2: Clean build and manifest check**

Firmware repo:

```bash
rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps && ./fbt 2>&1 | grep -E "API version|warning|error|Excluded"
grep -c -E 'apps/Games/|apps/Scripts/|js_app|cli_js|test_js|apps/Sub-GHz/subghz.fap' build/f7-firmware-C/resources/Manifest
```

Expected: 0. `tools/flash_headroom.sh`: record the final figure (this is the image that ships).

- [ ] **Step 3: Flash**

Confirm the device idle as in Task 4 Step 9, then `./fbt flash_usb_full 2>&1 | tail -3` and wait for the port. `sr screen` first.

- [ ] **Step 4: The device pass**

Through `tools/flipper_cli.py`, in this order, every reply into the measurements file:

1. `sr status`, `sr voice status`, `free` at 30 s after boot: idle heap with animations off (the default: Robin's settings file has no `desktop_anims` key).
2. Home screen: `sr chord up` says "Home screen". `input send ok short` (main menu read), `input send back short` ("Home screen" again after leaving: the return path with nothing to reload).
3. Lock: `input send up short` opens the lock menu (Up is Robin's keybind), `sr screen` reads its tiles, `input send ok short` on the Lock tile locks: "Locked, press Back three times quickly to unlock" spoken. The three presses must land within 600 ms of each other, so send them in one invocation on one open port: `.venv/bin/python tools/flipper_cli.py --quiet "input send back short" "input send back short" "input send back short"`; then `sr status` and `sr screen`: "Unlocked" and "Home screen" were spoken and the home screen shows.
4. The Animations row: `loader open Momentum`, `input send ok short` (Interface), `sr screen`; `input send ok short` on Graphics (the first item, verify with `sr screen`), `sr screen`: the first row is "Animations OFF". `input send right short`: "Animations ON". `input send back short` three times: `sr screen` shows the "Rebooting..." popup, then the port drops and comes back. After boot: `sr screen`, `free` at 30 s: idle heap with animations on; `sr status` shows suppressed or announcements moving if a bubble was drawn. Then the same path to set Animations OFF again and reboot; `free` at 30 s a second time.
5. `.venv/bin/python tools/ram_probe.py` (it reboots the device first, then runs every row including Sub-GHz Read and Frequency Analyzer with the reader on). Expected: no row reports a reboot; Sub-GHz rows show tens of KB free. Save its full output.
6. `storage list /ext/apps` (twelve folders, no Games, no Scripts), `storage list /ext/apps/Sub-GHz` (no subghz.fap).
7. A long screen: `loader open Momentum`, `sr chord up` (the whole screen in parts), `input send back short`.
8. Final: `sr status`, `sr voice status`, `free`; home screen, reader on, voice on, speech idle.

- [ ] **Step 5: The map script and the measurements file**

Create `tools/map_size.py` (the script the spec's figures came from):

```python
#!/usr/bin/env python3
"""Flash and static RAM per library, app or object from the firmware's linker map.
Usage: python3 tools/map_size.py Momentum-Firmware/build/f7-firmware-C/firmware.elf.map [lib|obj]
Counts loaded sections only: flash addresses for flash, RAM addresses for data and bss, with
.data counted in both since its initial values sit in flash. Output: flash bytes, RAM bytes,
group, largest first, then the totals."""
import collections
import re
import sys


def main():
    path = sys.argv[1]
    groupby = sys.argv[2] if len(sys.argv) > 2 else "lib"
    flash = collections.Counter()
    ram = collections.Counter()

    def key_of(obj):
        obj = re.sub(r"^build/f7-firmware-C/", "", obj)
        obj = re.sub(r"^/.*?/arm-none-eabi/", "toolchain/", obj)
        if groupby == "obj":
            return obj
        m = re.match(r"lib/(lib\w+\.a)\((.*)\)", obj)
        if m:
            return "lib/" + m.group(1)
        parts = obj.split("/")
        if parts[0] == "applications":
            return "/".join(parts[:3])
        if parts[0] in ("lib", "targets"):
            return "/".join(parts[:2])
        return parts[0]

    pending = None
    started = False
    for line in open(path, errors="replace"):
        if line.startswith("Linker script and memory map"):
            started = True
            continue
        if not started:
            continue
        if line.startswith("OUTPUT("):
            break
        m = re.match(r"^ (\.\S+)\s*$", line)
        if m:
            pending = m.group(1)
            continue
        m = re.match(r"^ (\.\S+)?\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S.*)$", line)
        if not m:
            pending = None
            continue
        sec = m.group(1) or pending
        pending = None
        if not sec:
            continue
        addr = int(m.group(2), 16)
        size = int(m.group(3), 16)
        obj = m.group(4).strip()
        if size == 0 or obj.startswith("*") or "load address" in obj:
            continue
        k = key_of(obj)
        if 0x08000000 <= addr < 0x08100000:
            flash[k] += size
        elif 0x20000000 <= addr < 0x20040000:
            ram[k] += size
            if sec.startswith(".data"):
                flash[k] += size
    print(f"{'flash':>8} {'ram':>7}  group")
    for k, v in flash.most_common():
        print(f"{v:8d} {ram[k]:7d}  {k}")
    for k in ram:
        if k not in flash:
            print(f"{0:8d} {ram[k]:7d}  {k}")
    print("TOTAL flash", sum(flash.values()), "static ram", sum(ram.values()))


if __name__ == "__main__":
    main()
```

Run it over the final map: `python3 tools/map_size.py Momentum-Firmware/build/f7-firmware-C/firmware.elf.map lib`; the screen reader's line and the totals go into the measurements file. Commit it with the file below.

`docs/measurements/2026-09-25-stripdown.txt`, plain text, with these sections: Flash (the headroom figures after Tasks 2, 3, 4, 5 and the final build, each with its commit); Static RAM (from the map script over the final `firmware.elf.map`: total data plus bss, and the screen reader's line); Idle heap (animations off, on, off again, each 30 s after boot); RAM probe (its full output); Device pass (each step's replies). Commit in the project repo.

---

### Task 7: Documents

**Files:**
- Modify: `docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md` (a note at the head of section 8, line 221; a new section 18 at the end)
- Modify: `docs/roadmap.md` (status line 5, the memory plan list at 28-32, the licensing line 44, the "Why a fork" JS figure at 11)
- Modify: `README.md` (device state 17-31; Back chords 61-62; Accessibility 80-111; Useful commands 255-268; Recorded voice 273-282 and 303-310 and 340-348; Known limits 178-192; Folder contents 205-219; Plan 402-414)

- [ ] **Step 1: The design spec**

At the head of section 8 add the paragraph: "SAM left the firmware on 2026-09-25 (docs/superpowers/specs/2026-09-25-firmware-stripdown-design.md, section 6). The engine below is described as built in phase 2; section 18 says what remains." Append section 18, "Stripdown as built (2026-09-25)", with: the build options and what they exclude; the JavaScript engine out with the API kept at 87.2 and why; Sub-GHz built in; the engine without SAM (mute semantics, the missing-letter rule, `speech_set_volume`, `SpeechVoiceStats.muted`, the settings fields removed); the `desktop_anims` setting and the guard list, the level-up rule, the reboot rule; the card cleanup by the updater; the figures from Task 6 (flash after each step, idle heap on and off, the Sub-GHz and NFC rows of the probe); deviations from the stripdown spec, each with its reason (at least: the level up granted in `check_blocking_process` rather than also at alloc, if that is what Task 5 did).

- [ ] **Step 2: The roadmap**

Line 5: status on 2026-09-25, the memory plan done, next the fork and release mechanics. Line 11: the JavaScript engine "41 KB of flash, measured". The memory plan list: items 2, 3 and 4 marked done with the figures (flash spare, idle heap, Sub-GHz free heap with the reader on), and the API decision (87.2 kept; a bump would only close the catalog). Line 44: the SAM sentence goes; the licensing line keeps the GPL-3 and the Piper points.

- [ ] **Step 3: The README**

- Device state (17-31): Sub-GHz is built into the firmware again; the games, the JS runner and SAM are gone; the flash history gains the final figure and commit.
- Back chords (61-62): the rate bullet goes.
- Accessibility (80-111): "The Accessibility screen has four rows"; the Voice and Rate bullets go; the app's list of four is unchanged.
- The home screen section (112-135): the bubbles paragraph says animations are off by default and where the Animations row is (Momentum, Interface, Graphics, first row; a change reboots the device).
- Known limits: the Sub-GHz entry and the bubbles entry go; add "Without the SD card, or without `/ext/sr/voice`, the reader is silent: SAM is gone, and on this base a device without a card has no main apps either."
- Useful commands (255-268): `sr rate` goes from the sentence; the `sam_calibrate` sentence goes; `sr voice off` "mutes until on or a reboot; the generator uses it around a sync".
- Recorded voice (273-282): "instead of SAM" becomes "from the SD card"; "SAM speaks a letter only when its clip is missing too, and everything when the voice is off" becomes "A letter whose clip is missing too is skipped and noted; with the voice off nothing is played." Console commands (303-310): `sr voice on|off` "mutes and unmutes; not saved, on after a reboot"; `sr voice status` gains the muted count. The sync note (340-348): "the saved setting then stays off, and the device speaks with SAM until sr voice on is typed" becomes "the device stays muted until `sr voice on` is typed or it reboots".
- Folder contents (205-219): the SAM port line and `tools/sam_calibrate.py` go; `tests/fbt/test_exclusions.py` is listed.
- Plan (402-414): item 8 done on 2026-09-25 with one line per change; item 9: the fork and release mechanics.

- [ ] **Step 4: Commit**

Project repo: `git add README.md docs/roadmap.md docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md` then `git commit -m "docs: stripdown as built; README without SAM, with the Animations row and the card changes" -- <the same files>`.
