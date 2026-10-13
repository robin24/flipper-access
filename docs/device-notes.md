# Device notes: Robin's Flipper

These are the working notes for the one device Sonar is developed on, and the developer's routine.

## Device state

- Device name: R0skie, its factory name, again since 2026-10-09, when the card was erased: Momentum
  keeps the name on the card. It was Delphi from 2026-09-25. Hardware version 12, region DE. 64 GB
  microSD card, exFAT, formatted on the device on 2026-10-09.
- Firmware: Momentum mntm-012, built 31 December 2025, installed 2026-09-22 from the terminal.
  Before that it ran official firmware 1.4.3. Since then it runs the `screen-reader` branch built
  here: phase 3 and the polish round on 2026-09-24, the firmware stripdown and the features after it
  on 2026-09-25, the publishing plan A's a5c2ed7d9 and then plan B's 86820a7db, with the voice sets,
  on 2026-09-26. On 2026-09-29 it got b9c87352c, the merge of the fixes after the review of
  2026-09-28, the first build on the new MacBook. On 2026-09-30 it got 4b56919df, on the fork's
  branch `claude/device-checks-2026-09-30`: those fixes with F2 corrected, so the settings are saved
  only once they were read from the card. On 2026-10-01 it got f37f06887 and then 0294fe871, on the
  fork's branch `claude/reading-fixes-2026-10-01`: that day's screen-reading fixes, then the crash
  address of hardware faults. On 2026-10-02 it got ea05c6d94 on the same branch, with the fixes
  after that day's review, then 778d09f8f on the branch `claude/card-settings-2026-10-02`, with the
  settings read after a card change or a format. On 2026-10-03 it got f9782c740, the merge of that
  branch into `screen-reader`, then 44e1d8e83 on the branch `claude/c64-menu-2026-10-03`, with the
  C64 menu style's numbers apart from the names. From 2026-10-03 it ran 59878faeb, the merge of that
  branch into `screen-reader`, whose files are 44e1d8e83's. On 2026-10-09 the card was erased and
  the device set up again from nothing, as a new user would with the README; since then it runs
  9149fe493, on the fork's branch `claude/device-checks-2026-10-09`, with that day's fixes: the
  flash on a blank card, every slash read as "slash", no first boot tutorial, the update picture
  spoken, and its view's crash fixed. It was flashed complete with `./fbt flash_usb_full`. It
  reports itself as Sonar and clean, with API version 87.3: `firmware.origin.fork : Sonar` and
  `firmware.commit.dirty : false`. firmware.bin is 870,172 bytes, 10,468 spare below the BLE stack.
  The apps on the card, the Passport among them, came with it. The earlier images are listed under
  Useful commands. The checks on the device after the review fixes are in
  `docs/measurements/2026-09-29-review-fixes.txt`, and those of 2026-10-01 in
  `docs/measurements/2026-10-01-remaining-items.txt`, and those of 2026-10-09 in
  `docs/measurements/2026-10-09-device-checks.txt`.
- Serial port on this Mac: `/dev/cu.usbmodemflip_R0skie1` since 2026-10-09, and
  `/dev/cu.usbmodemflip_Delphi1` while the device was named Delphi, at 230400 baud. It disappears
  while the device is in the updater and comes back after the reboot. Without the card it is R0skie
  again, since Momentum keeps the name on the card.
- Menu style List, set in `/int/.momentum_settings.txt`. `/int` is the folder `/ext/.int` on the
  card: Momentum has no internal storage of its own, so without the card the settings file is
  neither read nor saved. The Debug flag and the log level are kept in the clock's registers
  instead, and stay. The reader marks the main menu's focus only in the List style; the other styles
  are read by inversion where possible. Momentum's default style is DSi; Sonar's is List since
  a0dea0841. Since the card was erased on 2026-10-09 the file holds the defaults, the reader's
  volume apart, which Robin set to 40: lock on boot on, Momentum's default, which acts only with
  a PIN; dark mode off; the voice set Auto, the first set by name, which is espeak after a boot.
  Before, the file had lock on boot off, dark mode on, the volume at 40 and the voice set
  samantha. The first update of 2026-09-26, to a0dea0841,
  left it at its defaults, the volume apart, because keys pressed during the update saved the
  settings in RAM over the restored file: see `docs/measurements/2026-09-26-plan-a.txt`. The three
  values were restored from that update's `backup.tar`, and the device rebooted. Since 3bdcca70c the
  firmware saves no settings in an update boot, so a key pressed during an update no longer
  overwrites the file. Lock on boot acts only when a PIN is set, and none is.
- The Text to SAM app on the card is Momentum's stock build again since 2026-09-26; the patched
  build and tools/say.sh were retired, since the reader speaks from its own engine.
- The games, the JavaScript runner and its modules, and the screen reader's own SAM synthesizer
  are gone from the firmware and the card as of the stripdown round. The reader now speaks only
  from the recorded voice's clips. See Known limits and The voice in the README.
- Sub-GHz is built into the firmware again, not loaded from the card, and works with the reader
  on: Read keeps 53,064 bytes free at its lowest and the Frequency Analyzer 51,136, where it used
  to crash the device out of memory. The other main apps still load as external faps: NFC, RFID,
  infrared, iButton, GPIO, Bad USB and U2F. NFC read is now the heaviest, 23,232 bytes free.
- The Wi-Fi dev board sits on the GPIO header, with its own USB-C cable in the Mac, as the crash
  catcher. The Debug flag is on and the log level is debug, both kept across reboots, and
  `tools/uart_log.py` captures the debug console in the background. An update to a release build
  turns both off, so step 6 of the Routine sets them again. See Crash diagnosis. The board was not
  at hand for the checks of 2026-09-29 and 2026-09-30, nor on 2026-10-09, so no UART capture ran
  then, and the Debug flag and the log level are off since that day's flashes.
- The old project folder is gone, and with it `voice/`, `voices/`, `voice-models/`, `backups/`,
  `firmware-packages/` and `tools/voice_words.local.txt`. The project was cloned again on the
  MacBook on 2026-09-29, and the local word list made again with `delphi`. The samantha set was
  made again there on 2026-10-01: see The voice on this card.
  Since the card was erased on 2026-10-09 it holds neither the rollback packages nor any backup.
  The official 1.4.3 and Momentum mntm-012 packages are on the Mac in `firmware-packages/`, and the
  stock backup in `backups/backup-stock-1.4.3.tar`; the card's backup of 2026-09-29 is gone.

## The folders and tools

- `tools/flipper_cli.py`: send commands to the Flipper CLI and print the replies with colour codes
  stripped. For example:

  ```bash
  .venv/bin/python tools/flipper_cli.py "info device" "loader list"
  ```

- `.venv/`: Python virtual environment with the packages of `requirements.txt`, used by the
  helper scripts; on the MacBook since 2026-09-29 with Homebrew's Python 3.13. Not in git.
- `Momentum-Firmware/`: the firmware, a git submodule on the fork's branch `screen-reader`, with
  the ARM toolchain that fbt downloaded. API version 87.3 since 2026-09-25, which exported
  `canvas_tap_hint_note_at` for words placed among the drawn text; 87.2, since phase 3, exported
  two calls for the screen reader's spoken names of icons. Apps built here run on the device, and
  apps built for 87.1 and 87.2 still load.
- `firmware-packages/`: Momentum mntm-012 and official 1.4.3 update packages, both also unpacked.
  Not in git. Gone with the old project folder; the card keeps both packages in `/ext/update`,
  and both can be downloaded again.
- `backups/backup-2026-09-29.tar`: internal storage backup taken with `update backup` before the
  flash of 2026-09-29, on 86820a7db: the ten files of `/int`, the settings among them. Its copy is
  `/ext/backup-2026-09-29.tar` on the card. Not in git.
- `backups/backup-stock-1.4.3.tar`: internal storage backup taken on official 1.4.3 before the
  Momentum install, with the settings, the dolphin state and the region data. Not in git since
  2026-09-26. Copied back from the card's root on 2026-09-29, after the old folder was gone.
- `tools/sr_drive.py`: scripted check of the screen reader console stream, and with
  `--interactive` a tethered screen reader. In that mode arrows, Enter and Backspace drive the
  device, Tab reads the screen, letters type into text fields, and Ctrl-C ends. The scripted check
  has three sessions: the menus, an app's keyboard, and the Back chords on the home screen and in
  the main menu. `--chords` runs only the chords. Start it on the home screen.
- `tools/run_host_tests.sh`: unit tests for the screen model, the speech text, queue, PCM and
  voice helpers, the chords and the change throttle, and for Momentum's settings file, built
  against stand-ins for the card in `tests/host/stubs`. They run with clang on the Mac, and the
  Python checks in `tests/fbt/` follow. The voice pack's check also unpacks a pack with the
  firmware's own tar reader, `tests/host/tar_unpack.c` built from the firmware's `lib/microtar`,
  following the device's rules; it is skipped until fbt has checked out that submodule. Some
  Python checks need the packages of `requirements.txt` and are skipped without them. With
  `--no-skips`, as the continuous build runs it on Python 3.10, a skipped check fails the run.
- `tests/host/`: the unit tests.
- `tests/fbt/test_exclusions.py`: a plain Python test of the build's app and category exclusions,
  `EXCLUDE_EXT_APPS` and `EXCLUDE_EXT_CATEGORIES` in `fbt_options.py`, over synthetic manifests.
- `tests/fbt/test_subghz_sources.py`: a plain Python check that every `.c` file of the built-in
  Sub-GHz app is named in its manifest, `applications/main/subghz/application.fam`, and every
  named one exists. So a Momentum update cannot leave a new scene out of the build unnoticed.
- `tests/fbt/test_card_prune.py`: a plain Python test of `tools/card_prune.py`'s rule over
  synthetic folder lists.
- `tools/card_prune.py`: removes the fork's old update packages from `/ext/update` on the card,
  those of the claude/ work branches included, keeping the running build's folder and every
  package of another firmware, such as the two rollback packages; `--dry` lists what would go.
- `tools/flash_headroom.sh`: the image size against the flash the BLE stack leaves free; see
  Useful commands.
- `tools/momentum-base.txt`: the Momentum commit the fork builds on, the merged release tag's.
  The golden checks of the host tests compare the fork's API table and Sub-GHz manifest with
  Momentum's at that commit, which the continuous build fetches alone. `tools/momentum_base.py`
  reads it; see Merging Momentum.
- `tools/ram_probe.py`: free heap while each core app runs; the logs are in `docs/measurements/`.
- `tools/uart_log.py`: captures the debug console through the Wi-Fi dev board; see Crash
  diagnosis. `tools/flipper_log.py` captures the USB console's log stream instead, until the port
  drops; the UART capture replaced it for the crash hunt.
- `tools/map_size.py`: flash and static RAM per library, app or object, from the firmware's
  linker map.
- `tools/voice_build.py`: makes the recorded voice and copies it to the card; see The voice in the
  README. `tools/clip_make.py` makes a single test clip with the same processing.
- `tools/voice_words.txt`: the base word list. `tools/voice_names.txt`: the spoken names of the
  letters that spell a word without a clip.
- `tools/voice_words.local.txt`: personal words, one per line, here the device's name. Not in
  git; see Routine.
- `voice/`: the built vocabulary, not in git. Do not delete it; see The voice in the README.
- `docs/`: the specs, plans, build logs, measurements, the roadmap and these notes;
  `docs/README.md` is the index.

## Routine

The flash routine, run from the project folder:

1. Wipe the build folder. Before a release build, and after a merge from Momentum, wipe all of
   it. A build then uses nothing an earlier build left behind: a stale `libmjs.a` once let builds
   here pass that failed from a clean checkout.

   ```bash
   rm -rf Momentum-Firmware/build
   ```

   For an everyday build, wiping the resources and apps is enough, so nothing an earlier build
   left there reaches the card:

   ```bash
   rm -rf Momentum-Firmware/build/f7-firmware-C/resources Momentum-Firmware/build/f7-firmware-C/.extapps
   ```

2. Build the update package. The release options, `COMPACT=1` and `DEBUG=0`, are fbt's defaults:

   ```bash
   (cd Momentum-Firmware && ./fbt updater_package)
   ```

3. Check the image against the flash that the BLE stack leaves free, 880,640 bytes with the
   current stack:

   ```bash
   tools/flash_headroom.sh
   ```

4. Flash the firmware with its resources. The device then takes about six minutes to update; the
   serial port disappears during the update and comes back after the reboot:

   ```bash
   (cd Momentum-Firmware && ./fbt flash_usb_full)
   ```

5. Before any key is pressed, read the screen from the console, so a crash popup is seen before a
   key closes it:

   ```bash
   .venv/bin/python tools/flipper_cli.py "sr screen"
   ```

6. Turn the crash catcher back on. The updater of a release build turns the Debug flag off and
   the log level to none, and the UART capture then records nothing:

   ```bash
   .venv/bin/python tools/flipper_cli.py "sysctl debug 1" "sysctl log_level debug"
   ```

7. Remove the old update packages from the card. Add `--dry` to see first what would go:

   ```bash
   .venv/bin/python tools/card_prune.py
   ```

8. Give the words the device had to spell their own clips, with the generator's routine command:

   ```bash
   .venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync
   ```

The generator reads `tools/voice_words.local.txt` beside `tools/voice_words.txt` whenever it
exists. The local list holds personal words, one per line: here the device's name, `delphi`. It
is not in git, so the public word list names no one's device. On another device, its name reaches
the vocabulary through the missing-words list like any other word. `--words` with a file name adds
further lists, and can be given more than once.

## Merging Momentum

The fork follows Momentum by merging its release tags into `screen-reader`, never by a rebase.
Run the steps from the project folder; mntm-013 stands for the tag to merge.

1. Fetch Momentum's branches and tags. The first time, add Momentum as the remote `upstream`,
   which a fresh clone of the project lacks:

   ```bash
   git -C Momentum-Firmware remote add upstream https://github.com/Next-Flip/Momentum-Firmware.git
   git -C Momentum-Firmware fetch --tags upstream
   ```

2. See what the merge would meet: the new commits, the files changed on both sides, and the
   conflicts of a dry run.

   ```bash
   tools/upstream_check.sh --upstream mntm-013
   ```

3. Merge the tag into `screen-reader`, without committing yet:

   ```bash
   git -C Momentum-Firmware merge --no-commit mntm-013
   ```

4. The API table: if it conflicts, take Momentum's side. Then run the script in any case, since
   it also removes a JavaScript line that merged without a conflict. It sets the version to the
   merged table's own with the fork's step added, so a table that already has the fork's version
   keeps it.

   ```bash
   git -C Momentum-Firmware checkout --theirs targets/f7/api_symbols.csv
   tools/strip_js_symbols.py
   git -C Momentum-Firmware add targets/f7/api_symbols.csv
   ```

5. The Sub-GHz manifest the same way. The script also lists a file that Momentum added without
   touching its manifest. Taking upstream's file whole loses the fork's comment above the source
   list, which explains why the files are listed one by one. Restore it from
   `git -C Momentum-Firmware show HEAD:applications/main/subghz/application.fam` after running
   the script.

   ```bash
   git -C Momentum-Firmware checkout --theirs applications/main/subghz/application.fam
   tools/subghz_manifest.py
   git -C Momentum-Firmware add applications/main/subghz/application.fam
   ```

6. Resolve any other conflict, and commit the merge. Then pin the merged tag's commit as the
   fork's base in `tools/momentum-base.txt`: the golden checks of the host tests, the next
   command and the continuous build compare with Momentum's files at that commit. Then compare
   the script's exclude list with Momentum's new manifest. On a difference, update `EXCLUDED` in
   the script, run it again and commit the result.

   ```bash
   git -C Momentum-Firmware commit -m "Merge Momentum mntm-013"
   git -C Momentum-Firmware rev-parse "mntm-013^{commit}" > tools/momentum-base.txt
   tools/subghz_manifest.py --verify-upstream
   ```

7. Run the host tests. They fail while the pin is older than the merge base with upstream/dev or
   is one of the fork's own commits.

   ```bash
   tools/run_host_tests.sh
   ```

8. Wipe the whole build folder, so nothing from before the merge is linked. Then build and check
   the headroom:

   ```bash
   rm -rf Momentum-Firmware/build
   (cd Momentum-Firmware && ./fbt updater_package)
   tools/flash_headroom.sh
   ```

9. Flash the build with steps 4 to 7 of the Routine. Then run the RAM probe and the reader's
   scripted check, and try the chords and a few screens by hand as the README describes them.

   ```bash
   .venv/bin/python tools/ram_probe.py
   .venv/bin/python tools/sr_drive.py
   ```

10. Push `screen-reader` and bump the submodule in the project, in one commit with the new pin,
    since the continuous build compares the new firmware with the pinned commit. Then tag the
    release on both repositories, as section 7 of the release spec describes.

## Making a release

A release is made in two parts. The workflow `.github/workflows/release.yml` builds the firmware
from a pushed tag and leaves a draft release with six assets. This Mac then adds the one voice
pack, the checksums and `release.json`, and the draft is published by hand. Run the steps from the
project folder, but for step 6 and the first part of step 7, which run in the folder of the
download. `sonar-0.1.0` stands for the tag and `0.1.0` for its version; for a release candidate the
tag is `sonar-0.1.0-rc1` and the version is `0.1.0-rc1`.

1. Write the release's entry in `CHANGELOG.md` first: its version, with the day of the tag in place
   of `YYYY-MM-DD`, and what the release changes, since the release notes send readers to the
   changelog at the tag. A release candidate's tag has the entry of the version it leads to, and the
   final tag the same entry with its own day. The README's commands name the version too, so update
   them with the entry; the host tests, which the build runs, fail when they differ. Merge the entry
   into `main` with a pull request, as every change. The project's commit to tag is the merged
   commit on `main` whose submodule pointer is the fork's commit to tag, so check that commit out,
   with the submodule on the commit it records:

   ```bash
   git switch main
   ```

   ```bash
   git pull
   ```

   ```bash
   git submodule update Momentum-Firmware
   ```

   `git status` must then show no change for `Momentum-Firmware`. Tag the fork's commit and push
   the tag, then tag the project with the same name and push that tag, which starts the workflow.
   The workflow fails before the build unless the fork has the tag on the recorded commit, and it
   fails if a release of the tag exists already, a draft included.

   ```bash
   git -C Momentum-Firmware tag -a sonar-0.1.0 -m "sonar-0.1.0"
   git -C Momentum-Firmware push origin sonar-0.1.0
   git tag -a sonar-0.1.0 -m "sonar-0.1.0"
   git push origin sonar-0.1.0
   ```

2. When the workflow has finished, the draft lists the update package, the install zip, the elf
   and its map, the SDK and the source bundle:

   ```bash
   gh release view sonar-0.1.0
   ```

3. Make the voice pack by its explicit name. Heart is the only voice pack a release ships, and the
   default voice. The generator's set `heart` must be complete in `voices/heart`. The pack is
   written to the project folder as `voice-heart-sonar-0.1.0.tar`, which is `voice-heart-<tag>.tar`,
   and is about 111 megabytes:

   ```bash
   .venv/bin/python tools/voice_pack.py --set heart --version 0.1.0
   ```

4. Upload the pack to the draft:

   ```bash
   gh release upload sonar-0.1.0 voice-heart-sonar-0.1.0.tar
   ```

5. Finish the draft. The tool downloads every asset of the draft again, so that the checksums are
   those of the bytes a user will download. It checks that the draft holds the seven assets of a
   release and no other file, and reads the voice of the pack from its own `voice.txt`. It takes
   the fork's commit and the Momentum base from the tag, and the API version from the fork's
   table at that commit. It then writes `SHA256SUMS` and `release.json` and uploads both with
   `--clobber`, so it can be run again. It uses only Python's standard library and the `gh`
   command, signed in:

   ```bash
   tools/release_finalise.py sonar-0.1.0
   ```

   It refuses, with one sentence and without uploading anything, when an asset is missing, when a
   second voice pack or another file is in the draft, when the pack was made with a backend other
   than kokoro or espeak, when the tag is not in this checkout, and when the release is published
   already. Add `--dry` to see the two files first; it still downloads, and uploads nothing:

   ```bash
   tools/release_finalise.py sonar-0.1.0 --dry
   ```

6. Download the draft as a user would, into a folder that does not exist yet, outside the project
   folder. `mkdir` refuses a folder that is there already, so no file of an earlier try is checked
   by mistake:

   ```bash
   mkdir /tmp/sonar-0.1.0-check
   ```

   ```bash
   gh release download sonar-0.1.0 --dir /tmp/sonar-0.1.0-check
   ```

   The commands of this step and of step 7, up to its last checks, run in that folder:

   ```bash
   cd /tmp/sonar-0.1.0-check
   ```

   Check the files against `SHA256SUMS`. Each of the seven assets should say OK; `SHA256SUMS` and
   `release.json` are not among the checksums. Every asset was downloaded, so the check has no
   `--ignore-missing`, and an asset that is missing fails it:

   ```bash
   shasum -a 256 -c SHA256SUMS
   ```

7. Install the draft's own files on the Flipper, as the README's Install describes, so that the
   release is the binary that was tested (review of 2026-09-28, R7) and the release notes'
   promise holds: "Before it was published, this release's own files, downloaded from this page,
   were installed on a Flipper with the install script and checked there." Unpack the install zip:

   ```bash
   unzip install-sonar-0.1.0.zip
   ```

   Make a virtual environment with pyserial there, as a user does. `python3` must be 3.10 or
   newer:

   ```bash
   python3 -m venv .venv
   ```

   ```bash
   .venv/bin/pip install pyserial
   ```

   Install with that folder's `install.py`, which uses that folder's helpers, and answer its
   questions as a user would. Over USB it takes about half an hour:

   ```bash
   .venv/bin/python install.py --package flipper-z-f7-update-sonar-0.1.0.tgz --voice voice-heart-sonar-0.1.0.tar --release release.json
   ```

   Near its end the script says "The Flipper runs the firmware of the release.", then the lines of
   the prune: one for each older update package it removes and one with how many it removed, or
   "There are no older update packages to remove.". Its last line is "Done, after" with the time it
   took, such as 32 minutes. Then check on the Flipper. `info device` gives the tag as
   `firmware.version`, `sonar-0.1.0`; as `firmware.commit.hash`, the first 8 characters of the
   release's commit, `firmware_commit` in `release.json`; `firmware.commit.dirty` false; and
   `firmware.origin.fork` Sonar. Copy none of its other lines into a committed file, since they
   name the device:

   ```bash
   .venv/bin/python flipper_cli.py "info device"
   ```

   The prune keeps the running build's folder: its first line names `f7-update-sonar-0.1.0` among
   the folders it keeps, and no line says "would remove f7-update-sonar-0.1.0":

   ```bash
   .venv/bin/python card_prune.py --dry
   ```

   By ear: after the update, the picture is spoken, "Firmware updated, press OK to continue", and
   OK closes it. Then the voice: on a card that holds other sets, Auto may take another, such as
   espeak, so choose heart first, in the Voice row or with this command:

   ```bash
   .venv/bin/python flipper_cli.py "sr voice use heart"
   ```

   Back and Up on the home screen then says "Home screen" in the heart voice.

   Last, the checks of R7 and of section 10 of the release spec, with the project's own virtual
   environment and tools. They run in the project folder, and `cd -` goes back there from the
   folder of the download:

   ```bash
   cd -
   ```

   The RAM probe restarts the Flipper and opens the core apps one by one. None may crash it, so no
   line says "DEVICE REBOOTED" or "CONSOLE STOPPED ANSWERING":

   ```bash
   .venv/bin/python tools/ram_probe.py
   ```

   The reader's scripted check starts on the home screen and must end with "0 failures":

   ```bash
   .venv/bin/python tools/sr_drive.py
   ```

   Then the speech line of `sr status` must say "underruns 0", for all that was spoken since the
   probe's restart:

   ```bash
   .venv/bin/python tools/flipper_cli.py "sr status"
   ```

   The release's elf must turn an address into a line of code. `nm` gives the address of a known
   function, `screen_reader_is_enabled`, as the first word of its line, such as 0809dcc0:

   ```bash
   Momentum-Firmware/toolchain/current/bin/arm-none-eabi-nm /tmp/sonar-0.1.0-check/sonar-0.1.0-firmware.elf | grep " screen_reader_is_enabled$"
   ```

   addr2line, given that address with 0x in front of it in place of 0x0809dcc0, must name
   `screen_reader_is_enabled` and a line of `screen_reader.c`:

   ```bash
   Momentum-Firmware/toolchain/current/bin/arm-none-eabi-addr2line -e /tmp/sonar-0.1.0-check/sonar-0.1.0-firmware.elf -f -a 0x0809dcc0
   ```

8. Read the release notes on the draft's page on GitHub, then publish the draft there by hand. No
   script publishes a release, and a release that is published is not finalised again.

## The voice on this card

- The vocabulary here is made with `say` and the Samantha voice, the generator's defaults, so it
  is for this device only.
- On 2026-09-26 the vocabulary held 10,789 clips. Most of them come from the apps on the card,
  which `--card-apps` adds to the 2,900 words of `--extract`. `sr voice status` then showed a
  longest clip open of 66 ms since boot.
- On 2026-10-01 the set was made again on this MacBook, after Robin heard four of its words sound
  the same as the old Mac's: 10,539 clips, about 74 minutes to make and 39 to send, over the old
  clips. `voice/` holds the record of the card again, whose `.sync-id` is b1c1f2d07f7e630b. The
  words the device had spelled, "noted", "spoken", "samantha" and "espeak", have clips since.
- The card also holds the sets heart and espeak. A clip's open time follows its place in its
  folder, since the card finds a file by reading the folder's entries in the order the files were
  made. espeak and heart were written alphabetically on 2026-09-26, so common words such as "the"
  sat near the ends of their folders: espeak's clips opened in a median of 51 ms, up to 84,
  longer than the 82 ms half of the speech ring, and long sentences played with underruns. On
  2026-10-03 espeak's folders were rewritten in clip order, the most spoken words first: a median
  of 25 ms, and 3 underruns over three long sentences where there were 18. The same day heart's
  most spoken words, about 24 a folder, were moved to the fronts of its folders through the
  Flipper by renames, which copy no data and leave no macOS files: a median of 26 ms where it was
  55, and no underruns where there were 3. samantha keeps the order of its first rollout, the
  firmware's words first, 23 ms. espeak's clips are kept in
  `backups/espeak-clips-2026-10-03.tar`. See `docs/measurements/2026-10-01-remaining-items.txt`
  and `docs/measurements/2026-10-02-card-settings-and-clip-order.txt`.
- On 2026-10-09 the card was erased, and all three sets were made again from nothing with the
  README's commands and sent in the clip order: first the 2,911 words of `--extract`, then the
  routine with `--card-apps`, which added 7,628 words from the 160 apps on the card. Each set holds
  10,535 clips, samantha one more, a word the device had spelled. Making the clips took 72 seconds
  for espeak in all, about 22 minutes for heart and 67 for samantha; sending each set about 30
  minutes. The sets made before are kept on the Mac in `backups/voice-folders-2026-10-09/`.
- Writing to the card from this Mac through a card reader leaves a `._` file of 4 KB beside every
  file and folder written: macOS gives everything a process of this session makes the
  `com.apple.provenance` attribute, which exFAT keeps only in such a file, and which cannot be
  removed. They take 4 KB each and double a folder's entries. Removing them from the Flipper's
  console, as on 2026-10-03, frees the space, but the lookup still walks their free places, so
  write through the Flipper where it matters. The microSD adapter's lock slider must be up,
  towards the contacts, or the Mac mounts the card read-only.
- The figures behind the hashed folders: finding a file on this exFAT card reads the folder's
  entries one by one, about 0.17 ms per entry. At the rollout on 2026-09-24, with about 2,900
  clips, no folder held more than about 65, and a clip opened in under 40 ms.
- The speech ring is 8192 bytes, two halves of 82 ms. While one half plays, the worker opens the
  next clip and fills the other half. This ring costs 4 KB more heap than the 4096-byte ring of
  phase 2.
- The letter A is recorded from "a": `say` reads "ay" as "aye", which sounds exactly like the
  letter I.
- `--remove-legacy` removed the first layout from the card, the `/ext/sr/voice/<first letter>/`
  folders of the 2026-09-24 rollout. It uses `voice/synced.json` to know what to remove, and
  clears it; then `--sync` sends everything into the hashed folders. It was needed once, took about
  1.5 minutes for 2,831 clips, and needs the venv Python, like `--sync`:

  ```bash
  .venv/bin/python tools/voice_build.py --remove-legacy
  ```

- The measurements are in `docs/measurements/2026-09-24-voice-rollout.txt`.

## Useful commands

Flash limit: the firmware may only use the flash below the BLE stack, which starts at SFSA 0xD7
for ble_light 1.20.0: 880,640 bytes. fbt's `.free_flash` line is against the nominal 1024 KB
linker region and does not know this, and the updater refuses a larger image before writing. Run
the headroom check before every `./fbt flash_usb`. It reads the stack's address from the update
package the build made, so a new radio stack from Momentum moves the limit with it, and prints
the size of `build/f7-firmware-C/firmware.bin`, the limit and the spare bytes:

```bash
tools/flash_headroom.sh
```

The image sizes so far, newest first:

- 9149fe493, the slideshow view's key handler and timer without a picture, on the branch
  `claude/device-checks-2026-10-09`, on 2026-10-09: 870,172 bytes, 10,468 spare.
- 2bf03d177, the slideshow view's draw without a picture: 870,164 bytes, 10,476 spare.
- 859855918, the first boot without the tutorial and the update picture spoken, with the flash
  script's and the slash's fixes: 870,164 bytes, 10,476 spare, 80 over 59878faeb.
- 59878faeb again, built from an empty build folder for the fresh start of 2026-10-09: 870,084
  bytes, the same as on 2026-10-03.
- 59878faeb, the merge of the C64 fix into `screen-reader`, on 2026-10-03: 870,084 bytes, 10,556
  spare, 16 fewer than 44e1d8e83 for the shorter branch name.
- 44e1d8e83, the C64 menu style's numbers, on the branch `claude/c64-menu-2026-10-03`, on
  2026-10-03: 870,100 bytes, 10,540 spare.
- f9782c740, the merge of the settings fix into `screen-reader`, on 2026-10-03: 870,076 bytes,
  10,564 spare, 24 fewer than 778d09f8f for the shorter branch name.
- 778d09f8f, the settings read after a card change or a format, on the branch
  `claude/card-settings-2026-10-02`, on 2026-10-02: 870,100 bytes, 10,540 spare, 88 bytes over
  ea05c6d94.
- ea05c6d94, the fixes after the review of 2026-10-01 to the crash address, the line breaks and
  the file browser, on 2026-10-02: 870,012 bytes, 10,628 spare, 136 bytes over 0294fe871.
- 0294fe871, the crash address of hardware faults, on the branch
  `claude/reading-fixes-2026-10-01`, on 2026-10-01: 869,876 bytes, 10,764 spare, 160 bytes over
  95c956f89.
- 95c956f89, `sr screen` naming the up and down buttons: 869,716 bytes, 10,924 spare.
- f37f06887, the screen-reading fixes, on 2026-10-01: 869,708 bytes, 10,932 spare, 496 bytes over
  4b56919df.
- 4b56919df, F2 corrected, on the branch `claude/device-checks-2026-09-30`, on 2026-09-30:
  869,212 bytes, 11,428 spare. 102 bytes of code over b9c87352c, and 18 of the longer branch
  name, which the image holds.
- b9c87352c, the merge of the fixes after the review of 2026-09-28, on 2026-09-29, the first
  build on the new MacBook: 869,092 bytes, 11,548 spare. The review branch's last build,
  c71bd08a6, was 869,120: its branch name, `claude/flipper-access-review-fixes-ssg5yj`, has 28
  characters more than `screen-reader`.
- 86820a7db, plan B's voice sets and the Voice row, on 2026-09-26: 866,300 bytes, 14,340 spare.
- a5c2ed7d9, plan A's fix wave: no settings saved in an update boot, on 2026-09-26, built from a
  wiped build folder: 864,652 bytes, 15,988 spare. The continuous build's image of the same commit
  is 864,648 bytes.
- a0dea0841, the clean Sonar build of the publishing plan A, with the List menu style as the
  default, on 2026-09-26, built from a wiped build folder: 864,564 bytes, 16,076 spare, the
  same as 6451e86e8.
- 6451e86e8, FreeRTOS's stack overflow check on, on the evening of 2026-09-25: 864,564 bytes,
  16,076 spare.
- a9e4e7b94, the Archive's menus naming their selection: 864,428 bytes, 16,212 spare.
- 4a4420439, the reader toggle and the Passport's next level, on 2026-09-25: 864,396 bytes,
  16,244 spare. Before the review fixes, at f9f1e168f: 864,420 bytes.
- 9028a8499, the crash address: 863,644 bytes, 16,996 spare.
- c502de5ab, the dolphin in words: 863,284 bytes, 17,356 spare.
- 08e80106f, the firmware stripdown and its final fixes: 862,612 bytes, 18,028 spare.
- 22ae265ef, before the stripdown, after the polish round, on 2026-09-24: 877,036 bytes, 3,604
  spare.
- af4ee0952, phase 3 with its final review fixes: 876,056 bytes, 4,584 spare.
- 6c7469a79, phase 3 before those fixes: 875,928 bytes, 4,712 spare.
- d5b77c219, before phase 3: 872,048 bytes, 8,592 spare.
- 54794522b, before the recorded voice: 869,756 bytes, 10,884 spare.

Drive the buttons from the terminal, on Momentum only, with `input keyboard` inside an interactive
serial session:

```bash
screen /dev/cu.usbmodemflip_Delphi1 230400
```

Then type `input keyboard`. Arrows move, Enter is OK, Backspace is Back, Space before a key sends
it as a real button press instead of typed text, and Ctrl-C leaves keyboard mode. Single presses
without a session:

```bash
.venv/bin/python tools/flipper_cli.py "input send ok short"
```

Screen reader console commands, on firmware from the `screen-reader` branch:

```bash
.venv/bin/python tools/flipper_cli.py "sr on"
.venv/bin/python tools/flipper_cli.py "sr screen"
.venv/bin/python tools/flipper_cli.py "sr status"
```

`sr watch` is interactive; use the tethered reader instead:

```bash
.venv/bin/python tools/sr_drive.py --interactive
```

Speech: announcements are spoken by the device itself.

- `sr say <text>` speaks text and prints timing, and `sr stop` silences.
- `sr volume <0..100>` and `sr delay <500..10000>` are saved settings.
- `sr chord up|down|ok|okhold|downhold|left|right` runs what Back and that key do, as the
  README's Back chords section describes; `downhold` works also while the reader is off.
- `sr voice off` mutes until `sr voice on` or a reboot; `sr voice off 60` mutes for a minute,
  which the generator sets around a transfer and renews as it goes, so a generator that dies
  leaves the reader muted for a minute at most.

Any button press silences speech. With animations on, the dolphin's speech bubbles on the home
screen are not spoken unless a button was pressed in the last two seconds. `sr status` counts
them as suppressed, and `sr watch` still shows them. A change dropped while held, superseded by a
newer one or by the quiet rules once it comes due, never reaches `sr watch`; only the suppressed
counter of `sr status` may show it. During NFC-V emulation the reader is silent, because the
emulation borrows the speaker timer; it parks the speaker pin so nothing is heard.

## Crash diagnosis

What the crash popup says, how the reader speaks the address, and what `sr status` shows are in
When it crashes in the README. This section is the decoding and the capture.

To find the line of code on the Mac for an address starting with 08, which is in the firmware's
flash, look at its last digit. An even address, ending in 0, 2, 4, 6, 8, A, C or E, is the
instruction that faulted, which a hardware fault leaves: take it as it is. An odd address is
where a call would have returned to, the call of a failed check, or a call through a null
function pointer: subtract 2. Give the result to addr2line with the `firmware.elf` of the build
that `sr status` names, from the project folder. For "at 0803ABCD", odd:

```bash
Momentum-Firmware/toolchain/current/bin/arm-none-eabi-addr2line -e Momentum-Firmware/build/f7-firmware-C/firmware.elf -f -i -C -a 0x0803ABCB
```

It prints the function with its file and line, and with `-i` also the chain of functions the named
code was inlined into. The build directory holds only the latest build: if it has moved on from
the build `sr status` names, build that commit in a git worktree and use its elf. Builds of one
commit on this Mac have given the same image, so the addresses match. The continuous build's
image of the same commit differs by a few bytes, though: 12 more for a0dea0841, 4 fewer for
a5c2ed7d9. So a release's own `firmware.elf` must be kept to decode its addresses.

The caveats for an odd address. Without the 2 subtracted, addr2line names the instruction after
the check's call: often a later line, and sometimes another function, since that call never
returns. Even with it, the line is not always the failed check's own. The compiler often lets
several checks of one function share a single call to the crash routine. The line named is then
one of those checks, in that function or in one inlined into it. In
`ble_svc_serial_notify_buffer_is_empty`, for example, four checks share one call and addr2line
always names the last.

An even address comes with the hardware faults, "HardFault", "NULL pointer dereference",
"MemManage", "BusFault" and "UsageFault", on any thread. The fault handler takes it from the frame
the core pushed when the fault hit. It names the instruction itself, which is often inside a
library function such as strlen or memcpy; who called that function is not kept. For a function
of the C library addr2line prints the name alone, with "??:?" for the file and line, since the
library carries no line information. After an imprecise bus fault, a write the core reports late,
the instruction is a few past the write.

When the address that faulted is no code, as after a call through a null function pointer, the
handler takes the return address of that call from the frame instead: odd, and less 2 it names
the call. The popup then says "MemManage", since the jump to address 0 hits the memory guard there.
A stack overflow usually leaves an odd address in the handler: the frame the core pushes after
the overflow lands in the stack's guard too, so the handler cannot trust it. That is the usual
case for "MPU fault, possibly stack overflow" and "MemManage fault, possibly stack overflow".
"StackOverflow", found by FreeRTOS, and any other message from a crash call in the code give an
odd address as well.

An address starting with 20, from 2000 to 2003, is in RAM, inside an app loaded from the card. The
firmware's elf cannot name it, and the app's own elf would need the address the app was loaded at,
which is not kept.

The Wi-Fi dev board brings the crash handler's full dump to the Mac. It sits on the GPIO header
with its own USB-C cable in the Mac, and its factory firmware is the Black Magic Probe. The board
bridges the Flipper's pins 13 and 14, where the firmware writes its debug console once the Debug
flag is on, at the log level set. Both settings are kept across reboots, but not across an
update to a release build, whose updater turns both off; step 6 of the Routine sets them again:

```bash
.venv/bin/python tools/flipper_cli.py "sysctl debug 1" "sysctl log_level debug"
```

`tools/uart_log.py` captures that console with time stamps, and reopens the port when the board
re-enumerates after a reboot. Run it in the background with `nohup`, like the USB log capture:

```bash
nohup .venv/bin/python tools/uart_log.py docs/measurements/logs/<file>.txt &
```

A crash then leaves the registers, the thread and the stack in that file, followed by the reboot.
This does not change the device's sleep behaviour, whereas attaching a real debugger session would
keep it from deep sleep. The capture running since 2026-09-25 writes
`docs/measurements/logs/2026-09-25-uart.txt`, and this finds its process:

```bash
pgrep -f uart_log.py
```

Since 6451e86e8 the firmware checks for stack overflow, which Momentum ships switched off: an
overflow crashes at once as "StackOverflow" and names the thread on the UART. `top 0` prints the
thread table once. It shows each thread's stack size and, under Stack Min, the least stack it has
had free since boot, with the heap's total, free and minimum above:

```bash
.venv/bin/python tools/flipper_cli.py "top 0"
```

On 2026-09-25 the tightest threads were BtSrv, 224 bytes free at the lowest of 1,024, reached at
boot; ExpansionSrv, 216 of 764; and SerialControlDriver, 264 of 508. The reader's threads had room:
ScreenReaderSrv 1,932 of 3,068, SpeechWorker 2,484 of 3,068, and InputSrv 456 of 1,020.

## Rolling back to official firmware

The official 1.4.3 package is on the Mac, in `firmware-packages/official-1.4.3/f7-update-1.4.3`;
the card's copy went with the erase of 2026-10-09. Momentum's flash script sends it to the card and
starts the update, a blank card included since 2026-10-09:

```bash
(cd Momentum-Firmware && ../.venv/bin/python scripts/selfupdate.py ../firmware-packages/official-1.4.3/f7-update-1.4.3/update.fuf)
```

Then send the stock backup to the card and restore the settings from it:

```bash
.venv/bin/python Momentum-Firmware/scripts/storage.py send backups/backup-stock-1.4.3.tar /ext/backup-stock-1.4.3.tar
```

```text
update restore /ext/backup-stock-1.4.3.tar
```

To go back to an earlier Sonar build: the fork's history keeps every build flashed here. The build
before the review fixes is 86820a7db on `screen-reader`; the backup of its settings,
`backup-2026-09-29.tar`, was on the card and went with the erase of 2026-10-09. Check out its commit
in the submodule, with the submodules it records, and wipe the build folder:

```bash
git -C Momentum-Firmware checkout 86820a7db
```

```bash
git -C Momentum-Firmware submodule update --init --recursive
```

```bash
rm -rf Momentum-Firmware/build
```

Then build, check the headroom and flash with steps 2 to 7 of the Routine, and afterwards check the
branch out again the same way. The prune removes only the fork's own packages it knows by name:
releases and continuous builds, and builds on `screen-reader` or a detached HEAD. The package of
4b56919df, `f7-update-mntm-claude-device-checks-2026-09-30-4b56919d`,
has a name it does not know and stays on the card: delete that folder in the file browser, whose
Delete removes a folder with everything in it.

## Measurements

The files in `docs/measurements/`, all plain text:

- `2026-09-22-ram-probe-mntm-012.txt`: the RAM probe on stock Momentum mntm-012, before the
  reader: the lowest free heap while each core app was busy.
- `2026-09-22-ram-probe-screen-reader-on.txt`: the same probe with the phase 1 reader on.
- `2026-09-23-ram-probe-speech-on.txt`: the same probe with phase 2's speech on, where Sub-GHz
  Read fell to 2 KB free and the Frequency Analyzer crashed the device.
- `2026-09-24-phase-3.txt`: the device outputs of phase 3, the chords, the settings and the spoken
  names of icons, with the thread stacks from `top 0`. Everything in Using it on the device in the
  README was checked on this device, then named R0skie, except where it says otherwise.
- `2026-09-24-voice-rollout.txt`: the recorded voice's rollout, from the first layout by first
  letter to the 64 hashed folders and the 8192-byte ring, with the clip open times and underruns.
- `2026-09-25-stripdown.txt`: the firmware stripdown's flash, static RAM, idle heap, RAM probe and
  device pass.
- `2026-09-26-plan-a.txt`: the clean Sonar build of the publishing plan A: its build, headroom and
  flash, what the device reported after it, the Debug flag and the settings that the update reset,
  the card before and after the prune, and the chord session. Under After the fix wave, the same
  for a5c2ed7d9, with the settings file compared across the flash.
- `2026-09-26-plan-b.txt`: plan B on the device, the voice sets and the Voice row, with Samantha
  moved into the set layout and the Kokoro tuning clips.
- `2026-09-29-review-fixes.txt`: the fixes after the review of 2026-09-28 on the device: the new
  MacBook's setup and first build, the backup and the flash, the regression tools, every check
  of the fixes record with its console output, the underruns of the espeak set, and the
  correction of F2 with its flash and repeated check.

`docs/measurements/logs/` holds the raw session logs and the UART capture. It is not in git.
