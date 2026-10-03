#!/usr/bin/env python3
"""Remove the fork's old update packages from the Flipper's card.

    tools/card_prune.py [--dry] [--keep NAME ...] [--port PORT]

Every `./fbt flash_usb` and `flash_usb_full` leaves its package in /ext/update/<name>/, with
the updater's own backup.tar of internal storage inside, and nothing removes them. The rule:
only the fork's own builds are candidates, the folders whose names start with OWN_PREFIXES
(f7-update-sonar- for releases and continuous builds, f7-update-mntm-screen-reader- for builds
on the branch, f7-update-mntm-HEAD- for builds on a detached HEAD, which a fresh clone gives,
f7-update-mntm-claude- for builds on the claude/ work branches).
Every other folder stays: a package of another firmware, such as f7-update-1.4.3,
f7-update-mntm-012 or an Unleashed one, may be someone's way back, and is never touched. Of the
candidates, the running build's folder stays: its name ends with "-" and the
firmware.commit.hash that `info device` reports, or, when `info device` reports a
firmware.version other than mntm-dev (a tagged release), it is f7-update-<firmware.version>.
The folders named with --keep stay too, and every other candidate goes. `storage list` gives no
dates, so "the running build" is the rule, not "the newest". --dry prints the plan and removes
nothing. Run from the project root with the venv Python (pyserial):
.venv/bin/python tools/card_prune.py --dry
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    from flipper_cli import find_port, open_cli, run
except (SystemExit, ImportError):  # flipper_cli exits without pyserial; plan() needs neither (the tests, CI)
    find_port = open_cli = run = None

UPDATE_DIR = "/ext/update"
OWN_PREFIXES = ("f7-update-sonar-", "f7-update-mntm-screen-reader-", "f7-update-mntm-HEAD-", "f7-update-mntm-claude-")
DEV_VERSION = "mntm-dev"  # the firmware.version of every build that is not on a tag


def plan(folders, running_hash, running_version, keep):
    """The folder names to remove, sorted: the fork's own builds (names that start with one of
    OWN_PREFIXES) except those in keep and the running build's. The running build's name ends
    with "-" plus its hash (eight hex digits, lower case) or, for a version other than
    DEV_VERSION, is f7-update-<version>."""
    running = {f"f7-update-{running_version}"} if running_version and running_version != DEV_VERSION else set()
    remove = []
    for name in sorted(folders):
        if not name.startswith(OWN_PREFIXES):
            continue
        if name in keep or name in running:
            continue
        if running_hash and name.endswith("-" + running_hash):
            continue
        remove.append(name)
    return remove


def running_build(ser):
    """firmware.commit.hash (lower case) and firmware.version from `info device`; "" if absent."""
    found = {}
    for line in run(ser, "info device").splitlines():
        key, _, value = line.partition(":")
        found[key.strip()] = value.strip()
    return found.get("firmware.commit.hash", "").lower(), found.get("firmware.version", "")


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
    if run is None:
        sys.exit("pyserial is missing. Run: .venv/bin/pip install pyserial  (or use .venv/bin/python)")
    ser = open_cli(find_port(args.port))
    try:
        current, version = running_build(ser)
        if not current:
            sys.exit("could not read firmware.commit.hash from info device")
        folders, _files = list_dir(ser, UPDATE_DIR)
        remove = plan(folders, current, version, set(args.keep))
        kept = sorted(set(folders) - set(remove))
        print(f"running build {current}, version {version}; {len(folders)} folders in {UPDATE_DIR}; keeping {len(kept)}: {', '.join(kept)}")
        for name in remove:
            print(("would remove " if args.dry else "removing ") + name)
            remove_tree(ser, f"{UPDATE_DIR}/{name}", args.dry)
        print(f"{'would remove' if args.dry else 'removed'} {len(remove)} folders")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
