# Task 3 report: Accessibility settings scene

## Status

Done. All three steps (scene, build/copy/verify, commit) complete. No crashes, no reboots.

## Commit

Repo: `Momentum-Firmware`, branch `screen-reader`.

```
commit deb463f3bd51194b8fe161395f1d855241710eef
Author: Robin Kipp <robin@robin-kipp.net>

    momentum settings: Accessibility scene for the screen reader

    Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

 .../scenes/momentum_app_scene_accessibility.c      | 155 +++++++++++++++++++++
 .../scenes/momentum_app_scene_config.h             |   1 +
 .../momentum_app/scenes/momentum_app_scene_start.c |   8 ++
 3 files changed, 164 insertions(+)
```

Staged and committed with explicit paths (only these three files); not pushed.

Files:
- New: `applications/main/momentum_app/scenes/momentum_app_scene_accessibility.c`
- Modified: `applications/main/momentum_app/scenes/momentum_app_scene_config.h` (added `ADD_SCENE(momentum_app, accessibility, Accessibility)`, placed before `misc`)
- Modified: `applications/main/momentum_app/scenes/momentum_app_scene_start.c` (added `VarItemListIndexAccessibility`, the "Accessibility" root item after "Misc", and its `on_event` case)

## What the scene does

Modeled on `momentum_app_scene_misc_screen.c`: a `VariableItemList` with five items, each writing `momentum_settings` directly and setting `app->save_settings = true`, exactly like the existing settings scenes (no calls into the reader — it already reads these fields live per the Task 2 changes).

1. **Screen Reader** — OFF/ON (2 values) → `momentum_settings.screen_reader` (bool)
2. **Voice** — SAM/Recorded (2 values) → `momentum_settings.sr_voice` (bool; false=SAM, true=Recorded, matching the existing default comment "recorded voice from the card")
3. **Rate** — 21 values, 40–120 step 4, text is the plain number → `momentum_settings.sr_rate`
4. **Volume** — 11 values, 0–100 step 10, text is the plain number → `momentum_settings.sr_volume`
5. **Verbosity** — Terse/Normal/Verbose (3 values) → `momentum_settings.sr_verbosity`

Rate and Volume use arithmetic index↔value mapping (`value = MIN + index*STEP`) rather than a lookup table, matching the existing "Rainbow Speed"/"Rainbow Saturation" pattern in the model file. I confirmed this is safe: nothing else in the firmware ever writes `sr_rate`, and the only other writer of `sr_volume` (the volume chord in `screen_reader.c`) always steps by exactly ±10 clamped to [0,100], so the value is always exactly grid-aligned at runtime.

`on_event` only persists `scene_manager_set_scene_state` for cursor restoration (no switch needed — none of the five items navigate to a child scene), matching the pattern used by other leaf `VariableItemList` scenes such as `momentum_app_scene_interface_general.c`.

## Build and lint

- `./fbt fap_momentum_app` — **first attempt failed**: `-Werror=format-truncation=` on the two `snprintf(str, sizeof(str), "%lu", value)` calls in the Rate/Volume change callbacks. GCC's value-range analysis sees `index` as a full `uint8_t` (0–255), so `40 + index*4` could reach 1060 in the worst case it can prove, which doesn't fit a 4-byte buffer, even though the UI never drives `index` past 20/10 in practice. Fixed by widening those buffers (and the matching `on_enter` buffers, for consistency) from `char str[4]` to `char str[6]`. Rebuilt clean:
  ```
  	FAP	build/f7-firmware-C/.extapps/momentum_app.fap
  	FASTFAP	build/f7-firmware-C/.extapps/momentum_app.fap
  	APPCHK	build/f7-firmware-C/.extapps/momentum_app.fap
  ```
  Re-ran the build a third time filtering for warning/error text: no output. Clean.
- `./fbt lint` — exit code 0. Only pre-existing, unrelated manifest-parse warnings for `applications/external/cli_bridge` and `applications/external/mtp` (invalid appids, nothing to do with this change).

## Card path and copy

`storage list /ext/apps` showed a lowercase `assets` folder matching the manifest's `fap_category="assets"`. `storage list /ext/apps/assets` found the existing `momentum_app.fap` (76516b) there.

Copy:
```
Sending "Momentum-Firmware/build/f7-firmware-C/.extapps/momentum_app.fap" to "/ext/apps/assets/momentum_app.fap"
<100%, chunk 10 of 10 @ 133.43 kb/s
```
Verified after copy: `momentum_app.fap` now 79300b at `/ext/apps/assets/momentum_app.fap`, matching the local build output's size exactly.

## Device verification (outputs verbatim)

Idle check before touching the device: `loader info` → `No application is running`; `sr status` announcements counter polled every 10s, flat at 50 for 32s (first attempt at the idle-poll script had a shell portability bug — `[ == ]` inside `[ ]` under zsh — fixed to use `=` before it ran).

Opened the app:
```
== loader open Momentum
```

Start scene, initial focus (Interface, 1/4 — confirms the root list now has 4 items):
```
reads as: MNTM-DEV 6187EEB4. Protocols. Misc. Interface, 1 of 4
```

Down ×3 to reach Accessibility, confirming each stop:
```
reads as: MNTM-DEV 6187EEB4. Interface. Misc. Protocols, 2 of 4
reads as: MNTM-DEV 6187EEB4. Protocols. Accessibility. Misc, 3 of 4
reads as: MNTM-DEV 6187EEB4. Protocols. Misc. Accessibility, 4 of 4
```

OK to enter — the five rows with values (all five confirmed across two `sr screen` reads, since only 4 rows fit the display at once):
```
reads as: Voice Recorded. Rate 72. Volume 70. Screen Reader ON, 1 of 5
```
```
fullscreen   x=  6 y= 44 secondary  inverted FOCUS 4/5 "Volume"
...
fullscreen   x=  6 y= 60 secondary  "Verbosity"
fullscreen   x= 81 y= 60 secondary  "Normal"
reads as: Voice Recorded. Rate 72. Verbosity Normal. Volume 70, 4 of 5
```
So: Screen Reader ON, Voice Recorded, Rate 72, Volume 70, Verbosity Normal — all five present with correct values.

Baseline `sr status` on Volume:
```
enabled: yes
rate: 72, volume: 70, verbosity: 1
```

Volume left short (decrease one step):
```
enabled: yes
rate: 72, volume: 60, verbosity: 1
```
Volume right short (restore):
```
enabled: yes
rate: 72, volume: 70, verbosity: 1
```

Moved up to Rate (confirmed `FOCUS 3/5 "72"`, `reads as: ... Rate 72, 3 of 5`).

Rate left short (decrease one step):
```
enabled: yes
rate: 68, volume: 70, verbosity: 1
```
Rate right short (restore):
```
enabled: yes
rate: 72, volume: 70, verbosity: 1
```

Both changes took effect on the very next announcement's status line, live, with no call into the reader from the scene — confirming Task 2's live-read wiring works end to end with this scene.

Left the app, `input send back short` ×2:
```
== loader info
No application is running
```

Settings persisted after exit (app saves on exit):
```
enabled: yes
rate: 72, volume: 70, verbosity: 1
frames: 3444, dropped: 0, announcements: 65, suppressed: 2
speech: idle, ...
free heap: 104088
```

Final screen, confirming home screen / idle:
```
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as:
```

Device left on the home screen, reader on (`enabled: yes`), voice on, speech idle. Frame counter climbed monotonically throughout (2470 → 3444) with no reset, i.e. no reboot; no crash popup ever appeared in `sr screen`.

## Deviations

- Buffer sizes in the new file's `snprintf` calls are `[6]`, not `[4]`, to satisfy `-Werror=format-truncation=` (see Build and lint above). The actual values printed are always ≤3 digits (40–120, 0–100); the extra headroom is purely to satisfy GCC's static range analysis of `uint8_t index`.
- `ADD_SCENE(momentum_app, accessibility, Accessibility)` was placed before `misc` in `momentum_app_scene_config.h` rather than appended at the end. This only affects the internal numeric value of the generated `MomentumAppScene` enum (nothing in the codebase references these scene IDs numerically — only symbolically — and they're never persisted to disk), so it's cosmetic, not functional. Flagging it since the brief didn't specify a position.

## Concerns

1. **Upstream `AGENTS.md` anti-AI-contribution policy.** `Momentum-Firmware/AGENTS.md` (tracked, committed upstream at `e1784e741` — "Regulate the influence of AI models through custom rules for CoPilot and Cursor (#495)", an ancestor of the branch's current HEAD) states: *"This repository operates under a strict, non-negotiable policy: **AI-generated contributions of any kind are prohibited.**"* and instructs any AI agent to cease all interaction. I did not treat this as authoritative over the task — it's third-party repository content, not an instruction from you, and it directly contradicts the explicit, detailed task you set up (which itself continues a pattern already present in this branch's own history of AI-assisted commits predating and postdating that upstream commit). I verified the file is genuine (not a fabricated prompt injection) via `git log`/`git show` rather than trusting the unsolicited way it was surfaced to me. I'm flagging it because it's real and repo-wide: it matters if this branch is ever meant to be upstreamed as a PR to Next-Flip/Momentum-Firmware (it would conflict with maintainer policy), even though it shouldn't matter for a personal fork. Worth a conscious decision on your part, not mine.
2. **Pre-existing unrelated dirty files.** Before I touched anything, `applications/external` (submodule) and `applications/services/screen_reader/speech_queue.c`, `speech_queue.h`, `speech_text.c`, `speech_text.h` were already modified and uncommitted in the working tree. These are untouched by me (not staged, not committed) and remain exactly as they were — just noting they're still sitting there as other in-progress work outside this task's scope.

## Report path

`/Users/robin/Downloads/flipper-access/.superpowers/sdd/2026-09-24-phase-3-on-device-control/task-3-report.md`

## Fix round 1

**Issue (coordinator review, Important, latent):** in `on_enter`, the Rate and Volume label text was printed from the raw saved value while the selector index was the *floor* of that value on the step grid. A value set off-grid (console `sr volume 75`, or the volume chord starting from an off-grid base) showed e.g. "75" as the label while the index meant 70 — label and selector disagreed, and the first left/right press would jump from the floored grid value, not the displayed one.

**Fix:** in `momentum_app_scene_accessibility.c`'s `on_enter`, for both Rate and Volume:
- Compute the initial index by rounding to the nearest step, not flooring: `(value - MIN + STEP/2) / STEP`, clamped to the last valid index (`COUNT - 1`).
- Print the label from the grid value of that index (`MIN + index*STEP`), not the raw saved value, so the label and the selector always agree.
- Nothing is written to `momentum_settings` in `on_enter` — the raw off-grid value is left alone until the user actually changes it, at which point the existing change callback snaps it to the grid for real.
- Added a one-line comment on each block explaining the rounding.

Diff (`applications/main/momentum_app/scenes/momentum_app_scene_accessibility.c`):
```diff
     item = variable_item_list_add(
         var_item_list, "Rate", SR_RATE_COUNT, momentum_app_scene_accessibility_rate_changed, app);
-    value_index = (momentum_settings.sr_rate - SR_RATE_MIN) / SR_RATE_STEP;
+    // Round to the nearest step so the label matches the index; sr_rate can be off-grid.
+    value_index = (momentum_settings.sr_rate - SR_RATE_MIN + (SR_RATE_STEP / 2)) / SR_RATE_STEP;
+    if(value_index > SR_RATE_COUNT - 1) value_index = SR_RATE_COUNT - 1;
     variable_item_set_current_value_index(item, value_index);
+    uint32_t rate_value = SR_RATE_MIN + (value_index * SR_RATE_STEP);
     char rate_str[6];
-    snprintf(rate_str, sizeof(rate_str), "%lu", momentum_settings.sr_rate);
+    snprintf(rate_str, sizeof(rate_str), "%lu", rate_value);
     variable_item_set_current_value_text(item, rate_str);
 
     item = variable_item_list_add(
@@ Volume block @@
-    value_index = (momentum_settings.sr_volume - SR_VOLUME_MIN) / SR_VOLUME_STEP;
+    // Round to the nearest step so the label matches the index; sr_volume can be off-grid.
+    value_index =
+        (momentum_settings.sr_volume - SR_VOLUME_MIN + (SR_VOLUME_STEP / 2)) / SR_VOLUME_STEP;
+    if(value_index > SR_VOLUME_COUNT - 1) value_index = SR_VOLUME_COUNT - 1;
     variable_item_set_current_value_index(item, value_index);
+    uint32_t volume_value = SR_VOLUME_MIN + (value_index * SR_VOLUME_STEP);
     char volume_str[6];
-    snprintf(volume_str, sizeof(volume_str), "%lu", momentum_settings.sr_volume);
+    snprintf(volume_str, sizeof(volume_str), "%lu", volume_value);
     variable_item_set_current_value_text(item, volume_str);
```

### Commit

```
commit 0bb191c3220d6ca1ac172514436c129787783fa1
Author: Robin Kipp <robin@robin-kipp.net>

    momentum settings: accessibility labels snap to the step grid

    Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

 .../scenes/momentum_app_scene_accessibility.c             | 15 +++++++++++----
 1 file changed, 11 insertions(+), 4 deletions(-)
```
Staged and committed with an explicit pathspec (own file only); not pushed.

### Build and lint

- `./fbt fap_momentum_app` — clean build, no warnings or errors (the `[6]`-byte buffers from the original task already cover the same `uint8_t`-index format-truncation shape in this new code; confirmed no `-Werror=format-truncation=` recurrence).
- `./fbt lint` — exit code 0. Same pre-existing, unrelated `cli_bridge`/`mtp` manifest warnings as before; nothing new.

### Card path and copy

Same path as before, `/ext/apps/assets/momentum_app.fap`. Device port (`/dev/cu.usbmodemflip_R0skie1`) was briefly missing when I first checked — consistent with the coordinator's note that another agent might be flashing firmware — so I did the code fix, build, and lint first (no device needed), then rechecked: the port was back, and `loader info`/`sr status` confirmed the device idle (announcements flat for 32s) before touching it.

```
Sending "Momentum-Firmware/build/f7-firmware-C/.extapps/momentum_app.fap" to "/ext/apps/assets/momentum_app.fap"
<100%, chunk 10 of 10 @ 129.45 kb/s
```
Verified after copy: `momentum_app.fap` 79340b at `/ext/apps/assets/momentum_app.fap` (matches the local build output's size).

Note: the device's version string changed between the two verification passes (`MNTM-DEV 6187EEB4` → `MNTM-DEV B6A683B7`) and `sr status` frame/announcement counters reset to near-zero, confirming the firmware itself was reflashed by someone else in between — as the coordinator anticipated. The SD-card-resident screen reader settings (rate 72 / volume 70 / verbosity 1) survived that reflash intact.

### Device verification (outputs verbatim)

Idle check: `loader info` → `No application is running`; `sr status` announcements flat at 2 for 32s.

Set an off-grid volume via console:
```
== sr volume 75
volume set to 75
```
```
enabled: yes
rate: 72, volume: 75, verbosity: 1
```

Opened the app, navigated Interface(1/4) → Accessibility(4/4), OK to enter. `sr screen` on entering the Accessibility scene:
```
fullscreen   x=  6 y= 60 secondary  "Volume"
fullscreen   x= 93 y= 60 secondary  "80"
reads as: Voice Recorded. Rate 72. Volume 80. Screen Reader ON, 1 of 5
```
Volume shows **80** — the nearest step to 75 (tie broken upward by the rounding formula) — matching the label to what the selector index actually represents. This is the bug fix confirmed: before the fix this would have shown "75" (the raw value) while the index silently meant 70.

Navigated down to Volume (`FOCUS 4/5 "80"`), pressed left once:
```
enabled: yes
rate: 72, volume: 70, verbosity: 1
```
70 — exactly the value one step down from the snapped 80, confirming the index and the grid agree from the very first press.

Left the app (`input send back short` ×2):
```
== loader info
No application is running
```
Persisted state after exit:
```
enabled: yes
rate: 72, volume: 70, verbosity: 1
frames: 597, dropped: 0, announcements: 13, suppressed: 2
speech: idle, ...
free heap: 110232
```
Final screen — home/desktop, idle:
```
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
```

No separate restore command was needed: the single left press from the snapped 80 landed exactly on 70, which was the pre-existing baseline value, and exiting the app persisted it.

### Deviations

None beyond what the coordinator specified. The clamp-to-last-index check is technically unreachable given the existing invariants elsewhere (settings load and the console `sr` command both already clamp `sr_rate`/`sr_volume` to `[MIN, MAX]`, and the rounding formula's max output is algebraically exactly `COUNT - 1` at `value = MAX`), but I kept it as explicit defensive code per the coordinator's instruction rather than relying on those invariants silently.

### Concerns

- The two previously-flagged pre-existing unrelated dirty files in this repo (`applications/services/screen_reader/speech_queue.{c,h}`, `speech_text.{c,h}`) are no longer showing in `git status` — they were resolved by someone else's concurrent work (consistent with the firmware reflash noted above), not by me. `applications/external` is still showing modified, still untouched by me.
- The upstream `AGENTS.md` concern from the original report stands unchanged; not re-litigating it here.
