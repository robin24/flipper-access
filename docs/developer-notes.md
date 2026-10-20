# Developer notes

How Sonar is built, flashed, merged with Momentum and released, and how a crash is decoded. The
commands run from the project folder, with a Flipper on USB where they need one.

## The folders and tools

- `tools/flipper_cli.py`: send commands to the Flipper CLI and print the replies with colour codes
  stripped. For example:

  ```bash
  .venv/bin/python tools/flipper_cli.py "info device" "loader list"
  ```

- `.venv/`: Python virtual environment with the packages of `requirements.txt`, used by the
  helper scripts. Not in git.
- `Momentum-Firmware/`: the firmware, a git submodule on the fork's branch `screen-reader`, with
  the ARM toolchain that fbt downloaded. API version 87.3 since 2026-09-25, which exported
  `canvas_tap_hint_note_at` for words placed among the drawn text; 87.2, since phase 3, exported
  two calls for the screen reader's spoken names of icons. Apps built here run on the device, and
  apps built for 87.1 and 87.2 still load.
- `firmware-packages/` and `backups/`: other firmware's update packages, for rolling back, and the
  internal storage backups taken with `update backup`. Not in git; see Rolling back to official
  firmware.
- `tools/sr_drive.py`: scripted check of the screen reader console stream, and with
  `--interactive` a tethered screen reader. In that mode arrows, Enter and Backspace drive the
  device, Tab reads the screen, letters type into text fields, and Ctrl-C ends. The scripted check
  has three sessions: the menus, an app's keyboard, and the Back chords on the home screen and in
  the main menu. `--chords` runs only the chords. Start it on the home screen.
- `tools/run_host_tests.sh`: unit tests for the screen model, the speech text, queue, PCM and
  voice helpers, the chords and the change throttle, and for Momentum's settings file, built
  against stand-ins for the card in `tests/host/stubs`. They are built with clang, and the
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
- `tools/ram_probe.py`: the lowest free heap while each core app runs.
- `tools/uart_log.py`: captures the debug console through the Wi-Fi dev board; see Crash
  diagnosis. `tools/flipper_log.py` captures the USB console's log stream instead, until the port
  drops; the UART capture replaced it for the crash hunt.
- `tools/map_size.py`: flash and static RAM per library, app or object, from the firmware's
  linker map.
- `tools/voice_build.py`: makes the recorded voice and copies it to the card; see The voice in the
  README. `tools/clip_make.py` makes a single test clip with the same processing.
- `tools/voice_words.txt`: the base word list. `tools/voice_names.txt`: the spoken names of the
  letters that spell a word without a clip.
- `tools/voice_words.local.txt`: personal words, one per line, such as the device's name. Not in
  git; see Routine.
- `voice/` and `voices/`: the built vocabularies, not in git. Do not delete them; see The voice in
  the README.
- `docs/`: the specs, plans, the roadmap and these notes; `docs/README.md` is the index.

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
exists. The local list holds personal words, one per line, such as the device's name. It is not in
git, so the public word list names no one's device. On another device, its name reaches
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
from a pushed tag and leaves a draft release with six assets. The maintainer's computer then adds
the one voice pack, the checksums and `release.json`, and the draft is published by hand. Run the
steps from the project folder, but for step 6 and the first part of step 7, which run in the
folder of the download. `sonar-0.1.0` stands for the tag and `0.1.0` for its version; for a release
candidate the tag is `sonar-0.1.0-rc1` and the version is `0.1.0-rc1`.

1. Write the release's entry in `CHANGELOG.md` first: its version, with the day of the tag in place
   of `YYYY-MM-DD`, and what the release changes, since the release notes send readers to the
   changelog at the tag. A release candidate's tag has the entry of the version it leads to, and the
   final tag the same entry with its own day. The README names the version too, in its commands, in
   the file names it lists, and in the sentence that says which version the commands are for, so
   update them with the entry; the host tests, which the build runs, fail when one of them differs.
   Merge the entry into `main` with a pull request, as every change. The project's commit to tag is
   the merged commit on `main` whose submodule pointer is the fork's commit to tag, so check that
   commit out, with the submodule on the commit it records:

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

Drive the buttons from the terminal, on Momentum only, with `input keyboard` inside an interactive
serial session:

```bash
screen /dev/cu.usbmodemflip_<name>1 230400
```

`<name>` is the Flipper's name, as `ls /dev/cu.usbmodemflip_*` shows it on a Mac.

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

To find the line of code on the computer for an address starting with 08, which is in the firmware's
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
commit on one computer have given the same image, so the addresses match. The continuous build's
image of the same commit can differ by a few bytes, though, so a release's own `firmware.elf` must
be kept to decode its addresses.

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

The Wi-Fi dev board brings the crash handler's full dump to the computer. It sits on the GPIO
header with its own USB cable to the computer, and its factory firmware is the Black Magic Probe.
The board bridges the Flipper's pins 13 and 14, where the firmware writes its debug console once
the Debug flag is on, at the log level set. Both settings are kept across reboots, but not across an
update to a release build, whose updater turns both off; step 6 of the Routine sets them again:

```bash
.venv/bin/python tools/flipper_cli.py "sysctl debug 1" "sysctl log_level debug"
```

`tools/uart_log.py` captures that console with time stamps, and reopens the port when the board
re-enumerates after a reboot. Run it in the background with `nohup`, like the USB log capture:

```bash
nohup .venv/bin/python tools/uart_log.py logs/<file>.txt &
```

`logs/` is not in git. A crash then leaves the registers, the thread and the stack in that file,
followed by the reboot. This does not change the device's sleep behaviour, whereas attaching a
real debugger session would keep it from deep sleep. This finds the capture's process:

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

In a measurement of 2026-09-25 the tightest threads were BtSrv, 224 bytes free at the lowest of
1,024, reached at boot; ExpansionSrv, 216 of 764; and SerialControlDriver, 264 of 508. The reader's
threads had room: ScreenReaderSrv 1,932 of 3,068, SpeechWorker 2,484 of 3,068, and InputSrv 456 of
1,020.

## Rolling back to official firmware

The README's Going back is the way for users: the install script puts back official firmware or
Momentum and the backup it took. By hand, with an official update package unpacked in
`firmware-packages/`, Momentum's flash script sends it to the card and starts the update, also on a
blank card:

```bash
(cd Momentum-Firmware && ../.venv/bin/python scripts/selfupdate.py ../firmware-packages/official-1.4.3/f7-update-1.4.3/update.fuf)
```

Then send a backup taken with `update backup` before Sonar was installed to the card, and restore
the settings from it:

```bash
.venv/bin/python Momentum-Firmware/scripts/storage.py send backups/backup-stock-1.4.3.tar /ext/backup-stock-1.4.3.tar
```

```text
update restore /ext/backup-stock-1.4.3.tar
```

To go back to an earlier Sonar build, check out its commit in the submodule, with the submodules it
records, and wipe the build folder. `<commit>` stands for the build's commit on `screen-reader`:

```bash
git -C Momentum-Firmware checkout <commit>
```

```bash
git -C Momentum-Firmware submodule update --init --recursive
```

```bash
rm -rf Momentum-Firmware/build
```

Then build, check the headroom and flash with steps 2 to 7 of the Routine, and afterwards check the
branch out again the same way. The prune removes only the fork's own packages it knows by name:
releases and continuous builds, and builds on `screen-reader` or a detached HEAD. The package of a
build on a work branch has a name it does not know and stays on the card: delete that folder in
the file browser, whose Delete removes a folder with everything in it.
