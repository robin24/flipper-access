# Task 10 report: build, flash, verify, prune, and the notes

Status: **DONE_WITH_CONCERNS**. Every expectation of the brief was met: the device runs a0dea084, clean,
as Sonar; the card is pruned; the chord session found no failures; the notes and measurements are
pushed. The concerns are two things the flash revealed on the device, below. Concern 1 is a real
defect in the fork: an update can overwrite the user's Momentum settings with the defaults.

## Commits

Firmware (`Momentum-Firmware`, branch `screen-reader`, pushed to `origin` only):
- `a0dea0841` A fresh device starts with the List menu style, the one the screen reader can follow
  (pathspec `-- lib/momentum/settings.c`; pushed c0ba0af07..a0dea0841)

Project (`main`, pushed):
- `fecdc36` Firmware at the List menu default (pathspec `-- Momentum-Firmware`; pushed 358ab3f..fecdc36)
- `263dfd7` Plan A on the device: Sonar flashed clean, the card pruned, the notes and measurements
  (pathspec: the brief's three files plus `README.md` and the spec, per ruling 4; pushed fecdc36..263dfd7)

Each ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

The settings.c line is now
`.menu_style = MenuStyleList, // List: the only style whose focus the screen reader can name`
(95 columns, within the 99 of `.clang-format`). Nothing else in the firmware assumes the DSi
default: `MenuStyleDsi` appears only in `menu.c`'s drawing cases.

CI:
- Run 36218194579, on fecdc36: success in 9 min 23 s. Headroom line `firmware.bin 864576 bytes,
  limit 880640, spare 16064 bytes`; artifact `sonar-ci-a0dea084`, 12,044,002 bytes.
- Run 36219689259, on 263dfd7: in progress when I finished. The commit changes docs only.

## Step 1: the clean release build (ruling 2)

`git -C Momentum-Firmware status --short` printed nothing. Then `rm -rf Momentum-Firmware/build`
and `./fbt COMPACT=1 DEBUG=0 updater_package` ran from 06:34:08 to 06:36:43 (155 s), exit 0.
Its last five lines:

```
2026-09-26 06:36:38,837 [INFO] Use this directory to self-update your Flipper:
	dist/f7-C/f7-update-mntm-screen-reader-a0dea084
2026-09-26 06:36:39,101 [INFO] Bundling SDK
2026-09-26 06:36:40,975 [INFO] SDK bundle can be found at:
	dist/f7-C/flipper-z-f7-sdk-mntm-screen-reader-a0dea084.zip
```

- fbt printed "API version 87.3 is up to date" and no warning about the API table. The other
  warnings were the two known manifest warnings (cli_bridge `.cli_gui`, mtp `.f0_mtp`), each
  printed twice, and 20 compiler warnings. All 20 are in the external apps' own sources: the asn1
  code of seader, picopass and passy, flipboard, airmouse and mitsubishi_ac_remote. None is in
  our code, and there was no error line. The tree was still clean after the build.
- The headroom check, `tools/flash_headroom.sh`, exited 0. The spare is well above zero:

  ```
  firmware.bin 864564 bytes, limit 880640, spare 16076 bytes
  ```

  That is the same size as 6451e86e8's image. The md5 is `b47ad493eb0f5b6cf3c10b7d93848a08`.
- `dist/f7-C/`: `flipper-z-f7-update-mntm-screen-reader-a0dea084.tgz`, 12,039,391 bytes, and the
  folder `f7-update-mntm-screen-reader-a0dea084`. The folder holds `resources.tar.gz` (11,264,856
  bytes), firmware.dfu, firstboot.bin, radio.bin, splash.bin, update.fuf and updater.bin.

## Step 2: the flash

- Before it (06:37:29): no application running. `info device` gave 6451e86e, dirty true, origin
  Momentum. `/ext/update` held three folders. `sr status` read volume 40, free heap 109,840.
- `./fbt COMPACT=1 DEBUG=0 flash_usb_full` ran from 06:37:44 to 06:39:57, exit 0. It rebuilt the
  resources and the package: `resources.tar.gz` became 11,265,310 bytes and the .tgz 12,038,653.
  firmware.bin was unchanged, with the same md5. Its last lines were the upload's progress line
  for updater.bin, ending `<100%, chunk 15 of 15 @ 141.87 kb/s`, then
  `2026-09-26 06:39:54,497 [INFO] Closing current app, if any` and `Touch("build/usbinstall.flag")`.
- Port watch (polled every second): port gone at 06:39:55, back at 06:46:39, steady at 06:47:09.
  The update took **404 s (6 min 44 s)** with the port gone. The whole flash, from the command to
  the port's return, took **535 s (8 min 55 s)**.

At 06:47:17, before any key press:

```
== sr screen
records: 0, content layer: desktop
reads as: 
== info device   (the firmware lines and two system lines only; the hardware and radio lines are left out)
firmware.commit.hash          : a0dea084
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
system.debug                  : 0
system.log.level              : 1
== sr status
enabled: yes
last crash: at 2001384F in build 9028a849
volume: 30, verbosity: 1, change delay: 3000 ms
frames: 2, dropped: 0, announcements: 1, suppressed: 0
speech: idle, queued 0, speaker held: no, utterances 1, aborted 0, dropped 0, underruns 0, queue dropped 0
last utterance: 1089 ms played, 15972 subsamples, 998 ms nominal, worker stack free 2516
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 2, fallback 0, missing 0, muted 0, open max 27 ms, last 27 ms
free heap: 115864
```

- `a0dea084` equals the first eight characters of the submodule's HEAD, `a0dea08418ac...`. The
  build is dirty false, fork Sonar, git robin24, API 87.3, and the reader is enabled with the
  voice on and the Samantha line. All match the brief.
- `sr screen` found no records on the desktop layer. That is the post-update slideshow, exactly
  as after the 2026-09-25 flashes, not a crash popup: no crash text, and the only utterance was
  the boot's "Home screen" (15,972 subsamples).
- I then sent `input send back short`, which closed the slideshow, as the README and the earlier
  flashes do. `sr screen` then read `records: 1, content layer: desktop` with the battery `"100"`
  only: the home screen, with no application running.

## Step 3: the card

`/ext/apps/Media` holds `text2sam.fap 29100b`: the stock build, not the patched 30,200.
`/ext/apps/assets` holds `passport.fap 4364b`. Both are byte-for-byte the size of this build's own
faps in `build/f7-firmware-C/.extapps` and `resources/apps`. The full listings are in the
measurements file.

`/ext/update` counts:
- Task 3 found 37 folders, removed 34 and kept 3.
- Before this flash there were 3.
- After this flash there were 4:
  `f7-update-1.4.3`, `f7-update-mntm-012`, `f7-update-mntm-screen-reader-a0dea084` and
  `f7-update-mntm-screen-reader-6451e86e`.

I ran a dry run first; its plan was exactly as expected. Then the real prune:

```
running build a0dea084; 4 folders in /ext/update; keeping 3: f7-update-1.4.3, f7-update-mntm-012, f7-update-mntm-screen-reader-a0dea084
removing f7-update-mntm-screen-reader-6451e86e
removed 1 folders
== storage list /ext/update
	[D] f7-update-1.4.3
	[D] f7-update-mntm-012
	[D] f7-update-mntm-screen-reader-a0dea084
```

It took 0.67 s. What remains is the two rollback packages and the new build's folder only.

## Step 4: the workout

`tools/sr_drive.py --chords`: **0 failures**, exit 0. All eight chords, four on the home screen
and four in the main menu, spoke once and left the screen as it was. The menu opened in the List
style with its focus marked: `fullscreen, FOCUS 1/11 "Apps", reads as: Settings. Sub-GHz. Apps, 1 of 11`.
It ended on the home screen.

Afterwards, `sr status` read:
- `frames: 42, dropped: 0, announcements: 4, suppressed: 0`
- `utterances 12, aborted 0, dropped 0, underruns 0, queue dropped 0`
- `free heap: 116512`

`free`: `Free heap size: 116584`, minimum 103,408, largest block 116,256. That is within the
usual idle range.

## Steps 5 and 6: the notes, the measurements, the commit

`docs/measurements/2026-09-26-plan-a.txt` is new: plain prose lines between verbatim blocks, no
tables. It holds:
- the build and headroom
- the flash, with its times and the port watch
- the post-flash blocks. In `info device` it keeps the firmware lines and leaves out the hardware
  UID and the BLE MAC, following the stripdown file.
- the Debug flag and the settings findings
- the card before and after the prune, with Task 3's counts
- the chord session, `sr status` and `free`

`docs/device-notes.md`:
- The firmware line is rewritten for a0dea0841: flashed complete from a wiped build folder,
  reporting Sonar and clean, 864,564 bytes with 16,076 spare. The older history was condensed
  into one sentence, which also settles the Task 5 review's deferred note on the twelve-sentence
  bullet.
- The size history has a new top entry.
- The menu line now says Sonar's default is List since a0dea0841. It no longer claims lock on boot
  is off: see concern 1.
- The crash catcher bullet and the Crash diagnosis sentence now say that a release update turns
  the Debug flag and the log level off.
- The Routine has a new step 6 that sets the two again. The old steps 6 and 7 are now 7 and 8;
  nothing refers to them by number.
- The Measurements list has the new file.

`docs/roadmap.md`:
- The 2026-09-26 status now says plan A is done. It names card_prune.py, strip_js_symbols.py,
  subghz_manifest.py, upstream_check.sh and the Build workflow, and gives the device's build.
- Under Keeping the delta small, the two sentences now say merges, not rebases (ruling 3):
  - "so merges from Momentum stay mechanical"
  - "runs on every push, so also on the submodule bump that follows each merge from Momentum"

`README.md`: the Known-limits bullet on the List style is removed (ruling 3). The List style is
not mentioned anywhere else in the README, so no descriptive sentence was left to keep.

`docs/superpowers/specs/2026-09-26-github-release-design.md`, section 8:
- The API version rule now has the ruling's wording, with backticks on `FORK_MINOR_STEP` and
  `tools/strip_js_symbols.py` as elsewhere in the spec.
- Beyond ruling 3: two lines above, the strip_js_symbols bullet said the script "sets the version
  to upstream's major and minor plus one". That contradicted the new rule, so it now says "sets
  the version by the API version rule below".

`tools/run_host_tests.sh` passed, exit 0, all 13 lines green. After the push both trees were clean
and level with `origin`.

## Deviations and actions beyond the brief

1. **I ran the prune as a dry run first**, then for real. The dry run's plan matched.
2. **Back closed the post-update slideshow** after `sr screen`. This is the documented routine,
   and without it the chord session would start on the slideshow, not the home screen.
3. **I restored the crash catcher's settings**: `sysctl debug 1` and `sysctl log_level debug`, the
   command in device-notes.
   - The updater of a release build clears both. `update_task_worker_flasher.c` sets the log
     level to none at line 352 and clears the Debug flag at line 353, in its `#else // Production`
     branch.
   - After the flash, `info device` read `system.debug : 0` and `system.log.level : 1` (none).
   - The UART capture has logged nothing since 2026-09-25 at 20:16:02, the RAM updater's last
     line during last night's flash of 6451e86e8. So the crash catcher had been blind since then,
     not just since today.
   - Once the settings were set, the capture got lines at once (06:57:34). Its process, PID 90851,
     never stopped.
   - I judged this restores the documented state the binding rules assume ("records its debug
     console"). It is reversible with `sysctl debug 0`.
4. The doc edits beyond the brief and the rulings, listed above: the spec's "plus one", the
   device-notes menu, crash-catcher, routine and measurements entries.

## Concerns

1. **An update can reset the Momentum settings to their defaults.** This happened to Delphi here.
   - What changed: after the flash, `/int/.momentum_settings.txt` differs from the copy inside the
     update's own backup (`/ext/update/f7-update-mntm-screen-reader-a0dea084/backup.tar`, taken at
     the update's start). Four keys differ:
     - `lock_on_boot`: true now, false in the backup.
     - `dark_mode`: false now, true in the backup.
     - `rpc_color_bg`: 4286709760 now, 16777215 in the backup.
     - `sr_volume`: 30 now, 40 in the backup.

     Every key now holds its compiled default except `sr_volume`, whose default is 100.
   - Why the file must have been written during the post-update boot: a load clamps
     `rpc_color_bg` to 0xFFFFFF, so the default 0xFF820000 can only reach the file from settings
     that were never loaded. In that special boot, `/int` has just been wiped (flasher line 345),
     and the load at card mount finds no file, so RAM holds the defaults. The updater then
     restores `/int` and unpacks the resources for minutes. Any settings save in that window
     overwrites the restored file.
   - What saved it: nothing saves by itself. The saving paths are the Momentum app on exit, the
     lock menu, and the reader: the volume chord (±10 each), the toggle chord, and the console's
     sr on, off, volume and delay. Seven Back+Left chords turn 100 into exactly 30. The console
     was gone during the update and I sent no keys, so a person pressing keys on the device is the
     likeliest explanation. That is very possibly Robin, turning the reader down, since it spoke
     the updater's screens at the default volume 100.
   - Why this is new: the reader has been on by default since c00eed5c9 (Task 4), so it now runs
     in that boot. The flashes of 2026-09-25 kept the settings, when it was off by default.
   - Impact: every user who touches the volume, or toggles the reader, during an update loses
     their Momentum settings, and hears the update at volume 100 regardless of their setting.
   - A possible fix (not made; outside this task): have `momentum_settings_save()` do nothing when
     `!furi_hal_is_normal_boot()`. Alternatively the reader could skip saves, or chords, in a
     special boot.
   - Delphi now: menu style List and the reader on are intact, since they coincide with the
     defaults. Lock on boot is on, but it acts only with a PIN, and none is set. Dark mode is off.
     The volume is 30.
   - **I did not restore the old values**; that is for Robin or you to decide. The backup with them
     stays on the card in the running build's folder, which the prune keeps. device-notes now says
     so instead of "lock on boot off".
2. The README no longer says anywhere that other menu styles lose the focus hint. A user who
   picks the grid gets no warning. A sentence under First boot could say the menu starts in the
   List style, the one the reader follows.
3. Minor points:
   - This build is 12 bytes smaller than CI's image of the same commit (864,564 against 864,576),
     the same gap as at c0ba0af07. It is unexplained, probably strings, and harmless.
   - The device-notes routine still wipes only `resources` and `.extapps`. The whole-folder wipe
     was this task's ruling; I left the routine as it was.
