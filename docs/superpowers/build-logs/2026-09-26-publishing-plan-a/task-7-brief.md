### Task 7: `tools/subghz_manifest.py` and its test

**Files:**
- Create: `tools/subghz_manifest.py`, `tests/fbt/test_subghz_manifest.py`
- Modify: `tools/run_host_tests.sh`, `Momentum-Firmware/applications/main/subghz/application.fam` (regenerated once)

**Interfaces:**
- Produces: `subghz_manifest.sources(app_dir) -> list`, `subghz_manifest.rewrite(text, files) -> text`, `subghz_manifest.EXCLUDED`, and the command `tools/subghz_manifest.py [--check] [--verify-upstream] [MANIFEST]`.

- [ ] **Step 1: Write the failing test**

Create `tests/fbt/test_subghz_manifest.py`:

```python
#!/usr/bin/env python3
"""tools/subghz_manifest.py: the built-in Sub-GHz app's source list is every .c file under the
app's folder except the excluded basenames, top-level files first and then the subfolders, each
sorted; only the App block with appid "subghz" changes; the script is idempotent; the fork's
manifest is what the script writes; and the excluded names are the "!" entries of the merge
base's manifest. Run from the project root: python3 tests/fbt/test_subghz_manifest.py"""
import os
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


SAMPLE = '''App(
    appid="subghz",
    name="Sub-GHz",
    # a comment that mentions sources
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
    check('sources=["subghz_cli.c", "helpers/subghz_chat.c"]' in out, "the other App block is untouched")
    check("# a comment that mentions sources" in out and 'requires=["region"]' in out, "the rest of the block is untouched")
    check(rewrite(out, files) == out, "idempotent")

current = open(MANIFEST, encoding="utf-8").read()
app_dir = os.path.dirname(MANIFEST)
check(rewrite(current, sources(app_dir)) == current, "the fork's manifest is what the script writes (run the script once if not)")

try:
    theirs = upstream_excludes(MANIFEST)
except subprocess.CalledProcessError:
    print("skipped the upstream check: no upstream/dev in this checkout")
else:
    check(set(theirs) == set(EXCLUDED), f"EXCLUDED equals the merge base's \"!\" entries; theirs: {sorted(set(theirs) ^ set(EXCLUDED))}")

print(f"subghz manifest: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
```

- [ ] **Step 2: Run it to see it fail**

```bash
python3 tests/fbt/test_subghz_manifest.py
```

Expected: `ModuleNotFoundError: No module named 'subghz_manifest'`.

- [ ] **Step 3: Write the script**

Create `tools/subghz_manifest.py`:

```python
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
```

- [ ] **Step 4: Run the test, regenerate the manifest once**

```bash
python3 tests/fbt/test_subghz_manifest.py
```

Expected: every check passes except "the fork's manifest is what the script writes" (7 of 8 with the upstream check, the summary line counts what ran), because the hand-written list has `subghz_i.c` before `subghz_history.c`. Then:

```bash
python3 tools/subghz_manifest.py --verify-upstream
git -C Momentum-Firmware diff --stat
python3 tests/fbt/test_subghz_manifest.py
python3 tests/fbt/test_subghz_sources.py
```

Expected: the exclude list matches, the manifest is rewritten (a reorder of the same 36 files, no file added or removed: check the diff shows only moved lines), `subghz manifest: 8 of 8 checks passed` (7 of 7 where `upstream/dev` is absent), and the existing source-list check still passes.

- [ ] **Step 5: Runner, commits, pushes**

Append the runner block for `test_subghz_manifest.py` (output `subghz_manifest.txt`, message `Sub-GHz manifest checks failed`), then:

```bash
tools/run_host_tests.sh
cd Momentum-Firmware
git commit -m "subghz: the built-in app's source list in the order tools/subghz_manifest.py writes it

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- applications/main/subghz/application.fam
git push origin screen-reader
cd ..
git add tools/subghz_manifest.py tests/fbt/test_subghz_manifest.py tools/run_host_tests.sh Momentum-Firmware
git commit -m "subghz_manifest: the built-in Sub-GHz source list is regenerated after a Momentum merge

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- tools/subghz_manifest.py tests/fbt/test_subghz_manifest.py tools/run_host_tests.sh Momentum-Firmware
git push
```

---

