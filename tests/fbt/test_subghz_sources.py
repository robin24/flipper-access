#!/usr/bin/env python3
"""The built-in Sub-GHz app's source list. applications/main/subghz/application.fam names its
files one by one, because the firmware build cannot take "*.c" with "!" excludes, so a Momentum
merge that adds a scene could leave it out of the build without a word. Every .c file under
applications/main/subghz, in any subfolder, must be quoted somewhere in that manifest, and every
quoted .c must exist. A file quoted only in a commented-out App block counts as quoted: that is
how Momentum names subghz_fap.c, the fap's entry point. Only quoted file paths count, so a glob
such as "*.c", which the manifest's own comment quotes, is not taken for a file. Run from the
project root: python3 tests/fbt/test_subghz_sources.py"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.join(ROOT, "Momentum-Firmware", "applications", "main", "subghz")

on_disk = set()
for folder, _subfolders, files in os.walk(APP):
    for name in files:
        if name.endswith(".c"):
            path = os.path.relpath(os.path.join(folder, name), APP)
            on_disk.add(path.replace(os.sep, "/"))

with open(os.path.join(APP, "application.fam"), encoding="utf-8") as manifest:
    quoted = set(re.findall(r"[\"']([\w./-]+\.c)[\"']", manifest.read()))

unquoted = sorted(on_disk - quoted)
missing = sorted(quoted - on_disk)
for path in unquoted:
    print(f"on disk, not quoted in application.fam: {path}")
for path in missing:
    print(f"quoted in application.fam, not on disk: {path}")
print(
    f"subghz sources: {len(on_disk)} on disk, {len(quoted)} quoted, "
    f"{len(unquoted)} unquoted, {len(missing)} missing"
)
sys.exit(1 if unquoted or missing else 0)
