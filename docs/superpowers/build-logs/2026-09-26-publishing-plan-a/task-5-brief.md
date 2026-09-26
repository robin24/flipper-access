### Task 5: The README split: a public README, the device notes, the docs index

**Files:**
- Rewrite: `README.md`
- Create: `docs/device-notes.md`, `docs/README.md`
- Modify: `docs/roadmap.md`

**Interfaces:**
- Consumes: the current `README.md` (headings: Device state; Using it on the device with Back chords, The Accessibility settings, The home screen and the lock menu, Locking and unlocking, Infrared universal remotes, NFC-V emulation, The file browser's menus, Known limits; Folder contents; Useful commands; Recorded voice; Rolling back to official firmware; Plan), the spec's section 9, `docs/roadmap.md`.
- Produces: the public README that Task 10 and plan C extend; `docs/device-notes.md` that Task 10 updates with the flashed build.

Rules for all three files: prose and short lists, no tables, commands in code blocks, sentences of about twenty words, no em-dashes. Nothing in the public README names Robin's device (R0skie, Delphi) or the Mac's serial port; the device notes may.

- [ ] **Step 1: Write the public `README.md`**

Sections, in this order, with this content:

1. Title `# Flipper Access` and three sentences: Sonar is a firmware for the Flipper Zero, built on Momentum, with a screen reader that speaks every screen through the device's own speaker in a recorded voice, so a blind person can use the device without sight. This repository holds the documentation, the tools and, from the first release on, the downloads. The firmware's source is the fork at https://github.com/robin24/Momentum-Firmware, branch `screen-reader`.
2. `## How it was made`, this paragraph verbatim: "Sonar was written almost entirely by AI coding agents (Claude) working under the direction of Robin Kipp, a blind developer, who tested every change on the device and decided what it should do. Momentum's repository does not accept AI-written contributions, and the reader's memory needs would sit behind a build flag there in any case, so this is a separate firmware rather than a pull request. The specs, plans and build logs under `docs/` are the full record of how it was built." Then one sentence pointing at `docs/roadmap.md` for the reasoning and `docs/README.md` for the index.
3. `## What changed against Momentum`: a list of the additions (the screen reader service and its Back chords, the Accessibility settings, spoken names for screens that draw only icons, the dolphin's level and mood in words, the crash popup with its address, the recorded voice from the card) and a list of the removals (the games, the JavaScript engine and its apps, SAM, the home animations off by default with a setting to turn them on), each item one sentence, with the reasons in one sentence each where the current README gives them.
4. `## Install`: for now, two sentences: release packages and an install script come with the first release; until then, build from source and flash as described under Building from source.
5. `## First boot`: what a new device does: the reader is on from the first boot; the status chord and the read chord are the first two things to try; how to turn the reader off and on (Back and Down held together, long). Take the wording from the current "Back chords" section.
6. `## Using it on the device`: move the current sections "Back chords", "The Accessibility settings", "The home screen and the lock menu", "Locking and unlocking", "Infrared universal remotes", "NFC-V emulation" and "The file browser's menus" here as `###` sections, content kept, with the remarks that name the device or the measurement files removed ("checked on R0skie", "The device outputs are in docs/measurements/...": the pointer to the measurements goes to the device notes).
7. `## The voice`: from the current "Recorded voice" section keep what a user needs: clips on the card, one per word, spelling for a word without a clip, the missing-words list and how the generator fills it, the card layout in two sentences (one clip per word under 64 hashed folders, and why), the `voice.txt` settings line. Then licensing in this shape: the vocabulary shipped with a release is made with Piper and a freely licensed voice, and carries its own licence file; the generator can also use macOS's `say` voices, which Apple licenses for use on the Mac, so a vocabulary made that way is for the maker's own device only. Then the generator's command lines for both backends, as the current section gives them.
8. `## Known limits`: the current list, with "R0skie" removed from the slash bullet, plus one bullet: the device has rebooted a few times while idle with a "furi_check failed" popup, cause unknown; the popup now carries an address and `sr status` the build, and a report with both helps.
9. `## When it crashes`: from the current README's crash paragraph, what the user hears and what to report (the popup's address and build hash, `sr status`, what was open). The addr2line decoding and the dev board capture go to the device notes.
10. `## Building from source`: this code block

```bash
git clone --recurse-submodules https://github.com/robin24/flipper-access.git
cd flipper-access/Momentum-Firmware
./fbt updater_package
../tools/flash_headroom.sh
./fbt flash_usb_full
```

with one sentence each: fbt downloads its toolchain on first use; the release options are the defaults; the headroom check compares the image with the flash the radio stack leaves free (880,640 bytes); the last command flashes the device over USB with its resources. Then the host tests: `tools/run_host_tests.sh`, one sentence.
11. `## Following Momentum`: two sentences: the fork merges Momentum's release tags into `screen-reader`, never rebases, and `tools/upstream_check.sh` shows what a merge would meet before it is attempted (the tool arrives in Task 8 of this plan; write the sentence now).
12. `## Licence and credits`: the firmware fork is GPL-3.0 like Momentum and the official firmware, and so is everything in this repository (`LICENSE`); a release's voice pack carries its own licence. Credits: Momentum and its contributors, whose firmware this is built on; Flipper Devices for the device and the official firmware; Piper, the voice synthesizer the released vocabulary is made with; the Black Magic Probe project, whose firmware on the Wi-Fi dev board serves as the crash catcher.

- [ ] **Step 2: Write `docs/device-notes.md`**

Title `# Device notes: Robin's Flipper` and one sentence that these are the working notes for the one device this is developed on, and the developer's routine. Sections:

1. `## Device state`: the current README's "Device state" list, with the Text to SAM bullet as Task 2 left it, and the firmware line ending with a sentence that Task 10 updates it.
2. `## The folders and tools`: the current "Folder contents" list minus the retired items, plus `tools/card_prune.py` (one sentence) and `tools/voice_words.local.txt` (personal words, not in git).
3. `## Routine`: the flash routine as a numbered list: wipe `build/f7-firmware-C/resources` and `.extapps`; `./fbt updater_package`; `tools/flash_headroom.sh`; `./fbt flash_usb_full`; `sr screen` before any key; `tools/card_prune.py`; the generator's routine command. Then the vocabulary command with the local word list explained.
4. `## Useful commands`: the current section, complete, including the history of image sizes.
5. `## Crash diagnosis`: from the current README, the addr2line decoding paragraph and the dev board capture paragraphs (the UART capture command, the debug flag and log level, the `top 0` thread table).
6. `## Rolling back to official firmware`: the current section.
7. `## Measurements`: one sentence per file under `docs/measurements/`.

- [ ] **Step 3: `docs/roadmap.md` and `docs/README.md`**

In `docs/roadmap.md`: add a status paragraph dated 2026-09-26 after the existing status: the publishing spec exists (name it), plan A is in progress, the names are decided (repository `flipper-access`, firmware Sonar). Fold the README's "Plan" list into the roadmap as a section `## Done so far`, one line per item, keeping the dates. Under "Release mechanics" add one sentence that section 8 of the publishing spec now defines the sync procedure.

Create `docs/README.md`: a short index: what is in `specs/` (one line per file), `plans/` (one line per file), `build-logs/` (one sentence: per round, the ledger with its rulings, the briefs and the reports), `measurements/` (one sentence), `device-notes.md`, `roadmap.md`, `2026-09-14-investigation.md`.

- [ ] **Step 4: Check and commit**

```bash
grep -n -i "r0skie\|delphi\|usbmodem" README.md || echo "public README clean"
grep -c "^|" README.md docs/device-notes.md docs/README.md docs/roadmap.md
tools/run_host_tests.sh
git add README.md docs/device-notes.md docs/README.md docs/roadmap.md
git commit -m "README for the public, device notes for the working setup, the docs index, the roadmap folded

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- README.md docs/device-notes.md docs/README.md docs/roadmap.md
git push
```

Expected: `public README clean`, zero table lines in every file, the runner green.

---

