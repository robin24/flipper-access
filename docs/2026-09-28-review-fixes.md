# Fixes after the review of 2026-09-28

The review report is `docs/2026-09-28-review.md` on the branch `claude/flipper-access-review-m87rn7`.
The fixes are on the branch `claude/flipper-access-review-fixes-ssg5yj`, in this repository and in
the fork, one finding per commit, each firmware change followed by its own submodule bump here.

How it was checked, for every fix below:

- The host tests, with clang's address and undefined behaviour checks, after every change. Where a
  fix came with new tests, the tests were also run against the code before the fix, or against a
  deliberately broken copy, and failed there.
- A release build after every firmware change, with the headroom check. The last build, commit
  c71bd08 of the fork, is 869,120 bytes, 11,520 below the limit of 880,640.
- The continuous build, green on every push. Since R12 it installs `requirements.txt` on Python
  3.10 and runs the host tests with `--no-skips`, so no check is left out there.

Nothing was tried on the device; the checks for it are at the end.

## Fixed

Firmware:

- F1, as you chose in question 1: speech moves its samples through DMA1 channel 3, which nothing
  else in the firmware or its apps uses, off DMA2 channel 4, which the external CC1101 radio's
  driver transmits through. The README says external modules are untried with the reader on.
- F2: the settings are loaded at boot without a card too, so a chord before the card mounts no
  longer saves the defaults over them.
- S1: the NFC-V listener keeps the speaker from its first exchange until it ends.
- F3: the console's `input send` has its own chord state, apart from the keys'.
- G1 to G8: the keyboards read their prompt, field and keys, name their special keys, and never
  take a row of keys for typing; the cursor mode speaks; text boxes lose their question marks; a
  keyboard's description leaves out the key rows; long dialogs keep their buttons; every main menu
  style names its selected app with its position.
- G9, three of its six items: the file browser's menu no longer carries the list's focus, a
  button menu says positions, and the Loading screen says "Loading".
- S2 to S10: text is cut after a whole word; speech stays silent with less than 4 KB of heap in one
  block; `sr voice off` stops the utterance and takes a time limit; a card or set that goes away
  ends the item; the ring plays silence after an underrun; a burst of wake-ups no longer ends a
  word; the speaker is handed back 200 ms after the last item; the missing list is written at once
  and kept until it arrived; an interrupting announcement cuts in at once.
- F4: `sr` runs on a 2 KB stack. GCC's call graph puts its deepest path, a number printed through
  the console pipe, at about 1.3 KB, and about 1.6 KB with an interrupt's frame.
- F5: the volume chord and the reader-on chord speak before they save.
- F6: a frame the reader could not take is asked for again.
- F8: a chord key held into a second Back hold no longer takes that hold's keys, and with the
  reader off, Back held long and let go before Down's long press no longer opens the power-off
  dialog beside the toggle.
- F9: `sr voice use` takes every set the engine lists, a quoted name too, and the Voice row
  offers Auto first.

Tools and tests:

- R1: the voice pack is USTAR with folder entries, checked by unpacking it with the firmware's own
  tar reader on the host.
- T1: a Ctrl-C during a sync neither hangs nor leaves the device muted.
- T2: the voice generator refuses a Python older than 3.10 in one sentence.
- T3: `strip_js_symbols.py` sets the API version from upstream's own, so it is never raised twice.
- T4: the sync prints a line per hundred clips, stops at the first connection error or refused
  write with one line, and never counts a refused clip as sent (also T10's write error).
- T5, the part that puts nothing on the card: the sync looks up three clips before trusting
  `synced.json`, and sends everything to a wiped or another card.
- T6: `--pull-missing` keeps the words in the set's `pulled.txt` and leaves the card's list until
  a sync with nothing failed.
- T8: the port is found by the Flipper's USB id on any system, opened for one tool alone, and the
  console's first prompt is awaited 5 seconds.
- T10: `upstream_check.sh` names a missing remote; a silent clip counts as failed; `--jobs 0` is
  refused; the expander builds with clang, cc or gcc; an interrupted sync keeps `synced.json`.
- T11: a host test holds the generator's words and card folders to the device's, over every
  firmware string.
- R10, the parts outside the release: personal packs are named apart, and packs stay out of git.

Continuous build, R12: Momentum's `lint_all`; a check that the build changed no tracked file; the
golden checks against the Momentum commit pinned in `tools/momentum-base.txt`, which the host tests
check against upstream/dev; the Python packages on 3.10 with `--no-skips`; the headroom limit read
from the update package's radio address; and a build of the fork's `screen-reader` tip every
Monday and by hand. The weekly and manual runs start working once the branch is merged into main.

Documents: the README's voice sections for the voice sets, the three backends, the licences and
credits, the Accessibility screen's five rows, the virtual environment, the 64 words the missing
list remembers (F10) and where the crash address is kept (F10); the design and release specs, the
roadmap, the docs index and the merge routine where the code changed.

## Not done

- F7, the program counter for fault crashes: it means naked fault handlers in an upstream file,
  checked only by crashing the device on purpose, and the idle crashes seen so far are failed
  checks, whose address is already right. The design: read the stacked PC in HardFault, MemManage,
  BusFault and UsageFault, but not after a stacking error, and store it in place of the return
  address.
- G9's other three items: the file browser's position counts the parent folder entry and never
  says the folder's name; `elements_button_up` and `elements_button_down` have no button hint; and
  hyphenated or wrapped text splits words.
- T5's card identifier, T7 and T9 change what is on your card: see the questions.
- T11's second note, listing the 64 folders instead of looking up each clip, is a speed estimate
  that wants a measurement on the device first.
- R10's licence texts and source bundle, R11, R13 to R16, and R2, R3 and R5 to R9 belong to plan C.

## Questions for you

1. T5: may the sync write a small file into each set's folder on the card, for example
   `.sync-id`, so that a card holding an older copy of the set is recognized too?
2. T7: when a word also occurs without an apostrophe, may the generator make the plain form, so
   "were", "ill" and "id" are recorded as written? Those clips change on your card at the next
   sync.
3. T9: may the generator add the app names from the apps' manifests, about 222 more words? They
   add clips to your card.
4. The report's questions 2 to 5: the card-reader install path, a listening test at 11 kHz, the
   fork's inherited GitHub files, and the About screen's website line.
5. Shall I open pull requests for the two branches?

## Checks on the device

Flash the build first, with steps 4 to 7 of the Routine in `docs/device-notes.md`. The console
commands below run from the project folder.

Settings without a card, F2: remove the card, reboot, and change the volume with Back and Right.
Put the card back and reboot. The volume is the one you set, and your other settings, such as the
verbosity and the menu style, are still yours, not the defaults.

NFC-V, S1: emulate a saved ISO15693 card with the reader on and hold a phone with an NFC reader
app to the Flipper. The "Emulating" screen is read, the phone reads the card, the reader is silent
from the first exchange, and speech comes back after Back.

Console chords, F3: send a Back press from the console, try a chord with the buttons, and release
the console's Back. The buttons' chord works, and nothing stays stuck.

```bash
.venv/bin/python tools/flipper_cli.py "input send back press"
```

```bash
.venv/bin/python tools/flipper_cli.py "input send back release"
```

Keyboards, G1 to G6: rename a file, enter a Sub-GHz frequency, and edit an NFC UID. Each keyboard
opens with its prompt, its value and the selected key; Save and Backspace are named; moving between
keys is never read as typing; Back and Up reads the prompt, the field and the key, without the rows
of keys.

Screens, G5, G7, G8 and G9: a text box no longer says "question mark" at its line ends; a long
dialog, such as deleting a file with a long name, ends with its buttons; every main menu style,
set under Interface in the Momentum settings, says "Apps, 1 of 11" as you move; the file browser's
menu reads its own items; the Loading screen says "Loading".

Speech's channel, F1: speech sounds as before, without crackle and at its usual speed, in a long
read such as Back and Up on a menu. Then `sr status` still says "underruns 0" on its speech line:

```bash
.venv/bin/python tools/flipper_cli.py "sr status"
```

An external CC1101 module was not tried: with one, the check is a Sub-GHz transmit with the reader
on, watched by a second receiver such as another Flipper.

Speech, S2 to S10: a long screen read with Back and Up ends on a whole word; this mutes at once,
mid-word:

```bash
.venv/bin/python tools/flipper_cli.py "sr voice off"
```

This one mutes for ten seconds, after which speech comes back by itself:

```bash
.venv/bin/python tools/flipper_cli.py "sr voice off 10"
```

Remove the card while the reader speaks and put it back: the voice returns without a reboot.
Speech ends without a click or a repeated sound. Right after speech, another app's sound, such as
the Music Player's, plays at once. The status shows the low-memory count, normally 0:

```bash
.venv/bin/python tools/flipper_cli.py "sr voice status"
```

The console's stack, F4: each of these answers, and the device does not crash with "StackOverflow".
Then run `sr watch` through the tethered reader for a minute of moving around.

```bash
.venv/bin/python tools/flipper_cli.py "sr status"
```

```bash
.venv/bin/python tools/flipper_cli.py "sr voice list"
```

```bash
.venv/bin/python tools/flipper_cli.py "sr off"
```

```bash
.venv/bin/python tools/flipper_cli.py "sr on"
```

```bash
.venv/bin/python tools/sr_drive.py --interactive
```

Volume, F5: press Back and Right five times quickly. Each "Volume" is heard at once, and the last
value is kept after a reboot.

Chord corners, F8: with the reader off, on the lock screen, hold Back until its long press, press
Down, let go of Back, and hold Down: "Screen reader on", and no power-off dialog. The other
corner, a chord key held into a second hold of Back, needs all of it within OK's 300 ms, which is
too quick to try by hand; the host tests cover it.

Voice sets, F9: the Voice row's first value is Auto, then your sets. Auto speaks with the first set
in name order. On the console:

```bash
.venv/bin/python tools/flipper_cli.py "sr voice use samantha"
```

```bash
.venv/bin/python tools/flipper_cli.py "sr voice use auto"
```

The tools on the Mac, T2 to T10: the virtual environment has Python 3.10 or newer. A sync prints a
line per hundred clips, and the card's missing list stays until the sync succeeded:

```bash
.venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync
```

With qFlipper connected to the Flipper, a tool says the port is in use and stops:

```bash
.venv/bin/python tools/flipper_cli.py "info device"
```

Stack watermarks: after these checks, the least free stack of each thread since boot, under Stack
Min, stays clear of zero:

```bash
.venv/bin/python tools/flipper_cli.py "top 0"
```

The continuous build, R12: once the branch is merged into main, run the Build workflow by hand
from the Actions tab with the fork's `screen-reader`, and see the weekly run on Monday.
