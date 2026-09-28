#!/usr/bin/env python3
"""tools/flash_headroom.sh over synthetic builds: the limit is the radio address in the update
package's update.fuf less the flash base, so another radio stack moves it; an image of exactly the
limit fits and one byte more does not; the package is DIST_SUFFIX's when that is set, else the
newest, else the one named on the command line; and a missing image, package or radio address
ends with one sentence and exit 1. Run from the project root:
python3 tests/fbt/test_flash_headroom.py"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def package(root, suffix, radio="00 70 0D 08", age=0):
    """An update package folder with an update.fuf naming the radio address, age seconds old."""
    folder = os.path.join(root, "Momentum-Firmware", "dist", "f7-C", f"f7-update-{suffix}")
    os.makedirs(folder)
    lines = ["Filetype: Flipper firmware upgrade configuration", "Version: 2", f"Info: {suffix}", "Radio: radio.bin"]
    if radio is not None:
        lines.append(f"Radio address: {radio}")
    with open(os.path.join(folder, "update.fuf"), "w") as f:
        f.write("\n".join(lines) + "\n")
    stamp = 1_700_000_000 - age
    os.utime(folder, (stamp, stamp))
    return folder


def image(root, size):
    path = os.path.join(root, "Momentum-Firmware", "build", "f7-firmware-C", "firmware.bin")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(size)
    return path


def run(root, *args, suffix=None):
    env = {k: v for k, v in os.environ.items() if k != "DIST_SUFFIX"}
    if suffix is not None:
        env["DIST_SUFFIX"] = suffix
    p = subprocess.run(["bash", os.path.join(root, "tools", "flash_headroom.sh"), *args], capture_output=True, text=True, env=env)
    return p.returncode, (p.stdout + p.stderr).strip()


def tree(tmp, name):
    """A project folder with a copy of the script."""
    root = os.path.join(tmp, name)
    os.makedirs(os.path.join(root, "tools"))
    shutil.copy(os.path.join(ROOT, "tools", "flash_headroom.sh"), os.path.join(root, "tools"))
    return root


with tempfile.TemporaryDirectory() as tmp:
    root = tree(tmp, "one")
    package(root, "sonar-local")
    image(root, 869_080)
    code, out = run(root)
    check(code == 0 and "limit 880640" in out and "0x080D7000" in out and "spare 11560 bytes" in out,
          f"ble_light 1.20.0: 880,640 bytes, 11,560 spare: {code} {out}")
    image(root, 880_640)
    code, out = run(root)
    check(code == 0 and "spare 0 bytes" in out, f"an image of exactly the limit fits: {code} {out}")
    image(root, 880_641)
    code, out = run(root)
    check(code == 1 and "too large by 1 bytes" in out, f"one byte more does not: {code} {out}")

    root = tree(tmp, "stacks")
    image(root, 869_080)
    package(root, "old", radio="00 70 0D 08", age=100)
    package(root, "new", radio="00 60 0C 08", age=10)
    code, out = run(root)
    check(code == 1 and "limit 811008" in out and "0x080C6000" in out and "too large by 58072 bytes" in out,
          f"without DIST_SUFFIX the newest package, whose stack starts lower, so the image no longer fits: {code} {out}")
    code, out = run(root, suffix="old")
    check(code == 0 and "limit 880640" in out, f"DIST_SUFFIX names the package: {code} {out}")
    folder = os.path.join(root, "Momentum-Firmware", "dist", "f7-C", "f7-update-old")
    code, out = run(root, os.path.join(root, "Momentum-Firmware", "build", "f7-firmware-C", "firmware.bin"), folder, suffix="new")
    check(code == 0 and "limit 880640" in out, f"a package named on the command line wins: {code} {out}")
    code, out = run(root, os.path.join(root, "nothing.bin"))
    check(code == 1 and out.startswith("no firmware image") and len(out.splitlines()) == 1, f"no image: {code} {out}")
    code, out = run(root, suffix="missing")
    check(code == 1 and "updater_package" in out and len(out.splitlines()) == 1, f"DIST_SUFFIX's package missing: {code} {out}")

    root = tree(tmp, "empty")
    image(root, 869_080)
    code, out = run(root)
    check(code == 1 and "updater_package" in out and len(out.splitlines()) == 1, f"no package at all: {code} {out}")
    package(root, "noradio", radio=None)
    code, out = run(root)
    check(code == 1 and out.startswith("no radio address") and len(out.splitlines()) == 1, f"no radio address line: {code} {out}")

    root = tree(tmp, "zero")
    image(root, 869_080)
    package(root, "zero", radio="00 00 00 00")
    code, out = run(root)
    check(code == 1 and out.startswith("no radio address"), f"a package without a radio stack, address 0: {code} {out}")

print(f"flash headroom: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
