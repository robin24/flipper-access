#!/usr/bin/env python3
"""The first boot after an install, in the firmware's sources. Momentum shows a tutorial of seven
pictures at the first boot, from a firstboot.bin the update package carries, and again from the
Momentum app's Misc screen, row Show Momentum Intro, which copies /ext/dolphin/firstboot.bin into
place. The pictures hold their words as pixels and wait for given arrow keys, so the screen reader
reads nothing and calls the screen the home screen. Sonar leaves the tutorial out: scripts/update.py
makes neither firstboot.bin, and the row is gone. Without the package's file the updater shows the
update picture instead, the one every later update shows. These checks keep a merge from Momentum
from bringing the tutorial back. Run from the project root: python3 tests/fbt/test_first_boot.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIRMWARE = os.path.join(ROOT, "Momentum-Firmware")
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def read(path):
    with open(os.path.join(FIRMWARE, path)) as f:
        return f.read()


# The script's code, without its comments, which may name what it leaves out
update = "\n".join(line.split("#", 1)[0] for line in read("scripts/update.py").splitlines())
check("firstboot.bin" not in update, "scripts/update.py makes no firstboot.bin, in the package or the resources")
check("slideshow/firstboot" not in update, "scripts/update.py reads no tutorial pictures")
check("SPLASH_BIN_NAME" in update, "it still makes the update picture, splash.bin")

misc = read("applications/main/momentum_app/scenes/momentum_app_scene_misc.c")
check("Show Momentum Intro" not in misc, "the Momentum app's Misc screen has no Show Momentum Intro row")
check("dolphin/firstboot.bin" not in misc, "and copies no tutorial into place")

worker = read("applications/system/updater/util/update_task_worker_backup.c")
check('"firstboot.bin"' in worker and "splash_file" in worker,
      "the updater, unchanged, falls back to the update picture when the package has no firstboot.bin")

print(f"first boot: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
