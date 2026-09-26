#!/usr/bin/env python3
"""Regenerate the built-in Sub-GHz app's source list after a Momentum merge.

    tools/subghz_manifest.py [--check] [--verify-upstream] [MANIFEST]

The fork builds Sub-GHz into the firmware (the stripdown spec of 2026-09-25). The firmware build
hands each sources entry to the compiler on its own, so the fap's "*.c" with "!" excludes cannot
be used, and the files are listed one by one in applications/main/subghz/application.fam.
Momentum adds and renames files there, so after a merge this script rewrites the App block with
appid "subghz". Its sources list becomes every .c file under the app's folder, in any subfolder,
except the EXCLUDED basenames, which are the fap's "!" entries in Momentum's manifest (the
plugins' files, the startup hook, the fap entry point and the Add Manually app's own files).
Order: top-level files first, then the subfolders, each sorted. Its apptype line becomes
apptype=FlipperAppType.APP, whatever the file named, since Momentum loads the app from the card
(MENUEXTERNAL). So taking upstream's file whole at a merge and running this script gives the
fork's manifest, comments aside. Only lines that start with "apptype=" or "sources=[", after
leading spaces, are taken, so a comment that mentions either is left alone. --check exits 1 if
the manifest would change. --verify-upstream compares EXCLUDED with the "!" entries of the merge
base's manifest and exits 1 on a difference, so a change in Momentum's list is noticed at the
merge; without upstream/dev in the firmware checkout it says so in one sentence and exits 1.
tests/fbt/test_subghz_manifest.py covers all of this.
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
# The App block with appid "subghz", up to the ")" that starts a line; inside it, the sources
# list and the apptype line, each only where it starts a line, so a comment cannot match.
BLOCK = re.compile(r'^App\(\s*\n\s*appid="subghz",.*?^\)', re.S | re.M)
SOURCES = re.compile(r'^([ \t]*sources=\[)(.*?)(\n[ \t]*\],)', re.S | re.M)
APPTYPE = re.compile(r'^([ \t]*)apptype=FlipperAppType\.\w+,', re.M)


def sources(app_dir, excluded=EXCLUDED):
    found = []
    for folder, _sub, files in os.walk(app_dir):
        for name in files:
            if name.endswith(".c") and name not in excluded:
                rel = os.path.relpath(os.path.join(folder, name), app_dir)
                found.append(rel.replace(os.sep, "/"))
    return sorted(found, key=lambda p: (p.count("/"), p))


def parts(text, what):
    """The subghz block's match in text and its sources list's match inside the block."""
    block = BLOCK.search(text)
    if not block:
        sys.exit(f'{what}: no App block with appid="subghz"')
    listed = SOURCES.search(block.group(0))
    if not listed:
        sys.exit(f'{what}: the App block with appid="subghz" has no sources list')
    return block, listed


def rewrite(text, files):
    """The manifest with the subghz block's sources list set to files and its apptype to APP;
    everything else, the block's other lines and comments included, is left as it is."""
    block, listed = parts(text, "the manifest")
    body = block.group(0)
    body = body[: listed.start(2)] + "".join(f'\n        "{path}",' for path in files) + body[listed.end(2) :]
    body, count = APPTYPE.subn(r"\1apptype=FlipperAppType.APP,", body)
    if count != 1:
        sys.exit(f'the manifest: the App block with appid="subghz" has {count} apptype lines, not one')
    return text[: block.start()] + body + text[block.end() :]


def git(*args):
    """A git command's output in the firmware checkout. git's own error lines are not shown: the
    callers say in one sentence what failed."""
    return subprocess.check_output(["git", "-C", FIRMWARE, *args], text=True, stderr=subprocess.DEVNULL)


def upstream_excludes(manifest_path):
    """The "!" entries of the merge base's manifest (upstream's version of the file). Exits with
    one sentence when the firmware checkout has no upstream/dev or the base has no such file."""
    try:
        base = git("merge-base", "upstream/dev", "HEAD").strip()
    except (subprocess.CalledProcessError, OSError):
        sys.exit("no merge base with upstream/dev in the firmware checkout: fetch the upstream remote, then run --verify-upstream again")
    rel = os.path.relpath(manifest_path, FIRMWARE).replace(os.sep, "/")
    try:
        text = git("show", f"{base}:{rel}")
    except (subprocess.CalledProcessError, OSError):
        sys.exit(f"the merge base {base[:9]} has no {rel} to compare with")
    _block, listed = parts(text, "the merge base's manifest")
    return tuple(re.findall(r'"!([\w./-]+)"', listed.group(2)))


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
