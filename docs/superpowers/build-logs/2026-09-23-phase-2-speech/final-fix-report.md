# Final fix report: phase 2 speech, fix round after Task 6

Report for the ruling recorded after Task 6: Sub-GHz built into the firmware, home screen bubbles
not spoken without a key press, the two Task 4b follow-ups in the NFC-V listener, docs as built.
Phase A (build, tests, commits) is below; phase B (flash and device checks) is appended when the
controller says "flash". The device was not touched in phase A, not even `sr status`.

## Phase A

Status: DONE. Four commits, three in the firmware and one in the project; two firmware builds
(items 1 and 2 first, then Sub-GHz on top, so the Sub-GHz cost is measured on its own), both
exit 0 with only the two pre-existing manifest warnings; host tests green. One deviation from the
brief's letter for item 3, explained below: the internal build cannot use the manifest's `!`
excludes (nor the pre-a59ef9f05 manifest verbatim), so the fap's file set is listed explicitly.

### Commits

Firmware, branch screen-reader, on top of dc8ecf63e (Task 6). Each committed after an index.lock
check (none) with an explicit `git add` of the path and `git commit -F msg -- <paths>`; `git
status` afterwards shows only the pre-existing ` m applications/external`, untouched. Not pushed.

- 4b4144831 "screen reader: NFC-V listener reads the timer after the acquire and parks the
  speaker pin". lib/signal_reader/signal_reader.c, 9 insertions, 2 deletions.
- 013e5c816 "screen reader: home screen bubbles are not spoken without a key press".
  applications/services/screen_reader/screen_reader.c (28 lines changed), screen_reader.h (3),
  screen_reader_cli.c (5).
- 1c113c28a "screen reader branch: Sub-GHz built into the firmware for memory headroom".
  applications/main/subghz/application.fam only; api_symbols.csv untouched.

Project, main, on top of 4a37104:

- f509d77 "docs: Sub-GHz built in, home screen bubbles". README.md and
  docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md, added by path (the
  untracked .DS_Store files and tools/__pycache__ stay untracked).

```
f509d77 docs: Sub-GHz built in, home screen bubbles

 README.md                                          | 18 ++++++---
 .../2026-09-22-flipper-screen-reader-design.md     | 44 +++++++++++++++-------
 2 files changed, 43 insertions(+), 19 deletions(-)
```

All four messages have a body, a blank line and the Co-Authored-By line.

### Runner summary lines

`TMPDIR=<scratchpad>/tf tools/run_host_tests.sh`, exit 0, run after all edits:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 94 checks, 0 failures
speech PCM: 647 checks, 0 failures
```

The runner covers screen_model.c and the speech helpers; the bubble rule lives in the service
(screen_reader.c), which has no host build, because the model must keep emitting the change so
that the console mirror still shows it. It is checked on the device in phase B (three minute
soak: announcements flat, suppressed may rise).

### Builds and sizes

`./fbt` in Momentum-Firmware, `pgrep -fl fbt` empty before each run, both exit 0, about 20 s
each. The only warnings in both logs are the two pre-existing manifest ones from the external
submodule (cli_bridge `.cli_gui`, mtp `.f0_mtp`); no linker warning, no undefined or multiple
definition, no APPCHK failure.

Build A, items 1 and 2 on top of Task 6 (the "before" for Sub-GHz):

```
API version 87.1 is up to date
.text         674792 (658.98 K)
.rodata       192208 (187.70 K)
.data           1324 (  1.29 K)
.bss            8524 (  8.32 K)
.free_flash   179916 (175.70 K)
```

Against the Task 6 image (.text 674720, .rodata 192192, .free_flash 180004): .text plus 72,
.rodata plus 16, .free_flash minus 88; .data and .bss unchanged.

Build B, Sub-GHz built in (the image for phase B, apart from the version stamp, see notes):

```
API version 87.1 is up to date
.text         711260 (694.59 K)
.rodata       197768 (193.13 K)
.data           1328 (  1.30 K)
.bss            8556 (  8.36 K)
.free_flash   137880 (134.65 K)
```

Sub-GHz costs 42,036 bytes of flash (.free_flash 179,916 to 137,880): 134.65 KB stay free,
well above the 60 KB phase 3 needs. RAM sections: .data plus 4, .bss plus 32 bytes (static state
of the app's globals; nothing else moves into RAM at run time, which is the point).

The generated build/f7-firmware-C/applications/applications.c now lists `subghz_app` in
FLIPPER_APPS and FLIPPER_EXTERNAL_APPS has no Sub-GHz entry (before: `.path =
"/ext/apps/Sub-GHz/subghz.fap"`). The build no longer produces subghz.fap: nothing in the build
B log mentions subghz.fap or subghz_d.elf, and build/f7-firmware-C/.extapps/subghz.fap is the
stale file of Sep 22 19:27 from the last external build. So in phase B the card's copy,
/ext/apps/Sub-GHz/subghz.fap, must be removed: the main menu itself takes Sub-GHz from
FLIPPER_APPS (or, with a custom /int/.mainmenu_apps.txt, by name, which now resolves to the
internal app), but the Applications browser would still show and launch the RAM loaded fap.

### Change 1: NFC-V listener reads the timer after the acquire and parks the speaker pin

```
diff --git a/lib/signal_reader/signal_reader.c b/lib/signal_reader/signal_reader.c
index e6187cc34..a8a6f8f8a 100644
--- a/lib/signal_reader/signal_reader.c
+++ b/lib/signal_reader/signal_reader.c
@@ -193,8 +193,6 @@ void signal_reader_start(SignalReader* instance, SignalReaderCallback callback,
 
     // EXTI delay compensation
     instance->tim_cnt_compensation = 9;
-    instance->cnt_en = SIGNAL_READER_CAPTURE_TIM->CR1;
-    instance->cnt_en |= TIM_CR1_CEN;
 
     // TIM16 is shared with the speaker, and the speaker mutex is its single owner token:
     // acquiring it enables the timer and parks the speaker pin on the timer's alternate
@@ -203,6 +201,15 @@ void signal_reader_start(SignalReader* instance, SignalReaderCallback callback,
     // the bus directly would furi_check against a speaker user that already enabled it.
     furi_check(furi_hal_speaker_acquire(FuriWaitForever));
 
+    // Read CR1 only now that the timer is ours: the bus enable in the acquire has just released
+    // the peripheral reset, so this is the reset value and not a live register of another user
+    instance->cnt_en = SIGNAL_READER_CAPTURE_TIM->CR1;
+    instance->cnt_en |= TIM_CR1_CEN;
+
+    // The acquire put the speaker pin on the timer; the listener drives no output, so keep the
+    // pin quiet for the whole emulation (the release re-initialises the pin itself)
+    furi_hal_gpio_init(&gpio_speaker, GpioModeAnalog, GpioPullDown, GpioSpeedLow);
+
     // Capture timer config
     LL_TIM_SetPrescaler(SIGNAL_READER_CAPTURE_TIM, 0);
     LL_TIM_SetCounterMode(SIGNAL_READER_CAPTURE_TIM, LL_TIM_COUNTERMODE_UP);
```

Checked: furi_hal_speaker_acquire (targets/f7/furi_hal/furi_hal_speaker.c) enables the TIM16
bus (Momentum's furi_hal_bus_enable releases the peripheral reset, so CR1 reads 0) and puts
gpio_speaker on AF14; furi_hal_speaker_release stops the timer, re-initialises the pin as analog
with a pull down itself, then disables the bus. gpio_speaker comes from furi_hal_resources.h,
which furi_hal.h includes. The DMA trigger channel still writes cnt_en (now 0 | CEN) into CR1
on the first edge, as before. clang-format (toolchain, --dry-run --Werror) is clean.

### Change 2: home screen bubbles are not spoken without a key press

```
diff --git a/applications/services/screen_reader/screen_reader.c b/applications/services/screen_reader/screen_reader.c
index 71793764e..3eba02fae 100644
--- a/applications/services/screen_reader/screen_reader.c
+++ b/applications/services/screen_reader/screen_reader.c
@@ -14,6 +14,7 @@
 #define SR_SETTLE_MS      50
 #define SR_MAX_LATENCY_MS 300
 #define SR_KEY_RECENT_MS  500
+#define SR_DESKTOP_KEY_MS 2000
 
 struct ScreenReader {
     FuriThreadId thread_id;
@@ -111,21 +112,32 @@ static void sr_process(ScreenReader* sr) {
         memcpy(&sr->working, &sr->ready, sizeof(SrFrame));
         sr->ready_valid = false;
         uint32_t now = furi_get_tick();
-        bool key_recent = (now - sr->last_press_tick) < SR_KEY_RECENT_MS;
+        uint32_t since_press = now - sr->last_press_tick;
+        bool key_recent = since_press < SR_KEY_RECENT_MS;
+        // The home screen keeps redrawing its dolphin speech bubbles, and they arrive as
+        // changes on the same screen. Without a key press in the last two seconds nobody asked
+        // for them, so they are not spoken; they still reach the console mirror, and "Home
+        // screen" on arrival is a different kind and stays
+        bool quiet_desktop = sr->working.content_layer == SrLayerDesktop &&
+                             since_press >= SR_DESKTOP_KEY_MS;
         sr->model.verbosity = momentum_settings.sr_verbosity;
         size_t n = sr_model_process(
             &sr->model, &sr->working, now, key_recent, sr->announcements, SR_MAX_ANNOUNCEMENTS);
         sr->stats.frames++;
-        sr->stats.announcements += n;
         for(size_t i = 0; i < n; i++) {
-            if(momentum_settings.screen_reader) {
-                // Screen and focus announcements interrupt what is being said; a change on
-                // the same screen waits its turn and replaces a change still waiting
-                const SrAnnouncement* a = &sr->announcements[i];
-                speech_say(sr->speech, a->text, a->interrupt, a->kind == SrAnnChange);
+            const SrAnnouncement* a = &sr->announcements[i];
+            if(quiet_desktop && a->kind == SrAnnChange) {
+                sr->stats.suppressed++;
+            } else {
+                sr->stats.announcements++;
+                if(momentum_settings.screen_reader) {
+                    // Screen and focus announcements interrupt what is being said; a change
+                    // on the same screen waits its turn and replaces a change still waiting
+                    speech_say(sr->speech, a->text, a->interrupt, a->kind == SrAnnChange);
+                }
             }
             if(sr->watch_queue) {
-                furi_message_queue_put(sr->watch_queue, &sr->announcements[i], 0);
+                furi_message_queue_put(sr->watch_queue, a, 0);
             }
         }
     }
diff --git a/applications/services/screen_reader/screen_reader.h b/applications/services/screen_reader/screen_reader.h
index 4b2e7ba48..293a61c94 100644
--- a/applications/services/screen_reader/screen_reader.h
+++ b/applications/services/screen_reader/screen_reader.h
@@ -19,7 +19,8 @@ typedef struct ScreenReader ScreenReader;
 typedef struct {
     uint32_t frames; /**< frames processed */
     uint32_t dropped_frames; /**< frames the GUI could not hand over in time */
-    uint32_t announcements;
+    uint32_t announcements; /**< announcements handed to speech */
+    uint32_t suppressed; /**< home screen changes not spoken: no key press within 2 s */
 } ScreenReaderStats;
 
 /** Copy the last captured frame (raw records). */
diff --git a/applications/services/screen_reader/screen_reader_cli.c b/applications/services/screen_reader/screen_reader_cli.c
index 26b8f615b..811b8464d 100644
--- a/applications/services/screen_reader/screen_reader_cli.c
+++ b/applications/services/screen_reader/screen_reader_cli.c
@@ -129,10 +129,11 @@ static void sr_cli_status(ScreenReader* sr) {
         (unsigned long)momentum_settings.sr_volume,
         (unsigned long)momentum_settings.sr_verbosity);
     printf(
-        "frames: %lu, dropped: %lu, announcements: %lu\r\n",
+        "frames: %lu, dropped: %lu, announcements: %lu, suppressed: %lu\r\n",
         (unsigned long)stats.frames,
         (unsigned long)stats.dropped_frames,
-        (unsigned long)stats.announcements);
+        (unsigned long)stats.announcements,
+        (unsigned long)stats.suppressed);
     SpeechStats speech;
     speech_get_stats(screen_reader_get_speech(sr), &speech);
     printf(
```

Where the drop happens: after sr_model_process, per announcement, in the same loop that hands
announcements to speech and to the console queue. The model still emits the change, so `sr
watch` prints it exactly as in phase 1; only the speech_say is skipped. The drop did not have to
move before the console mirror. Counting: a suppressed announcement is counted in the new
`suppressed` field and not in `announcements`, which now means "handed to speech"; so in the
phase B soak `announcements` must stay flat while `suppressed` may rise. `sr status` prints
`frames: N, dropped: N, announcements: N, suppressed: N`. The desktop test uses the processed
frame's content layer (sr->working.content_layer, what the model saw); the window is 2000 ms
(SR_DESKTOP_KEY_MS) from last_press_tick, which the input callback of Task 6 already records on
every press. "Home screen" on arrival is SrAnnHome and passes; screen, focus and typed kinds
pass; only SrAnnChange on the desktop without a recent press is dropped.

### Change 3: Sub-GHz built into the firmware

```
diff --git a/applications/main/subghz/application.fam b/applications/main/subghz/application.fam
index d80978b8e..d44b008a5 100644
--- a/applications/main/subghz/application.fam
+++ b/applications/main/subghz/application.fam
@@ -1,29 +1,57 @@
 App(
     appid="subghz",
     name="Sub-GHz",
-    apptype=FlipperAppType.MENUEXTERNAL,
+    apptype=FlipperAppType.APP,
     targets=["f7"],
     entry_point="subghz_app",
     icon="A_Sub1ghz_14",
     stack_size=3 * 1024,
     order=10,
-    # Sources separation breaks linking with subghz on internal
+    # Built into the firmware on the screen-reader branch: as a fap it costs about 55 KB of
+    # RAM. The firmware build hands every sources entry to GatherSources on its own
+    # (firmware.scons, get_builtin_app_folders), so a "!" exclude never meets "*.c" there;
+    # that is the sources separation that broke the internal link. The fap's file set is
+    # therefore listed explicitly. Left out, as the fap excluded them: subghz_fap.c,
+    # subghz_cli.c and helpers/subghz_chat.c (cli_subghz plugin), helpers/subghz_gps.c and
+    # helpers/minmea.c (subghz_gps plugin), subghz_extended_freq.c (startup hook), and the
+    # Add Manually files (subghz_add_manually fap).
     sources=[
-        "*.c",
-        "!subghz_fap.c",
-        "!subghz_gps.c",
-        "!minmea.c",
-        "!subghz_cli.c",
-        "!subghz_chat.c",
-        "!subghz_extended_freq.c",
-        "!subghz_gen_info.c",
-        "!subghz_txrx_create_protocol_key.c",
-        "!subghz_scene_set_button.c",
-        "!subghz_scene_set_counter.c",
-        "!subghz_scene_set_key.c",
-        "!subghz_scene_set_seed.c",
-        "!subghz_scene_set_serial.c",
-        "!subghz_scene_set_type.c",
+        "subghz.c",
+        "subghz_i.c",
+        "subghz_history.c",
+        "subghz_last_settings.c",
+        "helpers/subghz_frequency_analyzer_worker.c",
+        "helpers/subghz_gps_plugin.c",
+        "helpers/subghz_threshold_rssi.c",
+        "helpers/subghz_txrx.c",
+        "scenes/subghz_scene.c",
+        "scenes/subghz_scene_decode_raw.c",
+        "scenes/subghz_scene_delete.c",
+        "scenes/subghz_scene_delete_raw.c",
+        "scenes/subghz_scene_delete_success.c",
+        "scenes/subghz_scene_frequency_analyzer.c",
+        "scenes/subghz_scene_more_raw.c",
+        "scenes/subghz_scene_need_saving.c",
+        "scenes/subghz_scene_radio_settings.c",
+        "scenes/subghz_scene_read_raw.c",
+        "scenes/subghz_scene_receiver.c",
+        "scenes/subghz_scene_receiver_config.c",
+        "scenes/subghz_scene_receiver_info.c",
+        "scenes/subghz_scene_rpc.c",
+        "scenes/subghz_scene_save_name.c",
+        "scenes/subghz_scene_save_success.c",
+        "scenes/subghz_scene_saved.c",
+        "scenes/subghz_scene_saved_menu.c",
+        "scenes/subghz_scene_show_error.c",
+        "scenes/subghz_scene_show_error_sub.c",
+        "scenes/subghz_scene_show_gps.c",
+        "scenes/subghz_scene_signal_settings.c",
+        "scenes/subghz_scene_start.c",
+        "scenes/subghz_scene_transmitter.c",
+        "views/receiver.c",
+        "views/subghz_frequency_analyzer.c",
+        "views/subghz_read_raw.c",
+        "views/transmitter.c",
     ],
     requires=["region"],
     resources="resources",
```

What a59ef9f05 changed and what came after it: the commit flipped apptype APP to MENUEXTERNAL,
uncommented the `sources` list with `!` excludes (adding `!subghz_fap.c`), commented out the
`subghz_fap` EXTERNAL stub app and its `sdk_headers`, and removed `subghz_app` and
subghz_fap.h from api_symbols.csv. Later commits on the base extended the excludes for the Add
Manually split (27015e81e moved six set_* scenes, gen_info and txrx_create_protocol_key into a
separate subghz_add_manually fap, launched by path from the Start scene), fixed the excludes to
bare file names (4bdd7a391: "Can't use ! with subdirs"), and re-enabled the startup hook's
`sources=["subghz_extended_freq.c"]` (c298ed01a). The plugins cli_subghz (subghz_cli.c,
subghz_chat.c) and subghz_gps (subghz_gps.c, minmea.c) and the hook were external or separate
in both configurations.

Why the apptype flip alone cannot work here, and why the verbatim manifest cannot either:
firmware.scons gathers built-in sources with `fwenv.GatherSources([source_type, "!lib"],
appdir)` for each `(appdir, source_type)` pair of `get_builtin_app_folders()`, that is one
manifest entry at a time; a `!` entry alone gathers nothing and `*.c` alone gathers every .c
file under the app recursively. That is the "sources separation" the manifest comment warns
about. With everything gathered, subghz_extended_freq.c is compiled twice (the hook lists it
too: a multiple definition at link, which is why the pre-a59ef9f05 manifest had the hook's
sources commented out), and the six set_* scenes reference SubGhzSceneSetKey, SetSerial,
SetButton, SetCounter, SetSeed and SetType, which subghz_scene_config.h only defines under
SUBGHZ_ADD_MANUALLY: they do not compile in the firmware. The pre-a59ef9f05 manifest verbatim
has the same compile set (its `sources` is commented out, so the default `*.c*` gathers all 50
files), lacks the subghz_add_manually app that the Start scene launches, and would need
`subghz_app` back in api_symbols.csv for its subghz_fap stub. So instead of a build that fails
twice I wrote the manifest's `sources` as the positive list of the fap's file set: the 50 .c
files under applications/main/subghz minus the 14 the fap excluded, 36 entries, checked by a
script (`listed 36 expected 36, missing [], extra []`, every file exists). Entries without glob
characters are taken as literal files on both the built-in and the fap path, so the manifest
would also still build as a fap if flipped back. Nothing else changed: the subghz_fap stub and
sdk_headers stay commented, api_symbols.csv is untouched (the internal app exports nothing),
the hook, the two plugins and the subghz_add_manually fap keep their own sources, `resources`,
`requires`, `fap_libs`, `fap_icon` and `fap_category` are as before (fap_libs and fap_icon are
ignored for a built-in app; firmware.scons only refuses fap_extbuild, fap_private_libs and
fap_icon_assets). The alternative would have been a build system fix (gather per app with the
whole `sources` list and dedupe nodes in firmware.scons, about eight lines, which is what the
comment has been asking for); I kept the change in the manifest as the brief asked and mention
the alternative in case the controller prefers it.

Card resources: `resources="resources"` was already on the MENUEXTERNAL app and
fbt_resources.py deploys an app's resources directory for built-in and external apps alike
(env["APPBUILD"].apps plus FW_EXTAPPS), so the internal build needs no card files the fap
did not: /ext/subghz/assets (keeloq_mfcodes, nice_flor_s, came_atomo, alutech_at_4n, the two
.example files), the Tesla .sub files, the playlist and the remote were on the card with the
fap and are still what the app expects. `./fbt flash_usb` is the minimal update package
(updater_minpackage: firmware and updater only, no resources, no radio stack), so it does not
touch the card.

Add Manually with the internal app: scene_start.c enqueues the add-manually fap and then its
own relaunch through loader_get_application_launch_path; the loader sets launch_path to the
name for any app it started (loader.c line 768), so for the internal app that is "Sub-GHz"
and the deferred launch resolves by name. Read from the code only; the phase B checks do not
include Add Manually.

### Change 4: docs

README.md: the Task 6 "known problem" bullet is now the as-built state (Sub-GHz in flash on
this branch, the other main apps still external faps, NFC read about 24 KB, remove the card's
subghz.fap after the flash), and the speech paragraph gained the home screen rule and one
sentence on NFC-V emulation. Spec, section 16: the phase 1 screen change rule now points at
phase 2 for bubbles; "Phase 2 as built" has the NFC-V listener's register read and pin parking
in the speaker sharing item, a new "Home screen" item, and the memory item's Sub-GHz paragraph
rewritten from open item to as built with the flash numbers.

### Concerns and notes for the controller

1. Item 3 deviates in form from "change the apptype, adjust the sources as that commit shows":
   the sources are an explicit list, for the reason above. The controller may prefer the
   firmware.scons fix instead; the manifest would then keep its `!` list with only the apptype
   flipped. Either way the compile set is the same 36 files.
2. `sr status` "announcements" changed meaning: it now counts announcements handed to speech,
   not everything the model produced; suppressed ones are in the new counter. sr_drive.py does
   not parse that line (it reads the watch stream), so no tool breaks.
3. Auto-lock without a key press: if the desktop locks by timeout and draws its locked text as
   a change on the desktop layer, that text is now not spoken (no key within 2 s). A lock by
   key press is within the window. Not verified on the device; mentioning it as the one thing
   the rule could hide.
4. The first two seconds after boot count as "key recent" for the desktop rule (last_press_tick
   starts at 0); harmless.
5. The stale build/f7-firmware-C/.extapps/subghz.fap is not deployed by anything (the resources
   manifest is generated from the current build set), but the card's copy must go in phase B.
6. Version stamp: build B ran before commit 1c113c28a existed, so its image carries the earlier
   hash if fbt stamps HEAD at build time; `./fbt flash_usb` in phase B rebuilds first, and
   `info device` is checked against 1c113c28a.
7. Nothing was pushed; applications/external (submodule, not mine) is untouched.

### Phase B plan (on "flash")

1. `pgrep -fl fbt`, then `./fbt flash_usb` (firmware only); wait for the port to return.
2. `info device` (firmware commit 1c113c28a expected), `sr screen` for a crash popup.
3. `storage list /ext/apps/Sub-GHz` and the other app folders; `storage remove
   /ext/apps/Sub-GHz/subghz.fap` if present; `storage read /int/.mainmenu_apps.txt` if it
   exists, to see whether the custom menu names Sub-GHz by path.
4. `loader list` and `sr screen` on the main menu: Sub-GHz listed once.
5. Sub-GHz Read and Frequency Analyzer with the reader speaking, `free` at the lowest point
   (ram_probe.py's approach for those two entries only), Back presses to leave, never
   `loader close`.
6. Open /ext/nfc/sr_nfcv_test.nfc during a long `sr say`: no crash, Back cuts speech and leaves.
7. Home screen for three minutes, `sr status` every 30 s: announcements flat, suppressed may
   rise; then `input send up short` and confirm the menu is announced.
8. Leave the device on the home screen, reader on, speech idle. On a crash popup or an
   unresponsive device: stop, report BLOCKED with the exact output.


## Phase A2 (whole-branch review findings, before the flash)

Status: DONE. Four more firmware commits on top of 1c113c28a, in the order the coordinator
listed; each committed after an index.lock check (none) with an explicit `git add` and a
pathspec commit; `git status` shows only the untouched ` m applications/external`; nothing
pushed; the device untouched. Final `./fbt` exit 0, `./fbt lint` exit 0 (was red on the two
gui files), host runner green.

### Commits

- 8e6c14707 "screen reader: speech waits for a beep to end instead of dropping the
  announcement". speech.c, 25 insertions, 4 deletions.
- 885c1504c "screen reader: a key press during the final flush keeps the next announcement".
  speech.c, speech.h, screen_reader.c (a comment).
- aedc2fcf0 "gui modules: clang-format". submenu.c and variable_item_list.c, 3 lines each.
- f2ba82193 "screen reader: SAM port symbols are file local". sam/sam.c, 99 insertions, 101
  deletions (60 `static` prefixes plus the table lines clang-format re-wrapped).

### Sizes, lint, runner

Final `./fbt` (all eight commits of this round), exit 0, only the two pre-existing manifest
warnings:

```
API version 87.1 is up to date
.text         711264 (694.59 K)
.rodata       197952 (193.31 K)
.data           1144 (  1.12 K)
.bss            8556 (  8.36 K)
.free_flash   137880 (134.65 K)
```

Against phase A's build B: .text plus 4 bytes, .rodata plus 184, .data minus 184, .bss
unchanged, .free_flash identical (137,880 bytes, 134.65 KB). Item 2 removed about as much code
as item 1 added, and the SAM change only moved bytes between sections: freq3data (80 bytes)
and timetable (100) are never written and now sit in .rodata, wait1 and wait2 were folded
into their uses; freq1data and freq2data stay in .data because the mouth and throat settings
rewrite them. So the SAM commit saves 184 bytes of RAM and no flash.

`./fbt lint`: exit 0 (before this round: exit 2 with the two clang-format violations at
submenu.c:135 and variable_item_list.c:114).

`TMPDIR=<scratchpad>/tf tools/run_host_tests.sh`, exit 0, run after the SAM change and again
after everything:

```
98 checks, 0 failures
port checks: 0 failures
SAM port matches the original on 11 cases
speech text: 1006 checks, 0 failures
speech queue: 94 checks, 0 failures
speech PCM: 647 checks, 0 failures
```

### Item 1: speech waits for a beep to end

```
diff --git a/applications/services/screen_reader/speech.c b/applications/services/screen_reader/speech.c
index 677755b64..bf81b4a7f 100644
--- a/applications/services/screen_reader/speech.c
+++ b/applications/services/screen_reader/speech.c
@@ -16,6 +16,7 @@
 #define SPEECH_IDLE_RELEASE_MS    200
 #define SPEECH_ACQUIRE_TIMEOUT_MS 500
 #define SPEECH_EVENT_TIMEOUT_MS   200
+#define SPEECH_BUS_POLL_MS        5
 
 #define SPEECH_FLAG_WORK  (1 << 0)
 #define SPEECH_FLAG_STOP  (1 << 1)
@@ -158,9 +159,25 @@ static void speech_flush(Speech* speech) {
 
 static bool speech_take_speaker(Speech* speech) {
     if(furi_hal_speaker_is_mine()) return true;
-    // Someone else drives TIM16 (another speaker user, or NFC tag emulation): do not touch it
-    if(furi_hal_bus_is_enabled(FuriHalBusTIM16)) return false;
-    if(!furi_hal_speaker_acquire(SPEECH_ACQUIRE_TIMEOUT_MS)) return false;
+    // Someone else drives TIM16: the notification service holds the speaker for a whole beep
+    // sequence (four 50 ms notes on a successful read, fired back to back with the result
+    // screen), the NFC-V listener for a whole emulation. Wait for the bus to go quiet instead
+    // of dropping the announcement, then take the mutex with what is left of the timeout; an
+    // emulation outlasts it and the utterance is dropped as before. A stop request or a newer
+    // utterance ends the wait at once
+    uint32_t started = furi_get_tick();
+    while(furi_hal_bus_is_enabled(FuriHalBusTIM16)) {
+        if(speech_superseded(speech)) {
+            speech->aborted = true;
+            return false;
+        }
+        if(furi_get_tick() - started >= SPEECH_ACQUIRE_TIMEOUT_MS) return false;
+        furi_delay_ms(SPEECH_BUS_POLL_MS);
+    }
+    uint32_t waited = furi_get_tick() - started;
+    uint32_t remaining = waited < SPEECH_ACQUIRE_TIMEOUT_MS ? SPEECH_ACQUIRE_TIMEOUT_MS - waited :
+                                                              0;
+    if(!furi_hal_speaker_acquire(remaining)) return false;
     speech_lock(speech);
     speech->stats.speaker_held = true;
     speech_unlock(speech);
@@ -194,7 +211,11 @@ static void speech_speak_item(Speech* speech, const SpeechItem* item) {
 
     if(!speech_take_speaker(speech)) {
         speech_lock(speech);
-        speech->stats.dropped++;
+        if(speech->aborted) {
+            speech->stats.aborted++; // a stop request or a newer utterance ended the wait
+        } else {
+            speech->stats.dropped++; // the timer stayed busy, as during an NFC-V emulation
+        }
         speech->stats.speaking = false;
         speech_unlock(speech);
         return;
```

The bus check stays (a TIM16 user outside the speaker mutex would make the acquire's
furi_hal_bus_enable furi_check; none exists in this tree after Task 4b, so it is belt and
braces) and is polled every 5 ms up to SPEECH_ACQUIRE_TIMEOUT_MS (500 ms); the mutex is then
taken with what is left of the timeout. The notification service takes the speaker with
furi_hal_speaker_acquire(30) at its first note and releases it at message_sound_off, so
sequence_success (c5, e5, g5, c6 with 50 ms delays) holds it for a bit over 200 ms, inside
the window. A bus still busy after 500 ms drops the utterance as before (NFC-V emulation: the
listener holds the speaker until the app leaves). The loop checks speech_superseded every
5 ms, so a key press or a newer utterance ends the wait within 5 ms; that exit is counted as
aborted, not dropped (speech_speak_item's early return distinguishes the two). Under the old
stop design, which item 1 was built and committed on, speech_superseded also covered the stop
flag; after item 2 it is the generation comparison, which the stop bumps, so the loop is
unchanged.

### Item 2: a key press during the final flush keeps the next announcement

```
diff --git a/applications/services/screen_reader/screen_reader.c b/applications/services/screen_reader/screen_reader.c
index 3eba02fae..6368dbb2d 100644
--- a/applications/services/screen_reader/screen_reader.c
+++ b/applications/services/screen_reader/screen_reader.c
@@ -98,8 +98,10 @@ static void sr_input_callback(const void* value, void* context) {
     ScreenReader* sr = context;
     if(event->type == InputTypePress) {
         sr->last_press_tick = furi_get_tick();
-        // Any key silences speech. This only sets a thread flag, so it is safe here on the
-        // input thread, and it lands before the app has seen the key
+        // Any key silences speech. speech_stop retires the queue under the speech mutex (its
+        // users hold it for microseconds) and wakes the worker; this callback runs on the
+        // input service thread, not in an interrupt, and the stop lands before the app has
+        // seen the key, so the announcement the key causes is queued after it and survives
         speech_stop(sr->speech);
     }
 }
diff --git a/applications/services/screen_reader/speech.c b/applications/services/screen_reader/speech.c
index bf81b4a7f..a83f38916 100644
--- a/applications/services/screen_reader/speech.c
+++ b/applications/services/screen_reader/speech.c
@@ -43,7 +43,6 @@ struct Speech {
     uint16_t fill_index;
     bool running;
     bool aborted;
-    bool stop_pending;
     uint32_t generation;
     uint8_t lut_volume;
     char expanded[SPEECH_TEXT_MAX];
@@ -68,27 +67,34 @@ static uint32_t half_flag(uint8_t half) {
     return half == 0 ? SPEECH_FLAG_HALF0 : SPEECH_FLAG_HALF1;
 }
 
-/** A newer utterance, a stop request or a key press makes the current one worthless. */
+/**
+ * A newer utterance or a stop request makes the current one worthless. Both bump the queue
+ * generation under the mutex, on the requesting thread, and every item carries the generation
+ * it was pushed in, so this comparison is the only thing that ends an utterance; the stop flag
+ * merely wakes a DMA wait so that the comparison runs at once.
+ */
 static bool speech_superseded(Speech* speech) {
-    if(speech->stop_pending) return true;
-    if(furi_thread_flags_get() & SPEECH_FLAG_STOP) {
-        speech->stop_pending = true;
-        return true;
-    }
     return *(volatile uint32_t*)&speech->queue.generation != speech->generation;
 }
 
-/** Wait until the DMA has finished playing `half`. False when stopped or when no event came. */
+/**
+ * Wait until the DMA has finished playing `half`. False when the utterance was superseded
+ * meanwhile or when no event came in time. A stop flag that wakes the wait is judged by the
+ * generation: a flag left over from a stop that already ended an earlier utterance makes this
+ * one look and keep waiting.
+ */
 static bool speech_wait_half_played(Speech* speech, uint8_t half) {
     uint32_t wanted = half_flag(half);
-    uint32_t flags = furi_thread_flags_wait(
-        wanted | SPEECH_FLAG_STOP, FuriFlagWaitAny, SPEECH_EVENT_TIMEOUT_MS);
-    if(flags & FuriFlagError) return false;
-    if(flags & SPEECH_FLAG_STOP) {
-        speech->stop_pending = true;
-        return false;
+    uint32_t started = furi_get_tick();
+    while(true) {
+        uint32_t waited = furi_get_tick() - started;
+        if(waited >= SPEECH_EVENT_TIMEOUT_MS) return false;
+        uint32_t flags = furi_thread_flags_wait(
+            wanted | SPEECH_FLAG_STOP, FuriFlagWaitAny, SPEECH_EVENT_TIMEOUT_MS - waited);
+        if(flags & FuriFlagError) return false;
+        if(speech_superseded(speech)) return false;
+        if(flags & wanted) return true;
     }
-    return (flags & wanted) != 0;
 }
 
 // Called by the PCM stage for every duty byte, on the worker thread
@@ -132,7 +138,11 @@ static bool speech_sam_output(const uint8_t values[5], uint16_t delta, void* con
     return speech_pcm_push(&speech->pcm, values, delta, speech_emit, speech);
 }
 
-/** Play out what was rendered and stop the hardware cleanly. */
+/**
+ * Play out what was rendered and stop the hardware cleanly. A stop request or a newer
+ * utterance ends the play out at the wait it lands in and the hardware stops at once: what
+ * would follow is padding, and a key press must silence the speaker without delay.
+ */
 static void speech_flush(Speech* speech) {
     uint8_t silence = speech_pcm_silence(&speech->pcm);
     if(!speech->running) {
@@ -144,15 +154,20 @@ static void speech_flush(Speech* speech) {
         speech->running = true;
         speech_wait_half_played(speech, 0);
     } else {
+        // The half being filled ends in silence. The DMA is still in the other half; once
+        // that has played it moves into this one, the other half is silenced too, and the
+        // hardware stops when the DMA has played this one
         uint8_t h = speech->fill_half;
         memset(
             &speech->ring[h * SPEECH_HALF + speech->fill_index],
             silence,
             SPEECH_HALF - speech->fill_index);
-        speech_wait_half_played(speech, h ^ 1);
-        memset(&speech->ring[(h ^ 1) * SPEECH_HALF], silence, SPEECH_HALF);
-        speech_wait_half_played(speech, h);
+        if(speech_wait_half_played(speech, h ^ 1)) {
+            memset(&speech->ring[(h ^ 1) * SPEECH_HALF], silence, SPEECH_HALF);
+            speech_wait_half_played(speech, h);
+        }
     }
+    if(speech_superseded(speech)) speech->aborted = true;
     speech_hw_stop();
     speech->running = false;
 }
@@ -192,16 +207,6 @@ static void speech_drop_speaker(Speech* speech) {
     speech_unlock(speech);
 }
 
-static void speech_apply_stop(Speech* speech) {
-    // Consume the request: speech_superseded only reads the flag, so without this the next
-    // wait would see it again and apply the stop a second time, dropping what was queued after it
-    furi_thread_flags_clear(SPEECH_FLAG_STOP);
-    speech_lock(speech);
-    speech_queue_stop(&speech->queue);
-    speech_unlock(speech);
-    speech->stop_pending = false;
-}
-
 static void speech_speak_item(Speech* speech, const SpeechItem* item) {
     speech->generation = item->generation;
     speech->aborted = false;
@@ -303,12 +308,10 @@ static int32_t speech_worker(void* context) {
             speech_drop_speaker(speech);
             continue;
         }
-        if(flags & SPEECH_FLAG_STOP) speech->stop_pending = true;
-        if(speech->stop_pending) speech_apply_stop(speech);
-
+        // A stop request has already retired the queue on the requesting thread; its flag
+        // only wakes this loop, which then finds nothing or what was pushed after the request
         while(speech_pop(speech, item)) {
             speech_speak_item(speech, item);
-            if(speech->stop_pending) speech_apply_stop(speech);
         }
     }
     return 0;
@@ -343,6 +346,17 @@ void speech_say(Speech* speech, const char* text, bool interrupt, bool replaceab
 
 void speech_stop(Speech* speech) {
     furi_check(speech);
+    // Retire the queue here, on the requesting thread, so that the stop takes effect at the
+    // request: what waits is dropped and the generation moves on, which supersedes what is
+    // being spoken at its next sample or wake up, while anything pushed from now on carries
+    // the new generation and survives however late the worker looks. Applied on the worker
+    // instead, the stop of a key press wiped the announcement that same press caused, pushed
+    // 50 ms later while the worker was still playing out. The flag then wakes the worker out
+    // of a DMA wait. The mutex is held for microseconds by every user, and the callers are
+    // threads (input service, console, reader), never interrupts
+    speech_lock(speech);
+    speech_queue_stop(&speech->queue);
+    speech_unlock(speech);
     furi_thread_flags_set(speech->thread_id, SPEECH_FLAG_STOP);
 }
 
diff --git a/applications/services/screen_reader/speech.h b/applications/services/screen_reader/speech.h
index c9251f583..a3939e1c3 100644
--- a/applications/services/screen_reader/speech.h
+++ b/applications/services/screen_reader/speech.h
@@ -17,7 +17,8 @@ typedef struct Speech Speech;
 typedef struct {
     uint32_t utterances; /**< started */
     uint32_t dropped; /**< could not get the speaker */
-    uint32_t aborted; /**< interrupted by a newer utterance, a stop, or a key press */
+    uint32_t aborted; /**< ended early by a newer utterance, a stop or a key press, also while
+                           waiting for the speaker or playing out the end */
     uint32_t underruns; /**< DMA reached a half before it was filled */
     uint32_t queue_dropped; /**< pushed out of a full queue */
     uint32_t queued; /**< items waiting */
@@ -36,7 +37,9 @@ Speech* speech_alloc(void);
  *  replaceable item is overwritten instead of queued behind it. */
 void speech_say(Speech* speech, const char* text, bool interrupt, bool replaceable);
 
-/** Stop speaking and drop the queue. Safe from any thread, including input callbacks. */
+/** Stop speaking and drop what is queued so far; anything pushed afterwards is kept. Takes the
+ *  speech mutex briefly, so callers are threads (input callbacks run on the input service
+ *  thread), never interrupts. */
 void speech_stop(Speech* speech);
 
 /** rate is the SAM speed (40..120), volume 0..100. Applied from the next utterance on. */
```

What was wrong, read from the old code: the flush's first speech_wait_half_played returned
on the stop flag (the wait consumes every requested flag on exit, furi_thread_flags_wait
passes `clear = flags` to xTaskNotifyWait) and set stop_pending; the flush ignored the
return value and waited for the last half anyway, up to 82 ms; only then did the worker's
speech_apply_stop clear the queue, which by then held the announcement of the screen the
key press had opened (the reader pushes it about 50 ms after the press, its settle time).

What the fix does: the queue is retired on the requesting thread. speech_stop takes the
speech mutex, calls speech_queue_stop (drops what waits, bumps the generation), releases,
and then sets the flag. The generation comparison in speech_superseded is now the only thing
that ends an utterance; the flag is a wake-up for a DMA wait, and speech_wait_half_played
loops: woken by the flag, it re-checks the generation and keeps waiting (with the remaining
timeout) when the utterance is still current. speech_apply_stop and stop_pending are gone;
the worker loop just pops. speech_flush stops the hardware as soon as a wait reports the
utterance superseded (the second wait is skipped) and marks it aborted for the statistics,
since the stop cut real audio in general (the DMA is in the previously filled half when the
flush starts).

Why it is race free:

1. Pushes (speech_say, also interrupting pushes) and stops both modify the queue under the
   speech mutex, and every item records the queue generation at its push. For any push and
   any stop there are exactly two orders: push first, and the stop's queue_stop drops that
   item; stop first, and the item carries the new generation, which no later action of that
   stop can touch, because the worker never clears the queue and only compares generations.
   The reader's announcement after a press is always the second case (it is pushed after the
   press by construction: the press's stop runs in the input callback before the app has seen
   the key, and the announcement follows the frame the app draws).
2. Inside speech_stop the queue is retired before the flag is set, so after the flag the
   worker can only pop items pushed after the request. An item of the old generation that is
   being rendered is superseded at its next sample (speech_emit checks first); one that sits
   in a DMA wait is woken by the flag and superseded at the wake-up; one that starts a wait
   after the flag was set returns at once, because the flag is pending in the notification
   value. A new generation item woken by a flag (a flag of a stop that already ended the
   previous item and was not consumed yet, or a stop that ran between its push and its
   wait) finds its generation current and resumes the wait, so no item pushed after a stop
   is ever ended by that stop.
3. The generation is a single aligned 32 bit word written only under the mutex and read
   with a volatile access; a torn read is impossible on Cortex-M4, and a stale read only
   delays the abort to the next sample, as before.
4. Lock order: the reader holds its own mutex while calling speech_say, and the input
   callback holds nothing when calling speech_stop; nothing in speech.c calls back into the
   reader, so the two mutexes never nest the other way. Every holder of the speech mutex
   keeps it for a memcpy or a few stores. Callers of speech_stop: the input service thread
   (real presses; long and repeat events come from a FuriTimer callback, which is the timer
   task, also a thread, and the reader only acts on presses anyway), the console thread (sr
   stop, and the synthetic presses of sr watch, which are published on the console thread),
   and the reader thread (sr off). furi_mutex_acquire furi_checks against interrupt context,
   so a future interrupt caller would fail loudly rather than corrupt the queue.

Behaviour that changed as a side effect and is intended: a stop during the take-speaker
poll or during the flush counts as aborted (before, a stop during the flush counted
nothing); the worker's idle release timer restarts on a stop wake-up (a key press can extend
a held speaker by up to 200 ms).

### Item 3: gui modules clang-format

```
diff --git a/applications/services/gui/modules/submenu.c b/applications/services/gui/modules/submenu.c
index 95fc06733..410bc2d8d 100644
--- a/applications/services/gui/modules/submenu.c
+++ b/applications/services/gui/modules/submenu.c
@@ -132,8 +132,7 @@ static void submenu_view_draw_callback(Canvas* canvas, void* _model) {
             }
 
             if(position == model->position) {
-                canvas_tap_hint_focus(
-                    canvas, position + 1, SubmenuItemArray_size(model->items));
+                canvas_tap_hint_focus(canvas, position + 1, SubmenuItemArray_size(model->items));
             }
 
             FuriString* disp_str = furi_string_alloc_set(SubmenuItemArray_cref(it)->label);
diff --git a/applications/services/gui/modules/variable_item_list.c b/applications/services/gui/modules/variable_item_list.c
index ea0bff46a..a0621ea0b 100644
--- a/applications/services/gui/modules/variable_item_list.c
+++ b/applications/services/gui/modules/variable_item_list.c
@@ -111,8 +111,7 @@ static void variable_item_list_draw_callback(Canvas* canvas, void* _model) {
             }
 
             if(position == model->position) {
-                canvas_tap_hint_focus(
-                    canvas, position + 1, VariableItemArray_size(model->items));
+                canvas_tap_hint_focus(canvas, position + 1, VariableItemArray_size(model->items));
             }
 
             elements_scrollable_text_line(
```

### Item 4: SAM port symbols file local

```
f2ba82193 screen reader: SAM port symbols are file local

 applications/services/screen_reader/sam/sam.c | 200 +++++++++++++-------------
 1 file changed, 99 insertions(+), 101 deletions(-)
```

The 62 non-API globals of sam.o (A, X, Y, input, inputtemp, the mem* bytes, wait1, wait2,
bufferpos, oldtimetableindex, the phoneme and stress buffers, the frequency, amplitude and
pitch arrays, the rules, the tables) are defined on 60 file scope lines (A, X and Y share
one); a script prefixed each with `static`, then clang-format re-wrapped the table lines that
grew past the column limit. Checks: with the `static ` tokens and whitespace removed the old
and new files are byte-identical; clang -Wall -Wextra -Werror compiles the file without an
unused symbol warning (every table and function is used, to_upper_case by TextToPhonemes);
`arm-none-eabi-nm -g --defined-only sam.o` prints only `00000000 T sam_speak`; the host object
likewise exports only `_sam_speak`; the golden cases and the port checks are unchanged.

### Phase B additions

To the plan in the phase A section: read /int/.mainmenu_apps.txt (a path entry would launch
the card fap, a name entry resolves to the built-in), and run the RFID read scene with sounds
on if a tag is at hand (the result announcement must now be spoken after the success beeps),
else say it was not exercised.

## Phase B (flash and device checks)

Status: BLOCKED. The flash was refused by the device's updater because the image with Sub-GHz
built in is larger than the flash the firmware may use on this device; the old image
(7efa4a16 dirty, the Task 6 build) is intact and running, the device is idle on the home
screen with the reader on and speech idle, and none of the device checks of the plan were run.
Nothing else was touched: no card file removed, no app opened, no key sent. The coordinator has
to rule on Sub-GHz (options at the end) before phase B can run.

### Idle precondition

`loader info` and `sr status` polled five times over 60 s (21:35:45 to 21:36:45), with `sr
screen` at each sample to tell home screen bubbles (which the running image still counts) from
use: "No application is running" every time, `enabled yes`, `speech idle`, `announcements 70`
at every sample, frames 9644 to 9765 (the dolphin animation), content layer desktop with an
empty "reads as". Result: idle on the first attempt.

### Flash attempt

`pgrep -fl fbt` empty. `./fbt flash_usb` at 21:37:49, exit 0 at 21:38:22: it rebuilt the
updater and the minimal package `dist/f7-C/f7-update-mntm-screen-reader-f2ba8219` (so the
package carries the final commit's hash), sent firmware.dfu (911,005 bytes, 112 chunks at about
130 kB/s), update.fuf and updater.bin to /ext/update/f7-update-mntm-screen-reader-f2ba8219/,
logged "Closing current app, if any" and issued `update install`; no error in its output. The
port node vanished at 21:38:22 and was back after 11.2 s (the Task 6 flash took 28 s). After
12 s of settling:

```
firmware.commit.hash          : 7efa4a16
firmware.commit.dirty         : true
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as:
== sr status
enabled: yes
rate: 72, volume: 100, verbosity: 1
frames: 26, dropped: 0, announcements: 2
speech: idle, queued 0, speaker held: no, utterances 2, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 2347 ms played, 90880 subsamples, 1633 ms nominal, worker stack free 2404
free heap: 115568
== loader info
No application is running
```

The device had rebooted (the counters restarted; the two utterances and the 2347 ms last
utterance are the same boot announcements the Task 6 report shows after its flash), but the
image is the old one: the commit hash is 7efa4a16 and the frames line has no `suppressed`
field. No crash popup. On the card the package is complete (firmware.dfu 911005b, update.fuf
351b, updater.bin 121145b) and next to it lies backup.tar 10240b, which the updater writes in
its IntBackup stage, so the updater did start and stopped after the backup, before writing
flash.

### Why: the image does not fit below the radio stack

The updater validates every DFU page address with check_address_boundaries
(applications/system/updater/util/update_task_worker_flasher.c line 43): an address must be
below furi_hal_flash_get_free_end_address(), which is SFSA times 4 KB from the flash base
(targets/f7/furi_hal/furi_hal_flash.c line 81), the start of the secure area holding the BLE
stack. The stage is UpdateTaskStageValidateDFUImage, before UpdateTaskStageFlashWrite; on an
error stage the updater resets the device (updater_scene_main.c line 50), which is the 11 s
round trip. scripts/ob.data, the option byte reference for the shipped copro stack (ble_light
1.20.0, which `info device` confirms the device runs: stack type 3, 1.20.0), says
`SFSA:0xD7`: the firmware may use 0x08000000 to 0x080D7000, 880,640 bytes.

fbt's `.free_flash` line never saw that boundary: the linker script gives FLASH LENGTH = 1024K
(targets/f7/stm32wb55xx_flash.ld line 9), so the figure is 1 MB minus the image. The numbers
against the real boundary (image = .text + .rodata + .data; the DFU adds 645 bytes):

- mntm-012: DFU 877,209, firmware.bin 876,900: fits, 3,740 bytes spare (which is what the "desperately
  out of flash space" comment in firmware.scons is about).
- Task 6 image (on the device now): sections 868,236, firmware.bin 868,572: fits, 12,068 bytes spare.
- Phase A build A (items 1 and 2): sections 868,324, about 12,000 bytes spare.
- Phase A build B and the final A2 image: sections 910,356 and 910,360, firmware.bin 910,696 (DFU 911,005 minus the constant 309 byte DFU wrapper): 30,056 bytes over the boundary.
  Sub-GHz added 42,036 bytes; the device had about 12 KB, not 175 KB.

So the claims in the phase A section ("134.7 KB stay free, well above the 60 KB phase 3
needs"), in commit 1c113c28a's message and in the docs commit f509d77 (README and spec: "134.7
KB left") are wrong and must be corrected whichever way the ruling goes: the usable headroom
with Sub-GHz external is about 12 KB, and phase 3's 60 KB do not exist on this base with this
radio stack. I should have checked the image against SFSA rather than trusting `.free_flash`;
the mntm-012 size and the firmware.scons comment were both there to see.

### Device state now

Old image 7efa4a16 (dirty) running, home screen, no application, reader on, speech idle, no
popup (`sr screen` shows only the battery record; a second check minutes later was the same
with frames rising from the animation only). The refused package stays in
/ext/update/f7-update-mntm-screen-reader-f2ba8219/ next to the earlier ones; /int is Momentum's
virtual mode on the card (storage info /int: Virtual), so the updater's backup.tar restores
nothing and nothing was lost. /ext/apps/Sub-GHz/subghz.fap is still on the card and still
what the running image's main menu launches.

### Not done

All device checks of the plan: card fap removal and /int/.mainmenu_apps.txt, menu listing,
Sub-GHz Read and Frequency Analyzer heap, the NFC-V file during `sr say` (and the reviewer's
question whether "Home screen" is spoken after the Back press once the listener releases), the
three minute soak with the suppressed counter, Up and the menu announcement, the RFID read
scene (not exercised; no tag was assumed at hand). None of items 1, 2, A2.1 to A2.4 has run on
the device yet.

### Options for the ruling

1. Revert 1c113c28a (Sub-GHz external again) and correct the docs; flash items 1, 2 and the
   four A2 fixes: the image is build A plus a few bytes, about 868.3 KB, 12 KB below the
   boundary, and phase B can run as planned minus the Sub-GHz heap checks. Sub-GHz stays
   unusable with the reader on (2 KB of heap in read mode).
2. Keep Sub-GHz built in and find 30 KB of flash elsewhere: link time optimisation (the
   commented `-flto` block in firmware.scons; a build system change with runtime risk), or
   moving other built-in code out. Nothing in the current FLIPPER_APPS table besides Sub-GHz is
   an app; the 868 KB base is services and libraries, so 30 KB is not a quick cut.
3. A smaller radio stack would move SFSA up, but changing the copro firmware is a different
   project.

Tag free beep for item 1, if wanted in a later phase B: the notification settings app plays
sequence_note_c when the volume item changes (notification_settings_app.c line 131), so
opening Settings, Notification, moving to Volume and pressing Right then Left exercises "speech
waits for a beep" without an RFID tag, at the cost of touching (and restoring) a setting.

## Correction to phase A and A2

Every flash figure in the phase A and A2 sections that speaks of free space (build A "175.70 K",
build B and the final image "134.65 K", "well above the 60 KB phase 3 needs", "Sub-GHz costs
42,036 bytes of flash, 134.7 KB remain") is fbt's .free_flash against the nominal 1024 KB
linker region. The real limit is the BLE stack's start, SFSA 0xD7 (880,640 bytes for the
firmware, scripts/ob.data for ble_light 1.20.0), which the updater enforces before writing.
Against it the Task 6 image (firmware.bin 868,572) had 12,068 bytes spare, the built-in
Sub-GHz image (firmware.bin 910,696) was 30,056 bytes over, and the reverted tree
(firmware.bin 868668) has 11972 bytes spare. The Sub-GHz commit 1c113c28a is reverted (the
ruling: option 1) and the docs are corrected in a new project commit; tools/flash_headroom.sh
prints the spare bytes from the build directory.

## Phase B, second attempt (ruling: option 1, Sub-GHz stays external)

Status: DONE_WITH_CONCERNS. The reverted tree (items 1, 2 and the four A2 fixes) is flashed
and verified on the device for everything the ruling asked except the beep scenario, which this
device cannot produce: it is in Stealth mode (the notification Volume item is fixed at
"Stealth", the `buzzer` console command refuses), and no RFID tag was at hand. The device is
idle on the home screen, reader on, speech idle.

### Commits of this attempt

- Firmware 77a57c979 "Revert "screen reader branch: Sub-GHz built into the firmware for memory
  headroom"", body with the reason (SFSA 0xD7, 880,640 bytes; the built-in image 910,360 bytes
  of sections, firmware.bin 910,696) and the true headroom. Build after the revert: .text
  674796, .rodata 192392, .data 1140, .bss 8524; sections 868,328, firmware.bin 868,668,
  firmware.dfu 868,977; 11,972 bytes below the boundary. Sub-GHz is back in
  FLIPPER_EXTERNAL_APPS as /ext/apps/Sub-GHz/subghz.fap. (First committed as 8b2cb753e and
  amended once to fix the built-in image's firmware.bin figure, 910,696 not 910,684: the DFU
  wrapper is a constant 309 bytes.)
- Project 6d8a47b "docs: flash boundary, Sub-GHz stays external": README bullet (Sub-GHz loads
  as an external app, about 2 KB of heap in read mode with the reader on, the frequency
  analyzer crashes out of memory, avoid it while the reader is enabled until phase 3), a
  "Flash limit" paragraph in Useful commands, the spec's section 16 memory paragraph rewritten
  the same way with the boundary and the headroom, and tools/flash_headroom.sh (five lines:
  prints `firmware.bin 868668 bytes, limit 880640, spare 11972 bytes` and exits non zero when
  the image is over). I did both: the README line and the script. (First committed as 2c3e032
  and amended once for mntm-012's figure, firmware.bin 876,900 with 3,740 bytes spare.)
- Report: the "Correction to phase A and A2" section above.

Host runner after the revert: 98 / 0 / 11 cases / 1006 / 94 / 647, all 0 failures, exit 0.

### Idle precondition and flash

Second idle check 21:51:10 to 21:52:11, five samples: no application, announcements 2 at every
sample, speech idle, desktop layer with empty text. /ext/nfc/sr_nfcv_test.nfc present (1157
bytes); /int/.mainmenu_apps.txt does not exist. (The coordinator's later "skip the idle wait"
arrived after this flash had already gone through.)

The generated stamp build/f7-firmware-C/toolbox/version.inc.h still said f2ba8219 from the
no-commit build (lib/toolbox/SConscript regenerates it only when its Value node changes), so I
deleted version.inc.h and version.json before the flash; the rebuilt stamp reads GIT_COMMIT
"77a57c97", BUILD_DIRTY 1 (version.py's `git diff HEAD --quiet` sees the modified submodule).
`./fbt flash_usb` 21:52:32 to 21:53:06, exit 0, package f7-update-mntm-screen-reader-77a57c97
(firmware.dfu 868,977 bytes), tools/flash_headroom.sh spare 11,972. Port gone at 21:53:06,
back after 28.5 s (the refused flash had taken 11 s). First commands after 12 s of settling:

```
== sr screen
records: 1, content layer: desktop
status-right x=103 y=  9 battery    inverted "100"
reads as:
firmware.commit.hash          : 77a57c97
firmware.commit.dirty         : true
== sr status
frames: 27, dropped: 0, announcements: 1, suppressed: 2
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1236 ms played, 50480 subsamples, 821 ms nominal, worker stack free 2396
== loader info
No application is running
```

No crash popup; the hash is the revert's; the frames line has the new `suppressed` field. The
boot spoke one announcement ("Home screen", 1236 ms, 50480 subsamples, the same numbers every
time it is spoken below) and suppressed two desktop changes; the Task 6 image had spoken two
at boot.

### Main menu list file, Sub-GHz once

`storage stat /int/.mainmenu_apps.txt` and `storage read`: "Storage error: file/dir not exist",
so the main menu is built from the firmware tables (FLIPPER_APPS, then FLIPPER_EXTERNAL_APPS),
not from a custom list; a path entry that would launch a card fap by path does not exist.
`loader list` names Sub-GHz exactly once. /ext/apps/Sub-GHz/subghz.fap was left in place as
ruled; it is what the menu entry launches.

### NFC-V file during a long `sr say`, first pass

`sr say` of 138 characters at t=0.12 s, `loader open NFC /ext/nfc/sr_nfcv_test.nfc` at
t=1.16 s. At t=4.0 s the screen read "Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?",
speech was speaking with the speaker held, announcements had risen by one, and the last
completed utterance was 1571 ms: the long say had been cut by the interrupting screen
announcement, which was then being spoken. At t=6.1 s still speaking: the announcement is long
(spelled letters and digits) and the listener, which waits for the speaker mutex, had not
started the emulation yet. Back at t=6.2 s: 0.3 s later speech was already speaking the next
item with the speaker held, the last completed utterance being the Emulating announcement cut
at 4470 ms; at 2.0 s after Back no application was running and the screen was the desktop; at
3.5 s speech was idle and the last utterance was 1236 ms / 50480 subsamples, "Home screen".
Raw counters after this pass: utterances 4, aborted 2, dropped 0, announcements 3, suppressed
3 (the say and the Emulating announcement aborted, nothing dropped). No crash. Because speech
held the speaker for the whole pass, the listener never ran here, so this pass does not answer
the reviewer's question; the second pass does.

### NFC-V second pass, the emulation holding TIM16

Speech idle at the open. `loader open NFC /ext/nfc/sr_nfcv_test.nfc` at t=0.02 s; at t=1.86 s
announcements had risen by one but utterances had not and dropped had gone 0 to 1: the
Emulating announcement polled the busy bus for 500 ms and was dropped, because the listener
had taken the speaker first (the documented "silent emulation when speech was idle at the
open"). The screen read "Emulating. ISO15693-3 (Unk. nown)?. sr_nfcv_test?". `sr say testing
during emulation` at t=3.43 s: 0.3 s later `speech: speaking` (the worker inside its poll),
1.8 s later idle with dropped 2: dropped after the 500 ms poll, utterances unchanged. Back at
t=5.4 s: 0.3 s later speech was speaking with the speaker held and utterances and
announcements had risen by one; 0.8 s later no application was running; 2.1 s later the screen
was the desktop with the dolphin bubble "So long and. thanks for. all the fish!"; 3.5 s later
utterances and announcements were up by two and the last completed utterance was 1236 ms /
50480 subsamples. So after the Back press the "Home screen" announcement was SPOKEN, not
dropped (it started within 0.3 s of the press: the emulate scene stops the listener, which
releases the speaker, before the desktop frame's announcement is even pushed, so the poll had
nothing to wait for), and the bubble that appeared within the 2 s key window after the press
was spoken as a change (3123 ms, 138600 subsamples), as the desktop rule intends. Dropped
stayed at 2 through the Back. Deltas for the pass: utterances +2, aborted 0, dropped +2,
announcements +3, suppressed 0. No crash, Back left the app within 0.8 s.

The two drops are the poll's drop branch of item 1 working as specified (the bus stayed busy
for the whole 500 ms); its wait-then-speak branch could not be shown on this device, see the
beep section.

### Three minute home screen soak

`sr status` every 30 s, seven samples from t=9 s to t=190 s: announcements 6, 6, 6, 6, 6, 6,
6; suppressed 3, 3, 3, 3, 3, 3, 3; utterances 6 throughout; frames 369 to 731 (the dolphin
animation); speech speaking at the first sample (the bubble utterance finishing) and idle
afterwards; no application at every sample. Announcements flat as required. Suppressed did not
rise because no bubble appeared in those three minutes (the boot had produced two, both
suppressed, and the one after the NFC exit fell inside the key window); the rule's suppression
is shown by the boot counters (announcements 1, suppressed 2 at the first `sr status`).

### Up, then the menu

`input send up short` after the soak changed nothing: the screen stayed the empty desktop and
neither announcements nor utterances moved; on this desktop Up short is not bound to a menu
(Momentum's desktop keybinds are user settings; I did not look up what Up is bound to). To
check the intent (a key press after the soak produces an announced menu) I sent OK instead:
the lock menu opened, "Keypad Lock. PIN Code Lock. PIN Lock + OFF" (3 records, desktop layer),
utterances 12 to 13, announcements 12 to 13, 3782 ms played. My exit loop mistook the lock
menu's desktop layer for the home screen and did not press Back, so I closed it with one
explicit Back press afterwards (never OK, which would lock the device): records 0, desktop, no
application, speech idle.

### Beep and announcement: not exercised, Stealth mode

`loader open "LCD and Notifications"`, four Down presses, focus on item 5/6 "Volume" whose
value reads "Stealth": the device has FuriHalRtcFlagStealthMode set, in which the settings app
adds Volume as a fixed single value item without a callback (notification_settings_app.c line
188), so Right and Left changed nothing (focused row still "Volume" "Stealth", no announcement,
no beep; utterances, dropped and aborted unchanged across both presses) and no setting was
touched. The console's `buzzer note C5 300ms` answers "Flipper is in stealth mode. Unmute the
device to control buzzer.", and the notification service's sound path is gated by the same
flag (notification_app.c lines 161 and 171). No RFID tag was at hand. So on this device, as
configured, no beep can be produced without changing Robin's Stealth setting, which I did not
do; the "announcement survives a beep" scenario stays verified by code reading and by the drop
branch above. Note for Robin: while Stealth is on no beep ever holds TIM16, so the read result
was not being silenced in this configuration; the fix matters the moment sounds are turned on.
The settings navigation itself was spoken as expected (five focus announcements, each
interrupting the previous: utterances 6 to 11, aborted 2 to 6).

### Final state

Home screen (records 0, desktop layer), no application, reader on, speech idle, speaker not
held; counters at the end: frames 791, dropped frames 0, announcements 13, suppressed 3,
utterances 13, aborted 6, dropped 2, underruns 0, queue dropped 0. No crash popup at any point,
the console answered every command, the device rebooted only for the flash.

### Concerns

1. The beep scenario of A2 item 1 is unverified on hardware because of Stealth mode; if Robin
   wants sounds, turning Stealth off and reading a tag (or `buzzer note C5 300ms` followed at
   once by `sr say hello`, expecting utterances to rise and dropped not to) would show it.
2. Up short does nothing on this desktop and OK opens the lock menu; phase 3's hotkey work
   should read the desktop keybind settings rather than assume the official layout.
3. My first checks script mis-parsed the speech counters (the line has no colons and the
   frames line's `dropped:` is the dropped frames counter) and stopped after the first NFC-V
   pass; the second script fixed the parser and ran the rest. Nothing on the device was
   affected.
4. Fourteen update package directories sit under /ext/update, including the refused
   f2ba8219 one (about 1 MB each); harmless, could be cleaned up later.
5. The two amended commits (revert, docs) changed hashes once each before anything was flashed
   or pushed; the device carries 77a57c97 and nothing is pushed.
