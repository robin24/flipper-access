Sonar is a firmware for the Flipper Zero that a blind person can use without sight. It is built on
Momentum, and its screen reader speaks every screen through the device's own speaker, from a
recorded voice on the SD card. It was written almost entirely by AI coding agents (Claude) under
the direction of Robin Kipp, a blind developer, who tested every change on the device.

This is the release {{TAG}}. The README at this release says how to install it, how to use it, how
to go back to other firmware, and what Sonar changes against Momentum:
https://github.com/robin24/flipper-access/blob/{{TAG}}/README.md

## What is new

The changes in this release are in the changelog, under its version:
https://github.com/robin24/flipper-access/blob/{{TAG}}/CHANGELOG.md

## The files

For the install:

- `flipper-z-f7-update-{{TAG}}.tgz`: the firmware's update package.
- `voice-heart-{{TAG}}.tar`: the voice, heart, made with Kokoro's voice af_heart. Its licence is
  `LICENSE.txt` inside it.
- `install-{{TAG}}.zip`: the install script `install.py`, with `flipper_cli.py`,
  `flipper_storage.py`, `card_prune.py` and the project's licence.
- `release.json`: the release's description, which the install script checks the installed
  firmware against.

For checking, crash reports and developers:

- `SHA256SUMS`: the SHA-256 checksum of every file here but `release.json` and `SHA256SUMS`
  itself. `release.json` lists the same checksums of the other files.
- `{{TAG}}-firmware.elf` and `{{TAG}}-firmware.map`: the firmware's symbols, which turn the address
  on a crash popup of this release into a line of code.
- `flipper-z-f7-sdk-{{TAG}}.zip`: the SDK, for building apps for this firmware.
- `{{SOURCE_BUNDLE}}`: the source of every binary here, as described under The source.

## Install

Download the first four files above into one folder, with Python 3.10 or newer on the computer.
In a terminal in that folder, unpack the install zip:

```bash
unzip install-{{TAG}}.zip
```

Make a virtual environment there, once:

```bash
python3 -m venv .venv
```

Put pyserial into it:

```bash
.venv/bin/pip install pyserial
```

Plug the Flipper in, unlock it and close qFlipper. Start on the Flipper's home screen, with no
application open: on Sonar, press Back until it says "Home screen"; on other firmware, which says
nothing, press Back a few times. Then run the install:

```bash
.venv/bin/python install.py --package flipper-z-f7-update-{{TAG}}.tgz --voice voice-heart-{{TAG}}.tar --release release.json
```

It works from the official firmware, from Momentum and from an earlier Sonar. It backs up the
Flipper's internal storage to the card first, and asks whether the voice goes through a card
reader, the default, or over USB. The Flipper says nothing about the install: the script says each
step on the computer, to the end. Over USB the install takes a little over half an hour; through a
card reader it is faster. The README's Install section has the details, Windows included, and its
Going back section the way back.

## Known issues

The main ones; the README's Known limits has them all.

- The Flipper has rebooted a few times while idle, with a "furi_check failed" popup, and the cause
  is unknown. A bug report with the popup's address and the output of `sr status` helps.
- During NFC-V emulation the reader is silent, from the first exchange with an NFC reader until
  you leave the emulation with Back.
- An external CC1101 radio module has not been tried with the reader on.
- When a menu opens over the file browser's list, the reader reads the menu's words mixed with the
  file names behind it.
- An app that uses the JavaScript engine's functions, which Sonar leaves out, fails to load with
  the error "Missing Imports". An app built with Sonar's SDK that uses the reader's functions fails
  to load on other firmware.
- Without the SD card, or without a voice on it, the reader is silent.

## Where it comes from

- The fork's commit: {{FORK_COMMIT}}, tagged {{TAG}} at
  https://github.com/robin24/Momentum-Firmware/tree/{{TAG}}
- The Momentum commit it builds on: {{MOMENTUM_BASE}}, at
  https://github.com/Next-Flip/Momentum-Firmware/commit/{{MOMENTUM_BASE}}

The fork's submodules, nested ones included, each at the commit this release was built from:

{{SUBMODULES}}

Before it was published, this release's own files, downloaded from this page, were installed on a
Flipper with the install script and checked there.

## The source

The firmware is licensed under the GPL-3.0, like Momentum and the official firmware, and so are the
install script and the other tools. The source of every binary in this release is the file
`{{SOURCE_BUNDLE}}` among its assets: the fork at {{FORK_COMMIT}} with every submodule, nested ones
included, each at the commit listed above, Momentum's apps among them, whose builds the update
package puts on the card. It is offered here, beside the binaries, for as long as they are offered.

The voice pack has its own terms, in its `LICENSE.txt`: Kokoro's model is under the Apache License
2.0, and what the Sonar project adds to the voice is released under CC0 1.0.
