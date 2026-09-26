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
