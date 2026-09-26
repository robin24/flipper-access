# Publishing the accessible firmware: repositories, first release, upstream sync, Piper voice

Date: 2026-09-26. Decisions taken with Robin: two repositories (option one below); the firmware
fork public from the start, the project repository private until the first release; GPL-3 for
the project repository; Piper for the shipped vocabulary; merges, never rebases, for upstream;
one tag per release; an honest statement that the code was written by AI agents under Robin's
direction. Earlier context: `docs/roadmap.md` (why a fork, the memory plan) and the main design
spec `2026-09-22-flipper-screen-reader-design.md`.

This document is written for a screen reader: prose and lists, no tables.

## 1. Purpose and scope

The first public iteration is a release a blind user can install and use without help from a
sighted person. It consists of:

- the firmware update package, built from the `screen-reader` branch with the release options
  (`COMPACT=1 DEBUG=0`), with its resources;
- the voice pack: the recorded vocabulary made with a freely licensed Piper voice, with its
  licence file;
- an install script that puts both on the device from a Mac, Linux or Windows computer, over
  the USB serial console, with plain-text progress;
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
  Robin's device settings, dolphin state and region data. The file stays on disk.
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
  naming) except the running build's; folders named with
  `--keep` are never touched, and the two rollback packages are kept by default. `--dry` lists
  what would go. The CLI's `storage list` gives no dates, so "the running build" is the rule,
  not "the newest". The install script (section 6) runs it at the end, and so does the flash
  routine in `docs/device-notes.md`.

## 5. The Piper voice

The vocabulary shipped in a release must come from a voice whose licence allows
redistribution. Apple's voices do not. Piper runs on any platform and its voices carry their
licences in a model card, so the generator's `piper` backend (written in the clip-voice round,
never run: Piper was not installed) is the release path.

Install: `piper-tts` 1.8.0 into the project venv (it brings `onnxruntime` and `numpy`; a
prebuilt wheel exists for this Mac and for Linux). Models are downloaded from the Hugging Face
repository `rhasspy/piper-voices` into `voice-models/` (ignored), each with its `MODEL_CARD`.

Candidate voices, chosen by licence from the model cards read on 2026-09-26. Public domain or
CC0: `en_US-kristin-medium`, `en_US-norman-medium`, `en_US-john-medium`, `en_US-bryce-medium`,
`en_US-ljspeech-high`, `en_US-joe-medium`, `en_US-mike-medium`, `en_GB-cori-high`. Under the
Apache licence: `en_US-sam-medium`. CC-BY 4.0: `en_GB-alba-medium`. Excluded: `ryan` and both
`hfc` voices (non-commercial share-alike), `lessac` (the Blizzard research licence), and every
voice whose card only says "see URL" (`amy`, `alan`, `kusal`, `danny`, `jenny_dioco`).

The spike, in order:

1. Make the ten-clip check set (`--check`) with each candidate, plus a listening set of about
   forty words that covers the hard cases: short function words ("of", "to", "on", "in"),
   digits, the spelled letters, long words, acronyms the pronunciation layer spells, and a few
   menu names. Send them to the card as `sr play` files, next to the same words from Samantha.
2. Robin listens on the device and picks the voice. Then the highpass, gain and limiter are
   tuned for that voice by ear, with the same set; today's values (highpass 500, gain 1.3,
   soft) were tuned for Samantha and are only the starting point.
3. Measure: clips per second on this Mac with `--jobs`, and whether `synth_piper` resamples
   correctly. The medium and high models speak at 22,050 Hz, the clips are 16,000 Hz unsigned
   8-bit; the resampling in the generator gets its first real test here and is fixed if wrong.
4. Generate the full vocabulary with `--extract --extract-all`: every string of the firmware
   and of every app that ships in the package, not just the apps on Robin's card. The count
   will be higher than today's 10,789 clips; the spike reports it and the card's `open max`
   time, since the folder hashing keeps lookups flat.
5. Sync to the device, run the reader's scripted routine and a day of use.

Known risks the spike answers: single words from a neural voice can sound clipped or oddly
stressed (sentence-final fall on a one-word utterance), and a voice that sounds good through
headphones may not carry through the piezo. If no candidate is acceptable by ear, the fallback
is the best candidate with heavier processing, and the release ships anyway: the reader is
useless without a vocabulary, and a user can regenerate with any voice.

The voice pack: `tools/voice_pack.py` writes `voice-sonar-X.Y.Z.tar` from the built
vocabulary: `sr/voice/<hh>/<word>.raw`, `sr/voice/voice.txt` (the settings line, first 63
characters shown by the device), and `sr/voice/LICENSE.txt` naming the model, the dataset and
its licence, Piper's MIT licence, and the pack's own terms: CC0 for a public-domain or CC0
dataset, otherwise the dataset's licence (CC-BY 4.0 with attribution for `alba`). Plain tar,
uncompressed: the device's tar library unpacks it (section 6), and 8-bit PCM compresses
poorly anyway. `voice/` on the Mac stays the local build directory.

The generator remains a user tool: anyone can make a vocabulary in another Piper voice, or
with `say` for personal use, and the README says how.

## 6. The install path

`tools/install.py` replaces qFlipper for our users. Requirements: Python 3.10 or newer and
`pyserial`; nothing else. It carries its own copy of the storage protocol
(`tools/flipper_storage.py`, adapted from Momentum's `scripts/flipper/storage.py`, GPL-3 like
the rest), so a user needs only the release assets and this script, not the firmware tree.
Progress is plain lines, one per step, for the computer's own screen reader; errors are
sentences; the exit code is non-zero on failure. The console protocol the script uses (each
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
3. Put the voice on the card: file by file, or as one archive unpacked on the device, whichever
   the time goal below settles on.
4. Upload the update package folder to `/ext/update/<name>/`.
5. `update install /ext/update/<name>/update.fuf`; the device reboots into the updater.
6. Wait for the console to come back (the updater reboots twice), read `info device` again,
   compare the hash with the package's, and say "done" or what differs.
7. Prune older packages of ours with `card_prune.py`.

Re-running is safe: on the file-by-file path, clips already on the card with the same size are
skipped; on the archive path the unpack overwrites; the package folder is replaced.

Time goal: a fresh install in under 15 minutes on a Mac, voice included. The measured baseline
is 6.4 files per second over the console (2,828 clips in 442 s on 2026-09-24), which puts the
current 10,789 clips at about 28 minutes. Two levers, measured in the spike, ship as needed:

- Larger transfer chunks: `storage.py` sends 8 KB per round trip; the spike measures 8, 32 and
  64 KB on a 5 MB file and on a folder of small files.
- One archive instead of 11,000 files: a new console command `sr voice unpack <tar>` in the
  screen reader's CLI plugin calls the firmware's `tar_archive_unpack_to` into
  `/ext/sr/voice`, with the voice muted during the unpack as the sync guard does, and removes
  the archive afterwards. The script uploads the pack as one file and runs the command. The
  device unpacks at card speed, which is much faster than the console's per-file overhead.

Rejected: shipping the voice inside the update package's resources tarball. The updater would
carry a manifest of 11,000 more entries and process it at every update, forever, and that path
is untested; the separate pack also lets the voice change without a firmware update.

## 7. Continuous builds and releases

Workflows live in the project repository; the fork's stay disabled.

`build.yml`, on every push and pull request: check out with submodules (shallow, with
`FBT_GIT_SUBMODULE_SHALLOW=1` as Momentum's workflow does); run the host tests with clang on
Ubuntu (`run_host_tests.sh` gets a bash-compatible form, and `flash_headroom.sh` a portable
`stat`); run `tests/fbt`; build the firmware with `./fbt COMPACT=1 DEBUG=0 updater_package`
(fbt downloads the toolchain itself); check the headroom against the 880,640-byte limit;
upload the package as a workflow artifact. Expected time: fifteen to twenty minutes.

`release.yml`, on a tag `sonar-X.Y.Z` in the project repository: the same build, plus the
voice pack made in the same job (Piper from pip, the chosen model downloaded from Hugging
Face, `--extract --extract-all`, then `voice_pack.py`), and a GitHub Release with three
assets: the update package `.tgz` from fbt, `voice-sonar-X.Y.Z.tar`, and
`install-sonar-X.Y.Z.zip` holding `install.py`, `flipper_storage.py` and `card_prune.py`,
plus `release.json`: the version, the Momentum base commit, the voice, and every asset's name
and SHA-256, so a later app can find and verify what to download. The release notes name the
Momentum commit the build is based on, the changes, the known issues, and the install steps. If Piper in CI turns out slower than thirty minutes, the pack
is made on the Mac and uploaded by hand; the plan measures.

Versions: semantic versions with a name prefix, starting at `sonar-0.1.0`. The tag goes on
both repositories: on the fork's commit, because fbt names the package after an exact-match
tag (`DIST_SUFFIX`) and `scripts/version.py` shows a tag as the firmware version on the
device's About screen; and on the project repository, which triggers the release. The release
job fetches the fork's tags for the submodule, checks that the submodule commit carries the
same tag, fails otherwise, and also sets `DIST_SUFFIX` from the tag in the environment, which
fbt honours over its own naming.
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
  JavaScript engine's functions from `targets/f7/api_symbols.csv`, sets the version to
  upstream's major and minor plus one, and adds our exported lines (`canvas_tap_hint_note`,
  `canvas_tap_hint_note_at`, `button_panel_item_set_name`, `input_publish_event`, and the
  disabled `input_set_filter`); `tools/subghz_manifest.py` regenerates the built-in Sub-GHz
  app's source list from its directory. Both have tests in `tests/fbt`; the existing
  `test_subghz_sources.py` stays as the check.
- The API version rule: ours is upstream's major and minor, with the minor raised by one,
  for as long as we export symbols upstream lacks. Apps from Momentum's catalog built for the
  same major still load.
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
  vocabulary in another Piper voice or with `say` for personal use.
- Known limits: today's list, plus the unexplained idle reboot with the request to report it.
- When it crashes: the popup's address and build, `sr status`, what to put in an issue.
- Building from source: the fork, fbt, the release options, the host tests, the headroom
  check.
- Following Momentum: the merge policy in two sentences.
- Licence and credits: GPL-3; Momentum and its contributors, Flipper Devices, Piper and the
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
3. The Piper spike; Robin picks the voice by ear and tunes it; the full vocabulary; the pack
   tool.
4. The install script, the transfer measurements, the unpack command if needed.
5. Continuous builds, then the release workflow and its rehearsal.
6. The public documentation, reviewed by Robin.
7. The round-trip install test from the official firmware.
8. Tag `sonar-0.1.0`, the project repository public, the GitHub Release.

Robin decides: the voice, the docs' final wording, and the moment of the round-trip test. The
names were decided on 2026-09-26: the repository `flipper-access`, the firmware Sonar, prefix
`sonar`.

Execution is three plans, because two steps wait for Robin: plan A covers steps 1 and 2, the
continuous build workflow and the upstream tooling from section 8, all of it automatable;
plan B is the Piper work of step 3, which pauses for the listening test; plan C is steps 4 to
8, which pause for the docs review and the round-trip test.

## 12. Open decisions

- Names: decided 2026-09-26. The project repository is `flipper-access`; the firmware is Sonar,
  prefix `sonar`, giving tags like `sonar-0.1.0`, packages `f7-update-sonar-0.1.0`, and the
  firmware origin `Sonar`.
- The voice, after the listening test.
- The voice pack's terms, CC0 by default when the dataset allows it.
