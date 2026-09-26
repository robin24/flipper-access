#!/usr/bin/env python3
"""tools/subghz_manifest.py: the built-in Sub-GHz app's source list is every .c file under the
app's folder except the excluded basenames, top-level files first and then the subfolders, each
sorted; the subghz block's apptype becomes APP whatever upstream's file names, so the app is
built in and not loaded from the card; only the App block with appid "subghz" changes, and a
comment in it that mentions "sources=[" is left alone; the script is idempotent; the fork's
manifest is what the script writes, with apptype APP; the golden check: the merge base's manifest
(upstream's) through the script is the fork's file, comment lines aside; the excluded names are
the "!" entries of the merge base's manifest; and --verify-upstream in a checkout without
upstream/dev ends with one sentence and exit 1, not a traceback. The checks against the merge
base are skipped without upstream/dev (CI). Run from the project root:
python3 tests/fbt/test_subghz_manifest.py"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from subghz_manifest import EXCLUDED, rewrite, sources, upstream_excludes  # noqa: E402

FIRMWARE = os.path.join(ROOT, "Momentum-Firmware")
MANIFEST = os.path.join(FIRMWARE, "applications", "main", "subghz", "application.fam")
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def git(*args):
    return subprocess.run(["git", "-C", FIRMWARE, *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)


def subghz_block(text):
    """The App block with appid "subghz", from "App(" to its closing parenthesis."""
    m = re.search(r'^App\(\s*\n\s*appid="subghz",\n.*?^\)', text, re.S | re.M)
    return m.group(0) if m else ""


def without_comments(text):
    return [line for line in text.splitlines() if not line.strip().startswith("#")]


SAMPLE = '''App(
    appid="subghz",
    name="Sub-GHz",
    apptype=FlipperAppType.MENUEXTERNAL,
    # a comment that mentions sources=[ before the list
    sources=[
        "old.c",
    ],
    requires=["region"],
)

App(
    appid="cli_subghz",
    apptype=FlipperAppType.PLUGIN,
    sources=["subghz_cli.c", "helpers/subghz_chat.c"],
)
'''

with tempfile.TemporaryDirectory() as tmp:
    for rel in ["subghz.c", "subghz_i.c", "subghz_cli.c", "helpers/subghz_txrx.c", "helpers/minmea.c",
                "scenes/subghz_scene_set_key.c", "views/receiver.c", "helpers/notes.txt"]:
        path = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
    files = sources(tmp)
    check(files == ["subghz.c", "subghz_i.c", "helpers/subghz_txrx.c", "views/receiver.c"],
          f"the list: top-level first, then subfolders, excluded names out: {files}")
    out = rewrite(SAMPLE, files)
    check('        "subghz.c",\n        "subghz_i.c",\n        "helpers/subghz_txrx.c",\n        "views/receiver.c",\n    ],' in out,
          "the list is written with eight spaces and trailing commas")
    check('"old.c"' not in out, "the old list is gone")
    check("    apptype=FlipperAppType.APP,\n" in subghz_block(out) and "MENUEXTERNAL" not in out,
          "the subghz block's apptype becomes APP")
    check('    apptype=FlipperAppType.PLUGIN,\n    sources=["subghz_cli.c", "helpers/subghz_chat.c"],' in out,
          "the other App block is untouched")
    check("    # a comment that mentions sources=[ before the list\n    sources=[\n" in out and 'requires=["region"]' in out,
          "the rest of the block is untouched, the comment that mentions sources=[ included")
    check(rewrite(out, files) == out, "idempotent")

current = open(MANIFEST, encoding="utf-8").read()
app_dir = os.path.dirname(MANIFEST)
check(rewrite(current, sources(app_dir)) == current, "the fork's manifest is what the script writes (run the script once if not)")
check("\n    apptype=FlipperAppType.APP,\n" in subghz_block(current), "the fork's subghz block has apptype APP: built in, not loaded from the card")

with tempfile.TemporaryDirectory() as tmp:
    # A copy of the script beside a firmware checkout that has no upstream/dev.
    os.makedirs(os.path.join(tmp, "tools"))
    script = shutil.copy(os.path.join(ROOT, "tools", "subghz_manifest.py"), os.path.join(tmp, "tools"))
    subprocess.run(["git", "init", "-q", os.path.join(tmp, "Momentum-Firmware")], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p = subprocess.run([sys.executable, script, "--verify-upstream", "--check", MANIFEST], capture_output=True, text=True)
    said = p.stderr.strip()
    check(p.returncode == 1 and len(said.splitlines()) == 1 and "Traceback" not in said and "upstream/dev" in said,
          f"--verify-upstream without upstream/dev: one sentence and exit 1, got exit {p.returncode}:\n{said}")

base = git("merge-base", "upstream/dev", "HEAD")
if base.returncode != 0:
    print("skipped the golden check and the exclude list check: no upstream/dev in this checkout")
else:
    rel = os.path.relpath(MANIFEST, FIRMWARE).replace(os.sep, "/")
    upstream = git("show", f"{base.stdout.strip()}:{rel}").stdout
    golden = rewrite(upstream, sources(app_dir))
    if without_comments(golden) != without_comments(current):
        import difflib

        for line in list(difflib.unified_diff(without_comments(golden), without_comments(current), "script", "fork", lineterm=""))[:20]:
            print(line)
    check(without_comments(golden) == without_comments(current),
          "golden: the merge base's manifest through the script is the fork's file, comment lines aside")
    theirs = upstream_excludes(MANIFEST)
    check(set(theirs) == set(EXCLUDED), f"EXCLUDED equals the merge base's \"!\" entries; theirs: {sorted(set(theirs) ^ set(EXCLUDED))}")

print(f"subghz manifest: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
