# Flipper Zero accessibility project

Working notes for making a Flipper Zero usable without sight. The background research is in
`flipper-zero-accessibility-investigation.md`. This file records the current state of the device
and the tools in this folder. Last updated 2026-09-23.

## Device state

- Device name: R0skie. Hardware version 12, region DE. 64 GB microSD card, exFAT.
- Firmware: Momentum mntm-012 (built 31 December 2025), installed 2026-09-22 from the terminal.
  Before that it ran official firmware 1.4.3.
- Serial port on this Mac: `/dev/cu.usbmodemflip_R0skie1`, 230400 baud. It disappears while the
  device is in the updater and comes back after the reboot.
- The Text to SAM app on the card (`/ext/apps/Media/text2sam.fap`) is a patched build that also
  speaks its launch argument. Its on-screen behaviour is unchanged.
- Known problem with the phase 2 firmware: Sub-GHz is loaded from the card into RAM in this
  firmware base (mntm-012 had it in flash), so with the reader on its read mode leaves 2 KB of
  memory and the frequency analyzer runs out of memory and reboots the device. Avoid Sub-GHz
  until it is built into the firmware again; the numbers are in `docs/measurements/`.

## Folder contents

- `tools/flipper_cli.py`: send commands to the Flipper CLI and print the replies with colour
  codes stripped. Example: `.venv/bin/python tools/flipper_cli.py "info device" "loader list"`.
- `tools/say.sh`: speak text on the device. Example: `tools/say.sh Hello there`.
  Voice control: `tools/say.sh --voice 64,72,128,128 Hello` with pitch, speed, mouth, throat.
  Bigger speed numbers talk slower. Keep each call under about 200 characters.
- `.venv/`: Python virtual environment with pyserial and colorlog (used by the helper scripts).
- `Momentum-Firmware/`: full source clone, branch `screen-reader`, with the ARM toolchain
  downloaded by fbt.
  API version 87.1, same as the installed release, so apps built here run on the device.
- `patches/text2sam-cli-mode.patch`: the change to Text to SAM (applies inside
  `Momentum-Firmware/applications/external`, which is a git submodule).
- `firmware-packages/`: Momentum mntm-012 and official 1.4.3 update packages.
- `backups/backup-stock-1.4.3.tar`: internal storage backup taken on official 1.4.3 before the
  Momentum install (settings, dolphin state, region data).
- `tools/sr_drive.py`: scripted check of the screen reader console stream, and with
  `--interactive` a tethered screen reader: arrows, Enter, Backspace drive the device, Tab
  reads the screen, letters type into text fields, Ctrl-C ends.
- `tools/run_host_tests.sh`: unit tests for the screen model, the SAM port (checked against the
  original C++ synthesizer) and the speech text, queue and PCM helpers, run with clang on the Mac.
- `tests/host/`: the unit tests.
- `tools/ram_probe.py`: free heap while each core app runs; the logs are in `docs/measurements/`.
- `tools/sam_calibrate.py`: timing calibration of the speech engine against the Text to SAM demo.

## Useful commands

Build the patched app and copy it to the card:

    cd Momentum-Firmware && ./fbt fap_text2sam
    ../.venv/bin/python scripts/storage.py -p /dev/cu.usbmodemflip_R0skie1 send -f build/f7-firmware-C/.extapps/text2sam.fap /ext/apps/Media/text2sam.fap

(The storage helper is `Momentum-Firmware/scripts/storage.py`; run it with the venv Python and
`-p /dev/cu.usbmodemflip_R0skie1`.)

Drive the buttons from the terminal (Momentum only): `input keyboard` inside an interactive
serial session such as `screen /dev/cu.usbmodemflip_R0skie1 230400`. Arrows move, Enter is OK,
Backspace is Back, Space before a key sends it as a real button press instead of typed text,
Ctrl-C leaves keyboard mode. Single presses without a session:
`tools/flipper_cli.py "input send ok short"`.

Screen reader console commands (firmware from the `screen-reader` branch):

    .venv/bin/python tools/flipper_cli.py "sr on"
    .venv/bin/python tools/flipper_cli.py "sr screen"
    .venv/bin/python tools/flipper_cli.py "sr status"

`sr watch` is interactive; use `tools/sr_drive.py --interactive`.

Speech: announcements are spoken by the device itself. `sr say <text>` speaks text and prints
timing; `sr stop` silences; `sr rate <40..120>` and `sr volume <0..100>` are saved settings.
Any button press silences speech. `tools/sam_calibrate.py --verify` checks the voice still
matches the Text to SAM demo's timing.

Phase 1 marks the focused main menu item only in the List style; other menu styles are read by
inversion where possible and will get hints in a later phase.

## Rolling back to official firmware

    .venv/bin/python Momentum-Firmware/scripts/selfupdate.py -p /dev/cu.usbmodemflip_R0skie1 firmware-packages/official-1.4.3/f7-update-1.4.3/update.fuf

after unpacking `firmware-packages/flipper-z-f7-update-1.4.3.tgz` into `firmware-packages/official-1.4.3/`.
Then restore settings with `update restore /ext/backup-stock-1.4.3.tar` on the CLI after
sending the backup file to the card.

## Plan

1. Done: terminal access, backup, Momentum install.
2. Done: CLI explored, helper tools written.
3. Done: source build environment set up, first app built and running.
4. Done: speech demo; SAM default voice judged intelligible.
5. Done: phase 1 of the screen reader: text capture, screen model, console mirror.
6. Done: phase 2, on device speech with SAM and DMA playback.
7. Next: phase 3, hotkeys, settings screen, and screens that draw no text.
