# Flipper Access

Flipper Access is the project behind Sonar, a firmware for the Flipper Zero that a blind person
can use without sight. Sonar is built on [Momentum](https://github.com/Next-Flip/Momentum-Firmware),
and its screen reader speaks every screen through the device's own speaker in a recorded voice.
This repository holds the documentation, the tools and the releases, which are the downloads to
install. The firmware's source is the fork at https://github.com/robin24/Momentum-Firmware, branch
`screen-reader`.

## How it was made

Sonar was written almost entirely by AI coding agents (Claude) working under the direction of
Robin Kipp, a blind developer, who tested every change on the device and decided what it should
do. Momentum's repository does not accept AI-written contributions, and the reader's memory needs
would sit behind a build flag there in any case, so this is a separate firmware rather than a pull
request. The specs, plans and build logs under `docs/` are the full record of how it was built.

The reasoning behind the separate firmware is in `docs/roadmap.md`, and `docs/README.md` is the
index of everything under `docs/`.

## What changed against Momentum

Added:

- A screen reader service speaks every screen, and chords with the Back button control it from
  the device's own keys.
- The Accessibility settings, a screen of the Momentum settings app, hold the reader's on and off
  switch, its volume, its verbosity and its change delay.
- Screens that draw only icons, such as the lock menu, the lock screen and the infrared universal
  remotes, have spoken names.
- The dolphin's level and mood are said in words: the status chord, Back with a short press of
  Down, says them, and a new level is announced.
- The crash popup ends with an address that locates the crash in the code, the failed check or,
  after a hardware fault, the instruction that faulted, and the reader speaks it.
- The reader speaks in a recorded voice, one clip per word from the SD card, made with a generator
  in this repository.

Removed:

- The games are gone from the build and from the card.
- The JavaScript engine, its script runner and its modules are gone from the firmware and the
  card.
- The screen reader's own SAM synthesizer is gone. The reader speaks only from the recorded clips,
  so without them it is silent.
- Momentum's tutorial of seven pictures at the first boot is gone, from the update package, the
  card and the Momentum app's Misc screen, since the reader cannot read its pictures. A first boot
  shows the picture that every update shows, which the reader speaks.
- The home screen's animations are off by default, and a setting turns them back on. With them
  off, the home screen has nothing else to read, and returning to it loads nothing from the card.

Changed:

- The screen reader is on from the first boot.
- The main menu starts in the List style, which the reader reads most cleanly. The other styles
  name the selected app and its position too, but some draw text of their own beside the apps,
  such as a clock or the free memory, which is read with the screen.
- FreeRTOS checks the threads' stacks for overflow, which Momentum ships switched off. An
  overflow crashes the device at once as "StackOverflow"; only the debug log names the thread.
- The picture after an update is spoken, and its view copes with being drawn, or sent a key's
  release, while it has no picture loaded, which crashed some boots after an update.
- `./fbt flash_usb_full` also works on a blank card, whose console lacks the loader command, a
  plugin on the card, that the flash used to close the running app first.

The removals were made so that Sub-GHz works with the reader on. It is built into the firmware
again, not loaded from the card, and no longer crashes the device out of memory.

## Install

Sonar is installed from a computer over the Flipper's USB cable, with the install script that
comes with each release. It works from the official firmware, from Momentum and from an earlier
Sonar, and with a blank card too. To build the firmware yourself instead, see Building from source.

### What you need

- The Flipper Zero with a microSD card in it, and a USB cable to the computer. The Flipper must be
  unlocked, since a Flipper locked with a PIN closes its console, and qFlipper must be closed,
  since only one program at a time can use the Flipper's port.
- A computer with macOS, Linux or Windows, and Python 3.10 or newer. The script needs one Python
  package, pyserial, and nothing else.
- A card reader for microSD cards in the computer, if you have one. It is not needed, but the
  install is faster with it.

This command shows which Python you have:

```bash
python3 --version
```

It must say 3.10 or newer. The `python3` that comes with the Mac's command line tools is 3.9,
while Homebrew's and the installer from python.org are newer. On Windows, Python comes from
python.org, and its command is `py` where these commands say `python3`.

### The downloads

The releases are at https://github.com/robin24/flipper-access/releases. Download four files of
the newest release into one folder. For the release `sonar-0.1.0` they are these, and a later
release has its own version in their names:

- `flipper-z-f7-update-sonar-0.1.0.tgz`, the firmware's update package, about 12 MB.
- `voice-heart-sonar-0.1.0.tar`, the voice, about 111 MB.
- `install-sonar-0.1.0.zip`, the install script with its three helpers and the licence.
- `release.json`, the release's description, which the script checks the installed firmware
  against.

A release has more files, which the install does not need: `SHA256SUMS`, the checksums of all the
others; the firmware's elf and map, which turn a crash address into a line of code; the SDK, for
building apps; and the source bundle, the source of every binary, described under Licence and
credits.

To check your downloads, download `SHA256SUMS` into the same folder too, and run this command
there. Each file you downloaded should say OK:

```bash
shasum -a 256 -c --ignore-missing SHA256SUMS
```

On Linux, the same check is:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

Unpack the install zip in the same folder. From a terminal in that folder, on a Mac or Linux:

```bash
unzip install-sonar-0.1.0.zip
```

On Windows, this does the same in a terminal:

```bash
tar -xf install-sonar-0.1.0.zip
```

That gives `install.py`, `flipper_cli.py`, `flipper_storage.py`, `card_prune.py` and `LICENSE`.
Then make a virtual environment in the folder, once, and put pyserial into it. It is the folder
`.venv`, as for the tools of this repository:

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install pyserial
```

On Windows, `.venv\Scripts\pip` and `.venv\Scripts\python` take the place of `.venv/bin/pip`
and `.venv/bin/python` in these commands.

### Running the install

Plug the Flipper in, unlock it, and run the script from the same folder:

```bash
.venv/bin/python install.py --package flipper-z-f7-update-sonar-0.1.0.tgz --voice voice-heart-sonar-0.1.0.tar --release release.json
```

Its three arguments, one by one. `--package` names the update package:

```text
--package flipper-z-f7-update-sonar-0.1.0.tgz
```

`--voice` names the voice pack:

```text
--voice voice-heart-sonar-0.1.0.tar
```

`--release` names the release's description. After the update, the script compares the firmware
on the Flipper with it and says whether it is the release's:

```text
--release release.json
```

Two more options are there when needed. `--port` names the Flipper's serial port, when the script
does not find it by itself. `--yes` asks nothing, and sends the voice over USB. This command lists
every option and the steps:

```bash
.venv/bin/python install.py --help
```

### What the install says and does

The Flipper itself says nothing about the install: other firmware has no reader, and Sonar's
reader is silent while the voice is unpacked and while the Flipper updates. The script speaks for
it: it says each step on its own line, for the computer's screen reader, to the very end. The
Flipper's first words come after the update, as described under First boot.

The steps, in order:

1. The script looks for the Flipper, and says where it found it and which firmware and version
   the Flipper runs.
2. It says what it will do and asks whether to go ahead. Enter alone means yes.
3. It asks which way the voice goes. Enter alone, or R, means the card reader, and U means USB:

   ```text
   Copy the voice through a card reader (faster) or over USB? [R/u]
   ```

4. It backs up the Flipper's internal storage to the card, as `/ext/backup-<date>.tar`, such as
   `/ext/backup-2026-10-11.tar`, and says the name. A backup that is already there is kept, and
   the new one is then named `backup-<date>-2.tar`, and so on. The backup holds the settings of
   the firmware you came from, and it is the way back, as described under Going back.
5. It puts the voice on the card, through the card reader or over USB, as described below.
6. It sends the update package to the card and starts the update. The Flipper restarts, updates
   itself and restarts again, silent all the while. The script waits for it, up to 15 minutes,
   and says a line about once a minute. Coming from other firmware, the update may also replace
   the Bluetooth radio's stack, which adds a restart and a few minutes.
7. It reads the firmware again and says whether the Flipper runs the release.
8. It removes Sonar's older update packages from the card. The packages of other firmware, such
   as the official one, stay.
9. It says "Done, after", and the minutes it took.

When a step fails, the script says in one sentence which step it was and the reason the Flipper
gave, and stops. Running it again is safe: the clips of the voice are overwritten, the folders are
kept, and the update package is replaced.

Through a card reader, the script first writes a small marker file to the card. Then it asks you
to take the microSD card out of the Flipper and put it into the computer's card reader, leaving the
Flipper plugged in and unlocked. It finds the card by the marker, unpacks the voice onto it, removes
the marker and the `._` files that macOS puts beside everything it writes, and ejects the card.
Then it asks you to put the card back into the Flipper, and waits until the Flipper sees the voice.
When no card turns up within 5 minutes, it says so and offers to send the voice over USB instead.
On a Mac, macOS may first ask whether the terminal may use the files on a removable volume; allow
it.

Over USB, the script sends the voice to the card as one file, and the Flipper unpacks it there.
When the Flipper already runs Sonar, its voice is off while the pack is unpacked, and it comes back
by itself if the script stops.

### How long it takes

Most of the time goes to the voice, which is about 111 MB. Over USB, a test install on a Mac on
2026-10-11 took 32 minutes in all, on a card that already held the voice: about 11 minutes to send
the voice, 13 to unpack it, a minute to send the update package, and 6 for the update. On a card
without the voice, the unpacking takes about 16 minutes, so a first install over USB takes about
35. The card reader way is faster, since the computer writes the voice to the card itself; it has
not been timed yet.

## First boot

The screen reader is on from the first boot. It speaks only from the recorded voice on the SD
card, so without the card, or without the voice on it, it is silent.

After the install, and after every later update, the device shows a picture saying that the
firmware was updated. The reader says "Firmware updated, press OK to continue" without a key
press, and OK, Right or Back closes it. Momentum's tutorial of seven pictures at the first boot is
left out, since its words are drawn as pixels and it waits for given arrow keys.

Two chords are the first things to try. For each, hold Back, press the second key, then let go of
Back.

- The status chord, Back and a short press of Down, reads the status bar, then the dolphin's level
  and mood, such as "battery 100 percent", then "level 3, mood happy".
- The read chord, Back and Up, reads the whole screen from the top. The home screen, which draws
  no text of its own, reads as "Home screen".

To turn the reader off, hold Back and then Down until the long press registers, about a third of a
second. You hear "Screen reader off". The same chord turns the reader on again, and you hear
"Screen reader on" followed by the screen. It works on every screen, the lock screen included, and
also in the PIN entry, where the digits entered so far are kept.

## Going back

The install script installs any firmware's update package, the official firmware's and Momentum's
included, and puts back the backup that the Sonar install made. The official firmware's update
package comes from Flipper's update server, such as version 1.4.3 at
https://update.flipperzero.one/builds/firmware/1.4.3/flipper-z-f7-update-1.4.3.tgz, and Momentum's
from its releases at https://github.com/Next-Flip/Momentum-Firmware/releases, such as
`flipper-z-f7-update-mntm-012.tgz`.

Download the package into the folder of the install, and run the script with it and with the
backup, named by its path on the card:

```bash
.venv/bin/python install.py --package flipper-z-f7-update-1.4.3.tgz --restore /ext/backup-2026-10-11.tar
```

Its two arguments, one by one. `--package` names the update package:

```text
--package flipper-z-f7-update-1.4.3.tgz
```

`--restore` names the backup to put back:

```text
--restore /ext/backup-2026-10-11.tar
```

Give the name of your own backup, the one the install that brought Sonar said, since that one holds
the settings of the firmware you came from. Every later install makes a backup of Sonar's settings
too, under a later date. `--restore` also takes a backup file on the computer, which the script
sends to the card first.

The script makes a new backup first, then installs the package, waits for the Flipper, checks that
it runs the package's version, and puts the old backup back. Then it tells you to restart the
Flipper, so that it reads the settings: hold Left and Back together for five seconds. It also
removes Sonar's update packages from the card. The official firmware and Momentum have no screen
reader, so the Flipper is silent from the update on, and the script says each step to the end. The
voice stays on the card, in the folder `sr`, which other firmware ignores.

To go back to an earlier Sonar release, install that release's files as described under Install.

## Using it on the device

The screen reader can be controlled from the device alone. Chords with the Back button read the
screen, the status bar and the focus, spell the focus, set the volume and turn the reader off and
on. An Accessibility screen in the Momentum settings holds the reader's settings. Screens that draw
only icons, such as the lock menu, the lock screen and the infrared universal remotes, have spoken
names.

A few sections also give a console command. It is sent from a computer over USB with
`tools/flipper_cli.py` from this repository, set up as described under Building from source. After
an install from a release, the same tool is in the install's folder, without the `tools/` in front:
there the commands start with `.venv/bin/python flipper_cli.py`.

### Back chords

Hold Back, press a second key, then let go of Back. The second key goes to the screen reader
only. The app on the screen never sees it, so a chord never moves the focus or opens anything. A
third key pressed while the second is still held goes to the app as a normal key.

- Back and Up reads the whole screen from the top. The home screen, which draws no text of its
  own, reads as "Home screen". A long screen is read in several parts, one after the other.
- Back and a short press of Down reads the status bar, then the dolphin's level and mood. You hear
  the time, when the status bar shows it, then the battery, as "battery 100 percent", then "level
  3, mood happy". The mood is happy, okay or angry, as the Passport shows it. A screen without a
  status bar, such as the main menu, answers with the level and the mood alone.
- Back and Down held until the long press registers, about a third of a second, turns the reader
  off, or on again. You hear "Screen reader off", or "Screen reader on" followed by the screen. It
  works while the reader is off, and on every screen, the lock screen included, and also in the
  PIN entry, where the digits entered so far are kept.
- Back and a short press of OK repeats the focused item with its position, for example "Apps, 1
  of 11". With nothing focused it says "No focus".
- Back and a long press of OK spells the focused item with the recorded letters: Apps is spelled
  A, P, P, S.
- Back and Left lowers the speech volume by 10, and Back and Right raises it by 10, between 0 and
  100. The reader says the new value, such as "Volume 60", and saves it. During a firmware update
  a volume change is heard but not kept, since no settings are saved while the device updates.

More about the chords:

- Back on its own works as usual: a short press goes back. A long press of Back on its own, which
  opens the power-off dialog on the home screen, takes effect when you let go of Back, not after
  the usual 300 ms. That way a slow chord is never mistaken for a long press. This holds while the
  reader is off too, since Back and Down held works then.
- The press of Back itself still reaches the app when a chord starts. Animations are off by
  default; with them on, the dolphin on the home screen may answer that press with a speech
  bubble, which you may hear after the chord.
- Any key press outside a chord silences speech.
- While the reader is off, the chords are ordinary key presses, all but Back and Down held, which
  turns the reader on again. Back and Up on the home screen then opens the lock menu. A short press
  of Down while Back is held does nothing then: the reader holds Down back until it is held long.
  If you let go of Back before Down's long press, a long press of Back is dropped, so the chord
  can still turn the reader on without the power-off dialog opening as well.
- Holding Back does not repeat, with the reader on or off, and for sighted users too, since the
  long press of Back waits for its release. In the text keyboard, holding Back deletes one
  character when you let go, not one after another while you hold it. In the byte keyboard,
  holding Back clears the selected byte when you let go.
- Back and Down held works on the lock screen too, where Back with Down means nothing else. After
  a reboot into a lock with the reader off, it is the way to get speech back.
- Chords work with the device's buttons and with `input send` on the console, each on its own: a
  Back sent from the console makes chords only with keys sent from the console, so a script cut off
  between a Back press and its release cannot turn the buttons into chords. Keys sent from
  `sr watch` bypass the chords. That console command streams the reader's announcements and lets
  arrows, Enter and Backspace drive the device. The tethered reader in this repository runs it:

  ```bash
  .venv/bin/python tools/sr_drive.py --interactive
  ```

  Keys from the remote control in qFlipper or the mobile app bypass the chords too.

To run a chord's command from the console without keys:

```bash
.venv/bin/python tools/flipper_cli.py "sr chord up"
```

The keys are `up`, `down`, `ok`, `okhold`, `downhold`, `left` and `right`, as in the list above.
`downhold` works while the reader is off, as the chord does; the others then answer "screen
reader is off".

### The Accessibility settings

The reader's settings are one screen of the Momentum settings app. To get there, press OK on the
home screen for the main menu. Momentum is the second-last item, just before Settings. The menu
opens on its first item, Apps, and wraps around, so pressing Up twice reaches Momentum; then press
OK. The lock menu's Momentum tile opens the same app. The app first reads the firmware version,
then its list of four: Interface, Protocols, Misc and Accessibility. Press Up once, or Down three
times, to reach Accessibility, and press OK.

The Accessibility screen has five rows. Up and Down move between them. Left and Right change the
value of the row you are on.

- Screen Reader, ON or OFF. OFF turns the reader off at once: nothing more is read, and the
  chords become ordinary keys, all but Back and Down held. If that happens by mistake, press Right
  straight away. The selection is still on this row, and Right turns the reader back on and the
  screen is read again: you hear "Screen Reader ON". Or, on any screen, including the lock screen,
  hold Back and then Down until the long press registers, about a third of a second: you hear
  "Screen reader on" and the screen. This console command also turns the reader on. It reads the
  screen, without saying "Screen reader on" first:

  ```bash
  .venv/bin/python tools/flipper_cli.py "sr on"
  ```
- Voice, the recorded voice set the reader speaks with: Auto, the first set on the card in name
  order, then each set on the card by name. None when the card holds no set. Auto is also what
  the reader falls back to when the set chosen is no longer on the card. The console's
  `sr voice use` sets the same, with a set's name, in quotes when it has a space, or auto.
- Volume, from 0 to 100 in steps of 10. This is the same setting the Back and Left or Right
  chords change.
- Verbosity, Terse, Normal or Verbose. Terse leaves out the button labels at the bottom of a
  screen, Normal reads them, and Verbose also says the position, such as "3 of 11", each time the
  focus moves.
- Change delay, from 0.5 to 10 s, default 3 s. Same-screen changes such as a progress bar are
  spoken at most once per delay, with the latest value. A change within half a second of a key
  press is spoken at once; a new screen or focus is never delayed.

A change applies from the next thing the reader says. The settings are saved when you leave the
Momentum settings app: press Back until you hear "Home screen".

### The home screen and the lock menu

Coming back to the home screen is announced as "Home screen". That includes closing a dialog of
the home screen, such as the power-off dialog, or the lock menu.

Animations are off by default, so the dolphin never plays an idle animation or draws a speech
bubble. The home screen then has nothing else to read, and returning to it loads nothing from the
card. To turn animations on, go to Momentum, Interface, Graphics; Animations is the first row, OFF
or ON. Changing it reboots the device: leaving the app shows "Rebooting..." and the device
restarts. With animations on, the dolphin's speech bubbles are read only when you pressed a key in
the last two seconds.

When the dolphin reaches a new level, the reader says "Level up, level 4". The dolphin earns its
points from deeds: an app such as Sub-GHz or NFC records one when you do something with it. The
announcement is queued about two seconds after the deed, later when a screen change follows within
those two seconds, but at most five seconds after the deed. So it is heard after the new screen
has been read. A key pressed while it waits in the speech queue or plays silences it, like all
speech.

With animations off, the level up is granted at the deed that completes the level's points, or at
the next boot when a level up was left pending. A level granted at boot is usually not announced,
because the reader may read its starting level only after the grant; the status chord tells you
the level at any time. With animations on, the level up is granted when you press a key on the
home screen's mail animation. A level raised by hand in Momentum, Misc, Dolphin is said as a level
up at the next deed; a level lowered by hand is only noted.

The Passport, which Right opens on the home screen, shows the level, the mood and the points. The
points line is labelled XP, which the reader says as "experience". It ends with the level the
points lead to, "to level 3", which the reader says but the screen does not show. At level 2
with 7 of its 100 points, the Passport reads the device's name, then "Mood, Happy. Level, two.
experience seven slash one hundred to level three". OK in the Passport shows the points in total
instead, and the line then ends with the last level, "to level 30". At the last level the line is
"Max Level!", with nothing after it.

On the home screen, Up opens the lock menu: that is Momentum's default key for it. The lock menu
is a grid of icons, and the reader names the selected one. It opens on Lock.

- The six square tiles stand in three columns of two: Left handed above Settings, Dark mode above
  Lock, and Bluetooth above Momentum. To the right of them are two sliders, Brightness and Volume.
- Left and Right move from column to column and on to the sliders, and wrap around at the ends.
  Up and Down move between the two tiles of a column. On a slider, Up and Down change its level
  in steps of 5 percent.
- You hear "Lock", "Momentum" and "Settings", and the switches with their state: "Left handed on"
  or "Left handed off", "Dark mode on" or "off", "Bluetooth on" or "off". The sliders are named
  with their level, such as "Brightness 100" and "Volume 95". In stealth mode the Volume slider
  keeps its level and adds "muted", such as "Volume 95, muted".
- OK uses the selected tile. A switch flips, Settings and Momentum open those apps, Lock offers
  the ways to lock, described below, and Volume switches stealth mode on or off. Stealth mode
  mutes the device's own beeps and sounds; the reader keeps speaking.
- Back closes the lock menu, and you hear "Home screen".

### Locking and unlocking

Select Lock in the lock menu and press OK. A short list offers Keypad Lock, PIN Code Lock and PIN
Lock + OFF, read as "Keypad Lock, 1 of 3" and so on. Up and Down choose, and OK locks.

When the device locks, from this list or by the auto-lock timer, you hear "Locked, press Back
three times quickly to unlock". A PIN lock says "Locked with PIN, press Up to enter it". For two
seconds after that the reader says nothing else about the home screen, so the sentence is heard in
full.

Any key pressed on the lock screen brings up its hint, and the reader says "Press Back three times
quickly to unlock" or "Press Up to enter the PIN". Back and Up reads the whole lock screen,
including the time and date.

To unlock a keypad lock, press Back three times quickly: each press must come less than 0.6
seconds after the one before. You hear "Unlocked", then "Home screen".

For a PIN lock, press Up to open the PIN entry. A PIN is a sequence of arrow key presses. The
reader says how many you have entered, "1 digit entered", "2 digits entered" and so on, never
which keys. OK confirms the PIN, and Back clears what you entered. A wrong PIN says "Wrong PIN try
again". From the third wrong PIN in a row, a timeout screen follows, 30 seconds after the third,
twice as long after each one more. While the device is locked with a PIN its console is closed, so
the computer's tools cannot reach it until it is unlocked.

### Infrared universal remotes

In the Infrared app, Universal Remotes lists TVs, Projectors, Audio, ACs, LEDs, Fans,
Blu-ray/DVDs, Monitors and Digital Signs. A remote's buttons are icons, and the reader names them.
When a remote has loaded its codes, which takes about 10 seconds for TVs, you hear its name and
the selected button, for example "TVs. Power". Each button you move to is named: "Mute", "Volume
up", "Channel down", "Cool high", "Dry", "Next" and so on. OK sends the button.

The remotes are drawn upright, for the Flipper turned a quarter turn clockwise, and the arrow keys
are turned with them. With the Flipper held normally, Right moves down a column of buttons and
Left moves up it; Up moves to the right-hand column and Down to the left-hand one. On the TV
remote the left column is Power, Channel up and Channel down, and the right column is Mute,
Volume up and Volume down. Turned a quarter turn clockwise, so that the Right key points down, the
keys move the way they point.

### NFC-V emulation

When NFC emulates an ISO15693 card, also called NFC-V, its "Emulating" screen is read as usual.
From the first exchange with an NFC reader on, the emulation keeps the speaker, whose timer it
needs, and the screen reader stays silent until you leave with Back.

### The file browser's menus

Down on the home screen opens the file browser, which Momentum calls Archive. Left and Right
switch its tabs: Favorites, Sub-GHz, RFID, NFC, Infrared, Bad KB, Apps, Search and Browser. Up and
Down move in the list, and OK opens a folder or a file.

A new tab is said by its name, then its selected entry, such as "NFC, Fun_Files". A folder you
open there is not named: the tab's name stays the screen's name.

The Apps menu and the file lists that apps open, such as a saved signal to load, name a folder as
it opens, then say "Parent folder", the entry that leads back up, which has no position; the
entries below it count from 1, so the first of five files is "1 of 5".

A long press of Back opens the manage menu for the selected entry: Cut, Copy, New Dir, Rename and
Delete, with Paste once something is cut or copied. A long press of OK opens the actions menu: Run
In App, Favorite, Info and Show. Left or Right inside a menu flips between the two. The reader
names the selected entry of these menus as you move.

Delete asks `Delete <name>?`, naming the entry, with Cancel on Left and Delete on Right. It
removes a folder with everything in it.

One flaw is known: when a menu opens over the list, the reader reads the menu's words mixed with
the file names showing behind it. The selection is read correctly after that.

### Keyboards

The on-screen keyboards for text, numbers and bytes open with their prompt, the value in the
field and the selected key, for example "Name the signal. RAW_433. Save". Moving says the key;
Save, Backspace, the keyboard switch and the number keyboard's sign key are said by name. A
character typed into the field is said, a space as "space", and "deleted" when one is removed.

Up from the top row of the text keyboard moves into the field. The reader then says where the
cursor is, such as "Cursor after r, 3 of 4", and again whenever Left or Right moves it. Down goes
back to the keys.

The byte keyboard, used for NFC keys, RFID data and the Bad USB IDs, says the bytes on screen and
the byte being edited after every key press, such as "12 A4 56 78, byte 2 of 4, digit 2": digit
2 means the next key sets the byte's second digit.

## The voice

The reader speaks with recorded clips from the SD card, one clip per word, played word by word.
Nothing else is built in: without the clips, the reader is silent.

A word without a clip is spelled letter by letter with the recorded letters and digits, 60 ms
apart, so nothing is left unspoken. The letters are recorded by their names, so "NFC" is heard as
"en eff see", not "capital N capital F capital C". The names are in `tools/voice_names.txt`. A
letter whose clip is missing too is skipped and noted, like a word.

Every word the device had to spell is noted on the card, one per line, in the `missing.txt` of
the voice set in use. The device remembers the last 64 words it noted, so a word is noted once
per boot unless 64 others came after it. The generator's missing-word command, under Making a
vocabulary, fetches that list, makes clips for its words and sends them to the card. So a spelled
word gets its own clip at the next run.

### On the card

The card holds one folder per voice set, `/ext/sr/voices/<set>/`. A set is a vocabulary made with
one engine and one voice: `heart`, made with Kokoro's voice af_heart, for example, or `samantha`,
made on a Mac with its Samantha voice. The reader speaks with the set chosen in the Accessibility
settings' Voice row or with `sr voice use`; Auto, the default, is the first set in name order. On
a card with the release's voice alone, Auto speaks with heart. A set added later whose name comes
first in name order, such as `espeak`, then becomes Auto's choice; choose heart in the Voice row to
keep it.

In a set's folder, each clip is a file `<hh>/<word>.raw`, where `<hh>` is one of 64 folders,
named by two hex digits: the word's FNV-1a hash modulo 64. Finding a file on the card means
reading its folder's entries one by one, in the order the files were made, so many small folders
keep every clip quick to open, and the sync and the release pack write the most spoken words
first into a new folder: the base list, then the firmware's own words by how often its texts use
them. A set already on the card keeps the order it was written in. A
clip is raw unsigned 8-bit mono sound at 16,000 samples per second, where 128 is silence.

Beside the clip folders are `voice.txt`, the generator's settings line, which `sr voice status`
shows; `missing.txt`, the words the device had to spell; and, in a set from a release,
`LICENSE.txt`. The settings line of a Kokoro set reads:

```text
kokoro af_heart rate 100 highpass 500 gain 1.3 soft 16000
```

### Voice commands on the console

This command mutes the reader, so nothing is played:

```bash
.venv/bin/python tools/flipper_cli.py "sr voice off"
```

This one unmutes it:

```bash
.venv/bin/python tools/flipper_cli.py "sr voice on"
```

With a number of seconds, up to 3600, the mute ends by itself after that time; this one mutes
for a minute:

```bash
.venv/bin/python tools/flipper_cli.py "sr voice off 60"
```

The setting is not saved: the voice is on again after every reboot.

This command names the voice sets on the card and marks the one in use:

```bash
.venv/bin/python tools/flipper_cli.py "sr voice list"
```

This one picks a set by its name, as the Voice row does, and saves it. A name with a space goes in
quotes, and `auto` goes back to the first set in name order:

```bash
.venv/bin/python tools/flipper_cli.py "sr voice use heart"
```

`sr voice status` prints the first 63 characters of the settings line, and these counts since
boot:

- words, and letters of spelled words, spoken from clips;
- words spelled letter by letter because they had no clip;
- words logged as missing;
- items completed muted, with the voice off or no vocabulary on the card;
- items completed silently because the app on screen left less than 4 KB of memory free in one
  block, which opening the clips needs for a moment;
- the longest and the latest clip open, in ms.

```bash
.venv/bin/python tools/flipper_cli.py "sr voice status"
```

The settings line is read at the first utterance after boot that uses the voice. So after a sync
that changes it, the new line shows after a reboot. With the voice off, the vocabulary figure
keeps its last value: the card is looked at again only when something is spoken with the voice
on.

### Licensing

A release ships one voice, the set `heart`, made with Kokoro, an open speech model by hexgrad,
with its voice af_heart. Its licence is the file `LICENSE.txt` in the set's folder on the card,
written to be read line by line:

- Kokoro's model is under the Apache License 2.0, whose whole text the file carries, with the
  model's version and the checksums of the two model files the clips were made with.
- What the Sonar project adds, the choice of words, the processing and the layout, is released
  under CC0 1.0, which dedicates it to the public domain as far as the law allows.
- The file also gives the credits of the model's card: the StyleTTS 2 architecture, by Li et al.,
  and two sets of training audio, Koniwa under CC BY 3.0 and SIWIS under CC BY 4.0.

More voices can be made with the generator, as described under Making a vocabulary, and chosen in
the Voice row: with eSpeak-NG, under the GPL-3.0, with its voice en-us+f3, or with another of
Kokoro's voices. A pack of such a set, made with `tools/voice_pack.py`, carries the same kind of
licence file. The generator can also use the voices of macOS's `say`, which Apple licenses for use
on the Mac, so a set made that way is for the maker's own device only.

### Making a vocabulary

`tools/voice_build.py` makes the clips of one voice set on a computer and copies them to the
card. `--set` names the set, `samantha` by default. It has three backends, each with its default
voice. `say`, the default, uses the Mac's voices, Samantha unless `--voice` names another:

```bash
.venv/bin/python tools/voice_build.py --extract --jobs 8
```

`espeak` uses eSpeak-NG, from the system's package manager, such as Homebrew's `espeak-ng` on a
Mac, with the voice en-us+f3:

```bash
.venv/bin/python tools/voice_build.py --set espeak --backend espeak --extract --jobs 8
```

`kokoro` uses Kokoro through the kokoro-onnx package, with the voice af_heart. It needs the model
files `kokoro-v1.0.onnx` and `voices-v1.0.bin`, from the kokoro-onnx project's model-files-v1.0
release, in the project's folder `voice-models/`. The whole vocabulary takes about 17 minutes:

```bash
.venv/bin/python tools/voice_build.py --set heart --backend kokoro --extract --jobs 8
```

A set keeps the backend and voice it was made with. A later run that names none takes the set's
own, so `--set` alone is enough, and a run that names others is refused, since it would make the
whole set again.

The tools that talk to the device find its serial port by the Flipper's USB id, on a Mac, Linux
or Windows. With two Flippers plugged in, or for another port, give it with `--port`, or in the
`FLIPPER_PORT` environment variable; `tools/sr_drive.py` has no `--port` option, so set
`FLIPPER_PORT` for it. Each tool opens the port for itself alone: when qFlipper or another tool
has it, the tool says so and stops, instead of waiting without a word.

`--extract` makes a clip for every word, about 2,900 words and 27 MB. The words come from:

- the base list `tools/voice_words.txt`;
- every string in the firmware's core apps and services, and the names and folder names their
  menus show, read from each app's `application.fam`;
- the dolphin's speech bubble texts;
- the apps on the card, with `--card-apps`, or every app under `applications/external` with
  `--extract-all`, for a wider one-off build instead of just the ones installed: their strings,
  and their names and folder names as the Apps menu shows them.

Everything goes through the reader's own pronunciation code. With `say` on a Mac, the 2,900 words
took about 16 minutes with `--jobs 8`, or 22 minutes with the default of 4 jobs. The limit is
`say` itself, not the number of processors. A rerun makes only new or changed clips.

Add `--dry` to any of these commands to build the word list and print its counts without making a
clip or touching the card. It shows how many strings and words there are, the ten longest words,
and with `--card-apps` which apps matched which source folder.

The sync sends new or changed clips and `voice.txt` to the card. Without `--set` it sends
samantha; for another set, name it:

```bash
.venv/bin/python tools/voice_build.py --sync
```

```bash
.venv/bin/python tools/voice_build.py --set heart --sync
```

A full sync of about 2,900 clips takes about 6.5 minutes. Later syncs send only what changed, which
takes seconds. It prints a line every hundred clips and a summary at the end. When the connection
fails or the card refuses a clip, a full card for example, it stops at that clip with one line
saying where and why, and the next sync sends what is left. The voice is switched off on the device
during the transfer and switched back on afterwards. The mute lasts a minute at a time and the
generator renews it while the transfer goes, so if the transfer dies, through Ctrl-C, a killed
process, a dead port or power loss, the voice comes back by itself within a minute. The generator's
reads give up after 30 seconds without an answer, and a Ctrl-C during the restore at the end cannot
hang it. This command switches the voice back on at once:

```bash
.venv/bin/python tools/flipper_cli.py "sr voice on"
```

The sync tells the card's copy of a set apart by a small file in the set's folder on the card,
`.sync-id`, which holds a random code. The set's `synced.json` on the computer keeps the same
code, and a sync that changes the card writes a new one to both before its first clip. When the
card's code is another, the copy is from another computer's sync, or it is a second card or an
older copy, and the sync sends everything. The sync also looks up three of the clips it sent
before, and sends everything when they are not on the card, after a wipe. Syncing two cards in
turn, or one card from two computers, therefore sends the whole set at each switch. A card
without the file, from before it, keeps its clips when the three are there, and gets the file.
`--mark-synced` makes the next sync keep whatever copy is on the card. To resend everything
anyway:

```bash
.venv/bin/python tools/voice_build.py --sync --sync-all
```

The missing-word command gives the words the device had to spell their own clips. It serves
samantha; for another set, add `--set` with its name, as in the second command:

```bash
.venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync
```

```bash
.venv/bin/python tools/voice_build.py --set heart --extract --card-apps --pull-missing --sync
```

It fetches `missing.txt` from the card, makes clips for those words and sends them. The words leave
the card's list only once every clip was made and sent; until then they wait in the set's
`pulled.txt` on the computer, so a run that fails or is stopped loses none of them, and the next
run makes them again. `--extract` is there because the spoken form of a word with an apostrophe
comes from the extraction, not from `missing.txt`, which has already lost the apostrophe.
`--card-apps` adds the strings, names and folder names of the apps actually on the card, so a
newly installed app's own words get clips too. For a few words it takes about 3 to 4 seconds.

`--check` makes ten test clips in a temporary folder and checks their format:

```bash
.venv/bin/python tools/voice_build.py --check
```

`--sync`, `--pull-missing` and `--card-apps` use the firmware's serial storage helper, so they
need Python with pyserial, as in the virtual environment of the examples.

The processing was chosen by ear for the Samantha voice through the device's speaker, and every
backend uses it. Written out, the defaults of `say` are:

```text
--backend say --voice Samantha --rate 175 --highpass 500 --gain 1.3 --soft
```

The clips are always made at 16,000 samples per second.

On the computer, the set `samantha` is the project's folder `voice/`, where the vocabulary was
before there were sets, and every other set is `voices/<set>/`. A set's folder holds the clips, as
`<first letter>/<word>.raw`, and its records: `manifest.json` records which clips were made and
with which settings, `synced.json` records what is on the card, and `pulled.txt` holds pulled
missing words until they are synced. The sync puts each clip into its hashed folder on the card.
Do not delete a set's folder: without it the next build starts from scratch, and the next sync
resends everything.

### Limits of the voice

- A clip's name is a word of lower case letters, up to 16 of them, or a single digit. Words longer
  than 16 letters never get a clip, so they are spelled letter by letter.
- Tokens that mix letters and digits, such as `md5`, `i2c` or `p1`, never get a clip. They are
  spelled every time, `md5` as "em dee five", logged as missing, and dropped by
  `--pull-missing`.
- Apostrophes are left out of clip names: "don't" is `dont.raw`, recorded as "don't". So two words
  that differ only by an apostrophe share one clip, recorded as the texts write it most often: the
  firmware's own texts decide for the words they hold, and the apps' texts only for the others,
  with a tie going to the apostrophe. The dolphin's "I'll" makes "ill" play as "i'll", while
  "were" and "id" are recorded as written, though an app writes "we're" and "I'd". The
  extraction lists each word written both ways, with the form it chose.
- A word the device logs as missing has already lost its apostrophe, so `--pull-missing` records
  "wont" as it is spelled, not as "won't". Words from the firmware's own strings keep their spoken
  form.

## Known limits

- Without the SD card, or without a voice set under `/ext/sr/voices` on it, the reader is silent,
  since SAM is gone.
  Without a card most main apps are missing too, since they load from the card, as in Momentum.
- Momentum keeps its settings on the card, in `/ext/.int`, where `/int` leads, and the device's
  name too, in `/ext/dolphin/name.settings`. Without a card the device starts with the default
  settings, the reader at volume 80, and a change made then is not kept. When a card goes in,
  this one or another, its settings are read at once, and a chord in the moment before that saves
  nothing. After a card is formatted on the Flipper, the settings in use are written to it with
  the next change.
- After a PIN unlock, "Unlocked" and "Home screen" may come in the other order.
- Twice, after a long idle, the first OK that the scripted driver `tools/sr_drive.py` sent on the
  home screen opened the lock menu instead of the main menu. It has not been reproduced since and
  is not explained. Up, not OK, is the default key for the lock menu. Back closes it.
- Keys sent from `sr watch` and from remote control bypass the chords, as described under Back
  chords.
- Numbers with slashes are not interpreted: every slash is read as "slash". The Passport's
  points, "18/100", are "eighteen slash one hundred", a count such as "Keys found: 5/32" is "five
  slash thirty two", and a date that an NFC card parser shows, such as 15/03/2019, is "fifteen
  slash zero three slash two thousand nineteen". "/ext/apps" is "slash ext slash apps".
- An external CC1101 radio module, the add-on board for a stronger Sub-GHz radio, has not been
  tried with the reader on. Speech moves its sound through a DMA channel that the external
  radio's driver does not use, so a transmit and speech should not disturb each other, but no
  transmission has been checked.
- The device has rebooted a few times while idle, with a "furi_check failed" popup, and the cause
  is unknown. The popup now carries an address, and `sr status` the build, so a report with both
  helps: see When it crashes.
- Apps from elsewhere: Sonar's app interface is version 87.3, and the Flipper's app loader checks
  only the first number, 87, so the second says nothing about which apps load. An app built for
  Momentum's version 87 loads, unless it uses the JavaScript engine's functions, which Sonar leaves
  out: such an app fails to load with the error "Missing Imports". The other way round, an app
  built with Sonar's SDK that uses the functions Sonar adds for its reader, such as
  `canvas_tap_hint_note`, fails to load on other firmware.

## When it crashes

When the device crashes, it reboots and shows a popup, and the reader reads it: "Flipper crashed
and was rebooted", then the message, most often "furi_check failed", or after a hardware fault its
name, such as "BusFault" or "NULL pointer dereference". The last line is "at" and an address of
eight hexadecimal digits, such as "at 0803ABCD": where the failed check is, the instruction that
faulted, or the call that went through a null function pointer. Back closes the popup. The address
stays, across reboots and firmware updates, until the next crash. It is kept in two of the clock's
backup registers, which the official firmware and Momentum leave unused; after another firmware
that uses them, the last crash shown may be wrong until the next one.

The reader says the address character by character, with two exceptions. One to three digits
after a letter are said as a number unless they start with 0: "AB20" is "ay B twenty", and "AB05"
is "ay B zero five". Four digits at the start, not beginning with 0 and followed only by letters,
are said as a number too: "2001ABCD" is "two thousand one ay B C D", but "0803ABCD" is "zero
eight zero three ay B C D".

On the console, `sr status` shows the address exactly, with the build that recorded it, for
example "last crash: at 2001384F in build 9028a849". It says "in build unknown" when a build older
than 9028a849 recorded it, and "last crash: none" when no crash has left one.

```bash
.venv/bin/python tools/flipper_cli.py "sr status"
```

From the install's folder of a release, the same command is:

```bash
.venv/bin/python flipper_cli.py "sr status"
```

To report a crash, open an issue on this repository with the bug report form, which asks for:

- the address, from the popup or from `sr status`, and the build that `sr status` names with it;
- the whole `sr status` output;
- the firmware's version and commit, and where the build came from: a release, a continuous build
  or a build of your own;
- what was open on the device when it crashed.

The address leads to a line of code only together with its build, which is why both matter. Each
release carries the elf of its firmware, which turns the address of a crash in that release into a
line of code.

## Building from source

```bash
git clone --recurse-submodules https://github.com/robin24/flipper-access.git
cd flipper-access/Momentum-Firmware
./fbt updater_package
../tools/flash_headroom.sh
./fbt flash_usb_full
```

The clone leaves the firmware submodule on a detached HEAD, at the commit this project records.
A build from there is named `f7-update-mntm-HEAD-<hash>` and reports its branch as HEAD. To give
it the branch's name, check the branch out from the project folder before building:

```bash
git -C Momentum-Firmware checkout screen-reader
```

This moves the submodule to the branch's tip, which is the recorded commit only while the
project's pointer is current. A source build of exactly the recorded commit keeps the detached
HEAD instead. The branch's name also ends the Firmware Info page under Settings, About, where a
release build, made from a version tag, names this project, flipper-access.

fbt, the firmware's build tool, downloads its toolchain on first use. Only the Flipper Zero
target, f7, is built. The release options, `COMPACT=1` and `DEBUG=0`, are the defaults, so the
plain command builds a release. The headroom check compares the image with the flash that the
Bluetooth radio stack leaves free, since the device's updater refuses a larger image. It reads
the stack's address from the update package, and with the current stack the limit is 880,640
bytes. The last command flashes the device over USB together with its resources, the apps and
files that go on the SD card. The device then takes about six minutes to update itself and
reboot.

The host tests build the screen reader's pure code with clang and run its unit tests, and
Momentum's settings file against stand-ins for the card, then the Python checks of the build's
configuration and of the tools. A Mac has clang with Xcode's command
line tools; on Linux, install it from the distribution's packages. Run the tests from the project
folder; they take a few seconds:

```bash
tools/run_host_tests.sh
```

The tools that talk to the device, such as `tools/flipper_cli.py` and the voice generator, need
Python 3.10 or newer; the voice generator says so when it starts on an older one. The `python3`
that comes with the Mac's command line tools is 3.9, while Homebrew's and the installer from
python.org are newer. The commands in this README run the tools from a virtual environment in the
project folder, made once, with the packages listed in `requirements.txt`: pyserial for the
device, numpy and scipy for the eSpeak and Kokoro voices, kokoro-onnx for Kokoro, and colorlog for
some of the firmware's own scripts:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`python3 --version` shows which Python the first command uses; `python3.12 -m venv .venv`, for
example, names one.

## Following Momentum

The fork follows Momentum by merging Momentum's release tags into `screen-reader`, and it never
rebases. Before a merge is attempted, `tools/upstream_check.sh` shows what it would meet. The
whole routine, from the fetch to the tag, is under Merging Momentum in `docs/device-notes.md`.

## Licence and credits

The firmware fork is licensed under the GPL-3.0, like Momentum and the official firmware, and so
is everything in this repository; the text is in `LICENSE`, and the install zip of each release
carries it too. The voice pack carries its own licence, as described under Licensing in The voice:
the Apache License 2.0 for Kokoro's model, and CC0 1.0 for what the project adds.

Each release offers the source of its binaries beside them, as its asset
`sonar-<version>-source.tar.gz`, such as `sonar-0.1.0-source.tar.gz`. It holds the fork at the
release's tag with every submodule, nested ones included, each at the commit the release was built
from, Momentum's apps among them, whose builds the update package puts on the card. The release
notes name the fork's commit, the Momentum commit it builds on, and the commit of each submodule.
The source stays in the same place as the binaries for as long as they are offered there. The
fork's history is at https://github.com/robin24/Momentum-Firmware, where each release's tag is too.

Credits:

- Momentum and its contributors, whose firmware Sonar is built on. The install's file transfer,
  `tools/flipper_storage.py`, is adapted from Momentum's `scripts/flipper/storage.py`.
- Flipper Devices, for the device and the official firmware.
- Kokoro-82M, the open speech model by hexgrad (https://huggingface.co/hexgrad/Kokoro-82M), under
  the Apache License 2.0, which the release's voice, `heart`, is made with. Its card credits the
  StyleTTS 2 architecture by Li et al. (arXiv 2306.07691), and the training audio of Koniwa, under
  CC BY 3.0, and of SIWIS, under CC BY 4.0. The kokoro-onnx project runs the model on a computer.
- eSpeak-NG, under the GPL-3.0, which the generator's `espeak` backend uses for the voices users
  make.
- The Black Magic Probe project, whose firmware on the Wi-Fi dev board serves as the crash catcher.
