### Task 3: `tools/card_prune.py`, its test, and the card cleanup

**Files:**
- Create: `tools/card_prune.py`, `tests/fbt/test_card_prune.py`
- Modify: `tools/run_host_tests.sh` (append the test)

**Interfaces:**
- Consumes: `tools/flipper_cli.py`: `find_port(explicit=None)`, `open_cli(port)` returning a pyserial handle, `run(ser, cmd, timeout=15.0)` returning the reply text without echo, prompt or colour codes.
- Produces: `card_prune.plan(folders, running_hash, keep)`, a pure function returning the sorted list of folder names to remove; the command `tools/card_prune.py [--dry] [--keep NAME ...] [--port PORT]`, which Task 10 runs after the flash. The module must import without pyserial (the test runs on the continuous build too), which is why the `flipper_cli` import is guarded.

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
try:
    from flipper_cli import find_port, open_cli, run
except SystemExit:  # flipper_cli exits when pyserial is missing; plan() needs neither (the tests, CI)
    find_port = open_cli = run = None

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

