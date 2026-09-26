# Publishing, plan A: repositories, cleanup, continuous build, upstream tooling

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the project and the firmware fork on GitHub, clean both repositories and the card, give the project a continuous build, and write the tools that make future Momentum merges mechanical.

**Architecture:** Two repositories under `robin24`: `flipper-access` (this repository: tools, tests, docs, workflows, later the releases) with the firmware clone `Momentum-Firmware/` turned into a submodule, and `Momentum-Firmware`, a public GitHub fork of `Next-Flip/Momentum-Firmware` whose default branch is `screen-reader`. Tools are plain Python 3 scripts with plain-script tests under `tests/fbt/`, run by `tools/run_host_tests.sh`; the continuous build is one GitHub Actions workflow in the project repository.

**Tech Stack:** git, the GitHub CLI (`gh`, logged in as `robin24`), Python 3 (the venv at `.venv` has pyserial), bash, GitHub Actions on `ubuntu-latest`, fbt (`./fbt` in the submodule), the Flipper's USB console through `tools/flipper_cli.py`.

**Spec:** `docs/superpowers/specs/2026-09-26-github-release-design.md` (sections 2, 3, 4, 7, 8 and the plan split in 11). The earlier context is `docs/roadmap.md` and the main spec `docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md`.

## Global Constraints

- Names: the repository is `flipper-access`, the firmware is Sonar, the prefix is `sonar`; `FIRMWARE_ORIGIN = "Sonar"` in `fbt_options.py`. Untagged builds keep fbt's `mntm-<branch>-<hash>` package naming.
- The fork `robin24/Momentum-Firmware` is public from day one; the project repository `robin24/flipper-access` is private until the first release. Nothing under `voice/`, `backups/`, `firmware-packages/`, `logs/` or `.venv/` is ever committed.
- Never push to Momentum's repository. In the firmware clone the remote `upstream` is Next-Flip with its push URL set to `no_push`; `origin` is the fork. Never run `git push upstream`.
- Merges, never rebases, on `screen-reader` once it is pushed: no `--amend` of a pushed commit, no force push, in either repository.
- The project repository is GPL-3.0 (`LICENSE`), the same licence as Momentum.
- `Momentum-Firmware/` is a git submodule of the project repository at that path, branch `screen-reader`. A task that commits in the firmware pushes `screen-reader` to `origin` and then commits the new submodule pointer in the project repository (`git add Momentum-Firmware`), so the continuous build can check the commit out. Never commit inside `Momentum-Firmware/applications/external` (a submodule of the firmware); only restore its files.
- Commit with explicit pathspecs (`git commit -m "..." -- path ...`), in the repository's style: plain sentences, no type prefixes, and every message ends with the line `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- One agent on the device at a time. Never send `loader close`; never set a PIN; never delete or move the repository-root `voice/` directory; the UART capture `tools/uart_log.py` keeps running throughout, do not stop it.
- Before a release build wipe `Momentum-Firmware/build/f7-firmware-C/resources` and `Momentum-Firmware/build/f7-firmware-C/.extapps`; check the image with `tools/flash_headroom.sh` (limit 880,640 bytes) before every flash; flash with `./fbt flash_usb_full`; after a flash run `sr screen` through `tools/flipper_cli.py` before any key is pressed, to catch a crash popup.
- Tests first for every script: a plain Python script under `tests/fbt/` that prints its failures and exits non-zero, added to `tools/run_host_tests.sh` in the same task. The whole runner must pass at the end of every task.
- Documentation is written for a screen reader user: prose and short lists, no tables, every command in its own code block. The device name `delphi` must not be in `tools/voice_words.txt`.
- Do not touch the Samantha vocabulary on the card except through the generator's routine command `.venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync`.

---

### Task 1: The fork and the project repository on GitHub

**Files:**
- Modify: `.gitignore` (drop the `Momentum-Firmware/` line)
- Create: `.gitmodules` (written by `git submodule add`)

**Interfaces:**
- Produces: the remotes `upstream` (Next-Flip, fetch only) and `origin` (the fork) in the firmware clone; `Momentum-Firmware` as a submodule of the project; the GitHub repositories `robin24/Momentum-Firmware` (public fork, default branch `screen-reader`, Actions disabled) and `robin24/flipper-access` (private). Every later task relies on the remote names `upstream` and `origin`.

- [ ] **Step 1: Preconditions**

Run from the project root `/Users/robin/Downloads/flipper-access`:

```bash
gh auth status
git status --short
git -C Momentum-Firmware status --short
git -C Momentum-Firmware branch --show-current
git -C Momentum-Firmware remote -v
```

Expected: logged in as `robin24`; the project tree clean; the firmware tree shows only ` m applications/external` (the Text to SAM patch, which Task 2 restores); branch `screen-reader`; one remote `origin` pointing at `https://github.com/Next-Flip/Momentum-Firmware.git`. Stop and report if anything differs.

- [ ] **Step 2: Create the fork**

```bash
gh repo fork Next-Flip/Momentum-Firmware --clone=false --default-branch-only
gh repo view robin24/Momentum-Firmware --json isFork,parent,visibility --jq '"fork=\(.isFork) parent=\(.parent.nameWithOwner) \(.visibility)"'
```

Expected: `fork=true parent=Next-Flip/Momentum-Firmware PUBLIC`. If the view fails right after the fork, the fork is still being created: run the view again a moment later.

- [ ] **Step 3: Point the clone at the fork, keep Momentum fetch-only**

```bash
cd Momentum-Firmware
git remote rename origin upstream
git remote set-url --push upstream no_push
git remote add origin https://github.com/robin24/Momentum-Firmware.git
git push -u origin screen-reader
git remote -v
git config branch.screen-reader.remote
cd ..
```

Expected: `upstream` shows the Next-Flip URL for fetch and `no_push` for push; `origin` shows the fork for both; the push reports the branch set up to track `origin/screen-reader`; the config prints `origin`. The push is fast: the fork already holds every commit below ours.

- [ ] **Step 4: The fork's default branch, description and Actions**

```bash
gh repo edit robin24/Momentum-Firmware --default-branch screen-reader --description "Momentum firmware with a built-in screen reader for blind users: the Sonar firmware. Documentation, releases and tools: https://github.com/robin24/flipper-access"
gh api -X PUT repos/robin24/Momentum-Firmware/actions/permissions -F enabled=false
gh api repos/robin24/Momentum-Firmware/actions/permissions --jq .enabled
gh repo view robin24/Momentum-Firmware --json defaultBranchRef --jq .defaultBranchRef.name
```

Expected: `false` and `screen-reader`.

- [ ] **Step 5: Check nothing in the tools names the old remote**

```bash
grep -rn "origin/dev" tools tests docs/*.md README.md || echo "no references"
```

Expected: `no references` (or only references inside build logs and measurement files, which are history and stay as they are).

- [ ] **Step 6: The submodule**

```bash
sed -i '' '/^Momentum-Firmware\/$/d' .gitignore
cat .gitignore
git submodule add -b screen-reader https://github.com/robin24/Momentum-Firmware.git Momentum-Firmware
cat .gitmodules
git submodule status
git status --short
```

Expected: the ignore file without the firmware line; git says it is adding the existing repository at `Momentum-Firmware` to the index; `.gitmodules` has `path = Momentum-Firmware`, the fork's URL and `branch = screen-reader`; the status line shows the current firmware commit with `(heads/screen-reader)`; the staged changes are `.gitignore`, `.gitmodules` and `Momentum-Firmware`.

- [ ] **Step 7: Commit**

```bash
git commit -m "The firmware clone becomes a submodule: the Sonar fork of Momentum on GitHub

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- .gitignore .gitmodules Momentum-Firmware
```

- [ ] **Step 8: Create the project repository and push**

```bash
gh repo create robin24/flipper-access --private --source=. --remote=origin --push --description "Sonar: a talking Flipper Zero. Momentum firmware with a built-in screen reader for blind users, a recorded voice, install tools and documentation."
git remote -v
gh repo view robin24/flipper-access --json visibility,defaultBranchRef --jq '"\(.visibility) \(.defaultBranchRef.name)"'
gh api repos/robin24/flipper-access/contents/.gitmodules --jq .name
git log --oneline -1 origin/main
```

Expected: `PRIVATE main`, `.gitmodules`, and the last commit of `main` on GitHub is the submodule commit.

- [ ] **Step 9: Report**

The report names both URLs, the remote layout of the firmware clone, and confirms that `git push upstream` fails (`git -C Momentum-Firmware push upstream screen-reader --dry-run` must print an error about `no_push`).

---

### Task 2: Retire Text to SAM, the stock backup out of git, the licence, ignore rules, the local word list

**Files:**
- Delete: `patches/text2sam-cli-mode.patch`, `tools/say.sh`
- Create: `LICENSE` (the GPL-3.0 text, copied from `Momentum-Firmware/LICENSE`), `tools/voice_words.local.txt` (ignored, holds `delphi`)
- Modify: `.gitignore`, `README.md` (small fixes only; Task 5 rewrites it), `tools/voice_build.py`, `tools/voice_words.txt`
- Move: `flipper-zero-accessibility-investigation.md` to `docs/2026-09-14-investigation.md`
- Restore in the firmware's apps submodule: `Momentum-Firmware/applications/external/text2sam/sam_app.cpp`

**Interfaces:**
- Produces: `tools/voice_build.py` loads `tools/voice_words.local.txt` beside `tools/voice_words.txt` when it exists; the firmware clone reports itself clean (`git diff HEAD --quiet` exits 0), so builds are no longer "dirty".

- [ ] **Step 1: Restore the patched app in the firmware's apps submodule**

```bash
git -C Momentum-Firmware/applications/external checkout -- text2sam/sam_app.cpp
git -C Momentum-Firmware status --short
git -C Momentum-Firmware diff HEAD --quiet && echo clean
```

Expected: an empty status and `clean`.

- [ ] **Step 2: Remove the patch and the helper, take the backup out of git, move the investigation**

```bash
git rm -q patches/text2sam-cli-mode.patch tools/say.sh
git rm -q --cached backups/backup-stock-1.4.3.tar
git mv flipper-zero-accessibility-investigation.md docs/2026-09-14-investigation.md
ls backups patches 2>&1
```

Expected: `backups/backup-stock-1.4.3.tar` still on disk; `patches` no longer exists (git removes the empty folder; if it remains, `rmdir patches`).

- [ ] **Step 3: Ignore rules**

Append to `.gitignore` these lines:

```
backups/
voice-models/
tools/voice_words.local.txt
```

- [ ] **Step 4: The licence**

```bash
cp Momentum-Firmware/LICENSE LICENSE
head -3 LICENSE
grep -c "" LICENSE
```

Expected: the GNU General Public License version 3 header, and a file of several hundred lines (the full text).

- [ ] **Step 5: The generator's local word list, and its wording**

In `tools/voice_build.py`:

Replace the docstring sentence `Defaults are the settings Robin chose by ear on 2026-09-24.` with `Defaults are the settings chosen by ear on 2026-09-24 for the Samantha voice.`

Replace the docstring sentence that begins `Words come from tools/voice_words.txt, from every string literal` so that it begins `Words come from tools/voice_words.txt and, when it exists, tools/voice_words.local.txt (personal words such as a device name, not in git), from every string literal` (keep the rest of the sentence).

In `main()`, the line

```python
    words = load_list(os.path.join(HERE, "voice_words.txt"))
```

becomes

```python
    words = load_list(os.path.join(HERE, "voice_words.txt"))
    words |= load_list(os.path.join(HERE, "voice_words.local.txt"))
```

(`load_list` returns an empty set for a missing file, so nothing else changes.)

Then move the device name:

```bash
grep -n "^delphi$" tools/voice_words.txt
sed -i '' '/^delphi$/d' tools/voice_words.txt
printf '# Personal words for this device, not in git: one per line.\ndelphi\n' > tools/voice_words.local.txt
grep -c "delphi" tools/voice_words.txt; git check-ignore tools/voice_words.local.txt
```

Expected: `0` and the local file's path (ignored).

- [ ] **Step 6: Check the generator still counts the word**

```bash
.venv/bin/python tools/voice_build.py --dry 2>&1 | tail -3
mv tools/voice_words.local.txt /tmp/vwl.txt && .venv/bin/python tools/voice_build.py --dry 2>&1 | tail -3; mv /tmp/vwl.txt tools/voice_words.local.txt
```

Expected: the first run's word count is one higher than the second's (the local list adds `delphi`); no error either way.

- [ ] **Step 7: Small README fixes so the tree is consistent until Task 5**

In `README.md`: replace `` `flipper-zero-accessibility-investigation.md` `` with `` `docs/2026-09-14-investigation.md` ``; remove the two "Folder contents" bullets for `tools/say.sh` and `patches/text2sam-cli-mode.patch`; remove the "Build the patched app and copy it to the card" command block under "Useful commands" together with its introductory sentence and the parenthetical note that follows it; in "Device state" replace the bullet about the Text to SAM app with: `- The Text to SAM app on the card is Momentum's stock build again since 2026-09-26; the patched build and tools/say.sh were retired, since the reader speaks from its own engine.`

- [ ] **Step 8: Run the tests and commit**

```bash
tools/run_host_tests.sh
git add .gitignore LICENSE tools/voice_build.py tools/voice_words.txt README.md docs/2026-09-14-investigation.md
git commit -m "Text to SAM retired, the stock backup out of git, the GPL-3 licence, a local word list for personal words

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- .gitignore LICENSE tools/voice_build.py tools/voice_words.txt tools/say.sh patches/text2sam-cli-mode.patch backups/backup-stock-1.4.3.tar README.md flipper-zero-accessibility-investigation.md docs/2026-09-14-investigation.md
git status --short
git push
```

Expected: the runner green, the status clean except the submodule (unchanged pointer, clean tree), the push accepted.

---

### Task 3: `tools/card_prune.py`, its test, and the card cleanup

**Files:**
- Create: `tools/card_prune.py`, `tests/fbt/test_card_prune.py`
- Modify: `tools/run_host_tests.sh` (append the test)

**Interfaces:**
- Consumes: `tools/flipper_cli.py`: `find_port(explicit=None)`, `open_cli(port)` returning a pyserial handle, `run(ser, cmd, timeout=15.0)` returning the reply text without echo, prompt or colour codes.
- Produces: `card_prune.plan(folders, running_hash, keep)`, a pure function returning the sorted list of folder names to remove; the command `tools/card_prune.py [--dry] [--keep NAME ...] [--port PORT]`, which Task 10 runs after the flash.

- [ ] **Step 1: Write the failing test**

Create `tests/fbt/test_card_prune.py`:

```python
#!/usr/bin/env python3
"""tools/card_prune.py's rule: of the folders under /ext/update, the running build's folder (its
name ends with the firmware.commit.hash from `info device`), the kept names and everything that
does not start with f7-update- stay; the rest goes. Run from the project root:
python3 tests/fbt/test_card_prune.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from card_prune import DEFAULT_KEEP, plan  # noqa: E402

failures = 0


def check(cond, what):
    global failures
    if not cond:
        failures += 1
        print("FAIL", what)


KEEP = set(DEFAULT_KEEP)
FOLDERS = [
    "f7-update-mntm-screen-reader-a9e4e7b9",
    "f7-update-1.4.3",
    "other",
    "f7-update-sonar-0.1.0",
    "f7-update-mntm-screen-reader-6451e86e",
    "f7-update-mntm-012",
]

check(DEFAULT_KEEP == ["f7-update-1.4.3", "f7-update-mntm-012"], "the rollback packages are kept by default")
check(
    plan(FOLDERS, "6451e86e", KEEP) == ["f7-update-mntm-screen-reader-a9e4e7b9", "f7-update-sonar-0.1.0"],
    "the running build, the kept names and a foreign folder stay; the rest goes, sorted",
)
check(
    plan(FOLDERS, "a9e4e7b9", KEEP) == ["f7-update-mntm-screen-reader-6451e86e", "f7-update-sonar-0.1.0"],
    "another running build",
)
check(
    plan(FOLDERS, "", KEEP)
    == ["f7-update-mntm-screen-reader-6451e86e", "f7-update-mntm-screen-reader-a9e4e7b9", "f7-update-sonar-0.1.0"],
    "no hash means no folder is the running build",
)
check(plan(FOLDERS, "6451e86e", KEEP | {"f7-update-sonar-0.1.0"}) == ["f7-update-mntm-screen-reader-a9e4e7b9"], "--keep adds a name")
check(plan([], "6451e86e", KEEP) == [], "an empty folder list")
check("other" not in plan(FOLDERS, "", set()), "a folder that is not a package is never touched")
check(plan(["f7-update-x-6451E86E"], "6451e86e", set()) == ["f7-update-x-6451E86E"], "the hash comparison is exact and lower case")

print(f"card prune: {8 - failures} of 8 checks passed")
sys.exit(1 if failures else 0)
```

- [ ] **Step 2: Run it to see it fail**

```bash
python3 tests/fbt/test_card_prune.py
```

Expected: `ModuleNotFoundError: No module named 'card_prune'`.

- [ ] **Step 3: Write the tool**

Create `tools/card_prune.py`:

```python
#!/usr/bin/env python3
"""Remove old update packages from the Flipper's card.

    tools/card_prune.py [--dry] [--keep NAME ...] [--port PORT]

Every `./fbt flash_usb` and `flash_usb_full` leaves its package in /ext/update/<name>/, with
the updater's own backup.tar of internal storage inside, and nothing removes them. The rule: the
folder of the running build stays (its name ends with the firmware.commit.hash that `info
device` reports), the folders named with --keep stay (the rollback packages f7-update-1.4.3 and
f7-update-mntm-012 are always kept), a folder whose name does not start with f7-update- is never
touched, and every other folder goes. `storage list` gives no dates, so "the running build" is
the rule, not "the newest". --dry prints the plan and removes nothing. Run from the project root
with the venv Python (pyserial): .venv/bin/python tools/card_prune.py --dry
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from flipper_cli import find_port, open_cli, run  # noqa: E402

UPDATE_DIR = "/ext/update"
DEFAULT_KEEP = ["f7-update-1.4.3", "f7-update-mntm-012"]


def plan(folders, running_hash, keep):
    """The folder names to remove, sorted: those that start with f7-update-, are not in keep,
    and do not end with "-" plus the running build's hash (eight hex digits, lower case)."""
    remove = []
    for name in sorted(folders):
        if not name.startswith("f7-update-"):
            continue
        if name in keep:
            continue
        if running_hash and name.endswith("-" + running_hash):
            continue
        remove.append(name)
    return remove


def running_hash(ser):
    for line in run(ser, "info device").splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "firmware.commit.hash":
            return value.strip().lower()
    return ""


def list_dir(ser, path):
    """(folders, files) of a card folder from `storage list`: lines "[D] name" and
    "[F] name 123b". A missing folder gives two empty lists."""
    folders, files = [], []
    for line in run(ser, f"storage list {path}", timeout=30).splitlines():
        line = line.strip()
        if line.startswith("[D] "):
            folders.append(line[4:].strip())
        elif line.startswith("[F] "):
            files.append(line[4:].rsplit(" ", 1)[0].strip())
    return folders, files


def remove_tree(ser, path, dry):
    """Remove a folder and everything in it: `storage remove` takes a file or an empty folder."""
    folders, files = list_dir(ser, path)
    for name in folders:
        remove_tree(ser, f"{path}/{name}", dry)
    if dry:
        return
    for name in files:
        reply = run(ser, f"storage remove {path}/{name}", timeout=30)
        if "error" in reply.lower():
            sys.exit(f"could not remove {path}/{name}: {reply}")
    reply = run(ser, f"storage remove {path}", timeout=30)
    if "error" in reply.lower():
        sys.exit(f"could not remove {path}: {reply}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true", help="print the plan and remove nothing")
    ap.add_argument("--keep", action="append", default=[], help="a folder name to keep (repeatable)")
    ap.add_argument("--port", help="serial port, default: auto-detect")
    args = ap.parse_args()
    keep = set(DEFAULT_KEEP) | set(args.keep)
    ser = open_cli(find_port(args.port))
    try:
        current = running_hash(ser)
        if not current:
            sys.exit("could not read firmware.commit.hash from info device")
        folders, _files = list_dir(ser, UPDATE_DIR)
        remove = plan(folders, current, keep)
        kept = sorted(set(folders) - set(remove))
        print(f"running build {current}; {len(folders)} folders in {UPDATE_DIR}; keeping {len(kept)}: {', '.join(kept)}")
        for name in remove:
            print(("would remove " if args.dry else "removing ") + name)
            remove_tree(ser, f"{UPDATE_DIR}/{name}", args.dry)
        print(f"{'would remove' if args.dry else 'removed'} {len(remove)} folders")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test**

```bash
python3 tests/fbt/test_card_prune.py
```

Expected: `card prune: 8 of 8 checks passed`.

- [ ] **Step 5: Add it to the runner**

Append to `tools/run_host_tests.sh` (same shape as the two blocks before it):

```zsh
if ! python3 "$ROOT/tests/fbt/test_card_prune.py" > "$OUT/card_prune.txt"; then
  cat "$OUT/card_prune.txt"
  echo "card prune checks failed"
  exit 1
fi
echo "$(tail -n 1 "$OUT/card_prune.txt")"
```

Run `tools/run_host_tests.sh`; expected: green, ending with the card prune line.

- [ ] **Step 6: Clean the card**

The device is idle on the home screen. First the plan, then the removal:

```bash
.venv/bin/python tools/card_prune.py --dry
.venv/bin/python tools/card_prune.py
.venv/bin/python tools/flipper_cli.py "storage list /ext/update"
```

Expected: the dry run lists 34 folders to remove and keeps `f7-update-1.4.3`, `f7-update-mntm-012` and `f7-update-mntm-screen-reader-6451e86e` (the running build; if `info device` reports another hash, that one); the real run removes them; the listing shows the three kept folders. Record the count and the time it took.

Then the ten voice trial clips:

```bash
.venv/bin/python tools/flipper_cli.py "storage list /ext/sr/clips"
```

Remove each listed file with `storage remove /ext/sr/clips/<name>` (one `flipper_cli.py` call can take all ten commands), then `storage remove /ext/sr/clips`, then confirm with `storage list /ext/sr`: `clips` gone, `voice` and `missing.txt` present.

- [ ] **Step 7: The routine generator pass**

```bash
.venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync
.venv/bin/python tools/flipper_cli.py "sr voice status"
```

Expected: the pulled missing words (about seven) get clips and are sent, the voice is restored, `missing.txt` is cleared, and the status shows the voice on with the Samantha settings line.

- [ ] **Step 8: Commit**

```bash
git add tools/card_prune.py tests/fbt/test_card_prune.py tools/run_host_tests.sh
git commit -m "card_prune: old update packages leave the card, the running build and the rollback packages stay

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- tools/card_prune.py tests/fbt/test_card_prune.py tools/run_host_tests.sh
git push
```

---

### Task 4: Firmware defaults: origin Sonar, reader on

**Files:**
- Modify: `Momentum-Firmware/fbt_options.py:7`, `Momentum-Firmware/lib/momentum/settings.c:50`

**Interfaces:**
- Produces: `info device` reports `firmware.origin.fork : Sonar`; a device with no saved Momentum settings starts with the screen reader on. Task 10 verifies the first on the device; the second is a default that only a fresh device sees (Robin's saved settings are untouched).

- [ ] **Step 1: The two lines**

In `Momentum-Firmware/fbt_options.py` change

```python
FIRMWARE_ORIGIN = "Momentum"
```

to

```python
# The fork's name: `info device` shows it as firmware.origin.fork, the About screen speaks it
FIRMWARE_ORIGIN = "Sonar"
```

In `Momentum-Firmware/lib/momentum/settings.c` change

```c
    .screen_reader = false, // OFF
```

to

```c
    .screen_reader = true, // ON: a device with no saved settings speaks from its first boot
```

- [ ] **Step 2: Check the build system accepts the option and the unit tests still pass**

```bash
cd Momentum-Firmware && ./fbt -h > /dev/null && echo "fbt ok" && cd ..
tools/run_host_tests.sh
```

Expected: `fbt ok`, the runner green. (`./fbt -h` evaluates `fbt_options.py`; a full build comes in Task 10.)

- [ ] **Step 3: Commit in the firmware, push, bump the pointer**

```bash
cd Momentum-Firmware
git commit -m "The firmware calls itself Sonar, and a fresh device starts with the screen reader on

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- fbt_options.py lib/momentum/settings.c
git push origin screen-reader
cd ..
git add Momentum-Firmware
git commit -m "Firmware at the Sonar defaults commit

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- Momentum-Firmware
git push
```

---

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

### Task 6: `tools/strip_js_symbols.py` and its test

**Files:**
- Create: `tools/strip_js_symbols.py`, `tests/fbt/test_strip_js_symbols.py`
- Modify: `tools/run_host_tests.sh`

**Interfaces:**
- Produces: `strip_js_symbols.strip(text) -> (new_text, changed)` and the command `tools/strip_js_symbols.py [--check] [PATH]`; after a Momentum merge the resolution of `targets/f7/api_symbols.csv` is "take upstream's file, run the script".

- [ ] **Step 1: Write the failing test**

Create `tests/fbt/test_strip_js_symbols.py`:

```python
#!/usr/bin/env python3
"""tools/strip_js_symbols.py: the JavaScript engine's lines leave targets/f7/api_symbols.csv,
the fork's exported lines are present at their sorted place, the version is upstream's with the
minor raised by one, and the script is idempotent. The golden check: the merge base's file
(upstream's) becomes the fork's file exactly. Run from the project root:
python3 tests/fbt/test_strip_js_symbols.py"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from strip_js_symbols import OUR_LINES, strip  # noqa: E402

FIRMWARE = os.path.join(ROOT, "Momentum-Firmware")
CSV = os.path.join(FIRMWARE, "targets", "f7", "api_symbols.csv")
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def git(*args):
    return subprocess.run(["git", "-C", FIRMWARE, *args], capture_output=True, text=True)


SYNTHETIC = """entry,status,name,type,params
Version,+,90.4,,
Header,+,applications/services/gui/canvas.h,,
Header,+,lib/mjs/mjs_core_public.h,,
Function,+,canvas_clear,void,Canvas*
Function,+,mjs_get_int,int,"struct mjs*, mjs_val_t"
Function,+,zz_last,void,void
Variable,+,mjs_something,int,
Variable,+,zz_var,int,
"""

out, changed = strip(SYNTHETIC)
lines = out.split("\n")
check(changed, "a synthetic upstream file changes")
check("Version,+,90.5,," in lines, "the minor version is raised by one")
check(not any("mjs" in line for line in lines), "every JavaScript line is gone")
for ours in OUR_LINES:
    check(ours in lines, f"our line is present: {ours[:40]}")
functions = [line.split(",")[2] for line in lines if line.startswith("Function,")]
check(functions == sorted(functions), "functions stay sorted by name")
check(functions[0] == "button_panel_item_set_name" and functions[-1] == "zz_last", "our lines sit at their sorted place")
check(out.endswith("\n") and not out.endswith("\n\n"), "one trailing newline")
again, changed_again = strip(out)
check(again == out and not changed_again, "idempotent: a second run changes nothing")

current = open(CSV, encoding="utf-8").read()
same, changed_current = strip(current)
check(same == current and not changed_current, "the fork's own file is left as it is")

base = git("merge-base", "upstream/dev", "HEAD")
if base.returncode != 0:
    print("skipped the golden check: no upstream/dev in this checkout")
else:
    upstream = git("show", f"{base.stdout.strip()}:targets/f7/api_symbols.csv").stdout
    golden, _ = strip(upstream)
    if golden != current:
        import difflib

        for line in list(difflib.unified_diff(golden.splitlines(), current.splitlines(), "script", "fork", lineterm=""))[:20]:
            print(line)
    check(golden == current, "golden: the merge base's file becomes the fork's file exactly")

print(f"strip js symbols: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
```

- [ ] **Step 2: Run it to see it fail**

```bash
python3 tests/fbt/test_strip_js_symbols.py
```

Expected: `ModuleNotFoundError: No module named 'strip_js_symbols'`.

- [ ] **Step 3: Write the script**

Create `tools/strip_js_symbols.py`:

```python
#!/usr/bin/env python3
"""Re-apply the fork's changes to targets/f7/api_symbols.csv after a Momentum merge.

    tools/strip_js_symbols.py [--check] [PATH]

The fork leaves the JavaScript engine out of the build (fbt_options.py, lib/SConscript), so its
API lines must leave the table too: every Header under lib/mjs/ and every Function or Variable
whose name starts with mjs_. The fork also exports the screen reader's calls (OUR_LINES), and its
API version is upstream's major and minor with the minor raised by one, for as long as those
exports exist. So a merge takes upstream's file whole and runs this script on it. The script is
idempotent: on a file it already produced it changes nothing, and the version is raised only when
a JavaScript line was removed or one of our lines was missing. Rows keep fbt's order: the
sections Version, Header, Function, Variable, each sorted by name, so our lines are inserted at
their sorted place. --check exits 1 if the file would change. PATH defaults to the submodule's
targets/f7/api_symbols.csv. tests/fbt/test_strip_js_symbols.py checks all of this, and that the
merge base's file becomes the fork's file exactly.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = os.path.join(ROOT, "Momentum-Firmware", "targets", "f7", "api_symbols.csv")
SECTIONS = ("Version", "Header", "Function", "Variable")
OUR_LINES = (
    'Function,+,button_panel_item_set_name,void,"ButtonPanel*, uint32_t, const char*"',
    'Function,+,canvas_tap_hint_note,void,"Canvas*, const char*, _Bool"',
    'Function,+,canvas_tap_hint_note_at,void,"Canvas*, uint8_t, uint8_t, const char*"',
    'Function,+,input_publish_event,void,"FuriPubSub*, InputEvent*"',
    'Function,-,input_set_filter,void,"InputFilterCallback, void*"',
)


def fields(row):
    """entry, status, name, type, params; the params may hold commas inside quotes."""
    return row.split(",", 4)


def is_js(row):
    kind, _status, name = fields(row)[:3]
    if kind == "Header":
        return name.startswith("lib/mjs/")
    return kind in ("Function", "Variable") and name.startswith("mjs_")


def sort_key(row):
    kind, _status, name = fields(row)[:3]
    return (SECTIONS.index(kind), name)


def strip(text):
    """The file's text after the fork's changes, and whether it changed."""
    lines = text.rstrip("\n").split("\n")
    header, rows = lines[0], lines[1:]
    kept = [row for row in rows if not is_js(row)]
    changed = len(kept) != len(rows)
    present = {fields(row)[2] for row in kept}
    for ours in OUR_LINES:
        if fields(ours)[2] not in present:
            kept.append(ours)
            changed = True
    kept.sort(key=sort_key)
    if changed:
        for i, row in enumerate(kept):
            parts = fields(row)
            if parts[0] == "Version":
                major, minor = parts[2].split(".")
                parts[2] = f"{major}.{int(minor) + 1}"
                kept[i] = ",".join(parts)
    return "\n".join([header, *kept]) + "\n", changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if the file would change, write nothing")
    ap.add_argument("path", nargs="?", default=DEFAULT)
    args = ap.parse_args()
    with open(args.path, encoding="utf-8") as f:
        text = f.read()
    out, changed = strip(text)
    if not changed:
        print(f"{args.path}: unchanged")
        return
    if args.check:
        sys.exit(f"{args.path}: would change; run without --check")
    with open(args.path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"{args.path}: updated, {len(text.splitlines()) - len(out.splitlines())} lines fewer, version {fields(out.splitlines()[1])[2]}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test**

```bash
python3 tests/fbt/test_strip_js_symbols.py
```

Expected: `strip js symbols: 14 of 14 checks passed` (13 of 13 where `upstream/dev` is absent, since the golden check is skipped there). If only the golden check fails, the sort order fbt uses differs from a plain name sort: read how `scripts/fbt/sdk.py` orders its entries (the `ApiEntries` dataclasses and where the CSV is written), match it in `sort_key`, and record what it was in the report. If the fork's own file fails "left as it is", the same applies.

- [ ] **Step 5: The command line, the runner, the commit**

```bash
python3 tools/strip_js_symbols.py --check
```

Expected: `... api_symbols.csv: unchanged`.

Append to `tools/run_host_tests.sh` the same block shape as for card prune, for `test_strip_js_symbols.py` with the output file `strip_js_symbols.txt` and the message `strip js symbols checks failed`. Run the runner: green.

```bash
git add tools/strip_js_symbols.py tests/fbt/test_strip_js_symbols.py tools/run_host_tests.sh
git commit -m "strip_js_symbols: the symbol table after a Momentum merge is upstream's file plus this script

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- tools/strip_js_symbols.py tests/fbt/test_strip_js_symbols.py tools/run_host_tests.sh
git push
```

---

### Task 7: `tools/subghz_manifest.py` and its test

**Files:**
- Create: `tools/subghz_manifest.py`, `tests/fbt/test_subghz_manifest.py`
- Modify: `tools/run_host_tests.sh`, `Momentum-Firmware/applications/main/subghz/application.fam` (regenerated once)

**Interfaces:**
- Produces: `subghz_manifest.sources(app_dir) -> list`, `subghz_manifest.rewrite(text, files) -> text`, `subghz_manifest.EXCLUDED`, and the command `tools/subghz_manifest.py [--check] [--verify-upstream] [MANIFEST]`.

- [ ] **Step 1: Write the failing test**

Create `tests/fbt/test_subghz_manifest.py`:

```python
#!/usr/bin/env python3
"""tools/subghz_manifest.py: the built-in Sub-GHz app's source list is every .c file under the
app's folder except the excluded basenames, top-level files first and then the subfolders, each
sorted; only the App block with appid "subghz" changes; the script is idempotent; the fork's
manifest is what the script writes; and the excluded names are the "!" entries of the merge
base's manifest. Run from the project root: python3 tests/fbt/test_subghz_manifest.py"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from subghz_manifest import EXCLUDED, rewrite, sources, upstream_excludes  # noqa: E402

FIRMWARE = os.path.join(ROOT, "Momentum-Firmware")
MANIFEST = os.path.join(FIRMWARE, "applications", "main", "subghz", "application.fam")
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


SAMPLE = '''App(
    appid="subghz",
    name="Sub-GHz",
    # a comment that mentions sources
    sources=[
        "old.c",
    ],
    requires=["region"],
)

App(
    appid="cli_subghz",
    apptype=FlipperAppType.PLUGIN,
    sources=["subghz_cli.c", "helpers/subghz_chat.c"],
)
'''

with tempfile.TemporaryDirectory() as tmp:
    for rel in ["subghz.c", "subghz_i.c", "subghz_cli.c", "helpers/subghz_txrx.c", "helpers/minmea.c",
                "scenes/subghz_scene_set_key.c", "views/receiver.c", "helpers/notes.txt"]:
        path = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
    files = sources(tmp)
    check(files == ["subghz.c", "subghz_i.c", "helpers/subghz_txrx.c", "views/receiver.c"],
          f"the list: top-level first, then subfolders, excluded names out: {files}")
    out = rewrite(SAMPLE, files)
    check('        "subghz.c",\n        "subghz_i.c",\n        "helpers/subghz_txrx.c",\n        "views/receiver.c",\n    ],' in out,
          "the list is written with eight spaces and trailing commas")
    check('"old.c"' not in out, "the old list is gone")
    check('sources=["subghz_cli.c", "helpers/subghz_chat.c"]' in out, "the other App block is untouched")
    check("# a comment that mentions sources" in out and 'requires=["region"]' in out, "the rest of the block is untouched")
    check(rewrite(out, files) == out, "idempotent")

current = open(MANIFEST, encoding="utf-8").read()
app_dir = os.path.dirname(MANIFEST)
check(rewrite(current, sources(app_dir)) == current, "the fork's manifest is what the script writes (run the script once if not)")

try:
    theirs = upstream_excludes(MANIFEST)
except subprocess.CalledProcessError:
    print("skipped the upstream check: no upstream/dev in this checkout")
else:
    check(set(theirs) == set(EXCLUDED), f"EXCLUDED equals the merge base's \"!\" entries; theirs: {sorted(set(theirs) ^ set(EXCLUDED))}")

print(f"subghz manifest: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
```

- [ ] **Step 2: Run it to see it fail**

```bash
python3 tests/fbt/test_subghz_manifest.py
```

Expected: `ModuleNotFoundError: No module named 'subghz_manifest'`.

- [ ] **Step 3: Write the script**

Create `tools/subghz_manifest.py`:

```python
#!/usr/bin/env python3
"""Regenerate the built-in Sub-GHz app's source list after a Momentum merge.

    tools/subghz_manifest.py [--check] [--verify-upstream] [MANIFEST]

The fork builds Sub-GHz into the firmware (the stripdown spec of 2026-09-25). The firmware build
hands each sources entry to the compiler on its own, so the fap's "*.c" with "!" excludes cannot
be used, and the files are listed one by one in applications/main/subghz/application.fam.
Momentum adds and renames files there, so after a merge this script rewrites the list of the App
block with appid "subghz": every .c file under the app's folder, in any subfolder, except the
EXCLUDED basenames, which are the fap's "!" entries in Momentum's manifest (the plugins' files,
the startup hook, the fap entry point and the Add Manually app's own files). Order: top-level
files first, then the subfolders, each sorted. --check exits 1 if the manifest would change.
--verify-upstream compares EXCLUDED with the "!" entries of the merge base's manifest and exits 1
on a difference, so a change in Momentum's list is noticed at the merge.
tests/fbt/test_subghz_manifest.py covers both.
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMWARE = os.path.join(ROOT, "Momentum-Firmware")
DEFAULT = os.path.join(FIRMWARE, "applications", "main", "subghz", "application.fam")
EXCLUDED = (
    "subghz_fap.c",
    "subghz_gps.c",
    "minmea.c",
    "subghz_cli.c",
    "subghz_chat.c",
    "subghz_extended_freq.c",
    "subghz_gen_info.c",
    "subghz_txrx_create_protocol_key.c",
    "subghz_scene_set_button.c",
    "subghz_scene_set_counter.c",
    "subghz_scene_set_key.c",
    "subghz_scene_set_seed.c",
    "subghz_scene_set_serial.c",
    "subghz_scene_set_type.c",
)
BLOCK = re.compile(r'(App\(\s*\n\s*appid="subghz",.*?sources=\[)(.*?)(\n\s*\],)', re.S)


def sources(app_dir, excluded=EXCLUDED):
    found = []
    for folder, _sub, files in os.walk(app_dir):
        for name in files:
            if name.endswith(".c") and name not in excluded:
                rel = os.path.relpath(os.path.join(folder, name), app_dir)
                found.append(rel.replace(os.sep, "/"))
    return sorted(found, key=lambda p: (p.count("/"), p))


def rewrite(text, files):
    m = BLOCK.search(text)
    if not m:
        sys.exit('no App block with appid="subghz" and a sources list')
    body = "".join(f'\n        "{path}",' for path in files)
    return text[: m.start(2)] + body + text[m.end(2) :]


def upstream_excludes(manifest_path):
    """The "!" entries of the merge base's manifest (upstream's version of the file)."""
    base = subprocess.check_output(["git", "-C", FIRMWARE, "merge-base", "upstream/dev", "HEAD"], text=True).strip()
    rel = os.path.relpath(manifest_path, FIRMWARE).replace(os.sep, "/")
    text = subprocess.check_output(["git", "-C", FIRMWARE, "show", f"{base}:{rel}"], text=True)
    m = BLOCK.search(text)
    if not m:
        sys.exit("no subghz App block in the merge base's manifest")
    return tuple(re.findall(r'"!([\w./-]+)"', m.group(2)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if the manifest would change, write nothing")
    ap.add_argument("--verify-upstream", action="store_true", help="compare EXCLUDED with the merge base's \"!\" entries")
    ap.add_argument("manifest", nargs="?", default=DEFAULT)
    args = ap.parse_args()
    if args.verify_upstream:
        theirs = set(upstream_excludes(args.manifest))
        if theirs != set(EXCLUDED):
            sys.exit(f"Momentum's exclude list differs: theirs only {sorted(theirs - set(EXCLUDED))}, ours only {sorted(set(EXCLUDED) - theirs)}")
        print("the exclude list matches the merge base's manifest")
    with open(args.manifest, encoding="utf-8") as f:
        text = f.read()
    files = sources(os.path.dirname(os.path.abspath(args.manifest)))
    out = rewrite(text, files)
    if out == text:
        print(f"{args.manifest}: unchanged, {len(files)} sources")
        return
    if args.check:
        sys.exit(f"{args.manifest}: would change; run without --check")
    with open(args.manifest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"{args.manifest}: rewritten, {len(files)} sources")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test, regenerate the manifest once**

```bash
python3 tests/fbt/test_subghz_manifest.py
```

Expected: every check passes except "the fork's manifest is what the script writes" (7 of 8 with the upstream check, the summary line counts what ran), because the hand-written list has `subghz_i.c` before `subghz_history.c`. Then:

```bash
python3 tools/subghz_manifest.py --verify-upstream
git -C Momentum-Firmware diff --stat
python3 tests/fbt/test_subghz_manifest.py
python3 tests/fbt/test_subghz_sources.py
```

Expected: the exclude list matches, the manifest is rewritten (a reorder of the same 36 files, no file added or removed: check the diff shows only moved lines), `subghz manifest: 8 of 8 checks passed`, and the existing source-list check still passes.

- [ ] **Step 5: Runner, commits, pushes**

Append the runner block for `test_subghz_manifest.py` (output `subghz_manifest.txt`, message `Sub-GHz manifest checks failed`), then:

```bash
tools/run_host_tests.sh
cd Momentum-Firmware
git commit -m "subghz: the built-in app's source list in the order tools/subghz_manifest.py writes it

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- applications/main/subghz/application.fam
git push origin screen-reader
cd ..
git add tools/subghz_manifest.py tests/fbt/test_subghz_manifest.py tools/run_host_tests.sh Momentum-Firmware
git commit -m "subghz_manifest: the built-in Sub-GHz source list is regenerated after a Momentum merge

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- tools/subghz_manifest.py tests/fbt/test_subghz_manifest.py tools/run_host_tests.sh Momentum-Firmware
git push
```

---

### Task 8: `tools/upstream_check.sh` and its test

**Files:**
- Create: `tools/upstream_check.sh`, `tests/fbt/test_upstream_check.py`
- Modify: `tools/run_host_tests.sh`

**Interfaces:**
- Produces: `tools/upstream_check.sh [--repo DIR] [--upstream REF] [--ours REF] [--no-fetch]`, exit 0 when there is nothing to merge or the dry run is clean, 2 on conflicts, 1 on an error.

- [ ] **Step 1: Write the failing test**

Create `tests/fbt/test_upstream_check.py`:

```python
#!/usr/bin/env python3
"""tools/upstream_check.sh against a throwaway repository: a base commit, a branch "ours" that
changes A and adds C, a branch "theirs" that changes A and B (a conflict on A), a branch
"theirs_clean" that changes only B. The script must count the new commits, list the files
changed on both sides, name the conflicts of the dry-run merge, and exit 2, 0 and 0. Run from
the project root: python3 tests/fbt/test_upstream_check.py"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "tools", "upstream_check.sh")
failures = 0


def check(cond, what):
    global failures
    if not cond:
        failures += 1
        print("FAIL", what)


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-C", repo, *args],
                   check=True, capture_output=True, text=True)


def write(repo, name, text):
    with open(os.path.join(repo, name), "w") as f:
        f.write(text)


def run_check(repo, upstream, ours):
    p = subprocess.run(["bash", SCRIPT, "--repo", repo, "--upstream", upstream, "--ours", ours, "--no-fetch"],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def section(out, title):
    """The indented lines after a title line, up to the next unindented line."""
    lines = out.split(title + "\n", 1)[1].split("\n") if title + "\n" in out else []
    names = []
    for line in lines:
        if not line.startswith("  "):
            break
        names.append(line.strip())
    return names


with tempfile.TemporaryDirectory() as tmp:
    repo = os.path.join(tmp, "r")
    os.makedirs(repo)
    git(repo, "init", "-q", "-b", "base")
    write(repo, "A", "a\n")
    write(repo, "B", "b\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "checkout", "-q", "-b", "ours")
    write(repo, "A", "a ours\n")
    write(repo, "C", "c\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "ours")
    git(repo, "checkout", "-q", "-b", "theirs", "base")
    write(repo, "A", "a theirs\n")
    write(repo, "B", "b theirs\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "theirs")
    git(repo, "checkout", "-q", "-b", "theirs_clean", "base")
    write(repo, "B", "b clean\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "clean")
    git(repo, "checkout", "-q", "ours")

    code, out = run_check(repo, "theirs", "ours")
    check(code == 2, f"a conflict exits 2, got {code}:\n{out}")
    check("upstream theirs: 1 new commits; ours ours: 1 commits on top" in out, f"the counts line:\n{out}")
    check("our footprint since the base: 1 added, 1 modified files" in out, f"the footprint line:\n{out}")
    check(section(out, "files changed on both sides:") == ["A"], f"both sides changed A only:\n{out}")
    check(section(out, "dry-run merge: conflicts in:") == ["A"], f"the conflict is A:\n{out}")

    code, out = run_check(repo, "theirs_clean", "ours")
    check(code == 0 and "dry-run merge: clean" in out, f"a clean merge exits 0:\n{out}")
    check(section(out, "files changed on both sides:") == [], f"nothing changed on both sides:\n{out}")

    code, out = run_check(repo, "base", "ours")
    check(code == 0 and "nothing to merge" in out, f"nothing new exits 0:\n{out}")

    code, out = run_check(repo, "nonexistent", "ours")
    check(code == 1, f"a bad ref exits 1, got {code}")

print(f"upstream check: {9 - failures} of 9 checks passed")
sys.exit(1 if failures else 0)
```

- [ ] **Step 2: Run it to see it fail**

```bash
python3 tests/fbt/test_upstream_check.py
```

Expected: failures (the script does not exist; bash reports it and the checks fail).

- [ ] **Step 3: Write the script**

Create `tools/upstream_check.sh` and make it executable (`chmod +x`):

```bash
#!/bin/bash
# What a merge of Momentum's branch into the fork's branch would meet, without touching the
# working tree.
#
#   tools/upstream_check.sh [--repo DIR] [--upstream REF] [--ours REF] [--no-fetch]
#
# Defaults: the submodule Momentum-Firmware, upstream/dev, HEAD. The upstream remote is fetched
# first unless --no-fetch. Prints the merge base, how many commits are new upstream, the fork's
# footprint, the files changed on both sides since the base, and the conflicts of a dry-run
# merge (git merge-tree --write-tree, git 2.38 or newer). Exit 0 when there is nothing to merge
# or the dry run is clean, 2 on conflicts, 1 on an error. Tested by
# tests/fbt/test_upstream_check.py. After a real merge, run tools/strip_js_symbols.py and
# tools/subghz_manifest.py --verify-upstream, then the host tests and a build.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
REPO="$ROOT/Momentum-Firmware"
UPSTREAM="upstream/dev"
OURS="HEAD"
FETCH=1
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --upstream) UPSTREAM="$2"; shift 2 ;;
    --ours) OURS="$2"; shift 2 ;;
    --no-fetch) FETCH=0; shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
cd "$REPO"
if [ "$FETCH" = 1 ]; then
  git fetch --quiet "${UPSTREAM%%/*}"
fi
if ! BASE=$(git merge-base "$OURS" "$UPSTREAM" 2>/dev/null); then
  echo "no merge base between $OURS and $UPSTREAM" >&2
  exit 1
fi
AHEAD=$(git rev-list --count "$OURS..$UPSTREAM")
ON_TOP=$(git rev-list --count "$UPSTREAM..$OURS")
ADDED=$(git diff --name-only --diff-filter=A "$BASE" "$OURS" | wc -l | tr -d ' ')
MODIFIED=$(git diff --name-only --diff-filter=M "$BASE" "$OURS" | wc -l | tr -d ' ')
echo "merge base: $(git log -1 --format='%h %ad %s' --date=short "$BASE")"
echo "upstream $UPSTREAM: $AHEAD new commits; ours $OURS: $ON_TOP commits on top"
echo "our footprint since the base: $ADDED added, $MODIFIED modified files"
if [ "$AHEAD" = 0 ]; then
  echo "nothing to merge"
  exit 0
fi
echo "files changed on both sides:"
comm -12 <(git diff --name-only "$BASE" "$OURS" | sort) <(git diff --name-only "$BASE" "$UPSTREAM" | sort) | sed 's/^/  /'
set +e
OUT=$(git merge-tree --write-tree --name-only --no-messages "$OURS" "$UPSTREAM" 2>&1)
STATUS=$?
set -e
case "$STATUS" in
  0) echo "dry-run merge: clean"; exit 0 ;;
  1) echo "dry-run merge: conflicts in:"; echo "$OUT" | tail -n +2 | sed '/^$/d; s/^/  /'; exit 2 ;;
  *) echo "dry-run merge failed: $OUT" >&2; exit 1 ;;
esac
```

- [ ] **Step 4: Run the test**

```bash
python3 tests/fbt/test_upstream_check.py
```

Expected: `upstream check: 9 of 9 checks passed`. If the "1 commits on top" or the footprint wording differs, fix the script's text, not the test.

- [ ] **Step 5: Run it for real, add it to the runner, commit**

```bash
tools/upstream_check.sh
```

Expected today: the merge base `d3f89dfe2` of 2026-08-18, `0 new commits`, the footprint `24 added, 53 modified files`, then `nothing to merge`, exit 0. Record the output in the report.

Append the runner block for `test_upstream_check.py` (output `upstream_check.txt`, message `upstream check checks failed`), run the runner, then:

```bash
git add tools/upstream_check.sh tests/fbt/test_upstream_check.py tools/run_host_tests.sh
git commit -m "upstream_check: what a Momentum merge would meet, from a dry run

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- tools/upstream_check.sh tests/fbt/test_upstream_check.py tools/run_host_tests.sh
git push
```

---

### Task 9: The test runner in bash, a portable headroom check, the continuous build

**Files:**
- Modify: `tools/run_host_tests.sh` (bash), `tools/flash_headroom.sh` (portable)
- Create: `.github/workflows/build.yml`

**Interfaces:**
- Produces: a green Build workflow on `main`, which uploads the update package as an artifact; `tools/flash_headroom.sh [BIN]` usable on Linux.

- [ ] **Step 1: The runner in bash**

In `tools/run_host_tests.sh` change the first lines

```zsh
#!/bin/zsh
# Build and run the host tests for the screen reader: ...
set -e
ROOT="${0:A:h:h}"
```

to

```bash
#!/bin/bash
# Build and run the host tests for the screen reader: ... (keep the comment lines)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
```

Everything else stays (the array `CFLAGS=(...)` and `"${CFLAGS[@]}"` are valid bash). Run `bash tools/run_host_tests.sh` and `tools/run_host_tests.sh`: both green.

- [ ] **Step 2: The headroom check without BSD stat**

Replace `tools/flash_headroom.sh` with:

```bash
#!/bin/bash
# Firmware image size against the flash the BLE stack leaves free: the updater refuses any page
# at or above SFSA (0xD7 for ble_light 1.20.0, 880,640 bytes); fbt's .free_flash ignores this.
#   tools/flash_headroom.sh [BIN]   (default: the submodule's build/f7-firmware-C/firmware.bin)
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
BIN="${1:-$ROOT/Momentum-Firmware/build/f7-firmware-C/firmware.bin}"
LIMIT=880640
if [ ! -f "$BIN" ]; then echo "no firmware image at $BIN" >&2; exit 1; fi
SIZE=$(wc -c < "$BIN" | tr -d ' ')
echo "firmware.bin $SIZE bytes, limit $LIMIT, spare $((LIMIT - SIZE)) bytes"
[ "$SIZE" -le "$LIMIT" ]
```

Run `tools/flash_headroom.sh`: expected `firmware.bin 864564 bytes, limit 880640, spare 16076 bytes` (the image from 2026-09-25 still in the build folder; another size is fine as long as it is below the limit).

- [ ] **Step 3: The workflow**

Create `.github/workflows/build.yml`:

```yaml
name: Build

on:
  push:
  pull_request:

concurrency:
  group: build-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    env:
      FBT_GIT_SUBMODULE_SHALLOW: "1"
      WORKFLOW_BRANCH_OR_TAG: ${{ github.ref_name }}
    steps:
      - name: Check out the project
        uses: actions/checkout@v4

      - name: Check out the firmware submodule
        run: git submodule update --init --depth 1 Momentum-Firmware

      - name: Name the build after the firmware commit
        run: echo "DIST_SUFFIX=sonar-ci-$(git -C Momentum-Firmware rev-parse --short=8 HEAD)" >> "$GITHUB_ENV"

      - name: Cache the toolchain
        uses: actions/cache@v4
        with:
          path: Momentum-Firmware/toolchain
          key: toolchain-${{ hashFiles('Momentum-Firmware/scripts/fbtenv.sh') }}

      - name: Host tests
        run: tools/run_host_tests.sh

      - name: Build the firmware and its update package
        run: cd Momentum-Firmware && ./fbt COMPACT=1 DEBUG=0 updater_package

      - name: Flash headroom
        run: tools/flash_headroom.sh

      - name: Upload the package
        uses: actions/upload-artifact@v4
        with:
          name: ${{ env.DIST_SUFFIX }}
          path: Momentum-Firmware/dist/f7-C/flipper-z-f7-update-*.tgz
          if-no-files-found: error
```

- [ ] **Step 4: Commit, push, watch the run**

```bash
git add .github/workflows/build.yml tools/run_host_tests.sh tools/flash_headroom.sh
git commit -m "A continuous build: host tests, the firmware package on Linux, the headroom check

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- .github/workflows/build.yml tools/run_host_tests.sh tools/flash_headroom.sh
git push
gh run list --limit 1
gh run watch --exit-status $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')
```

Expected: the run completes green within about twenty minutes and lists the artifact. If a step fails, read `gh run view --log-failed`, fix the cause (a missing package on the runner, a path, a shallow-clone limitation), commit with a plain message and push again; up to three rounds. Report the run URL, its duration, the toolchain download time and whether the cache hit on a second run (`gh run rerun` is not needed; a second push in a later task will show it).

---

### Task 10: Build, flash, verify, prune, and the notes

**Files:**
- Modify: `docs/device-notes.md` (the firmware line and the headroom figure), `docs/roadmap.md` (status)
- Create: `docs/measurements/2026-09-26-plan-a.txt`

**Interfaces:**
- Consumes: `tools/card_prune.py`, `tools/flash_headroom.sh`, `tools/flipper_cli.py`.
- Produces: the device on the current `screen-reader` commit, reporting itself clean and as Sonar.

- [ ] **Step 1: A clean release build**

```bash
cd Momentum-Firmware
git status --short
rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps
./fbt COMPACT=1 DEBUG=0 updater_package 2>&1 | tail -5
cd ..
tools/flash_headroom.sh
ls Momentum-Firmware/dist/f7-C/
```

Expected: an empty status (the tree is clean, so the build is not "dirty"); the build ends without a warning about the API table; the headroom line with a spare below 880,640; the dist folder holds `flipper-z-f7-update-mntm-screen-reader-<hash>.tgz` and the update folder with `resources.tar.gz` in it.

- [ ] **Step 2: Flash with the resources**

```bash
cd Momentum-Firmware && ./fbt COMPACT=1 DEBUG=0 flash_usb_full 2>&1 | tail -5; cd ..
```

This takes about six minutes; the serial port disappears during the update and returns after the reboot. Then, before any key press:

```bash
.venv/bin/python tools/flipper_cli.py "sr screen" "info device" "sr status"
```

Expected: the home screen, not a crash popup; `firmware.commit.hash` equal to the submodule's HEAD (first eight characters), `firmware.commit.dirty : false`, `firmware.origin.fork : Sonar`, `firmware.origin.git : https://github.com/robin24/Momentum-Firmware.git`, `firmware.api.major : 87` and `minor : 3`; `sr status` with `enabled: yes`, the voice on and the Samantha settings line.

- [ ] **Step 3: The card after the flash**

```bash
.venv/bin/python tools/flipper_cli.py "storage list /ext/apps/Media" "storage list /ext/apps/assets"
.venv/bin/python tools/card_prune.py
.venv/bin/python tools/flipper_cli.py "storage list /ext/update"
```

Expected: `text2sam.fap` present with a size different from the patched build's 30,200 bytes (the stock build was deployed); `passport.fap` present; the prune removes the previous build's folder, and the listing shows the two rollback packages and the new build's folder only.

- [ ] **Step 4: A short workout**

```bash
.venv/bin/python tools/sr_drive.py --chords
.venv/bin/python tools/flipper_cli.py "sr status" "free"
```

Expected: the chord session reports no failures; `sr status` shows no dropped frames and the free heap in the usual range (about 110 to 117 KB idle).

- [ ] **Step 5: Notes and measurements**

Write `docs/measurements/2026-09-26-plan-a.txt`: the headroom line, the `info device` block, the `sr status` block, the `storage list /ext/update` listing before and after the prune (the counts from Task 3 and this task), the free heap, and the time the flash took. Prose lines between the blocks, no tables.

Update `docs/device-notes.md`: the firmware line in "Device state" now says the device runs commit `<hash>` of 2026-09-26, flashed complete with `./fbt flash_usb_full`, reporting itself as Sonar and clean, with the image size and the spare; add the size to the history in "Useful commands". Update `docs/roadmap.md`'s status paragraph: plan A done, listing the tools by name.

- [ ] **Step 6: Commit and push**

```bash
tools/run_host_tests.sh
git add docs/measurements/2026-09-26-plan-a.txt docs/device-notes.md docs/roadmap.md
git commit -m "Plan A on the device: Sonar flashed clean, the card pruned, the notes and measurements

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- docs/measurements/2026-09-26-plan-a.txt docs/device-notes.md docs/roadmap.md
git push
git status --short
git -C Momentum-Firmware status --short
gh run list --limit 1
```

Expected: both trees clean, the push accepted, and the continuous build starting on the new commit.
