# Flipper Zero accessibility project

Working notes for making a Flipper Zero usable without sight. The background research is in
`flipper-zero-accessibility-investigation.md`. This file records the current state of the device
and the tools in this folder. Last updated 2026-09-24.

## Device state

- Device name: R0skie. Hardware version 12, region DE. 64 GB microSD card, exFAT.
- Firmware: Momentum mntm-012 (built 31 December 2025), installed 2026-09-22 from the terminal.
  Before that it ran official firmware 1.4.3.
- Serial port on this Mac: `/dev/cu.usbmodemflip_R0skie1`, 230400 baud. It disappears while the
  device is in the updater and comes back after the reboot.
- The Text to SAM app on the card (`/ext/apps/Media/text2sam.fap`) is a patched build that also
  speaks its launch argument. Its on-screen behaviour is unchanged.
- Sub-GHz loads as an external app from the card into RAM in this firmware base (mntm-012 had
  it in flash). With the reader on, its read mode leaves about 2 KB of heap and the frequency
  analyzer crashes out of memory (numbers in `docs/measurements/`), so avoid Sub-GHz while the
  reader is enabled until phase 3 addresses memory. Building it into the firmware was tried and
  reverted: the image did not fit below the BLE stack (see the flash limit under Useful
  commands). The other main apps (NFC, RFID, infrared, iButton, GPIO, Bad USB, U2F) load as
  external faps too; NFC read leaves about 24 KB with the reader on.
- Since the recorded voice's 8 KB speech ring (2026-09-24), the reader holds 4 KB more heap
  than when the numbers above were taken. Idle free heap went from 114,552 to 110,520 bytes.
  So Sub-GHz read is expected to run out of memory with the reader on, and NFC read to leave
  about 20 KB. Neither was measured again.

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
- `tools/voice_build.py`: makes the recorded voice and copies it to the card (see Recorded
  voice below). `tools/clip_make.py` makes a single test clip with the same processing.
- `voice/`: the built vocabulary, not in git. Do not delete it; see Recorded voice.

## Useful commands

Build the patched app and copy it to the card:

    cd Momentum-Firmware && ./fbt fap_text2sam
    ../.venv/bin/python scripts/storage.py -p /dev/cu.usbmodemflip_R0skie1 send -f build/f7-firmware-C/.extapps/text2sam.fap /ext/apps/Media/text2sam.fap

(The storage helper is `Momentum-Firmware/scripts/storage.py`; run it with the venv Python and
`-p /dev/cu.usbmodemflip_R0skie1`.)

Flash limit: the firmware may only use the flash below the BLE stack (SFSA 0xD7 for ble_light
1.20.0, 880,640 bytes); fbt's `.free_flash` line is against the nominal 1024 KB linker region
and does not know this, and the updater refuses a larger image before writing. Run
`tools/flash_headroom.sh` before every `./fbt flash_usb`: it prints the size of
`build/f7-firmware-C/firmware.bin` and the spare bytes (this branch on 2026-09-24: 871,872
bytes, 8,768 spare; before the recorded voice, at 54794522b, it was 869,756 bytes, 10,884
spare).

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
Any button press silences speech. On the home screen the dolphin's speech bubbles are not
spoken unless a button was pressed in the last two seconds (`sr status` counts them as
suppressed; `sr watch` still shows them). During NFC-V emulation the reader is silent, because
the emulation borrows the speaker timer; it parks the speaker pin so nothing is heard.
`tools/sam_calibrate.py --verify` checks the voice still matches the Text to SAM demo's timing.

Phase 1 marks the focused main menu item only in the List style; other menu styles are read by
inversion where possible and will get hints in a later phase.

## Recorded voice

The reader speaks with recorded word clips from the SD card instead of SAM. The clips are made
on the Mac from a high quality voice (Samantha by default) and played word by word.

A word without a clip is spelled letter by letter with the recorded letters and digits, 60 ms
between letters, and noted on the card, so nothing is left unspoken. SAM speaks a letter only
when its clip is missing too, and everything when the voice is off. The letters are recorded by
their names, so "NFC" is heard as "en eff see", not "capital N capital F capital C". The names
live in `tools/voice_names.txt`. The letter A is recorded from "a": `say` reads "ay" as "aye",
which sounds exactly like the letter I. A spelled word gets its own clip at the next run of the
routine command, `.venv/bin/python tools/voice_build.py --extract --pull-missing --sync`.

On the card:

- `/ext/sr/voice/<hh>/<word>.raw`: one clip per word.
  - The format is raw unsigned 8-bit mono at 16,000 samples per second, and 128 is silence.
  - A word is lower case letters, up to 16 of them, or a single digit. Apostrophes are left
    out of the name: "don't" is `dont.raw`, recorded as "don't".
  - `<hh>` is one of 64 folders, chosen by a hash of the word (FNV-1a modulo 64, two hex
    digits). The reason: finding a file on this exFAT card reads the folder's entries one by
    one, about 0.17 ms per entry. With 64 folders none holds more than about 65 clips, and a
    clip opens in under 40 ms.
- `/ext/sr/voice/voice.txt`: the generator's settings line, which `sr voice status` shows.
- `/ext/sr/missing.txt`: words the device could not find, one per line, each at most once per
  boot.

The speech ring is 8192 bytes, two halves of 82 ms. While one half plays, the worker opens the
next clip and fills the other half. This ring costs 4 KB more heap than the 4096-byte ring of
phase 2.

Console commands:

- `sr voice on` and `sr voice off` switch between the clips and SAM alone. The setting is saved.
- `sr voice status` prints the first 63 characters of the settings line, and these counts since
  boot:
  - words, and letters of spelled words, spoken from clips;
  - words spelled letter by letter because they had no clip;
  - words logged as missing;
  - the longest and the latest clip open, in ms.

  The settings line is read at the first utterance after boot that uses the voice. So after a
  sync that changes it, the new line shows after a reboot. With the voice off, the vocabulary
  shows as "no" until the voice is back on and something is spoken.

Making the vocabulary with `tools/voice_build.py`:

- `tools/voice_build.py --extract --jobs 8` makes a clip for every word, about 2,900 words and
  27 MB. The words come from:
  - the base list `tools/voice_words.txt`;
  - every string in the firmware's core apps and services;
  - the dolphin's speech bubble texts.

  Everything goes through the reader's own pronunciation code.
  - Time on this Mac: about 16 minutes with `--jobs 8`, or 22 minutes with the default of 4.
    The build is limited by `say` itself, not by CPU count.
  - A rerun makes only new or changed clips.
  - Locally the clips sit in `voice/<first letter>/<word>.raw`. The sync puts each one into its
    hashed folder on the card.
- `.venv/bin/python tools/voice_build.py --sync` sends new or changed clips and voice.txt to the
  card.
  - A full sync of about 2,900 clips takes about 6.5 minutes. Later syncs send only what
    changed, which takes seconds.
  - The recorded voice is switched off on the device during the transfer and switched back on
    afterwards. If a transfer dies hard (power loss, a killed process, a dead port), the
    restore may not run: the saved setting then stays off, and the device speaks with SAM
    until `sr voice on` is typed.
  - After the card was wiped or replaced, add `--sync-all` to resend everything. `--sync-all`
    works only together with `--sync`.
- `.venv/bin/python tools/voice_build.py --extract --pull-missing --sync` is the missing-word
  workflow. It fetches missing.txt from the card, makes clips for those words, sends them and
  removes the list. `--extract` is there because the spoken spelling of apostrophe words
  comes from the extraction, not from missing.txt, which has already lost them. For a few
  words it takes about 3 to 4 seconds.
- `.venv/bin/python tools/voice_build.py --remove-legacy` removes the first layout from the card:
  the `/ext/sr/voice/<first letter>/` folders of the 2026-09-24 rollout. Then run `--sync` to
  send everything into the hashed folders.
  - It uses `voice/synced.json` to know what to remove, and clears it.
  - It is only needed once, when a card still has the old folders.
  - It took about 1.5 minutes for 2,831 clips.
- `--sync`, `--pull-missing` and `--remove-legacy` need the venv Python, because they use the
  firmware's serial storage helper.
- `tools/voice_build.py --check` makes ten test clips in a temporary folder and checks their
  format.
- The defaults are Robin's choices by ear: `--backend say --voice Samantha --rate 175
  --highpass 500 --gain 1.3 --soft --hz 16000`.
- There are two backends:
  - `say`, the default, uses the Mac's voices.
  - `piper` runs on any platform: `--backend piper --model <voice.onnx>`.
- `voice/` in this folder holds the clips and two records:
  - `manifest.json` records which clips were made and with which settings.
  - `synced.json` records what is on the card.

  Do not delete this folder. Without it the next build starts from scratch, which takes about 16
  minutes, and the next sync resends everything.

Licensing: Apple's voices are licensed for use on the Mac, so a vocabulary made with `say` is
for Robin's own device only. A released vocabulary must be made with Piper and a freely
licensed voice model.

Known limits:

- Words longer than 16 letters never get a clip, so they are spelled letter by letter.
- Tokens that mix letters and digits (for example `md5`, `i2c`, `p1`) never get a clip: the
  generator's word filter accepts letters-only words up to 16 characters or a single digit.
  They are spelled every time (`md5` is "em dee five"), logged as missing once per boot, and
  dropped by `--pull-missing`.
- Two words that differ only by an apostrophe share one clip. For example, "ill" plays the clip
  recorded as "i'll".
- A word the device logs as missing has already lost its apostrophe. So `--pull-missing` records
  "wont" as it is spelled, not as "won't". Words from the firmware's own strings keep their
  spoken form.
- The measurements are in `docs/measurements/2026-09-24-voice-rollout.txt`.

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
