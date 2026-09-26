#!/usr/bin/env python3
"""tools/card_prune.py's rule: of the folders under /ext/update, only the fork's own builds are
candidates, the folders named f7-update-sonar-, f7-update-mntm-screen-reader- or
f7-update-mntm-HEAD- plus anything; every other folder stays, a foreign package such as
f7-update-1.4.3, f7-update-mntm-012 or an Unleashed one included. Of the candidates, the running
build's folder stays: its name ends with "-" and the firmware.commit.hash from `info device`, or,
for a tagged build whose firmware.version is not mntm-dev, it is f7-update-<firmware.version>.
The names given with --keep stay too, and the rest goes, sorted. Run from the project root:
python3 tests/fbt/test_card_prune.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from card_prune import plan  # noqa: E402

failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


FOREIGN = ["f7-update-1.4.3", "f7-update-mntm-012", "f7-update-1.5.0", "f7-update-unlshd-080e", "other"]
FOLDERS = [
    "f7-update-mntm-screen-reader-a9e4e7b9",
    "f7-update-1.4.3",
    "other",
    "f7-update-sonar-ci-1234abcd",
    "f7-update-mntm-screen-reader-6451e86e",
    "f7-update-mntm-012",
]

check(
    plan(FOLDERS, "6451e86e", "mntm-dev", set()) == ["f7-update-mntm-screen-reader-a9e4e7b9", "f7-update-sonar-ci-1234abcd"],
    "the running build and the foreign folders stay; the fork's other builds go, sorted",
)
check(
    plan(FOLDERS, "a9e4e7b9", "mntm-dev", set()) == ["f7-update-mntm-screen-reader-6451e86e", "f7-update-sonar-ci-1234abcd"],
    "another running build",
)
check(
    plan(FOLDERS, "", "", set())
    == ["f7-update-mntm-screen-reader-6451e86e", "f7-update-mntm-screen-reader-a9e4e7b9", "f7-update-sonar-ci-1234abcd"],
    "no hash and no version means no folder is the running build",
)
check(plan(FOLDERS, "6451e86e", "mntm-dev", {"f7-update-sonar-ci-1234abcd"}) == ["f7-update-mntm-screen-reader-a9e4e7b9"],
      "--keep adds a name")
check(plan([], "6451e86e", "mntm-dev", set()) == [], "an empty folder list")
check(plan(FOREIGN, "", "", set()) == [], "a foreign package or a folder that is not a package is never a candidate")
check(plan(FOREIGN, "080e", "unlshd-080e", set()) == [], "a foreign package stays whatever the device runs")
check(plan(["f7-update-sonar-x-6451E86E"], "6451e86e", "mntm-dev", set()) == ["f7-update-sonar-x-6451E86E"],
      "the hash comparison is exact and lower case")
tagged = ["f7-update-sonar-0.0.9", "f7-update-sonar-0.1.0", "f7-update-sonar-ci-b1c2d3e4", "f7-update-mntm-screen-reader-6451e86e"]
check(plan(tagged, "b1c2d3e4", "sonar-0.1.0", set()) == ["f7-update-mntm-screen-reader-6451e86e", "f7-update-sonar-0.0.9"],
      "a tagged running build is recognised by its version: f7-update-sonar-0.1.0 stays, f7-update-sonar-0.0.9 goes, "
      "and the same commit's build named by its hash stays too")
check(plan(tagged, "6451e86e", "mntm-dev", set()) == ["f7-update-sonar-0.0.9", "f7-update-sonar-0.1.0", "f7-update-sonar-ci-b1c2d3e4"],
      "with a development build running, the tagged builds go")
head = ["f7-update-mntm-HEAD-a5c2ed7d", "f7-update-mntm-HEAD-3bdcca70"]
check(plan(head, "a5c2ed7d", "mntm-dev", set()) == ["f7-update-mntm-HEAD-3bdcca70"],
      "a source build on a detached HEAD is the fork's own: the running one stays, the other goes")

print(f"card prune: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
