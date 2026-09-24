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
`build/f7-firmware-C/firmware.bin` and the spare bytes (this branch: 868,668 bytes, 11,972
spare; the Task 6 image was 868,572, about 12 KB spare).

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
on the Mac from a high quality voice (Samantha by default) and played word by word. SAM is still
the fallback. A word without a clip is spoken by SAM and noted on the card, so nothing is left
unspoken.

On the card:

- `/ext/sr/voice/<initial>/<word>.raw`: one clip per word. The format is raw unsigned 8-bit
  mono at 16,000 samples per second, and 128 is silence. `<initial>` is the word's first letter
  or digit. A word is lower case letters, up to 16 of them, or a single digit.
- `/ext/sr/voice/voice.txt`: the generator's settings line, which `sr voice status` shows.
- `/ext/sr/missing.txt`: words the device could not find, one per line, each at most once per
  boot.

Console commands:

- `sr voice on` and `sr voice off` switch between the clips and SAM alone. The setting is saved.
- `sr voice status` prints the settings line, and three counts since boot: words spoken from
  clips, words that fell back to SAM, and words logged as missing. The settings line is read
  once per boot, so after a sync that changes it, the new line shows after a reboot.

Making the vocabulary with `tools/voice_build.py`:

- `tools/voice_build.py --extract --jobs 8` makes a clip for every word. The words come from the
  base list `tools/voice_words.txt` and from every string in the firmware's core apps and
  services, run through the reader's own pronunciation code. That is about 2,800 words and
  27 MB.
  - Time on this Mac: about 16 minutes with `--jobs 8`, or 22 minutes with the default of 4.
    The limit is the macOS speech server that `say` uses, not the CPU.
  - A rerun makes only new or changed clips.
- `.venv/bin/python tools/voice_build.py --sync` sends new or changed clips and voice.txt to the
  card.
  - The first sync of the whole vocabulary took about 7.5 minutes. Later syncs send only what
    changed, which takes seconds.
  - The recorded voice is switched off on the device during the transfer and switched back on
    afterwards.
  - After the card was wiped or replaced, add `--sync-all` to resend everything. `--sync-all`
    works only together with `--sync`.
- `.venv/bin/python tools/voice_build.py --pull-missing --sync` is the missing-word workflow. It
  fetches missing.txt from the card, makes clips for those words, sends them and removes the
  list. For a few words it takes about 4 seconds.
- `--sync` and `--pull-missing` need the venv Python, because they use the firmware's serial
  storage helper.
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

- Words with an apostrophe, such as don't, can't and it's, are spoken by SAM for now. So are
  words longer than 16 letters.
- The dolphin's speech bubble texts are not extracted. Their words reach the vocabulary through
  missing.txt.
- Some words cause underruns. The largest folders, s, c, m, p and d, hold up to 315 clips.
  Finding a word near the end of one of them takes up to about 65 ms, which is longer than one
  half of the speech ring (41 ms). Each such word causes a short glitch, counted as an underrun.
  Smaller folders would fix this. The numbers are in
  `docs/measurements/2026-09-24-voice-rollout.txt`.

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
