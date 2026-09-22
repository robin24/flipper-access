# Flipper Zero accessibility project

Working notes for making a Flipper Zero usable without sight. The background research is in
`flipper-zero-accessibility-investigation.md`. This file records the current state of the device
and the tools in this folder. Last updated 2026-09-22.

## Device state

- Device name: R0skie. Hardware version 12, region DE. 64 GB microSD card, exFAT.
- Firmware: Momentum mntm-012 (built 31 December 2025), installed 2026-09-22 from the terminal.
  Before that it ran official firmware 1.4.3.
- Serial port on this Mac: `/dev/cu.usbmodemflip_R0skie1`, 230400 baud. It disappears while the
  device is in the updater and comes back after the reboot.
- The Text to SAM app on the card (`/ext/apps/Media/text2sam.fap`) is a patched build that also
  speaks its launch argument. Its on-screen behaviour is unchanged.

## Folder contents

- `tools/flipper_cli.py`: send commands to the Flipper CLI and print the replies with colour
  codes stripped. Example: `.venv/bin/python tools/flipper_cli.py "info device" "loader list"`.
- `tools/say.sh`: speak text on the device. Example: `tools/say.sh Hello there`.
  Voice control: `tools/say.sh --voice 64,72,128,128 Hello` with pitch, speed, mouth, throat.
  Bigger speed numbers talk slower. Keep each call under about 200 characters.
- `.venv/`: Python virtual environment with pyserial and colorlog (used by the helper scripts).
- `Momentum-Firmware/`: full source clone, branch dev, with the ARM toolchain downloaded by fbt.
  API version 87.1, same as the installed release, so apps built here run on the device.
- `patches/text2sam-cli-mode.patch`: the change to Text to SAM (applies inside
  `Momentum-Firmware/applications/external`, which is a git submodule).
- `firmware-packages/`: Momentum mntm-012 and official 1.4.3 update packages.
- `backups/backup-stock-1.4.3.tar`: internal storage backup taken on official 1.4.3 before the
  Momentum install (settings, dolphin state, region data).

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

## Rolling back to official firmware

    .venv/bin/python Momentum-Firmware/scripts/selfupdate.py -p /dev/cu.usbmodemflip_R0skie1 firmware-packages/official-1.4.3/f7-update-1.4.3/update.fuf

after unpacking `firmware-packages/flipper-z-f7-update-1.4.3.tgz` into `firmware-packages/official-1.4.3/`.
Then restore settings with `update restore /ext/backup-stock-1.4.3.tar` on the CLI after
sending the backup file to the card.

## Plan

1. Done: terminal access, backup, Momentum install.
2. Done: CLI explored, helper tools written.
3. Done: source build environment set up, first app built and running.
4. In progress: speech demo. Robin judges intelligibility and loudness of SAM on the piezo.
5. Next: spec and build the screen-text capture hook with a CLI mirror, then the on-device
   speech service.
