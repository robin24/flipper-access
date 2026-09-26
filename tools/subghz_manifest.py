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
