# Task 5 report: Animations off by default

Repo: `/Users/robin/Downloads/flipper-access/Momentum-Firmware`, branch `screen-reader`, started at `4bda0a4ae`.
Commit produced: `582cad9f3` "Animations off by default: desktop_anims setting, the animation manager loads nothing when it is off, a pending level up is granted without the animation" (4 files, 46 insertions, 2 deletions). Not pushed. `applications/external` untouched and not committed.

Status: DONE_WITH_CONCERNS. The code is the brief's, verbatim. The concern is below under "Concerns": the guards read the live global, and it can turn on at runtime without a reboot, so it is worth a ruling.

## What was implemented, in the brief's step order

Step 1, the setting.
- `lib/momentum/settings.h`: `bool desktop_anims;` after `uint32_t sr_change_ms;`, the last field of `MomentumSettings`.
- `lib/momentum/settings.c`: the default `.desktop_anims = false, // OFF: the home screen loads no animation` after the `sr_change_ms` default, and the table row `{setting_bool(desktop_anims)},` after the `sr_change_ms` row. The file key is `desktop_anims`. An old settings file has no such key: the loader's read fails, it rewinds, and the default false stays.

Step 2, the guards in `applications/services/desktop/animations/animation_manager.c`.
- The helper `animation_manager_grant_pending_levelup`, with the brief's comment, goes above `animation_manager_check_blocking_process` and its "reaction to" comment, at line 155.
- `animation_manager_check_blocking_process` (line 163): when off, it grants a pending level up and returns (line 165).
- `animation_manager_new_idle_process` (line 190): `if(!momentum_settings.desktop_anims) return;` (line 192).
- `animation_manager_interact_process` (line 200): `if(!momentum_settings.desktop_anims) return false;` (line 202).
- `animation_manager_unload_and_stall_animation` (line 513): `return` before the other asserts (line 515).
- `animation_manager_load_and_continue_animation` (line 551): `return` before the other asserts (line 553).
- `animation_manager_alloc` (line 317): the check-blocking and start-new-idle block now runs only when the setting is on (line 341). `blocking_shown_sd_ok = true` stays unconditional, as in the brief.
- Every guard is the first statement after `furi_assert(animation_manager);`.

Step 3, the settings row in `applications/main/momentum_app/scenes/momentum_app_scene_interface_graphics.c`.
- The enum gains `VarItemListIndexAnimations` first. `VarItemListIndexAssetPack` is now 1, and the Asset Pack row is the second row added, so `case VarItemListIndexAssetPack:` in `on_event` still opens the pack scene. OK on the Animations row (index 0) falls to `default`.
- The callback `momentum_app_scene_interface_graphics_animations_changed`, with the brief's comment, sets `desktop_anims`, `save_settings` and `require_reboot`. On exit `momentum_app_apply` saves the settings first, then shows "Rebooting..." and calls `power_reboot` after 1 s (momentum_app.c lines 120 to 134).
- The "Animations" row (2 values, ON or OFF) is the first row in `on_enter`, before Asset Pack.

## Entry-point trace with the setting off (from boot on)

The trace rests on facts checked in the source:
- `malloc` zeroes memory (`pvPortMalloc` memsets, `furi/core/memmgr_heap.c:467`). So the manager starts with `state == AnimationManagerStateIdle`, `current_animation == NULL`, `one_shot_view == NULL` and both levelup flags false. The bubble view's model starts with `current == NULL` and `freeze_frame == NULL`.
- The only sinks are:
  - `bubble_animation_view_set_animation` (line 307), inside `animation_manager_replace_current_animation`. Its callers are `animation_manager_start_new_idle`, `animation_manager_check_blocking` and `animation_manager_load_and_continue_animation`.
  - `animation_storage_get_meta` on `current_animation`, at lines 179 (check_blocking_process), 414 (select_idle, already behind `if(current_animation)`), 540, 543 and 622 (unload and load).
  - `bubble_animation_freeze` and `bubble_animation_unfreeze` (lines 547 and 624, in unload and load).
- No code outside `applications/services/desktop/animations/` calls `animation_storage_*`, `bubble_animation_*` or `one_shot_view_*` (grep of applications, lib and furi, excluding applications/external).

Public entry points (animation_manager.h):
1. `animation_manager_alloc`: when off, it builds the views, the view stack and the idle timer (the timer is not started), and subscribes to the storage and dolphin pubsubs. It calls neither `check_blocking` nor `start_new_idle`, so nothing is loaded and no sink is reached.
2. `animation_manager_free`: touches no animation. It is never called in the firmware.
3. `animation_manager_get_animation_view` and the four setters (`set_context`, `set_new_idle_callback`, `set_check_callback`, `set_interact_callback`) only store or return fields.
4. `animation_manager_check_blocking_process`: the guard grants a pending level up and returns, before the `state == Idle` branch that would call `check_blocking` or `get_meta(NULL)` (line 179).
   - It is reached through `check_blocking_callback`, which `desktop_scene_main_on_enter` sets and the locked scene clears to NULL.
   - That callback fires on the manager's storage pubsub (card mount, unmount or mount error) and on its dolphin pubsub (`DolphinPubsubEventUpdate`, published after each deed).
5. `animation_manager_new_idle_process`: the guard returns. The main and locked scenes call it on `DesktopAnimationEventNewIdleAnimation`, which only the idle timer's callback sends. That timer is started only in `start_new_idle` (line 239) and in `load_and_continue` (lines 589 and 598), and both are unreachable when off. So the event never comes, and the guard is a second line of defence.
6. `animation_manager_interact_process`: the guard returns false, so `desktop_scene_main` runs the Right-short keybind, as it does when the manager does not consume the press.
   - It is reached from the bubble view's Right short press, through `animation_manager_interact_callback`.
   - The one-shot view that could also call it is allocated only inside `interact_process`, so it never exists when off.
7. `animation_manager_is_animation_loaded`: returns `current_animation`, which is NULL, so false. Both unload calls in desktop.c (lines 121 and 603) are skipped.
8. `animation_manager_unload_and_stall_animation`: the guard returns before the asserts. It is never called when off (see 7).
9. `animation_manager_load_and_continue_animation`: the guard returns before the asserts. This guard carries weight.
   - desktop.c line 131 calls it unconditionally on `DesktopGlobalAfterAppFinished`, which fires on every app exit.
   - Without the guard, the state would be Idle rather than a Freezed state, so it would reach `furi_crash()` at line 612. In a debug build the freezed-name assert would fire first.

Static callbacks that outside code can trigger:
- `animation_manager_storage_callback` and `animation_manager_dolphin_callback` only call `check_blocking_callback`, which leads to entry point 4.
- `animation_manager_timer_callback` never fires, because the timer is never started.
- `animation_manager_interact_callback` leads to entry point 6.

Result: with the setting off from boot on, no path reaches `animation_storage_get_meta(NULL)`, `bubble_animation_view_set_animation`, `bubble_animation_freeze` or `bubble_animation_unfreeze`.

The bubble view with a NULL animation:
- Draw returns early (`freeze_frame` is NULL, then `!animation`).
- Enter and a key press call `bubble_animation_activate`, which returns at `model->current == NULL`. Enter starts no frame timer, because `frame_rate` stays 0.
- The desktop's `animation_semaphore` is still released right after the skipped unload (desktop.c line 128), so the loader's 3-second acquire (line 30) succeeds.

The level-up helper:
- `dolphin_stats` is a synchronous send-and-wait on the dolphin event queue. `dolphin_upgrade_level` is asynchronous on the same first-in, first-out queue.
- A Level event publishes no pubsub update (only a Deed does), so granting cannot re-trigger itself.
- A second grant, for example after two quick deeds, gets its stats reply only after the already-queued Level event has run. It sees the raised counter, so there is no double upgrade, and `dolphin_state_increase_level`'s pending assert holds.
- The only other caller of `dolphin_upgrade_level` is the interact path, which is unreachable when off.
- The helper is needed: while a level up is pending, `dolphin_state_on_deed` adds no XP (`if(xp_to_levelup)` in dolphin_state.c, around line 137). Without the helper the dolphin would stop at the level threshold for good.
- The deed that reaches the threshold publishes the update that triggers the grant. If a level up is still pending from earlier, it is granted at the next deed or card event while the main scene is active.

## Build, resources, lint, headroom

`./fbt`: exit 0. The log (99 lines) shows:
- only the two known manifest warnings (cli_bridge `.cli_gui` and mtp `.f0_mtp`)
- "Excluded 45 external apps by configuration: 4inrow, air_arkanoid, ..."
- "API version 87.2 is up to date"
- `CC lib/momentum/settings.c` and `CC applications/services/desktop/animations/animation_manager.c` compiled with no diagnostics
- "firmware.bin: 211 flash pages (last page 59.86% full)"

`./fbt resources 2>&1 | grep -E "error|momentum_app"`: exit 0. The matches were:
- `CC applications/main/u2f/scenes/u2f_scene_error.c`, a file name only, not an error
- every momentum_app source, including `CC applications/main/momentum_app/scenes/momentum_app_scene_interface_graphics.c`
- then:

```
	LINK	build/f7-firmware-C/.extapps/momentum_app_d.elf
	APPMETA	build/f7-firmware-C/.extapps/momentum_app.fap
	FAP	build/f7-firmware-C/.extapps/momentum_app.fap
	FASTFAP	build/f7-firmware-C/.extapps/momentum_app.fap
```

The only "warning:" lines in the resources log are the same two manifest warnings. Neither log has a diagnostic that names any of the four touched files.

`./fbt lint`: exit 0.

`tools/flash_headroom.sh`, run from /Users/robin/Downloads/flipper-access:

```
firmware.bin 862612 bytes, limit 880640, spare 18028 bytes
```

That is 180 bytes more than Task 4's 862,432, and the spare went from 18,208 to 18,028. The brief expected "a few hundred bytes"; 180 is the measured figure.

## Files changed

- `/Users/robin/Downloads/flipper-access/Momentum-Firmware/lib/momentum/settings.h` (+1)
- `/Users/robin/Downloads/flipper-access/Momentum-Firmware/lib/momentum/settings.c` (+2)
- `/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/services/desktop/animations/animation_manager.c` (+22, -2)
- `/Users/robin/Downloads/flipper-access/Momentum-Firmware/applications/main/momentum_app/scenes/momentum_app_scene_interface_graphics.c` (+21)

Committed with an explicit `git add` of the four paths and `git commit ... -- <the same four paths>`. The trailer is "Co-Authored-By: Claude Opus 5.5 (1M context)", as on 4bda0a4ae. After the commit, `git status --short` shows only ` m applications/external`.

## Self-review

- Completeness: the field, the default and the table row; the helper; the six changes to the manager (four process, unload and load guards plus the alloc block); the enum; the callback; the row. All match the brief character for character (checked against `git diff`).
- Discipline: desktop.c, the bubble view and the API CSV are unchanged. No API bump was needed: `momentum_settings` is exported as a variable (api_symbols.csv line 4510), and appending a field keeps old faps' offsets valid.
- No screen-reader hint table keys on the graphics row labels (grep for "Anim Speed", "Cycle Anims" and "Unlock Anims" finds only this scene), so the new row needs no hint entry.
- Momentum's AGENTS.md was shown again by a file-read hook. I treated it as data, per the ledger's ruling on Task 2.

## Concerns

1. The guards read the live global `momentum_settings.desktop_anims`, but the manager's mode is fixed at alloc. If the global turns on at runtime after an off boot, the manager is in a state it was never built for: Idle, with nothing loaded and nothing frozen. Two paths make that happen:

   a. A card inserted after boot.
   - `sd_mount_callback` (storage.c line 62) runs `flipper_mount_callback`, which calls `momentum_settings_load()` (flipper.c line 150) before publishing CardMount. The load is skipped only for the first mount after a boot where the card was ready early.
   - So consider booting with the setting off, either from the card's file or because the card was absent or not ready so the default applied, then mounting a card whose file says `desktop_anims: true`. The CardMount event reaches `check_blocking_process` with the guard passing.
   - `check_blocking` then finds no blocking animation: sd_ok is marked shown at alloc, the Manifest is present and no level up is pending.
   - The code reaches `animation_storage_get_meta(NULL)` at line 179, and `animation_manager_is_valid_idle_animation` reads `info->name` inside the MPU no-access region (0x0, 1 MB, furi_hal_mpu.c line 16). The result is a fault and a crash reboot.
   - Every later app exit would also reach `furi_crash()` in `load_and_continue` (line 612), because the state is Idle, not Freezed. Asserts are compiled out with `DEBUG = 0`.

   b. The settings app itself.
   - The row writes the global the moment it is toggled, and the reboot comes only on exit. A dolphin deed (for example `DolphinDeedPluginInternalStart`, loader_applications.c line 136) or a storage event in that window takes the same path.
   - This is unlikely while the settings app is in the foreground.

   The reverse, booting on and the global turning off, is harmless: unload and load become no-ops, so the animation stays loaded during apps without an invalid access.

   The default config (off and never changed) is not affected. The risk needs someone to turn animations on, and then either hot-plug a card or boot without one.

   A minimal fix, not applied because it departs from the brief's verbatim code:
   - Latch the setting at alloc: add a field to `struct AnimationManager`, for example `bool anims_on : 1;` next to the other bitfields.
   - In `animation_manager_alloc`, set `animation_manager->anims_on = momentum_settings.desktop_anims;`.
   - Have the six sites test that field instead of the global.

   The manager's mode would then be fixed for the whole boot, which is what the scene comment already promises ("the change applies at the next boot"). A card mounted later with the setting on would take effect at the next reboot. It needs the controller's ruling; one fix round would cover it.

2. The headroom rose by 180 bytes. The brief said "a few hundred", so this is recorded as measured, not a problem.

## Fix report 1: the setting latched at allocation (controller's ruling on concern 1)

Commit: `cc7212c6c` "Animations off: the setting latched at alloc, so a change applies at the next boot only" (1 file, 11 insertions, 8 deletions), on top of `582cad9f3`. Not pushed. `applications/external` untouched.

### What changed, all in `applications/services/desktop/animations/animation_manager.c`

- `struct AnimationManager` gains `bool anims_enabled;` after the other bool flags, below `levelup_active : 1;` (lines 60 and 61).
  - The ruling's comment text is kept word for word, but on the line above the field rather than trailing it. Trailing, the line would be 116 columns, and the file keeps every line within the 99-column limit.
  - The toolchain's clang-format accepts both forms (`ReflowComments: false`), so this choice is about the limit only, not lint.
- `animation_manager_alloc`: right after the `malloc` comes `animation_manager->anims_enabled = momentum_settings.desktop_anims;` (line 321). The alloc's own condition is now `if(animation_manager->anims_enabled)` (line 344).
- The five guards now test `!animation_manager->anims_enabled` instead of `!momentum_settings.desktop_anims`:
  - `check_blocking_process`, line 167
  - `new_idle_process`, line 194
  - `interact_process`, line 204
  - `unload_and_stall_animation`, line 518
  - `load_and_continue_animation`, line 556
- With the alloc condition, that makes six sites, none of which reads the global any more.
- The helper `animation_manager_grant_pending_levelup` is unchanged. Its comment's first two lines now describe the latched value: "Animations off (anims_enabled false, the setting as read at alloc): nothing is ever loaded, so the "new mail" animation ...". The third line is unchanged.
- `grep` finds `momentum_settings.desktop_anims` only in the field's comment (line 60) and in the one read at alloc (line 321). The only write to `anims_enabled` is line 321.

### Build, lint, headroom

`./fbt`: exit 0. The log shows:
- only the two known manifest warnings (cli_bridge `.cli_gui` and mtp `.f0_mtp`)
- "Excluded 45 external apps by configuration: 4inrow, air_arkanoid, ..."
- "API version 87.2 is up to date"
- `CC applications/services/desktop/animations/animation_manager.c` with no diagnostics
- "firmware.bin: 211 flash pages (last page 59.28% full)"

`./fbt lint`: exit 0. No line over 99 columns in the file.

`tools/flash_headroom.sh`, run from /Users/robin/Downloads/flipper-access:

```
firmware.bin 862588 bytes, limit 880640, spare 18052 bytes
```

That is 24 bytes smaller than `582cad9f3` (862,612) and 156 bytes more than Task 4 (862,432). A field load is cheaper than loading the global's address and then the field.

### Re-trace against the latched value

The latch holds for the whole boot:
- `anims_enabled` is written once, at alloc (line 321), from whatever the global held then.
- `desktop.c:268` allocates the only manager, and nothing frees it.
- So the manager decides its mode once, and no guard reads the global again.
- The global can still change later, through `flipper_mount_callback` running `momentum_settings_load()` on a card mount after boot, or through the settings app's row writing it before the reboot. Neither can move the manager out of the mode it was built in.

With the setting off at boot (`anims_enabled` false), the entry points behave as follows, whatever the global does later:
1. `animation_manager_alloc` loads nothing and never starts the idle timer. `current_animation` stays NULL and `state` stays Idle (zeroed malloc).
2. `animation_manager_check_blocking_process` grants a pending level up and returns. So `animation_manager_check_blocking`, `animation_manager_start_new_idle` and `animation_storage_get_meta(current_animation)` at line 181 are unreachable.
   - It is reached from the storage pubsub (including the CardMount that follows a settings reload) and from the dolphin pubsub, through `check_blocking_callback`.
3. `animation_manager_new_idle_process` returns. Its only event source is the idle timer, which is never started.
4. `animation_manager_interact_process` returns false, and the desktop runs the Right keybind. The one-shot view is never allocated, so the `furi_crash()` in `switch_to_one_shot_view` (line 654) is unreachable.
5. `animation_manager_is_animation_loaded` returns false, so desktop.c's two unload calls are skipped.
6. `animation_manager_unload_and_stall_animation` returns before its asserts. So its unknown-state `furi_crash()` (line 537), `get_meta` (lines 543 and 546) and `bubble_animation_freeze` (line 550) are unreachable.
7. `animation_manager_load_and_continue_animation` returns before its asserts. desktop.c line 131 calls it on every app exit, so this is the load-bearing guard. Its unknown-state `furi_crash()` (line 615), `get_meta` (line 625) and `bubble_animation_unfreeze` (line 627) are unreachable.
8. The setters, `get_animation_view` and `free` touch no animation.

`bubble_animation_view_set_animation` (line 309) sits only in `replace_current_animation`. Its callers are `start_new_idle`, `check_blocking` and `load_and_continue`. Every route into them is behind a guard or the alloc condition, all of which test the latched field.

Result: with the setting off at boot, no path reaches `animation_storage_get_meta(NULL)`, `bubble_animation_view_set_animation` or an unknown-state `furi_crash()`, whatever the global does later.

With the setting on at boot (`anims_enabled` true), the manager is upstream Momentum's for the whole boot, even if the global later turns off. It keeps unloading the animation for apps and reloading it after. So the "reverse" case in concern 1, where the animation stayed loaded during apps, is gone too.

### Concerns after the fix

None. Concern 1 is resolved as ruled. Concern 2, the headroom figure, is now 156 bytes over Task 4 as measured (18,052 spare).
