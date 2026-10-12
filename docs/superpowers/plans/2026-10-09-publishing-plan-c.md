# Publishing, plan C: the install script, the release workflow, the public documents, the first release

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Sonar installable by a blind user without sighted help, from the official firmware or Momentum, and publish it as `sonar-0.1.0`: an install script, a tag-triggered release with every asset a user and a crash report need, the public documents, a rehearsal, the round trip from official firmware, and the release itself.

**Architecture:** `tools/install.py` talks to the device's USB console through the project's own `tools/flipper_cli.py` (port by USB id) and a new `tools/flipper_storage.py` (file transfer, adapted from Momentum's `scripts/flipper/storage.py`); it uses only console commands that are built in on every firmware it starts from, so it works on a blank card and from official 1.4.3. The voice goes to the card as one pack, unpacked by the console's `storage extract`, or through a card reader. A new `release.yml` builds a draft GitHub Release from annotated `sonar-*` tags; the voice packs, made on the Mac, are uploaded to the draft, and `tools/release_finalise.py` then writes `SHA256SUMS` and `release.json`, which the install script checks the installed firmware against.

**Tech Stack:** Python 3.10 or newer with pyserial for the user's side (nothing else); the project's venv for the tools; GitHub Actions and `gh`; the firmware's fbt in the submodule; the device's USB console.

**Spec:** `docs/superpowers/specs/2026-09-26-github-release-design.md`, sections 6, 7, 9 and 10, and steps 4 to 8 of section 11. The review report `docs/2026-09-28-review.md` on the branch `claude/flipper-access-review-m87rn7`, findings R2, R3, R5 to R8, R10, R11, R13, R15 and R16 and its release checklist; their state is in `docs/2026-09-28-review-fixes.md`, "Not done". The device checks of 2026-10-09 in the same record and in `docs/measurements/2026-10-09-device-checks.txt`.

## Robin's decisions, 2026-10-11

1. One voice ships: heart (Kokoro af_heart). It is the only pack among the release's assets, so on a fresh card it is the only set and Auto speaks with it; the install script sets no default. `release.json` still names `"default_voice": "heart"` for the later desktop app. The espeak backend and its licence text stay for users who make a set themselves.
2. What the project adds to a pack (the word selection, the processing, the layout) is released under CC0 1.0; the engines' own terms apply beside it (Apache 2.0 for Kokoro's model, GPL-3 for eSpeak-NG).
3. The review report moves into main's `docs/` (Task 9), and the branch `claude/flipper-access-review-m87rn7` is deleted once that is merged.

Task 1 was done by the controller on 2026-10-11: pull requests robin24/Momentum-Firmware#6 and robin24/flipper-access#7 merged, their branches and the leftover `claude/blank-card-flash-2026-10-09` deleted, and the branches `claude/plan-c-2026-10-11` created in both repositories.

## Global Constraints

- The user's side needs Python 3.10 or newer and pyserial, nothing else: `install.py`, `flipper_cli.py`, `flipper_storage.py` and `card_prune.py` import only the standard library and pyserial.
- The port is found by USB id 0483:5740 through pyserial's port list, on macOS, Linux and Windows, as `flipper_cli.find_port` does; `--port` overrides it.
- The install uses only console commands built into every firmware it starts from: `info`, `storage` (with `extract`), `update` (`install`, `backup`, `restore`) and, once Sonar runs, `sr`. Never `loader`, `power`, `input` or `sysctl`, which are plugins on the card and missing on a blank card (2026-10-09).
- Progress is plain lines on the computer, one per step, for the computer's own screen reader; errors are one sentence; no Python traceback reaches the user, a port that vanishes included; the exit code is non-zero on failure. The device is silent until Sonar runs with a voice on the card, so the script narrates to the last step.
- Re-running the install is always safe: the unpack overwrites clips and keeps folders, the package folder is replaced.
- Time goal: a fresh install in under 15 minutes on a Mac, voice included (spec section 6).
- Tags: `sonar-X.Y.Z` and `sonar-X.Y.Z-rcN`, annotated, the same name on the fork's commit and on the project's commit that records it, the fork's pushed first. The package is then `f7-update-sonar-X.Y.Z`, and `firmware.version` on the device is the tag.
- Release asset names: `flipper-z-f7-update-sonar-X.Y.Z.tgz`, `voice-heart-sonar-X.Y.Z.tar`, `install-sonar-X.Y.Z.zip`, `sonar-X.Y.Z-firmware.elf`, `sonar-X.Y.Z-firmware.map`, `flipper-z-f7-sdk-sonar-X.Y.Z.zip`, `sonar-X.Y.Z-source.tar.gz`, `SHA256SUMS`, `release.json`.
- Workflow security for `release.yml` (R16): actions pinned by commit SHA, no toolchain cache, no cancel-in-progress, `permissions` per job, `contents: write` only on the job that creates the draft.
- Flash limit 880,640 bytes, checked by `tools/flash_headroom.sh`; a release build starts from a clean checkout.
- Tests first, in the project's style: plain-script checks under `tests/fbt/` with `check()` and a closing "N of M checks passed" line, each added to `tools/run_host_tests.sh`; a check that needs pyserial says "skipped ..." without it. The runner is green with `--no-skips` in the venv before every commit.
- Commits: one finding or one deliverable per commit; the message is one sentence describing the state after the change, ending in a tag in parentheses such as "(install)" or "(release)", with the Co-Authored-By line; each firmware change on the fork is followed by its own submodule bump here. Work branches `claude/<topic>-<date>` in both repositories, a pull request per branch, merged with a merge commit "Merge <title> (#N)" once its build is green, then the branch deleted.
- Documents: plain sentences without contractions, no tables, no em-dashes, every command in its own code block, 9-character hashes, numbers with thousands commas; the fixes record wraps at 100 characters; the public README names no device and no port.
- Device: one agent on the device at a time; after a flash `sr screen` before any key; never set a PIN; the round trip from official firmware (Task 11) and making the repository public (Task 12) only with Robin's explicit go in chat.

## Review Focus

- A device whose console cannot be opened: PIN-locked (the port is gone altogether), in the updater, or held by qFlipper. The script must say which of these it may be in one sentence, not "not in the updater" alone. Task 4 tests the message.
- The port vanishing mid-step: the update reboots it, a cable comes loose. Waiting for the reboot must tolerate the port's absence for the updater's whole run, minutes, and a radio stack update adds reboots (R13); a loss outside a wait is one sentence and a non-zero exit. Tasks 3 and 4 test both.
- A card that is missing, unformatted, full or not exFAT: `storage` replies with an error mid-upload or mid-extract. The script stops with the device's reason and the step it was in, and a re-run continues. Tasks 3 and 4 test an error reply at each transfer.
- Starting from official 1.4.3 or a Momentum release: its `info device` keys and its `storage extract` output may differ from Sonar's, and it has no `sr`. Task 4's tests use a recorded 1.4.3 reply; Task 11 is the real check.
- A tag on the wrong commit, or rc1 and the final tag on one commit: the release job must fail before building rather than ship a package that calls itself mntm-dev or rc1, which `card_prune` would then delete from the user's card (R2, R3). Task 7 tests the checks with throwaway tags.

---

### Task 1: The work branches and the pending merges

**Files:** none changed; GitHub only.

- [ ] **Step 1: Merge the device checks of 2026-10-09 if they are still open**

The fork's `claude/device-checks-2026-10-09` into `screen-reader` and the project's branch of the same name into main, each with a merge commit once the project's build is green, then both branches deleted, and the fork's leftover `claude/blank-card-flash-2026-10-09` too. The project's merge then records the fork's merge commit (a submodule bump on main after the merge, as on 2026-10-03).

- [ ] **Step 2: Create the plan's work branches**

`claude/plan-c-<date>` in both repositories, from `screen-reader` and main.

---

### Task 2: `tools/flipper_storage.py`, the install's own file transfer

**Files:**
- Create: `tools/flipper_storage.py`
- Test: `tests/fbt/test_flipper_storage.py`
- Modify: `tools/run_host_tests.sh`

**Interfaces:**
- Consumes: `flipper_cli.open_port(port)` for an exclusive serial port.
- Produces: `class Storage` with `Storage(ser, chunk_size=DEFAULT_CHUNK)`, `command(line: str, timeout: float = 30) -> str` (one console command, its output without echo and prompt), `mkdir(path)`, `exists(path) -> bool`, `remove(path)`, `send_file(local: str, remote: str, progress=None)` (chunked `storage write_chunk`; `progress(sent_bytes, total_bytes)`), `send_tree(local_dir: str, remote_dir: str, progress=None)`, `extract(archive: str, dest: str, on_entry=None, timeout: float) -> int` (runs `storage extract`, counts the lines it prints, returns the count), and `class StorageError(Exception)` whose message is the device's own error sentence and the path. `DEFAULT_CHUNK` is 8,192 until Task 3 measures.

- [ ] **Step 1: Write the failing test**

A stand-in console in the style of `tests/fbt/test_selfupdate.py`: a byte stream that answers each command as the shell does, the echo and a line end, the output, then a line end and the prompt `>: `; `storage write_chunk` answers `Ready` and then takes the given number of bytes. Checks: a file of 20,000 bytes goes over in chunks of 8,192, 8,192 and 3,616, and the bytes the stand-in received are the file's; a `Storage error: file/dir not exist` reply raises `StorageError` whose message holds that sentence and the path; `extract` returns the number of entry lines and calls `on_entry` once per line; `exists` is true for a stat reply and false for "file/dir not exist"; a stream that ends mid-reply raises `StorageError("the connection was lost ...")`, not a serial exception. Without pyserial the test prints "skipped the storage checks: no pyserial".

- [ ] **Step 2: Run it and see it fail**

Run: `.venv/bin/python tests/fbt/test_flipper_storage.py`
Expected: an ImportError on `flipper_storage`.

- [ ] **Step 3: Write `tools/flipper_storage.py`**

Adapted from Momentum's `scripts/flipper/storage.py` (GPL-3, credited in the module's docstring): the same `storage write_chunk` protocol and error codes, with the console opened by `flipper_cli` instead of its own serial setup, no colorlog, no progress bar of its own, and the `extract` command added. A read that gets nothing for 30 seconds is a lost connection.

- [ ] **Step 4: Run it and see it pass, add it to the runner, run the runner**

Run: `.venv/bin/python tests/fbt/test_flipper_storage.py`, then `PATH="$PWD/.venv/bin:$PATH" tools/run_host_tests.sh --no-skips`
Expected: "flipper storage: N of N checks passed", the runner green.

- [ ] **Step 5: Commit**

Message: "The install's own file transfer, tools/flipper_storage.py, sends files and trees in chunks, runs storage extract and reports the device's errors as sentences (install)".

---

### Task 3: The transfer spike on the device

**Files:**
- Create: `docs/measurements/<date>-transfer-spike.txt`
- Modify: `tools/flipper_storage.py` (`DEFAULT_CHUNK`), `docs/superpowers/specs/2026-09-26-github-release-design.md` (section 6's figures)

**Interfaces:**
- Consumes: `Storage` from Task 2; `tools/voice_pack.py --set heart --version 0.0.0 --out <tmp>` for a full pack.
- Produces: `DEFAULT_CHUNK` and the constant `EXTRACT_SECONDS_PER_MB` in `tools/flipper_storage.py`, which Task 4's timed mute uses.

- [ ] **Step 1: Measure the chunk sizes**

With a scratch script in the session's scratchpad, not in the repository: send a 5 MB file and a folder of 500 clips with chunk sizes 8, 32 and 64 KB, each three times, and note the seconds. The device's reply to a chunk larger than its buffer is part of the result.

- [ ] **Step 2: Measure the pack's way over USB**

Mute with `sr voice off 900`, send the heart pack as one file to `/ext`, run `storage extract /ext/voice-heart-sonar-0.0.0.tar /ext`, time both, then `sr voice on` and remove the tar. Check `sr voice list`, a few `storage stat`s of clips, and that the reader speaks with heart (`sr voice use heart`, Back and Up, Robin listens). Then check the clip order the extract left: `storage list` of two folders against the pack's order.

- [ ] **Step 3: Set the constants and record**

`DEFAULT_CHUNK` to the fastest size that never failed; `EXTRACT_SECONDS_PER_MB` from the extract's time with a margin of half again. Write the measurements file in the style of the earlier ones, and replace section 6's estimates (28 minutes for the voice over USB) with the measured figures. If the whole install over USB still exceeds 15 minutes, say so in the file; the card reader stays the default answer either way (Robin, 2026-09-28).

- [ ] **Step 4: Commit**

Message: "The transfer spike's figures set the chunk size and the extract's time per megabyte, and the spec gives the measured install time over USB (install)".

---

### Task 4: `tools/install.py` over USB

**Files:**
- Create: `tools/install.py`
- Test: `tests/fbt/test_install.py`
- Modify: `tools/run_host_tests.sh`, `tools/flipper_cli.py` (the no-port sentence)

**Interfaces:**
- Consumes: `flipper_cli.find_port`, `flipper_cli.open_port`; `Storage`, `StorageError`, `EXTRACT_SECONDS_PER_MB` from Task 2 and 3; `card_prune.plan(folders, running_hash, running_version, keep)`.
- Produces, for Task 5 and the later desktop app: `read_info(storage) -> dict` (the `info device` keys and values), `describe(info) -> str` (one sentence: name, firmware origin and version), `backup(storage, date: str) -> str` (the backup's path), `voice_over_usb(storage, pack: str, sonar: bool, say)`, `upload_package(storage, package_dir: str, say) -> str` (the package's folder on the card), `start_update(storage, folder: str)`, `wait_for_device(timeout: float, say) -> Storage`, `verify(info: dict, release: dict) -> list[str]` (each difference as a sentence, empty when it matches), `prune(storage, say)`, and `main(argv) -> int`. `say` is a function taking one line.

- [ ] **Step 1: Write the failing tests**

A stand-in console as in Task 2, with recorded `info device` replies of Sonar 9149fe493, Momentum mntm-012 and official 1.4.3 (record the latter two in Task 11 if they are not at hand; until then a reply made from the keys the official firmware's `furi_hal_info` prints). Checks:

- `describe` names Sonar, Momentum and the official firmware from `firmware.origin.fork` and `firmware.version`.
- The commands a whole run sends, in order, contain no `loader`, `power`, `input` or `sysctl`, and are: `info device`, `update backup /ext/backup-<date>.tar`, the pack's upload, `storage extract`, the package's upload, `update install /ext/update/<name>/update.fuf`; and after the wait `info device`; no `sr voice use`, since heart is the only pack (decision 1).
- When the first `info device` shows Sonar, the extract is wrapped in `sr voice off <seconds>` with `<seconds>` from the pack's size and `EXTRACT_SECONDS_PER_MB`, and `sr voice on` after it; from another firmware no `sr` command is sent.
- `verify` against a `release.json` of version `sonar-0.1.0`, commit `9149fe493`, API 87.3: no difference for a matching reply; one sentence each for another version, another commit, `dirty: true`, another origin.
- `wait_for_device` with a stand-in port list that is empty for a while returns once the port comes back, and with one that never does, says one sentence after the time-out and the run exits with 1.
- A `StorageError` in the upload ends the run with the step's name and the device's sentence, exit 1, and no traceback in the output.
- `main` with no port found prints the sentence from `flipper_cli`, which now names the PIN lock too: "No Flipper serial port found. Is it plugged in, unlocked, not in the updater, and not used by qFlipper? Or name it with --port."

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/python tests/fbt/test_install.py`
Expected: an ImportError on `install`.

- [ ] **Step 3: Write `tools/install.py`**

Arguments: `--package <.tgz or folder>`, `--voice <pack.tar>` (repeatable, one per set), `--release <release.json>` (optional; without it `verify` compares only the commit against the package's folder name), `--port`, `--restore <backup.tar>` (runs `update restore` and waits, R13), `--yes` (no questions, the USB way). The steps are the spec's section 6, in its order, with the voice before the update since `storage extract` is in every firmware (R4). A `.tgz` is unpacked to a temporary folder with `tarfile` and the `data` filter. The wait allows 15 minutes and tolerates the port's absence throughout. Every line the user sees comes from `say`.

- [ ] **Step 4: The `flipper_cli` sentence**

Change `find_port`'s exit sentence to the one in Step 1, and its test in `tests/fbt/test_flipper_cli.py`.

- [ ] **Step 5: Run the tests and see them pass; run the runner**

Run: `.venv/bin/python tests/fbt/test_install.py` and the runner with `--no-skips`.
Expected: all checks passed.

- [ ] **Step 6: On the device, from Sonar**

With a package of the current branch and a heart pack of version 0.0.0: `.venv/bin/python tools/install.py --package <tgz> --voice <tar> --yes`. Time it, keep the output, and check `sr status`, `sr voice list`, `card_prune.py --dry`. Robin listens to the first boot ("Firmware updated, press OK to continue") and to Back and Up.

- [ ] **Step 7: Commit**

Message: "tools/install.py installs a package and voice packs over USB from any firmware with built-in console commands only, narrates each step, waits out the updater and checks the result against release.json (install)".

---

### Task 5: The card reader way, and the protocol document

**Files:**
- Modify: `tools/install.py`
- Test: `tests/fbt/test_install.py`
- Create: `docs/install-protocol.md`

**Interfaces:**
- Consumes: Task 4's functions.
- Produces: `card_volumes() -> list[str]` (mounted volumes on this system: `/Volumes/*` on macOS, `/media/$USER/*` and `/run/media/$USER/*` on Linux, drive letters D to Z on Windows), `find_card(marker: str, volumes: list[str]) -> str | None`, `unpack_to_card(pack: str, volume: str) -> int` (clips written), `remove_appledouble(volume: str, set_name: str) -> int`, and `voice_through_reader(storage, packs, say, ask) -> bool` (false when the card did not appear and the user chose USB).

- [ ] **Step 1: Write the failing tests**

With temporary folders as volumes: `find_card` finds the one holding the marker and ignores the others; `unpack_to_card` writes the pack's entries in the pack's order (the clip order) and refuses an entry that leaves the volume; `remove_appledouble` removes every `._*` file under `sr/voices/<set>/` and nothing else; `voice_through_reader` with a stand-in `ask` writes the marker over the console, says to move the card, gives up after the time-out and offers USB, and after a found card asks to put it back and waits for `storage stat /ext/sr/voices/<set>/voice.txt`.

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/python tests/fbt/test_install.py`
Expected: the new checks fail on missing functions.

- [ ] **Step 3: Write the functions; the question in `main`**

Without `--yes`, `main` asks "Copy the voice through a card reader (faster) or over USB? [R/u]", the card reader being the default (Robin, 2026-09-28). The marker is `/ext/.sonar-install-<8 hex digits>`. On macOS the card is ejected with `diskutil eject`; elsewhere the user is asked to eject it. After the card is back, the `._` files are removed: first from the computer before the eject, then any left are removed over the console with `storage remove`; the step reports how many each way found.

- [ ] **Step 4: Run the tests and the runner**

Expected: all checks passed.

- [ ] **Step 5: On the device, through this Mac's card reader**

With Robin moving the card: install the heart pack through the reader, time it, and count the `._` files the console still lists afterwards in two folders. Record whether the removal from the Mac worked (the spec calls it untried) in the transfer spike's file.

- [ ] **Step 6: Write `docs/install-protocol.md`**

For the later desktop app, without Python: each console command the script sends, the reply it expects and how it reads it, the chunked write, the extract's output, the wait for the reboot with its time-out, the card reader steps with the marker, and the `release.json` fields `verify` compares. The commands' order is Task 4's.

- [ ] **Step 7: Commit**

Two commits: the card reader way "(install)", and the protocol document "(install protocol)".

---

### Task 6: The voice packs' licences

**Files:**
- Modify: `tools/voice_pack.py` (`LICENCES`, `licence_text`)
- Create: `tools/licences/Apache-2.0.txt`, `tools/licences/GPL-3.0.txt`
- Test: `tests/fbt/test_voice_pack.py`

**Interfaces:**
- Consumes: Robin's decisions 1 and 2; the set's `manifest.json` settings, which hold the Kokoro model's and voices file's SHA-256.
- Produces: `licence_text(settings: dict) -> str`, the project's part always CC0 1.0.

- [ ] **Step 1: Write the failing test**

The heart pack's `LICENSE.txt` contains the whole Apache License 2.0 text (its first and last lines checked), the model's name and URL, the model file's and the voices file's SHA-256 from the manifest, the voice's name, and the attribution the model card asks for; it states that what the project adds is released under CC0 1.0 (decision 2). The espeak pack's text, for packs users make themselves, says the clips are made with eSpeak-NG (GPL-3, its text included) and that what the project adds is CC0 1.0. A pack whose backend is neither kokoro nor espeak is still refused without `--personal`.

- [ ] **Step 2: Run it and see it fail; write the texts; run it and see it pass**

Run: `.venv/bin/python tests/fbt/test_voice_pack.py` before and after.

- [ ] **Step 3: Commit**

Message: "The voice packs carry their licences in full: Apache 2.0 with the Kokoro model's version and checksums and its attribution, eSpeak-NG's GPL-3, and the terms of what the project adds (R10)".

---

### Task 7: Every build keeps its elf, and `release.yml`

**Files:**
- Modify: `.github/workflows/build.yml` (the upload step)
- Create: `.github/workflows/release.yml`, `tools/release_tag_check.sh`, `tools/source_bundle.sh`
- Test: `tests/fbt/test_release_tag_check.py`, `tests/fbt/test_source_bundle.py`

**Interfaces:**
- Produces: `tools/release_tag_check.sh <tag>` (run in the project root with the submodule checked out: fetches the fork's tag explicitly, deletes every other tag in the submodule, exits 1 with a sentence unless `git describe --tags --exact-match` gives the tag and HEAD is its commit, R2 and R3); `tools/source_bundle.sh <tag> <out>` (the fork at the tag with every submodule, archived recursively, R10); the draft release with the assets of the Global Constraints except the packs, `SHA256SUMS` and `release.json`.

- [ ] **Step 1: Write the failing tests**

`test_release_tag_check.py`, with throwaway repositories as in `test_upstream_check.py`: a tag at HEAD passes; a tag one commit behind HEAD fails with a sentence; `rc1` and the final tag, lightweight and annotated, on one commit: the check for the final tag passes and leaves only that tag, so `git describe` gives it. `test_source_bundle.py`: a throwaway repository with one submodule bundles both, with the submodule's files inside the archive.

- [ ] **Step 2: Run them and see them fail; write the two scripts; run them and see them pass**

- [ ] **Step 3: `build.yml` keeps the elf, the map and the SDK**

The upload step also takes `Momentum-Firmware/build/f7-firmware-C/firmware.elf`, `firmware.elf.map` and `Momentum-Firmware/dist/f7-C/flipper-z-f7-sdk-*.zip` (R6).

- [ ] **Step 4: Write `release.yml`**

On a push of a tag `sonar-*`; one build job with `contents: read` and a release job with `contents: write`; actions pinned by SHA; no cache; no cancel-in-progress. The build job: the project at the tag, the submodule at depth 1, `tools/release_tag_check.sh "$TAG"`, `DIST_SUFFIX=$TAG` and `WORKFLOW_BRANCH_OR_TAG=screen-reader`, the host tests with `--no-skips`, `./fbt lint_all`, the build, `git diff --exit-code`, the headroom, and a check that `build/f7-firmware-C/toolbox/version.json` says `"firmware_version": "<tag>"`; it uploads the update `.tgz`, the elf and map renamed `<tag>-firmware.elf` and `<tag>-firmware.map`, the SDK zip, the source bundle and `install-<tag>.zip` (install.py, flipper_cli.py, flipper_storage.py, card_prune.py), with build attestations for each asset (`actions/attest-build-provenance`, which needs `id-token: write` and `attestations: write` on that job alone). The release job creates a draft release, a prerelease for `-rc` tags, whose notes come from `docs/release-notes-template.md` (Task 9) with the Momentum base from `tools/momentum-base.txt`, the fork's commit, the submodules' commits and the source offer filled in.

- [ ] **Step 5: Check the workflow's syntax and commit**

`actionlint` if installed, else a YAML parse with Python. Commits: the elf upload "(R6)", the tag check "(R2, R3)", the source bundle "(R10)", the workflow "(release)".

---

### Task 8: `tools/release_finalise.py`

**Files:**
- Create: `tools/release_finalise.py`
- Test: `tests/fbt/test_release_finalise.py`

**Interfaces:**
- Consumes: the draft's assets, downloaded with `gh release download <tag> --dir <tmp>`; `tools/momentum-base.txt`; the API version from `Momentum-Firmware/targets/f7/api_symbols.csv`.
- Produces: `release_json(tag: str, fork_commit: str, momentum_base: str, api_version: str, default_voice: str, assets: list[tuple[str, str, int]]) -> dict` and `sha256sums(assets) -> str`; the command `tools/release_finalise.py <tag>` uploads `SHA256SUMS` and `release.json` to the draft with `gh release upload --clobber`. `release.json`'s keys: `version`, `firmware_version` (the tag), `firmware_commit` (9 characters), `momentum_base`, `api_version`, `default_voice`, `voices` (each pack's set, backend, voice, file), `assets` (each name, SHA-256, size). Task 4's `verify` reads `firmware_version`, `firmware_commit` and `api_version`.

- [ ] **Step 1: Write the failing test**

For a list of three assets with known bytes: the SHA-256 values, `SHA256SUMS` in `sha256sum`'s format sorted by name, the JSON keys above, `voices` read from the packs' `voice.txt` lines, and a refusal, one sentence, when an expected asset (Global Constraints) is missing or a pack's backend is not kokoro or espeak.

- [ ] **Step 2: Run it and see it fail; write the tool; run it and see it pass**

- [ ] **Step 3: The Mac's part, in the device notes**

A section "Making a release" in `docs/device-notes.md`: make the pack by explicit name with `tools/voice_pack.py --set heart --version X.Y.Z`, `gh release upload <tag> voice-heart-<tag>.tar`, then `tools/release_finalise.py <tag>` (R5).

- [ ] **Step 4: Commit**

Message: "tools/release_finalise.py writes SHA256SUMS and release.json from a draft release's assets, packs included, and uploads them (R5, R8)".

---

### Task 9: The public documents

**Files:**
- Modify: `README.md`, `docs/README.md`, `docs/roadmap.md`, `docs/2026-09-28-review-fixes.md`
- Create: `CHANGELOG.md`, `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/bug.md`, `docs/release-notes-template.md`; `docs/2026-09-28-review.md` if Robin chose so (decision 3)

- [ ] **Step 1: The README**

Install: the release's assets, the install command with each argument in its own code block, from official firmware or Momentum, the backup it takes, the card reader question, the time it takes, what it says, and that the device stays silent until the end. First boot: already updated on 2026-10-09; check it against what Task 4 heard. A new section "Going back": `install.py --restore <backup>`, and installing the official package with the same script (R13). The voice: the shipped pack, heart, its licence (Task 6), and that espeak or a Mac's voice can be added with the generator and chosen in the Voice row. Known limits: the API caveat, catalog apps that import the JavaScript engine's symbols fail to load, and apps that use the reader's exports fail on other firmware (R15). Licence and credits: Momentum and its contributors, Flipper Devices, Kokoro and its model card's attribution, eSpeak-NG, the source offer for the binaries (R10). The section's sentences that still say "the first release" or "until then" are updated.

- [ ] **Step 2: The new files**

`CHANGELOG.md` with 0.1.0's entry; `CONTRIBUTING.md` (issues welcome, pull requests welcome, AI-assisted ones included with disclosure, the writing rules, the tests to run); the bug template asking for `firmware.version`, where the build came from (release, CI or local), the `sr status` output, the steps and what was spoken (R16); the release notes template with the Momentum base, the fork tag, the submodule commits, the changes, the known issues, the install steps and the source offer (R7, R10).

- [ ] **Step 3: Decision 3, and the record**

If the report moves: copy it with `git show origin/claude/flipper-access-review-m87rn7:docs/2026-09-28-review.md > docs/2026-09-28-review.md` and point the fixes record's first line at it. In the fixes record, move each R item this plan closes from "Not done" to a section "Fixed in plan C".

- [ ] **Step 4: Robin reviews the wording**

Stop here and give Robin the README and the new files to read; apply the changes Robin asks for before going on.

- [ ] **Step 5: Commit**

One commit per document group, tagged "(docs)", the record's "(record)".

---

### Task 10: The rehearsal, `sonar-0.1.0-rc1`

**Files:**
- Create: `docs/measurements/<date>-release-rehearsal.txt`

- [ ] **Step 1: Merge the plan's branches**

Both pull requests, as in Task 1, once green.

- [ ] **Step 2: Tag and push**

The annotated tag `sonar-0.1.0-rc1` on the fork's `screen-reader` merge commit, pushed; the submodule bump on main if needed; the same tag on the project's main, pushed. The release workflow runs and leaves a draft prerelease.

- [ ] **Step 3: The Mac's part**

As written in Task 8's section: the heart pack, the upload, `release_finalise.py`.

- [ ] **Step 4: Install the draft's own assets**

Download them with `gh release download sonar-0.1.0-rc1`, check them with `shasum -a 256 -c SHA256SUMS`, and install with the downloaded `install.py` from the downloaded zip, on Robin's device as it is (Sonar). Then: `info device` gives `sonar-0.1.0-rc1`, the commit, `dirty false`, origin Sonar; `card_prune.py --dry` keeps the running build's folder; `arm-none-eabi-addr2line` on the release's elf resolves a known function's address; `tools/sr_drive.py` and `tools/ram_probe.py` pass, and `sr status` then says "underruns 0" (R7, spec section 10); Robin listens to the first boot and the heart voice.

- [ ] **Step 5: Record**

The measurements file: the workflow's run, the assets' sizes and checksums, the install's time and output, the checks above.

---

### Task 11: The round trip from official firmware 1.4.3

Only with Robin's explicit go in chat: it wipes the device's Sonar settings for its duration.

- [ ] **Step 1: Back to official firmware**

With the routine in `docs/device-notes.md`, "Rolling back to official firmware", and the stock backup in `backups/backup-stock-1.4.3.tar` restored. Record official 1.4.3's `info device` reply for Task 4's test if it was made up there.

- [ ] **Step 2: Install the rc1 release from official firmware**

The downloaded assets and `install.py`, the card reader way if Robin wants to try it, else USB. Time it against the 15-minute goal. The same checks as Task 10, Step 4.

- [ ] **Step 3: Record and fix**

Add the round trip to the rehearsal's measurements file. A failure here is fixed on a new branch, with its test, and the rehearsal repeated with `rc2`.

---

### Task 12: The release, `sonar-0.1.0`

- [ ] **Step 1: Tag protection**

On both repositories, a ruleset protecting tags `sonar-*` from deletion and update: Robin's settings, or `gh api` with Robin's go.

- [ ] **Step 2: Tag and build**

The annotated tag `sonar-0.1.0` on the same fork commit as rc1, pushed first, then on the project's main. The workflow's tag check leaves only `sonar-0.1.0` in its clone, so the build calls itself `sonar-0.1.0` (R3). Then the Mac's part, as in Task 10.

- [ ] **Step 3: Install the draft's assets and publish**

Install and check as in Task 10, Step 4, with `sonar-0.1.0`. Then publish the draft, and, with Robin's explicit go, make flipper-access public.

- [ ] **Step 4: Record**

The roadmap's status, the fixes record, the device notes' state, and the measurements file, in one documents branch merged as usual.
