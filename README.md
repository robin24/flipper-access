# Flipper Zero accessibility project

Working notes for making a Flipper Zero usable without sight. The background research is in
`flipper-zero-accessibility-investigation.md`. This file records the current state of the device
and the tools in this folder. Last updated 2026-09-24.

## Device state

- Device name: R0skie. Hardware version 12, region DE. 64 GB microSD card, exFAT.
- Firmware: Momentum mntm-012 (built 31 December 2025), installed 2026-09-22 from the terminal.
  Before that it ran official firmware 1.4.3. Since then it runs the `screen-reader` branch built
  here: on 2026-09-24 that is phase 3 with its final review fixes, commit 859c87c98, API version
  87.2. The device carries firmware commit 70a60c8f5 plus the settings app of 859c87c98; the
  polish round's other fixes are built but not yet flashed.
- Serial port on this Mac: `/dev/cu.usbmodemflip_R0skie1`, 230400 baud. It disappears while the
  device is in the updater and comes back after the reboot.
- The Text to SAM app on the card (`/ext/apps/Media/text2sam.fap`) is a patched build that also
  speaks its launch argument. Its on-screen behaviour is unchanged.
- Sub-GHz loads as an external app from the card into RAM in this firmware base (mntm-012 had
  it in flash). With the reader on, its read mode leaves about 2 KB of heap and the frequency
  analyzer crashes out of memory (numbers in `docs/measurements/`), so avoid Sub-GHz while the
  reader is enabled until the memory plan in `docs/roadmap.md` makes room. Building it into the
  firmware was tried and reverted: the image did not fit below the BLE stack (see the flash
  limit under Useful commands). The other main apps (NFC, RFID, infrared, iButton, GPIO, Bad USB,
  U2F) load as external faps too; NFC read leaves about 24 KB with the reader on.
- Since the recorded voice's 8 KB speech ring (2026-09-24), the reader holds 4 KB more heap
  than when the numbers above were taken. Idle free heap went from 114,552 to 110,520 bytes.
  So Sub-GHz read is expected to run out of memory with the reader on, and NFC read to leave
  about 20 KB. On 2026-09-24, during phase 3, just opening Sub-GHz with the reader on ran out of
  memory and restarted the device. NFC read was not measured again.

## Using it on the device

Since phase 3 (2026-09-24) the screen reader can be controlled from the device alone. Chords with
the Back button read the screen, the status bar and the focus, spell the focus and set the
volume. An Accessibility screen in the Momentum settings holds the reader's settings. Screens that
draw only icons, such as the lock menu, the lock screen and the infrared universal remotes, now
have spoken names. Everything in this section was checked on R0skie, except where it says
otherwise. The device outputs are in `docs/measurements/2026-09-24-phase-3.txt`.

### Back chords

Hold Back, press a second key, then let go of Back. The second key goes to the screen reader
only. The app on the screen never sees it, so a chord never moves the focus or opens anything. A
third key pressed while the second is still held goes to the app as a normal key.

- Back and Up reads the whole screen from the top. The home screen, which draws no text of its
  own, reads as "Home screen". A long screen is read in several parts, one after the other.
- Back and Down reads the status bar: the time, when the status bar shows it, and the battery, as
  "battery 100 percent". A screen without a status bar, such as the main menu, answers "No
  status bar".
- Back and a short press of OK repeats the focused item with its position, for example "Apps, 1
  of 11". With nothing focused it says "No focus".
- Back and a long press of OK spells the focused item with the recorded letters: Apps is spelled
  A, P, P, S.
- Back and Left lowers the speech volume by 10, and Back and Right raises it by 10, between 0 and
  100. The reader says the new value, such as "Volume 60", and saves it.

More about the chords:

- The speech rate has no chord. Set it on the Accessibility screen, described below, or with
  `sr rate`.
- Back on its own works as before: a short press goes back. A long press of Back on its own,
  which opens the power-off dialog on the home screen, takes effect when you let go of Back, not
  after the usual 300 ms. That way a slow chord is never mistaken for a long press.
- The press of Back itself still reaches the app when a chord starts. On the home screen the
  dolphin may answer it with a speech bubble, which you may hear after the chord.
- Any other key press silences speech, as before.
- While the reader is off, the chords are ordinary key presses. Back and Up on the home screen
  then opens the lock menu.
- Chords work with the device's buttons and with `input send` on the console. Keys sent from
  `sr watch`, and from the remote control in qFlipper or the mobile app, bypass the chords.

To run a chord's command from the console without keys:

    .venv/bin/python tools/flipper_cli.py "sr chord up"

The keys are `up`, `down`, `ok`, `okhold`, `left` and `right`, as in the list above.

### The Accessibility settings

The reader's settings are one screen of the Momentum settings app. To get there, press OK on the
home screen for the main menu. Momentum is the second-last item, just before Settings. The menu
opens on its first item, Apps, and wraps around, so pressing Up twice reaches Momentum; then
press OK. The lock menu's Momentum tile opens the same app. The app first reads the firmware
version, then its list of four: Interface, Protocols, Misc and Accessibility. Press Up once, or
Down three times, to reach Accessibility, and press OK.

The Accessibility screen has five rows with the recorded voice, six with SAM. Up and Down move
between them. Left and Right change the value of the row you are on.

- Screen Reader, ON or OFF. OFF turns the reader off at once: nothing more is read, and the
  chords become ordinary keys. If that happens by mistake, press Right straight away. The
  selection is still on this row, and Right turns the reader back on and the screen is read
  again: you hear "Screen Reader ON". The console command `sr on` does the same.
- Voice, Recorded or SAM. Recorded speaks with the word clips on the SD card, SAM with the
  built-in synthesizer.
- Rate, from 40 to 120 in steps of 4. Bigger is slower. Shown only when Voice is SAM; the
  recorded voice's words play at the speed they were recorded, so there is nothing to set.
- Volume, from 0 to 100 in steps of 10. This is the same setting the Back and Left or Right
  chords change.
- Verbosity, Terse, Normal or Verbose. Terse leaves out the button labels at the bottom of a
  screen, Normal reads them, and Verbose also says the position, such as "3 of 11", each time
  the focus moves.
- Change delay, from 0.5 to 10 s, default 3 s. Same-screen changes such as a progress bar are
  spoken at most once per delay, with the latest value. A change within half a second of a key
  press is spoken at once; a new screen or focus is never delayed.

A change applies from the next thing the reader says. The settings are saved when you leave the
Momentum settings app: press Back until you hear "Home screen".

### The home screen and the lock menu

Coming back to the home screen is announced as "Home screen". That includes closing a dialog of
the home screen, such as the power-off dialog, or the lock menu. The dolphin's speech bubbles are
read only when you pressed a key in the last two seconds.

On the home screen, Up opens the lock menu: that is Momentum's default key for it. The lock menu
is a grid of icons, and the reader names the selected one. It opens on Lock.

- The six square tiles stand in three columns of two: Left handed above Settings, Dark mode above
  Lock, and Bluetooth above Momentum. To the right of them are two sliders, Brightness and
  Volume.
- Left and Right move from column to column and on to the sliders, and wrap around at the ends.
  Up and Down move between the two tiles of a column. On a slider, Up and Down change its level
  in steps of 5 percent.
- You hear "Lock", "Momentum", "Settings", "Left handed on" or "Left handed off", "Dark mode on"
  or "off", "Bluetooth on" or "off", and the sliders with their level, such as "Brightness 100"
  and "Volume 95". In stealth mode the Volume slider keeps its level and adds "muted", such as
  "Volume 95, muted".
- OK uses the selected tile. A switch flips, Settings and Momentum open those apps, Lock offers
  the ways to lock, described below, and Volume switches stealth mode on or off. Stealth mode
  mutes the device's own beeps and sounds; the reader keeps speaking.
- Back closes the lock menu, and you hear "Home screen".

### Locking and unlocking

Select Lock in the lock menu and press OK. A short list offers Keypad Lock, PIN Code Lock and PIN
Lock + OFF, read as "Keypad Lock, 1 of 3" and so on. Up and Down choose, and OK locks.

When the device locks, from this list or by the auto-lock timer, you hear "Locked, press Back
three times quickly to unlock". A PIN lock says "Locked with PIN, press Up to enter it". For two
seconds after that the reader says nothing else about the home screen, so the sentence is heard
in full.

Any key pressed on the lock screen brings up its hint, and the reader says "Press Back three
times quickly to unlock" or "Press Up to enter the PIN". Back and Up reads the whole lock screen,
including the time and date.

To unlock a keypad lock, press Back three times quickly: each press must come less than 0.6
seconds after the one before. You hear "Unlocked", then "Home screen".

For a PIN lock, press Up to open the PIN entry. A PIN is a sequence of arrow key presses. The
reader says how many you have entered, "1 digit entered", "2 digits entered" and so on, never
which keys. OK confirms the PIN, and Back clears what you entered. The PIN entry has not been
tried on the device yet: setting a PIN unattended could have locked Robin out of the device.

### Infrared universal remotes

In the Infrared app, Universal Remotes lists TVs, Projectors, Audio, ACs, LEDs, Fans,
Blu-ray/DVDs, Monitors and Digital Signs. A remote's buttons are icons, and the reader now names
them. When a remote has loaded its codes, which takes about 10 seconds for TVs, you hear its name
and the selected button, for example "TVs. Power". Each button you move to is named: "Mute",
"Volume up", "Channel down", "Cool high", "Dry", "Next" and so on. OK sends the button as before.

The remotes are drawn upright, for the Flipper turned a quarter turn clockwise, and the arrow keys
are turned with them. With the Flipper held normally, Right moves down a column of buttons and
Left moves up it; Up moves to the right-hand column and Down to the left-hand one. On the TV
remote the left column is Power, Channel up and Channel down, and the right column is Mute,
Volume up and Volume down. Turned a quarter turn clockwise, so that the Right key points down,
the keys move the way they point.

### NFC-V emulation

When NFC emulates an ISO15693 (NFC-V) card, its "Emulating" screen is read in full first. Then
the emulation takes over the speaker, and the reader stays silent until you leave with Back.

### Known limits

- Sub-GHz does not fit in memory beside the reader: on 2026-09-24 opening it restarted the device
  with an out of memory error. Avoid Sub-GHz until the memory plan in `docs/roadmap.md` makes
  room.
- The dolphin keeps drawing speech bubbles behind the lock screen, and now and then one is read
  around a lock.
- The screen shown after a firmware update is not read. Back closes it.
- After a PIN unlock, "Unlocked" and "Home screen" may come in the other order.
- Twice, after a long idle, the first OK that the scripted driver `tools/sr_drive.py` sent on the
  home screen opened the lock menu instead of the main menu. It has not been reproduced since and
  is not explained. Up, not OK, is the default key for the lock menu. Back closes it.
- Keys sent from `sr watch` and from remote control bypass the chords, as described under Back
  chords.

## Folder contents

- `tools/flipper_cli.py`: send commands to the Flipper CLI and print the replies with colour
  codes stripped. Example: `.venv/bin/python tools/flipper_cli.py "info device" "loader list"`.
- `tools/say.sh`: speak text on the device. Example: `tools/say.sh Hello there`.
  Voice control: `tools/say.sh --voice 64,72,128,128 Hello` with pitch, speed, mouth, throat.
  Bigger speed numbers talk slower. Keep each call under about 200 characters.
- `.venv/`: Python virtual environment with pyserial and colorlog (used by the helper scripts).
- `Momentum-Firmware/`: full source clone, branch `screen-reader`, with the ARM toolchain
  downloaded by fbt.
  API version 87.2 since phase 3, which exported two calls for the screen reader's spoken names
  of icons. Apps built here run on the device, and apps built for 87.1 still load.
- `patches/text2sam-cli-mode.patch`: the change to Text to SAM (applies inside
  `Momentum-Firmware/applications/external`, which is a git submodule).
- `firmware-packages/`: Momentum mntm-012 and official 1.4.3 update packages.
- `backups/backup-stock-1.4.3.tar`: internal storage backup taken on official 1.4.3 before the
  Momentum install (settings, dolphin state, region data).
- `tools/sr_drive.py`: scripted check of the screen reader console stream, and with
  `--interactive` a tethered screen reader: arrows, Enter, Backspace drive the device, Tab
  reads the screen, letters type into text fields, Ctrl-C ends. The scripted check has three
  sessions: the menus, an app's keyboard, and the Back chords on the home screen and in the main
  menu. `--chords` runs only the chords. Start it on the home screen.
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
`build/f7-firmware-C/firmware.bin` and the spare bytes. This branch after phase 3 and its final
review fixes, at 859c87c98 on 2026-09-24: 877,036 bytes, 3,604 spare. After phase 3 before those
fixes, at 6c7469a79: 875,928 bytes, 4,712 spare. Before phase 3, at d5b77c219: 872,048 bytes,
8,592 spare. Before the recorded voice, at 54794522b: 869,756 bytes, 10,884 spare.

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
timing; `sr stop` silences; `sr rate <40..120>`, `sr volume <0..100>` and `sr delay <500..10000>`
are saved settings.
`sr chord up|down|ok|okhold|left|right` runs what Back and that key do (see Back chords above).
Any button press silences speech. On the home screen the dolphin's speech bubbles are not
spoken unless a button was pressed in the last two seconds (`sr status` counts them as
suppressed; `sr watch` still shows them). A change dropped while held -- superseded by a newer
one, or by the quiet rules once it comes due -- never reaches `sr watch`; only the suppressed
counter (`sr status`) may show it. During NFC-V emulation the reader is silent, because
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
routine command, `.venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing
--sync`.

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
  - the dolphin's speech bubble texts;
  - the apps on the card, with `--card-apps`, or every app under `applications/external` with
    `--extract-all` for a wider one-off build instead of just the ones installed.

  Everything goes through the reader's own pronunciation code.
  - Time on this Mac: about 16 minutes with `--jobs 8`, or 22 minutes with the default of 4.
    The build is limited by `say` itself, not by CPU count.
  - A rerun makes only new or changed clips.
  - Locally the clips sit in `voice/<first letter>/<word>.raw`. The sync puts each one into its
    hashed folder on the card.
- Add `--dry` to any of the above to build the word list and print its counts -- how many
  strings, how many words, the ten longest, and with `--card-apps` which faps matched which
  source folder -- without making a single clip or touching the card.
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
- `.venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync` is the
  missing-word workflow. It fetches missing.txt from the card, makes clips for those words,
  sends them and removes the list. `--extract` is there because the spoken spelling of
  apostrophe words comes from the extraction, not from missing.txt, which has already lost
  them. `--card-apps` adds the strings of the apps actually on the card, so a newly installed
  app's own words get clips too. For a few words it takes about 3 to 4 seconds.
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
7. Done: phase 3, on-device control: Back chords, the Accessibility settings screen, and
   spoken names for screens that draw only icons (2026-09-24).
8. Next: the memory plan in `docs/roadmap.md`, so that Sub-GHz works with the reader on.
