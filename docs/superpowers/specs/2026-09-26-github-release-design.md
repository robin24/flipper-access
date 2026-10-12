# Publishing the accessible firmware: repositories, first release, upstream sync, the voice

Date: 2026-09-26. Decisions taken with Robin: two repositories (option one below); the firmware
fork public from the start, the project repository private until the first release; GPL-3 for
the project repository; Kokoro and eSpeak-NG for the vocabularies (section 5), of which, by
Robin's decision of 2026-10-11, a release ships one, heart, made with Kokoro; merges, never
rebases, for upstream; one tag per release; an honest statement that the code was written by AI
agents under Robin's direction. Earlier context: `docs/roadmap.md` (why a fork, the memory plan)
and the main design spec `2026-09-22-flipper-screen-reader-design.md`.

This document is written for a screen reader: prose and lists, no tables.

## 1. Purpose and scope

The first public iteration is a release a blind user can install and use without help from a
sighted person. It consists of:

- the firmware update package, built from the `screen-reader` branch with the release options
  (`COMPACT=1 DEBUG=0`), with its resources;
- the voice pack: the recorded vocabulary `heart`, made with Kokoro's `af_heart` voice, with its
  licence file. It is the only pack a release ships, by Robin's decision of 2026-10-11; the
  eSpeak-NG backend stays for the sets users make;
- an install script that puts the firmware and the voice on the device from a Mac, Linux or
  Windows computer, over the USB serial console or with the voice through a card reader, with
  plain-text progress;
- documentation for blind users first: install, first boot, the chords and settings, the voice,
  known limits, how to report a crash;
- the repositories on GitHub, continuous builds, a release workflow, and a sync procedure for
  following Momentum.

Out of scope for this iteration: the unexplained idle crash (the hunt continues in parallel
through the UART capture; it is a known issue in the release notes), Marauder or FlipperHTTP
on the Wi-Fi board, the iOS companion app, vocabularies in languages other than English (the
pronunciation layer is English), Momentum's app catalog, qFlipper, and the accessible desktop
app Robin wants later (Electron, for flashing, clip generation and the tethered text stream,
usable with VoiceOver on the Mac and NVDA on Windows). That app is a later project with its
own design; this iteration's install script is the interim path, and what it does over the
console is written down so the app can implement it in JavaScript later (section 6). The
release assets get a machine-readable manifest for the same reason (section 7).

## 2. Repositories (option one, chosen)

Two repositories, as today, both under Robin's GitHub account `robin24`:

- The project repository, `flipper-access`, the folder's name. It is the landing page: README, docs, tools, tests, continuous builds, and the GitHub
  Releases. The firmware clone at `Momentum-Firmware/` becomes a git submodule pinned to the
  commit each release was built from; `.gitignore` drops the `Momentum-Firmware/` line.
  Private until the first release, then public.
- The firmware fork, a proper GitHub fork of `Next-Flip/Momentum-Firmware`, created with
  `gh repo fork --clone=false`; it keeps the name `Momentum-Firmware` and shows "forked from"
  on GitHub. Branch `screen-reader` is pushed and made the default branch. Forks of public
  repositories are public, and the branch holds nothing sensitive, so it is public from day
  one. Momentum's README is left untouched (zero merge surface); the fork's GitHub description
  says what it is and links to the project repository. GitHub Actions stay disabled on the
  fork: Momentum's workflow would fail its check of the API version against the official
  release channel, since ours is 87.3, and its upload steps need Momentum's secrets.

Remotes in the local clone: `upstream` is Next-Flip, fetch only, with its push URL set to the
word `no_push` so a push there cannot happen by accident; `origin` is the fork.
`scripts/version.py` reads the branch's remote to fill `firmware.origin.git`, so the device
reports the fork's URL after the change.

Option two, rejected: folding tools, docs and tests into the fork under one folder. Simpler for
a contributor with one clone, but it mixes our history into Momentum's, makes the fork harder
to diff against upstream, and changes how every tool finds the firmware tree.

Creating the repositories is the first task, before any cleanup, so that everything after it
is pushed as it lands. Pushing to `origin` follows the standing rule (no asking); pushing to
`upstream` never happens.

## 3. Cleanup in the project repository

- The Text to SAM patch and `tools/say.sh` are retired: the reader speaks from its own engine
  since the clip voice, and `say.sh` was the patch's only user. `patches/` goes away, the
  modified file in the apps submodule is restored (`git -C applications/external checkout
  text2sam/sam_app.cpp`), and the firmware stops reporting itself as dirty, since
  `scripts/version.py` marks a build dirty on any difference from HEAD, submodules included.
  The patched `text2sam.fap` on the card is replaced by the stock build at the next resources
  deploy.
- `backups/backup-stock-1.4.3.tar` leaves git (`git rm --cached`, `backups/` ignored): it holds
  Robin's device settings, dolphin state and region data. The file stays on disk. Its blob stays
  in the history, since it holds only those, and no keys and no PIN.
- `LICENSE`: GPL-3.0 at the project root, the same licence as Momentum and the official
  firmware, because the host tests compile the firmware's sources. The voice pack has its own
  terms (section 5).
- The README is split. `README.md` becomes the public document (section 8). A new
  `docs/device-notes.md` takes the sections that are about Robin's device and the working
  setup: "Device state", the developer parts of "Folder contents", "Useful commands",
  "Rolling back to official firmware". The README's "Plan" list is folded into
  `docs/roadmap.md`, which already carries it. `flipper-zero-accessibility-investigation.md`
  moves to `docs/2026-09-14-investigation.md`.
- Personal references: the specs, plans, build logs and measurements stay as they are; they
  are the record of how this was built. Tool docstrings that name Robin ("the settings Robin
  chose by ear") are reworded. The device name `delphi` leaves `tools/voice_words.txt` and
  moves to `tools/voice_words.local.txt`, ignored by git and passed with `--words`; a user's
  device name reaches the vocabulary through the missing-words mechanism, like any other
  word.
- Nothing secret was found in the tracked files or the history (token patterns, the board's
  Wi-Fi password, which appears only in Momentum's own documentation). Robin's e-mail address
  is in three build-log reports, the same address as every commit's author line, so it stays.
- `.gitignore` keeps `voice/` ignored: the vocabulary on this Mac is made with Apple's
  Samantha and must never be committed. `logs/` stays ignored (the UART and USB captures).
- `docs/README.md`, a short index: what the specs, plans, build logs and measurements are.

## 4. Cleanup on the card, and a tool so it stays clean

- `/ext/update` holds 37 folders: `f7-update-1.4.3`, `f7-update-mntm-012`, and 35 builds of
  ours, each with the updater's own `backup.tar` of internal storage inside. Keep the two
  Momentum and official packages for rollback and the folder of the running build; delete the
  other 34. Delete `/ext/sr/clips`, the ten voice trial clips. `/ext/backup-stock-1.4.3.tar` at
  the card root stays. Run the routine generator pass for the words in `missing.txt`.
- `tools/card_prune.py`: reads the running build's hash from `info device`, lists
  `/ext/update`, and removes every folder of ours (tagged releases are named
  `f7-update-sonar-X.Y.Z`; untagged builds keep fbt's `f7-update-mntm-screen-reader-<hash>`
  naming, or `f7-update-mntm-HEAD-<hash>` on a detached HEAD) except the running build's, which a
  tagged release shows by its `firmware.version`; folders named with `--keep` are never touched,
  and neither is any other firmware's package, such as the two rollback packages. `--dry` lists
  what would go. The CLI's `storage list` gives no dates, so "the running build" is the rule,
  not "the newest". The install script (section 6) runs it at the end, and so does the flash
  routine in `docs/device-notes.md`.

## 5. The voice: the engine, the choice, and voice sets

The vocabulary shipped in a release must come from a voice whose licence allows
redistribution. Apple's voices do not, so Robin's Samantha vocabulary stays a personal set.

The research of 2026-09-26, four rounds of samples on the Mac (`voice-samples/`, ignored by git)
and nine trial files through the piezo, settled the engine:

- Piper is out. Isolated words came out clipped or garbled with every voice; zero generator
  noise made them repeatable but robotic; cutting each word out of a carrier sentence by the
  model's phoneme timings still left many words wrong. The generator's Piper backend goes.
- Pocket TTS (Kyutai) is out: weird timbre and audio artifacts through the piezo, one preset
  broken outright.
- Kokoro (Apache 2.0, deterministic by design, the words one by one) was the easiest to
  understand through the piezo with its voice `af_heart`. It makes a word in 0.37 s on this
  Mac's CPU, so a vocabulary of 10,800 words takes about 17 minutes with four processes, and
  new words later take seconds. The release vocabulary is made with it.
- eSpeak-NG (GPL-3, repeatable by nature, a vocabulary in minutes) came second with its
  `en-us+f3` female variant; the male default was harsh through the piezo. It was planned as a
  light second set: small, fast to make, and independent of any model download. By Robin's
  decision of 2026-10-11 a release ships the Kokoro set alone, and eSpeak-NG stays a backend for
  the sets users make.

Determinism: Kokoro and eSpeak render a word identically every time, and the generator only
makes missing clips or, when a setting changes, all of them, so a set never mixes renditions.
Each set's manifest records the backend, the model file's SHA-256 and the processing settings.

Voice sets, decided with Robin on 2026-09-26: the card holds one folder per set under
`/ext/sr/voices/<set>/`, each with the 64 hashed clip folders, its `voice.txt` settings line,
its own `missing.txt` and, for a shipped set, `LICENSE.txt`. A string setting `sr_voice_set`
(up to 31 characters) names the chosen set; the Accessibility screen gets a "Voice" row that
cycles through the sets found on the card when the screen opens; the console gets
`sr voice list` and `sr voice use <set>`, and `sr voice status` names the set. When the saved
set is missing, the reader uses the first set found, in name order, and says nothing about it
beyond the status line. The engine's clip path takes the set name; nothing else about playback
changes. Robin's existing `/ext/sr/voice` moves once to `/ext/sr/voices/samantha` by a
generator command; the firmware reads only the new layout, and the install script never sees
the old one.

The generator: `--set <name>` selects the set; locally the Samantha set stays in `voice/`
(never deleted or moved) and every other set lives in `voices/<name>/`; `--backend kokoro`
with `--voice af_heart` runs the model in-process in `--jobs` worker processes; `--backend
espeak` with `--voice en-us+f3` runs the command; `say` stays for personal sets. The routine
command gains the set, and `--sync` uploads to the set's folder. The piezo tuning of the Kokoro
set (gain and high-pass, by ear, with `sr play` of a few clips) is the first device step of
plan B; the trial files used the Samantha settings (high-pass 500, gain 1.3, soft limiter).

The voice pack: `tools/voice_pack.py --set <name>` writes `voice-<name>-sonar-X.Y.Z.tar` with
`sr/voices/<name>/...`, its `voice.txt` and a `LICENSE.txt` naming the engine, the model and
its licence (Kokoro: Apache 2.0, in full, with attribution; eSpeak-NG: GPL-3, in full), and the
pack's own terms: what the project adds is CC0 1.0, by Robin's decision of 2026-10-11. Plain tar,
uncompressed (8-bit PCM compresses poorly), in the USTAR format with an entry for every folder
before the files in it, since the device's unpacker makes a folder only from its entry (section
6). A release ships one pack, the Kokoro set `heart`, by Robin's decision of 2026-10-11. On a
fresh card it is the only set, so Auto speaks with it, and the install script sets no default;
`release.json` still names `heart` as the default voice for the later desktop app. The install
script puts on the card each pack it is given.

The generator remains a user tool: anyone can make a set in another Kokoro voice, with eSpeak,
or with `say` for personal use, and the README says how.

## 6. The install path

`tools/install.py` replaces qFlipper for our users. Requirements: Python 3.10 or newer and
`pyserial`; nothing else. It carries its own copy of the storage protocol
(`tools/flipper_storage.py`, adapted from Momentum's `scripts/flipper/storage.py`, GPL-3 like
the rest), so a user needs only the release assets and this script, not the firmware tree.
Progress is plain lines, one per step, for the computer's own screen reader; errors are
sentences; the exit code is non-zero on failure. The device says nothing until Sonar runs with
the voice on the card, so the script narrates every step on the computer, to the last. The console protocol the script uses (each
command, its reply, the chunked write, the wait for the reboot) is documented in
`docs/install-protocol.md`, so the later desktop app can implement it without reading Python.
Neither Python nor Node is preinstalled on Windows; the script is the interim path, and the
desktop app, which packages its own runtime, is the answer for users who install nothing.

Inputs: the update package (`.tgz`, unpacked by the script) and the voice pack (`.tar`), by
path; `--port` overrides the port. The port is found by USB vendor and product id
(`0483:5740`) through `pyserial`'s port list, on macOS, Linux and Windows.

Steps:

1. Read `info device`; say which device, firmware and version were found. Works from the
   official firmware (its console has `update install` and the storage commands) and from
   Momentum.
2. `update backup /ext/backup-<date>.tar`: internal storage to the card, for a rollback with
   `update restore`.
3. Put the voice on the card. The script asks which way, through a card reader or over USB,
   and the card reader is the default answer (Robin, 2026-09-28, the review's question 2):
   - Through a card reader, about 3 minutes for the copy of the voice's 10,537 files and 26
     seconds for the `._` files on 2026-10-11, and 2 minutes 40 seconds for the computer's whole
     part on 2026-10-12 (`docs/measurements/2026-10-11-installer-device-checks.txt`): the script
     first writes a small marker file to the card over USB, then asks the user to take the
     microSD card out of the Flipper and put it into the computer's card reader. It finds the
     card among the mounted
     volumes by that marker, unpacks the pack onto it with Python's own tar reader, removes the
     marker, ejects the card, and asks the user to put it back into the Flipper, then waits
     until the console sees the card again. The tar reader copies no metadata, but macOS still
     puts a `._` file of 4 KB beside every file and folder written: it gives everything a
     process makes the `com.apple.provenance` attribute, which exFAT keeps only in such a file,
     and which cannot be removed (seen on 2026-10-03,
     `docs/measurements/2026-10-02-card-settings-and-clip-order.txt`). So the script deletes
     every `._` file under the set's folder: from the Mac before the eject, which took 26 seconds
     for the voice's 10,537 files on 2026-10-11
     (`docs/measurements/2026-10-11-installer-device-checks.txt`), and through the console
     afterwards for any that are left, as was done on 2026-10-03. Their free places stay between
     the clips; with them, espeak's clips opened in a median of 25 ms. When no card with the
     marker turns up within 30 seconds of the user's Enter, the script stops with one sentence
     that says to put the card back into the Flipper and run it again: it never falls back to USB
     by itself, and no clock runs while the user moves the card (Robin, 2026-10-11).
   - Over USB: upload the pack as one file to `/ext`, unpack it with
     `storage extract /ext/<pack>.tar /ext`, and remove the tar (the archive lever below).
     These are commands the official firmware has, so the step works from 1.4.3, Momentum and
     Sonar alike. When step 1 found Sonar running, a timed mute before the unpack and
     `sr voice on` after it keep the reader from holding open a clip that the unpack replaces,
     as the sync guard does: `sr voice off <seconds>`, with the unpack's time from the spike and
     a margin, since the console is busy for the whole unpack and the mute cannot be renewed
     meanwhile; if the script dies, the voice comes back by itself.
4. Upload the update package folder to `/ext/update/<name>/`.
5. `update install /ext/update/<name>/update.fuf`; the device reboots into the updater.
6. Wait for the console to come back (the updater reboots twice), read `info device` again,
   compare the hash with the package's, and say "done" or what differs.
7. Prune older packages of ours with `card_prune.py`.

Re-running is safe: the unpack overwrites every clip and keeps the folders that are already
there; the package folder is replaced.

Time goal: a fresh install in under 15 minutes on a Mac, voice included. Through a card reader,
copying the voice's 10,537 files onto the card took about 3 minutes on a Mac on 2026-10-11, and
the whole of the computer's part 2 minutes 40 seconds on 2026-10-12
(`docs/measurements/2026-10-11-installer-device-checks.txt`). Over USB the
transfers alone take 25 to 28 minutes, whichever of the two levers below is used (the spike of
2026-10-11, `docs/measurements/2026-10-11-transfer-spike.txt`). That is a lower bound, since
the backup, the update with its restarts and the checks come on top: the whole install over USB
with `tools/install.py`, measured on 2026-10-11 over a heart set already on the card, took 32
minutes. So the goal is met only through the card reader, which stays the default answer. The two
levers, measured:

- Larger transfer chunks: `storage.py` sent 8 KB per round trip and `flipper_storage.py` sends
  32 KB. On a file of 5 MB that is 35.7 s against 28.5 s, and on a folder of 500 clips 88.4 s
  against 78.9 s (6.3 files per second; the baseline of 2026-09-24 was 6.4, 2,828 clips in 442
  s). 64 KB and sizes up to 4 MB are no faster and the device refused none, since it writes what
  it reads at about 180 KB per second. The whole heart set sent file by file, 10,537 files and
  103.6 MB, took 26 minutes 21 seconds, a quarter of it the `storage stat` before each file.
- One archive instead of 11,000 files: the console's own `storage extract <archive>
  <destination>`, in the official firmware since June 2024 and so in 1.4.3, Momentum and
  Sonar, calls `tar_archive_unpack_to`, the unpacker the updater uses for the resources. The
  script uploads the pack as one file to `/ext`, runs `storage extract` into `/ext`, reads the
  line it prints for every entry without showing them, says the result, and removes the tar.
  The unpacker makes a folder only from a folder entry and opens every file with create-always,
  so the pack is USTAR with an entry for every folder first (`tools/voice_pack.py`, whose test
  unpacks it with the firmware's own tar reader, `tests/host/tar_unpack.c`). Measured with a
  full pack (111.3 MB, 10,604 entries): 653 s to send it and 964 s to unpack it onto a card
  without the set, 786 s over a set that is there, 24 to 27 minutes in all. That is no faster
  than the files: the limit is the card's writes, not the console's round trips, and the pack
  writes the bytes twice. The unpacker prints an entry line every 0.1 s and never went more
  than 3.1 s between two. This replaces the earlier plan of a new `sr voice unpack` command: it
  would have been Sonar's own, so missing from the firmware the script starts from (review of
  2026-09-28, R4).

The USB way keeps the pack and `storage extract`, though sending the files one by one takes as
long: it is the design here and in `docs/install-protocol.md`, the pack is what the release
ships, and the mute that goes with it ends by itself if the script dies. That mute is set once,
for the extract's whole time with a margin, since the console is busy with the extract and
cannot renew it meanwhile, where the sync renews its mute while it sends.

The update package (11.8 MB) adds 72 s over USB. A MB here is 1,048,576 bytes, a KB 1,024.

Held back: clips at 11,025 samples a second instead of 16,000, which would make the pack about a
third smaller. It changes the sound, so it waits for a listening test through the piezo, and that
test is made only if USB is still too slow once the spike has measured the two levers above
(Robin, 2026-09-28, the review's question 3). The spike has measured them and USB is still too
slow. Smaller clips would shorten the voice's transfer over USB, and the listening test is still
held back.

Rejected: shipping the voice inside the update package's resources tarball. The updater would
carry a manifest of 11,000 more entries and process it at every update, forever, and that path
is untested; the separate pack also lets the voice change without a firmware update.

## 7. Continuous builds and releases

Workflows live in the project repository; the fork's stay disabled.

`build.yml`, on every push and pull request: check out with submodules (shallow, with
`FBT_GIT_SUBMODULE_SHALLOW=1` as Momentum's workflow does), and fetch alone the Momentum commit
the fork builds on, pinned in `tools/momentum-base.txt`, for the golden checks; run the host
tests with clang on Ubuntu (`run_host_tests.sh` gets a bash-compatible form, and
`flash_headroom.sh` a portable `stat`) and `tests/fbt` on Python 3.10, the oldest the tools
support, with the packages of `requirements.txt`, and `--no-skips`, so that no check is left
out; run Momentum's lint, `./fbt lint_all`; build the firmware with
`./fbt COMPACT=1 DEBUG=0 updater_package` (fbt downloads the toolchain itself); check with
`git diff --exit-code` that the build changed no tracked file, since fbt rewrites the API table
when the API drifts; check the headroom against the radio stack's address in the package's
`update.fuf`, 880,640 bytes with ble_light 1.20.0; upload the package as a workflow artifact.
The fork's own workflows stay disabled, so the same workflow builds the fork's `screen-reader`
tip every Monday, and by hand any branch, tag or commit of the fork. Expected time: fifteen to
twenty minutes.

`release.yml`, on a tag `sonar-X.Y.Z` in the project repository: the same build, and a GitHub
Release with these assets: the update package `.tgz` from fbt, the one voice pack
`voice-heart-sonar-X.Y.Z.tar` (Robin's decision of 2026-10-11), made on the Mac and uploaded to
the draft release (Kokoro needs the model and about 17 minutes; the continuous build does not
make packs), and `install-sonar-X.Y.Z.zip` holding `install.py`, `flipper_cli.py`,
`flipper_storage.py`, `card_prune.py` and the project's GPL-3 `LICENSE`, plus `release.json`:
the version, the Momentum base commit, the voice, and every asset's name and SHA-256, so a later
app can find and verify what to download. The release notes name the Momentum commit the build
is based on, the changes, the known issues, and the install steps. The pack is made on the Mac
and uploaded to the draft, and `tools/release_finalise.py` then writes `SHA256SUMS` and
`release.json` from the draft's assets (review of 2026-09-28, R5).

Versions: semantic versions with a name prefix, starting at `sonar-0.1.0`. The tag goes on
both repositories: on the fork's commit, because fbt names the package after an exact-match
tag (`DIST_SUFFIX`) and `scripts/version.py` shows a tag as the firmware version on the
device's About screen; and on the project repository, which triggers the release. The release
job fetches the fork's tags for the submodule, checks that the submodule commit carries the
same tag, fails otherwise, and also sets `DIST_SUFFIX` from the tag in the environment, which
fbt honours over its own naming. On such a build, the About screen's firmware page ends with
"flipper-access", the project's name, where Momentum puts its website (review of 2026-09-28,
R9); a build from a branch shows the branch's name there.
`FIRMWARE_ORIGIN` in `fbt_options.py` changes from `Momentum` to `Sonar`, the firmware's name,
which `info device` shows as `firmware.origin.fork`.

## 8. Upstream sync

Momentum's `dev` branch has not moved since our base commit `d3f89dfe2` of 18 August 2026,
and `mntm-012` of 31 December 2025 is still the newest release, so the fork is current today.
The delta is 78 commits: 24 new files (the screen reader service, its tests' subjects) and 53
modified ones. The rules for when upstream moves:

- Merge, never rebase, once the branch is public: a rebase rewrites history that releases,
  tags and the submodule pointer refer to. Each merge is one commit "Merge Momentum
  mntm-013" on `screen-reader`, followed by a submodule bump in the project repository.
- Merge at Momentum's release tags, not at every dev commit. A dev merge before one of our
  releases is allowed when it carries a fix we want.
- `tools/upstream_check.sh` runs first: fetch `upstream`; print how many commits are new;
  list the files changed on both sides since the merge base (our 53 modified files against
  upstream's changes); run `git merge-tree --write-tree` as a dry run and print the
  conflicting paths; exit non-zero when there are conflicts. It also prints our footprint for
  the record.
- The two mechanical conflicts become scripts, so the resolution is "take upstream's file,
  rerun the script": `tools/strip_js_symbols.py` removes the `lib/mjs` headers and the
  JavaScript engine's functions from `targets/f7/api_symbols.csv`, sets the version by the
  API version rule below, and adds our exported lines (`canvas_tap_hint_note`,
  `canvas_tap_hint_note_at`, `button_panel_item_set_name`, `input_publish_event`, and the
  disabled `input_set_filter`); `tools/subghz_manifest.py` regenerates the built-in Sub-GHz
  app's source list from its directory. Both have tests in `tests/fbt`; the existing
  `test_subghz_sources.py` stays as the check.
- The API version rule: ours is upstream's major and minor, with the minor raised by the
  number of the fork's export rounds, two so far (87.1 to 87.3), kept as the constant
  `FORK_MINOR_STEP` in `tools/strip_js_symbols.py`, for as long as we export symbols
  upstream lacks. Apps from Momentum's catalog built for the same major still load.
- After a merge: host tests, `tests/fbt`, a release build, the headroom check, the RAM probe,
  the reader's scripted routine, the manual chord and screen check from the README, then the
  tag.

## 9. Public documentation

Audience: blind users first, then developers. Prose and lists, no tables; every command in
its own code block.

`README.md`, public:

- What this is, in three sentences, and who it is for.
- How it was made: the code was written by AI agents under Robin's direction; that, and
  Momentum's flash limit, is why it is a fork and not a pull request (as in `docs/roadmap.md`).
- What changed against Momentum: the reader and its chords, the Accessibility settings, the
  spoken names of icon screens, the dolphin in words, the crash address; the removals: games,
  the JavaScript engine and its apps, the home animations off by default, SAM.
- Install: the script, from the official firmware or Momentum, the backup it takes, how long
  it takes, what it says.
- First boot: what is heard, the reader is on, how to turn it off and on (Back and Down held).
- Using it: the chords, the Accessibility settings, the home screen and lock menu, locking,
  the infrared remotes, the file browser's menus, all taken from today's README.
- The voice: what the pack is, its licence, the missing-words mechanism, generating a
  vocabulary in another Kokoro voice, with eSpeak-NG, or with `say` for personal use.
- Known limits: today's list, plus the unexplained idle reboot with the request to report it.
- When it crashes: the popup's address and build, `sr status`, what to put in an issue.
- Building from source: the fork, fbt, the release options, the host tests, the headroom
  check.
- Following Momentum: the merge policy in two sentences.
- Licence and credits: GPL-3; Momentum and its contributors, Flipper Devices, Kokoro and eSpeak-NG and the
  voice's dataset with its attribution, the Black Magic Probe project for the board firmware.

Also: `docs/device-notes.md` (section 3), `docs/roadmap.md` updated, `docs/README.md`,
`CONTRIBUTING.md` (issues welcome; pull requests welcome, AI-assisted ones included, with
disclosure; the writing rules above; the tests to run), one issue template for bugs (firmware
hash, `sr status` output, steps, what was spoken), and `CHANGELOG.md` starting with the first
release.

## 10. Testing

- Host tests and `tests/fbt` run in CI on every push; the new scripts have tests there.
- The install script is tested against the device twice: from the Momentum build it runs
  today, and once from the official firmware 1.4.3 (rollback with the documented command,
  restore the stock backup, then install the release with the script). The second is the real
  user path and takes about half an hour of device time; it happens once before the first
  release, with Robin's agreement, since it wipes the device's Momentum settings for the
  duration.
- The voice pack is verified on the card: file count, `voice.txt`, the reader's `sr status`
  clip counters after the scripted routine, no underruns.
- The release workflow is rehearsed on a pre-release tag (`sonar-0.1.0-rc1`) before the
  real one, and the rehearsal's assets are installed with the script.
- The upstream check script is tested against a synthetic upstream branch in a throwaway
  clone (one commit that touches the CSV and the Sub-GHz directory), so its conflict report
  and the two re-application scripts are seen working before Momentum moves.

## 11. Order of work, and what needs Robin

1. Repositories created and everything pushed, the submodule registered.
2. Repository cleanup and the README split; card cleanup and `card_prune.py`.
3. The voice sets in the firmware and the generator; the Kokoro and eSpeak backends; the
   Kokoro set tuned by ear on the piezo; both sets on Robin's card beside Samantha; the pack
   tool.
4. The install script, the transfer measurements, the unpack through `storage extract`.
5. Continuous builds, then the release workflow and its rehearsal.
6. The public documentation, reviewed by Robin.
7. The round-trip install test from the official firmware.
8. Tag `sonar-0.1.0`, the project repository public, the GitHub Release.

Robin decides: the voice, the docs' final wording, and the moment of the round-trip test. The
names were decided on 2026-09-26: the repository `flipper-access`, the firmware Sonar, prefix
`sonar`.

Execution is three plans, because two steps wait for Robin: plan A covers steps 1 and 2, the
continuous build workflow and the upstream tooling from section 8, all of it automatable;
plan B is the voice work of step 3 (the voice sets, the Kokoro and eSpeak backends, the sets on Robin's card, the pack), which pauses for the piezo tuning; plan C is steps 4 to
8, which pause for the docs review and the round-trip test.

## 12. Open decisions

- Names: decided 2026-09-26. The project repository is `flipper-access`; the firmware is Sonar,
  prefix `sonar`, giving tags like `sonar-0.1.0`, packages `f7-update-sonar-0.1.0`, and the
  firmware origin `Sonar`.
- The voice: decided 2026-10-11. A release ships one pack, heart, made with Kokoro's voice
  af_heart.
- The voice pack's terms: decided 2026-10-11. What the project adds is CC0 1.0, beside the
  Apache 2.0 of Kokoro's model.
