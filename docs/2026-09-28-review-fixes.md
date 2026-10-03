# Fixes after the review of 2026-09-28

The review report is `docs/2026-09-28-review.md` on the branch `claude/flipper-access-review-m87rn7`.
The fixes are on the branch `claude/flipper-access-review-fixes-ssg5yj`, in this repository and in
the fork, one finding per commit, each firmware change followed by its own submodule bump here.
That branch was merged on 2026-09-30 and deleted on 2026-10-01. What was finished on 2026-10-01
is on the branch `claude/reading-fixes-2026-10-01`, in both, the same way.

How it was checked, for every fix below:

- The host tests, with clang's address and undefined behaviour checks, after every change. Where a
  fix came with new tests, the tests were also run against the code before the fix, or against a
  deliberately broken copy, and failed there.
- A release build after every firmware change, with the headroom check. The last build before
  the device checks, commit c71bd08 of the fork, is 869,120 bytes, 11,520 below the limit of
  880,640; the builds since are under Results on the device.
- The continuous build, green on every push. Since R12 it installs `requirements.txt` on Python
  3.10 and runs the host tests with `--no-skips`, so no check is left out there.

Nothing was tried on the device before 2026-09-29; the checks for it, and their results, are at
the end.

## Fixed

Firmware:

- F1, as you chose in question 1: speech moves its samples through DMA1 channel 3, which nothing
  else in the firmware or its apps uses, off DMA2 channel 4, which the external CC1101 radio's
  driver transmits through. The README says external modules are untried with the reader on.
- F2, corrected after the device check of 2026-09-30: the settings are saved only once they were
  read with a card mounted. Momentum keeps /int on the card, as the folder /ext/.int, so the
  settings file is not on internal storage as the review took it to be, and the load that the
  first fix added at boot without a card found no file. Without a card nothing can be saved
  either. The gap was the moment a card goes in after a boot without one, before the settings are
  read from it: a chord then wrote the defaults over them. A host test holds the new rule, and
  failed against the first fix. Two cases stayed open until 2026-10-02, when both were fixed.
  After a change to another card while the device ran, Momentum did not read the new card's
  settings: skip_double_mount in furi/flipper.c, meant for the boot's mount event, swallowed the
  first real mount, since Momentum's 7db15e838 sends no mount event for a card mounted at boot,
  so a save wrote the old card's settings onto the new one. Now a card taken out clears that skip
  and stops the saves until the next card's settings are read. After a format on the device no
  mount followed, so after a boot with an unusable card nothing was saved until a restart; now a
  format counts as the card taken out and put in. A host test holds the card change, and failed
  against the code before; on the device the card change was checked before and after, the format
  was not, since no spare card was at hand.
- S1: the NFC-V listener keeps the speaker from its first exchange until it ends.
- F3: the console's `input send` has its own chord state, apart from the keys'.
- G1 to G8: the keyboards read their prompt, field and keys, name their special keys, and never
  take a row of keys for typing; the cursor mode speaks; text boxes lose their question marks; a
  keyboard's description leaves out the key rows; long dialogs keep their buttons; every main menu
  style names its selected app with its position.
- G9: the file browser's menu no longer carries the list's focus, a button menu says positions,
  and the Loading screen says "Loading". The other three items followed on 2026-10-01: the file
  browser counts its entries from 1 below the parent folder's entry, which has no position, and
  says the name of the folder it opens; `elements_button_up` and `elements_button_down` are read
  as the up and down buttons; and a word the screen shows in pieces, hyphenated by the wrapper or
  broken by the text box, is read whole. With them came two found on the device: a new tab of
  the file browser says its name first, and the DSi menu style's letter-spaced START is one
  word. A third followed on 2026-10-03: the C64 style draws its numbers apart from the names, so
  its focus is read as "Apps, 1 of 11", not "0.Apps". The screen model's host tests hold the titles, the joined words and the up and down
  buttons, and failed against the model before; the positions were checked on the device. The
  review of 2026-10-01 found three edge cases, fixed on 2026-10-02: a text box line that starts
  after a bold or monospace marker following a space is a new word, not the end of the one
  before; a line too narrow for a letter and the wrapper's dash no longer reads before the text;
  and the file browser forgets its folder's name when it stops. A host test holds where a line
  break falls inside a word, and failed against the old logic.
- S2 to S10: text is cut after a whole word; speech stays silent with less than 4 KB of heap in one
  block; `sr voice off` stops the utterance and takes a time limit; a card or set that goes away
  ends the item; the ring plays silence after an underrun; a burst of wake-ups no longer ends a
  word; the speaker is handed back 200 ms after the last item; the missing list is written at once
  and kept until it arrived; an interrupting announcement cuts in at once.
- F4: `sr` runs on a 2 KB stack. GCC's call graph puts its deepest path, a number printed through
  the console pipe, at about 1.3 KB, and about 1.6 KB with an interrupt's frame.
- F5: the volume chord and the reader-on chord speak before they save.
- F6: a frame the reader could not take is asked for again.
- F7, on 2026-10-01 and 2026-10-02: after a hardware fault, HardFault, MemManage, BusFault or
  UsageFault, the crash address is the instruction that faulted, which the handler takes from the
  frame the core pushed, instead of an address inside the handler. Such an address is even. After
  a call through a null function pointer, whose target is no code, it is the return address of
  that call, from the same frame, and odd like a failed check's. A frame the core could not push
  or pop, as after a stack overflow, is not trusted, and the address stays in the handler as
  before. The first version, of 2026-10-01, trusted a frame only in SRAM1, which left out the
  services' threads, the GUI's among them, whose stacks lie in SRAM2; an independent review found
  that, and it is fixed. The review's second idea, part of the thread's name after a stack
  overflow, is left out: the second register holds the build now, and the debug log names the
  thread. Checked on the device with three faults the Crash Test app gained, each before and after
  its change: strlen reading an address no memory answers, from BusFault_Handler to the load in
  strlen that faulted; the same while the GUI draws, from the bus fault handler to that load; and
  a null call inside furi_hal_info_get, from the MemManage handler to the call in
  property_value_out.
- F8: a chord key held into a second Back hold no longer takes that hold's keys, and with the
  reader off, Back held long and let go before Down's long press no longer opens the power-off
  dialog beside the toggle.
- F9: `sr voice use` takes every set the engine lists, a quoted name too, and the Voice row
  offers Auto first.
- R9, as you chose in question 8: on a release build, made from a version tag, the About
  screen's Firmware Info page ends with "flipper-access" instead of Momentum's website. A build
  from a branch still shows the branch's name there. The About app lives on the card, so the
  flash image does not change.

Tools and tests:

- R1: the voice pack is USTAR with folder entries, checked by unpacking it with the firmware's own
  tar reader on the host.
- T1: a Ctrl-C during a sync neither hangs nor leaves the device muted.
- T2: the voice generator refuses a Python older than 3.10 in one sentence.
- T3: `strip_js_symbols.py` sets the API version from upstream's own, so it is never raised twice.
- T4: the sync prints a line per hundred clips, stops at the first connection error or refused
  write with one line, and never counts a refused clip as sent (also T10's write error).
- T5: the sync looks up three clips before trusting `synced.json`, and sends everything to a
  wiped card. As you chose in question 2, a random code in the set's folder on the card,
  `.sync-id`, which `synced.json` keeps too and a sync renews before its first clip, tells an older
  copy, a second card or another computer's copy apart, which gets everything as well. A card
  without the file keeps its clips when the three are there, and gets the file.
- T6: `--pull-missing` keeps the words in the set's `pulled.txt` and leaves the card's list until
  a sync with nothing failed.
- T7: as you chose in question 3, a word written both with and without an apostrophe is
  recorded as the texts write it most often, the firmware's own texts deciding the words they
  hold, and a tie going to the apostrophe. "were" and "id" are recorded as written, and "don't",
  "can't", "doesn't" and "I'll" keep their apostrophe whichever apps are extracted. Checked
  against the old code: the same words, and with every app 9 clips spoken differently, none
  with the firmware's texts alone.
- T8: the port is found by the Flipper's USB id on any system, opened for one tool alone, and the
  console's first prompt is awaited 5 seconds.
- T9: as you chose in question 4, the extraction also reads the names and folder names the
  menus show, from the apps' `application.fam`: the firmware's own apps always, the card's with
  `--card-apps`, every app with `--extract-all`. With the apps the update installs and your usual
  command, that is 10 more words: the nine of the question and "notifications", from the Settings
  entry "LCD and Notifications". Checked against the old code: no word lost.
- T10: `upstream_check.sh` names a missing remote; a silent clip counts as failed; `--jobs 0` is
  refused; the expander builds with clang, cc or gcc; an interrupted sync keeps `synced.json`.
- T11: a host test holds the generator's words and card folders to the device's, over every
  firmware string.
- R10, the parts outside the release: personal packs are named apart, and packs stay out of git.

Continuous build, R12: Momentum's `lint_all`; a check that the build changed no tracked file; the
golden checks against the Momentum commit pinned in `tools/momentum-base.txt`, which the host tests
check against upstream/dev; the Python packages on 3.10 with `--no-skips`; the headroom limit read
from the update package's radio address; and a build of the fork's `screen-reader` tip every
Monday and by hand. The weekly and manual runs work from main, where the branch is merged.

Documents: the README's voice sections for the voice sets, the three backends, the licences and
credits, the Accessibility screen's five rows, the virtual environment, the 64 words the missing
list remembers (F10) and where the crash address is kept (F10); the design and release specs, the
roadmap, the docs index and the merge routine where the code changed.

## Not done

- T11's second note, listing the 64 folders instead of looking up each clip: measured on
  2026-10-01, and the sync left as it is. The sync looks up every clip it sends, about 51 ms when
  the clip is not on the card and 29 ms when it is, and listing a folder costs 134 ms. Listing
  would save about 9 minutes of a full sync into an empty set, and about 5 of the 39 minutes the
  full sync of 2026-10-01 took over the old clips; an everyday sync of a few new words would gain
  nothing. Left out on 2026-10-02, since full syncs are rare.
- For plan C: the release spec's card reader step counts on Python's tar reader writing no macOS
  metadata files. On this Mac on 2026-10-03, every file and folder written to the card got a
  `._` file beside it, from the `com.apple.provenance` attribute that macOS gives everything a
  process makes and exFAT keeps only in such a file. The install script will have to remove them
  afterwards, which leaves gaps in the folders, or unpack on the device.
- R10's licence texts and source bundle, R11, R13, R15, R16, and R2, R3 and R5 to R8 belong to
  plan C.
  Your answers to the report's questions 2 and 3, on R11, are in the release spec's install
  step: the script asks whether to copy the voice through a card reader or over USB, the card
  reader being the default, and clips at 11,025 samples a second wait for a listening test,
  made only if USB is still too slow once the transfer is measured.

## Your answers

All nine questions are answered, and each answer is carried out:

1. External CC1101 modules: speech has a DMA channel of its own, and the README says an external
   module is untried with the reader on (F1).
2. A code in each set's folder on the card, `.sync-id`, tells its copy apart (T5).
3. A word written both with and without an apostrophe is recorded as the texts write it most
   often, the firmware's own texts deciding the words they hold (T7).
4. The apps' names and folder names come from their manifests (T9).
5. The install script asks whether to copy the voice through a card reader or over USB, the card
   reader being the default (release spec, R11).
6. No listening test at 11 kHz for now: it waits until USB's speed is measured (release spec,
   R11).
7. The fork's inherited GitHub files stay, and settings keep them from doing anything: the steps
   are below (R14).
8. A release build's About screen names flipper-access (R9).
9. A pull request for each branch, merged once its build is green: the fork's into
   `screen-reader`, this project's into main.

## On GitHub, for you

The fork's GitHub files stay as they are, and these settings keep them from doing anything
(R14). Issues and Discussions are off already, and the fork's description already points to
flipper-access. GitHub's labels may differ slightly from these.

1. Actions off: on the fork's settings, under Actions and then General, choose "Disable actions"
   under "Actions permissions", then Save. The page is
   https://github.com/robin24/Momentum-Firmware/settings/actions
2. The Sponsor button off: on the fork's settings, General, in the Features section, uncheck
   Sponsorships. The page is https://github.com/robin24/Momentum-Firmware/settings
3. The website: on the fork's main page, the About section's edit button, "Edit repository
   details", opens a Website field that holds https://momentum-fw.dev. Replace it with
   https://github.com/robin24/flipper-access and save.

## Checks on the device

Flash the build first, with steps 4 to 7 of the Routine in `docs/device-notes.md`. The console
commands below run from the project folder.

Settings without a card, F2: remove the card, reboot, and change the volume with Back and Right.
Put the card back and reboot. The volume change is not kept, since nothing can be saved without
the card, and your settings, such as the verbosity and the menu style, are still yours, not the
defaults. Without the card the console lacks its power command, so reboot with Left and Back
held for five seconds, Left pressed first, so that Back and Left is no volume chord.

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

About screen, R9: under Settings, About, the Firmware Info page still ends with the branch's name
as before, such as screen-reader, since your builds come from a branch. Only a release build
shows "flipper-access".

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

Apostrophes, T7: that sync's extraction lists the words written both ways, with the form it
chose. After it, "were" sounds as written:

```bash
.venv/bin/python tools/flipper_cli.py "sr say They were here"
```

App names, T9: after that sync, the Apps menu's Sub-GHz folder says "Chief Cooker" in words,
and Settings says "LCD and Notifications".

The card's code, T5: after that sync, run the same command again. It says "0 sent", and the
set's folder on the card holds `.sync-id` (samantha here, or your set's name):

```bash
.venv/bin/python tools/flipper_cli.py "storage list /ext/sr/voices/samantha"
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

The continuous build, R12: on Monday, the Actions tab shows the weekly build of the fork's
`screen-reader`. A run by hand, with Run workflow on the Build workflow there, builds any branch,
tag or commit of the fork.

## Results on the device, 2026-09-29 and 2026-09-30

The build of the fork's b9c87352c was flashed on 2026-09-29, and the checks above went through
with Robin: Claude ran the console, Robin did everything physical and listened. The settings
check led to the correction of F2 above; its firmware, 4b56919df on the fork's branch
claude/device-checks-2026-09-30, was flashed on 2026-09-30 and the settings check repeated. The
console output and the figures are in `docs/measurements/2026-09-29-review-fixes.txt`.

Passed:

- F2: the settings stay yours without a card; the volume set without the card is not kept, and
  cannot be. The repeat after the correction is under Section: The correction of F2 in the
  measurements.
- S1: the Emulating screen is read, a phone reads the SLIX2 card, the reader is silent during the
  exchange, and speech is back after Back.
- F3: the buttons' chord works while a console Back is held, and nothing sticks after its release.
- G1 to G6: the text, number and byte keyboards, tried on a file's rename, a Sub-GHz frequency and
  an NFC UID.
- G5, G7, G8 and G9: the text boxes, the long delete dialog, the file browser's two menus, the
  Loading screen, and all nine main menu styles, each saying "Apps, 1 of 11".
- F1: a long read sounds as before, clean and at its usual speed, with no underrun.
- S2 to S10: the cut after a whole word, sr voice off and sr voice off 10, the card leaving and
  coming back during speech, a clean end, the speaker handed back 200 ms after speech, heard with
  the Metronome, and the low-memory count at 0.
- F4, F5, F8, R9 and F9, and T8, with a second program holding the port since qFlipper is not
  installed on this Mac.
- The stack watermarks, and the two regression tools: tools/sr_drive.py with 0 failures, and
  tools/ram_probe.py without a crash, about 400 bytes lower everywhere than on 2026-09-25.

Waiting for a sync of the voice, since Robin left the samantha set on the card as it was: T4 and T6
for the sync, T7 for "were", T9 for the app names, and T5 for the card's code. T2 is met: the
virtual environment has Python 3.13. R12's weekly build is due on Monday 5 October. The five
voice checks passed on 2026-10-01, below.

Found on the way:

- The espeak set plays with underruns on this card: a sentence of 24 common words gave 4 or 5,
  and its clips took up to 77 ms to open, where samantha's took about 20. samantha and heart gave
  none. Since S6 an underrun is a short silence, not a repeat.
- Some common words have no clip in the samantha set, such as "noted" and "spoken"; the missing
  list holds them for the next sync.
- Switching the file browser's tabs says the first entry but not the tab's name. The DSi menu
  style reads its START label as "S TAR T", and C64's items keep their numbers, such as "0.Apps".
  A long file name is split where the screen wraps it, one of G9's open items. All are fixed,
  C64's numbers on 2026-10-03 and the rest since 2026-10-01, below.
- Without a card the device takes back its factory name, R0skie here, since Momentum keeps the
  name on the card too; the console lacks its power command, and Settings, Power is an app on the
  card.

## Results on the device, 2026-10-01

Claude ran the console and Robin listened. The samantha set was made again on this Mac, and the
device got two builds of the fork's branch `claude/reading-fixes-2026-10-01`: f37f06887, with the
screen-reading fixes, and 0294fe871, with the crash address as well. On 2026-10-02 it got
ea05c6d94, with the fixes after the day's independent review. The console output and the
figures are in `docs/measurements/2026-10-01-remaining-items.txt`.

Passed:

- T4, T5 and T6, in the sync of the samantha set made again from this Mac, after Robin heard four
  of its words sound as before; T7, "were" heard as were; and T9, "Chief Cooker" heard as two
  words and "Notifications" as one.
- G9 and the two found on the device: the file browser's tab names said first, its folder names
  and positions, the long file name read whole in the delete dialog and on the NFC emulation
  screen, START in the DSi style, and the FM Radio app's up and down buttons. tools/sr_drive.py:
  0 failures.
- F7: the Crash Test app's bus fault, before the change at 08007F9F, in BusFault_Handler, and
  after it at 0807337E, the load in strlen that faulted. On 2026-10-02, after the review's fixes,
  in ea05c6d94: the bus fault while the GUI draws, before at 08008007 in the bus fault handler,
  after at 080733DE in strlen; and the null call, before at 08007F23 in the MemManage handler,
  after at 08040937, the call in property_value_out.

Measured: T11's second note, and the espeak set's gaps, whose cause is narrowed down but not
found; both are under Not done.

Left: R12's weekly build, due on Monday 5 October.

## Results on the device, 2026-10-02 and 2026-10-03

After the merges of 2026-10-02, the remaining items were done with Robin. The console output and
the figures are in `docs/measurements/2026-10-02-card-settings-and-clip-order.txt`.

- F2's two cases, in 778d09f8f on the fork's branch `claude/card-settings-2026-10-02`: with the
  card's settings file at volume 50 and the device at 30, Robin took the card out and put it
  back. Before the fix the device stayed at 30, the mount swallowed; after it, it read 50. The
  format was not tried, for want of a spare card.
- The espeak set's gaps: a clip's open time follows its place in its folder, which keeps the
  order the files were made in, and espeak and heart were written alphabetically, so common
  words sat near the ends. The sync and the pack now write the most spoken words first, and
  espeak's folders on the card were rewritten that way through the Mac's card reader: the test
  words' median place fell from 106 to 7, the median open from 51 ms to 25, and three long
  sentences gave 3 underruns where they gave 18. macOS's `._` files from that write, which the
  plan C note above describes, were removed through the Flipper.
- The heart set, the same day: its most spoken words, about 24 a folder, were moved to the
  fronts of its folders through the Flipper by renames, which copy no data and leave no macOS
  files. The median open fell from 55 ms to 26, and the long sentences' 3 underruns to none.
- The C64 menu style, in 44e1d8e83 on the fork's branch `claude/c64-menu-2026-10-03`: its
  focus read "0.Apps, 1 of 11" before the fix and "Apps, 1 of 11" after it.
- The prune removes the packages of the claude/ work branches too, checked on the card.
- T11's second note: the faster sync was left out, as recommended, since full syncs are rare.
