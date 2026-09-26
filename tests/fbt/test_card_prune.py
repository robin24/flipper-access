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
