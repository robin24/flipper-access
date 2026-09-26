# Task 5 Report: the README split, the device notes, the docs index

Status: DONE_WITH_CONCERNS. The three files are written, the roadmap is changed, and every check
in the brief passes. The commit is b2289b1, pushed to origin/main. The concerns are at the end.
The first one matters for the release: a fresh device's main menu is not in the List style.

## Commit

- b2289b1 "README for the public, device notes for the working setup, the docs index, the roadmap
  folded". Four files: README.md, docs/device-notes.md (new), docs/README.md (new),
  docs/roadmap.md. 837 insertions, 395 deletions.
- The commit used the explicit pathspec. It ends with this session's own Co-Authored-By line,
  Claude Opus 5.5 (1M context), as the task instructions say, not with the brief's Fable line.
- Pushed to origin: 9cd75f8..b2289b1 main -> main. The tree was clean afterwards. The firmware
  submodule was not touched.

## Check outputs

- The device-name check on README.md printed "public README clean". There is no R0skie, Delphi
  or usbmodem in it.
- Table lines: README.md 0, docs/device-notes.md 0, docs/README.md 0, docs/roadmap.md 0.
- tools/run_host_tests.sh: exit 0. All checks passed: 195; speech text 968; queue 156; PCM 597;
  voice 4433; chords 208; throttle 119; fbt exclusions 0 failures; subghz sources 50 of 50; card
  prune 8 of 8. It ran twice, the second time after the last edit.
- My own checks:
  - No em-dashes, en-dashes or double-dash dashes in any of the four files.
  - The only parenthesis in the prose of the three new files is "(Claude)" in the verbatim
    paragraph.
  - No code span is broken across lines, and every code fence is closed.
  - No prose line is longer than 100 characters.
  - The verbatim paragraph is present word for word, compared with whitespace normalized.
  - The public README's twelve sections are in the brief's order. So are the seven subsections
    of Using it on the device.
  - Sentence length: the public README has 308 sentences with a mean of 15.5 words. The few over
    32 words are the brief's own verbatim sentences and some list-like sentences carried over.
- Loss check: I split the old README into its 416 sentences and matched each against the new
  README, the device notes and the roadmap. I read the 32 weak matches by hand. 29 were
  rewordings. Three facts had been dropped, and I restored them: the clip format, the FNV-1a
  detail of the folder hash, and the "checked on R0skie" remark, which is now in the device
  notes.

## Section map, old README to new place

- Intro ("Working notes...", last updated 2026-09-25): replaced by the brief's three sentences.
  The pointer to the investigation is now in docs/README.md.
- Device state: moved to device-notes.md, Device state. Changes:
  - The firmware line is corrected; see the corrections below.
  - The Text to SAM bullet is kept verbatim, as Task 2 left it.
  - Two bullets are new: the List menu style, and the Wi-Fi dev board with its debug settings.
- Using it on the device, the intro: moved to the README's section of the same name.
  - "Checked on R0skie" moved to device notes, Measurements, under the phase-3 file.
  - The pointer to the measurements moved to the same place.
  - "Since phase 3 (2026-09-24)" was dropped.
  - Added: one sentence on how console commands are sent.
- Back chords: moved to the README's `###` section of the same name, content kept.
  - First boot is drawn from it and names the status chord and the read chord.
  - "As before" became "as usual", and "Any other key press" became "Any key press outside a
    chord".
  - `sr watch` is now explained in one sentence.
- The Accessibility settings: README, `###` of the same name, content kept.
- The home screen and the lock menu: README, `###`, content kept.
  - "Delphi's home screen" became "the home screen". Right opens the Passport by default:
    desktop_keybinds.c:66.
  - The Passport example now reads "the device's name, then ...".
  - One sentence explains deeds before the word is used.
- Locking and unlocking: README, `###`. The PIN remark now says "not been tried on a device yet"
  and "his own Flipper".
- Infrared universal remotes and NFC-V emulation: README, `###`, content kept.
- The file browser's menus: README, `###`.
  - The history in parentheses was dropped.
  - "Delete <name>?" became "asks for confirmation, naming the entry". A raw `<name>` would be
    swallowed as an HTML tag on GitHub.
- Known limits: README, Known limits.
  - "Not tried on R0skie" became "has not been tried on a device".
  - The idle-reboot bullet from the brief was added.
  - The List-style limit from Useful commands was added, because the user needs it.
  - "No main apps without a card" became "most main apps", since Sub-GHz is now built in.
- Folder contents: device-notes.md, The folders and tools.
  - Updated: the submodule, the test runner's list, and what is not in git.
  - Added: card_prune.py and voice_words.local.txt, as the brief asks.
  - Also added, because the old list lacked them: test_card_prune.py, flash_headroom.sh,
    uart_log.py, flipper_log.py, map_size.py, voice_words.txt, voice_names.txt and docs/.
- Useful commands: device-notes.md, Useful commands, complete.
  - The size history is now a list, newest first, with 6451e86e8 added.
  - The crash popup paragraph moved to the README's When it crashes.
  - The addr2line decoding, its caveats and the dev board paragraph moved to device notes, Crash
    diagnosis. That section gained the `top 0` thread table and the stack overflow check.
- Recorded voice, the user parts: README, The voice.
  - Kept: the clips, spelling, the missing list, the card layout in two sentences plus the
    format, voice.txt, the console commands, the licensing in the brief's shape, and both
    backends' commands.
  - Also kept: --dry, --sync, --sync-all, the missing-word command, --check, the defaults, the
    voice/ folder warning, and the voice's four limits.
- Recorded voice, the developer parts: device-notes.md, a new section "The voice on this card".
  It holds the speech ring, --remove-legacy, the lookup figures with their date, the letter A
  note, the vocabulary size, and the measurements pointer.
- Rolling back to official firmware: device-notes.md, same section. It is now two steps with
  code blocks, and notes that the package is already unpacked here.
- Plan: moved to docs/roadmap.md, "Done so far".
  - It is one entry per item, with the dates the list had, plus the dates the records give for
    the Momentum install and phases 1 and 2.
  - Added, because the old list lacked them: the recorded voice, the polish round, and the
    2026-09-25 bounded changes.
  - Item 9 ("Next: the fork and release mechanics") became the new 2026-09-26 status paragraph.

The roadmap also has the 2026-09-26 status paragraph from the brief. It names the spec and plan
A, notes that plans B and C follow, and gives the names. Under Release mechanics is the new
sentence saying that section 8 now defines the sync procedure.

## What I shortened or corrected, and why

- The public README drops dates and history that only matter to the developer, for example
  "since 2026-09-25" and "before that only the whole menu was read".
- Long original sentences were split where they divided cleanly, to keep near twenty words. The
  meaning is unchanged.
- Stale statements from the old README were corrected against the source and the records:
  - Firmware line: the old README said the device runs a9e4e7b94. Task 3's `info device` and the
    UART log both show 6451e86e8, flashed on 2026-09-25 at 20:15 and reported dirty.
  - Its size, 864,564 bytes with 16,076 spare, comes from tools/flash_headroom.sh on the build
    directory, which holds that build. The dist folder and the timestamps match.
  - The 864,420-byte figure belonged to the reader toggle's first round, f9f1e168f, according to
    its build log. The old sentence had attached it to a9e4e7b94.
  - The "about 65 clips per folder, open under 40 ms" figures are dated to the 2026-09-24
    rollout. On 2026-09-26 the card held 10,789 clips and showed a longest open of 66 ms, from
    Task 3's report.
  - flipper_cli examples now use .venv/bin/python, because the system python3 has no pyserial.
- Additions a newcomer needs, all checked in the code:
  - A venv setup block in Building from source. Every command in the README uses
    .venv/bin/python.
  - The note that --card-apps also needs pyserial: it opens the storage helper.
  - The note that the Piper backend has not been used for a full vocabulary yet, per the spec.
  - "The removals were made so that Sub-GHz works", which is the old README's reason, from the
    Plan and Device state.
- Measured and corrected: the test runner takes about 3 seconds here, so the README says "a few
  seconds", not "about a minute".
- Verified before I wrote them:
  - COMPACT=1 and DEBUG=0 are fbt's defaults (fbt_options.py).
  - A missing settings key keeps the default (settings.c, load), so a device coming from
    Momentum also starts with the reader on.
  - `--extract` gives 2,900 words: a dry run, which touched no clips and no device.
  - `top 0` prints the table once with "Stack Min" (cli_main_commands.c:409).
  - configCHECK_FOR_STACK_OVERFLOW is 2 (FreeRTOSConfig.h:50, firmware commit 6451e86e8).

## Concerns

1. A fresh device's main menu is not in the List style, and that matters for the release.
   - Momentum's default is DSi (lib/momentum/settings.c:14, `.menu_style = MenuStyleDsi`).
   - The reader's focus hint exists only in the List style (gui/modules/menu.c:132).
   - Robin's device uses List, set by hand, according to the project memory.
   - So the README's main-menu steps may not be spoken as written on a fresh device. That covers
     "Apps, 1 of 11" and "Up twice reaches Momentum".
   - The roadmap already lists "List menus" as a fork default, but Task 4 changed only the
     reader default.
   - Suggestion: a one-line default, `.menu_style = MenuStyleList`, in a firmware task before
     the release.
   - I put the limit in the public Known limits and did not invent a path to the setting.
2. The Text to SAM bullet in the device notes is verbatim as Task 2 left it. It says the stock
   build is on the card "since 2026-09-26". The stock build only reaches the card with Task 10's
   flash_usb_full, whose step 3 checks exactly that. Task 10 should adjust the bullet if it is
   still premature by then.
3. The roadmap's "Keeping the delta small" still speaks of rebases: "rebases onto Momentum stay
   mechanical" and "runs on every rebase". That contradicts the merge policy. It is outside this
   brief, so I left it, and the new sentence points at section 8.
4. The `top 0` paragraph and the 2026-09-25 thread figures are the one part of the device notes
   not taken from the old README.
   - The brief asked for them, but the old README had no such text.
   - The figures come from the project memory's crash-hunt notes. The command's behaviour comes
     from the firmware source.
   - The same holds for the stack overflow check, the List-style bullet and `pgrep -f uart_log.py`.
5. Plan B should check how Piper is found. synth_piper runs the `piper` program by name.
   `.venv/bin/python` does not put `.venv/bin` on PATH, so the README's Piper command may need
   the venv activated. The README only says the backend has not been used yet.
6. Building from source works on a Mac today. flash_headroom.sh and run_host_tests.sh stay zsh
   until Task 9 makes them portable.
7. "The voice on this card" is an eighth section in the device notes, beyond the brief's seven.
   Without it, the developer-only parts of Recorded voice would have been lost.
