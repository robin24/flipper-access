### Task 6: `tools/strip_js_symbols.py` and its test

**Files:**
- Create: `tools/strip_js_symbols.py`, `tests/fbt/test_strip_js_symbols.py`
- Modify: `tools/run_host_tests.sh`

**Interfaces:**
- Produces: `strip_js_symbols.strip(text) -> (new_text, changed)` and the command `tools/strip_js_symbols.py [--check] [PATH]`; after a Momentum merge the resolution of `targets/f7/api_symbols.csv` is "take upstream's file, run the script".

- [ ] **Step 1: Write the failing test**

Create `tests/fbt/test_strip_js_symbols.py`:

```python
#!/usr/bin/env python3
"""tools/strip_js_symbols.py: the JavaScript engine's lines leave targets/f7/api_symbols.csv,
the fork's exported lines are present at their sorted place, the version is upstream's with the
minor raised by one, and the script is idempotent. The golden check: the merge base's file
(upstream's) becomes the fork's file exactly. Run from the project root:
python3 tests/fbt/test_strip_js_symbols.py"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from strip_js_symbols import OUR_LINES, strip  # noqa: E402

FIRMWARE = os.path.join(ROOT, "Momentum-Firmware")
CSV = os.path.join(FIRMWARE, "targets", "f7", "api_symbols.csv")
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def git(*args):
    return subprocess.run(["git", "-C", FIRMWARE, *args], capture_output=True, text=True)


SYNTHETIC = """entry,status,name,type,params
Version,+,90.4,,
Header,+,applications/services/gui/canvas.h,,
Header,+,lib/mjs/mjs_core_public.h,,
Function,+,canvas_clear,void,Canvas*
Function,+,mjs_get_int,int,"struct mjs*, mjs_val_t"
Function,+,zz_last,void,void
Variable,+,mjs_something,int,
Variable,+,zz_var,int,
"""

out, changed = strip(SYNTHETIC)
lines = out.split("\n")
check(changed, "a synthetic upstream file changes")
check("Version,+,90.5,," in lines, "the minor version is raised by one")
check(not any("mjs" in line for line in lines), "every JavaScript line is gone")
for ours in OUR_LINES:
    check(ours in lines, f"our line is present: {ours[:40]}")
functions = [line.split(",")[2] for line in lines if line.startswith("Function,")]
check(functions == sorted(functions), "functions stay sorted by name")
check(functions[0] == "button_panel_item_set_name" and functions[-1] == "zz_last", "our lines sit at their sorted place")
check(out.endswith("\n") and not out.endswith("\n\n"), "one trailing newline")
again, changed_again = strip(out)
check(again == out and not changed_again, "idempotent: a second run changes nothing")

current = open(CSV, encoding="utf-8").read()
same, changed_current = strip(current)
check(same == current and not changed_current, "the fork's own file is left as it is")

base = git("merge-base", "upstream/dev", "HEAD")
if base.returncode != 0:
    print("skipped the golden check: no upstream/dev in this checkout")
else:
    upstream = git("show", f"{base.stdout.strip()}:targets/f7/api_symbols.csv").stdout
    golden, _ = strip(upstream)
    if golden != current:
        import difflib

        for line in list(difflib.unified_diff(golden.splitlines(), current.splitlines(), "script", "fork", lineterm=""))[:20]:
            print(line)
    check(golden == current, "golden: the merge base's file becomes the fork's file exactly")

print(f"strip js symbols: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
```

- [ ] **Step 2: Run it to see it fail**

```bash
python3 tests/fbt/test_strip_js_symbols.py
```

Expected: `ModuleNotFoundError: No module named 'strip_js_symbols'`.

- [ ] **Step 3: Write the script**

Create `tools/strip_js_symbols.py`:

```python
#!/usr/bin/env python3
"""Re-apply the fork's changes to targets/f7/api_symbols.csv after a Momentum merge.

    tools/strip_js_symbols.py [--check] [PATH]

The fork leaves the JavaScript engine out of the build (fbt_options.py, lib/SConscript), so its
API lines must leave the table too: every Header under lib/mjs/ and every Function or Variable
whose name starts with mjs_. The fork also exports the screen reader's calls (OUR_LINES), and its
API version is upstream's major and minor with the minor raised by one, for as long as those
exports exist. So a merge takes upstream's file whole and runs this script on it. The script is
idempotent: on a file it already produced it changes nothing, and the version is raised only when
a JavaScript line was removed or one of our lines was missing. Rows keep fbt's order: the
sections Version, Header, Function, Variable, each sorted by name, so our lines are inserted at
their sorted place. --check exits 1 if the file would change. PATH defaults to the submodule's
targets/f7/api_symbols.csv. tests/fbt/test_strip_js_symbols.py checks all of this, and that the
merge base's file becomes the fork's file exactly.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = os.path.join(ROOT, "Momentum-Firmware", "targets", "f7", "api_symbols.csv")
SECTIONS = ("Version", "Header", "Function", "Variable")
OUR_LINES = (
    'Function,+,button_panel_item_set_name,void,"ButtonPanel*, uint32_t, const char*"',
    'Function,+,canvas_tap_hint_note,void,"Canvas*, const char*, _Bool"',
    'Function,+,canvas_tap_hint_note_at,void,"Canvas*, uint8_t, uint8_t, const char*"',
    'Function,+,input_publish_event,void,"FuriPubSub*, InputEvent*"',
    'Function,-,input_set_filter,void,"InputFilterCallback, void*"',
)


def fields(row):
    """entry, status, name, type, params; the params may hold commas inside quotes."""
    return row.split(",", 4)


def is_js(row):
    kind, _status, name = fields(row)[:3]
    if kind == "Header":
        return name.startswith("lib/mjs/")
    return kind in ("Function", "Variable") and name.startswith("mjs_")


def sort_key(row):
    kind, _status, name = fields(row)[:3]
    return (SECTIONS.index(kind), name)


def strip(text):
    """The file's text after the fork's changes, and whether it changed."""
    lines = text.rstrip("\n").split("\n")
    header, rows = lines[0], lines[1:]
    kept = [row for row in rows if not is_js(row)]
    changed = len(kept) != len(rows)
    present = {fields(row)[2] for row in kept}
    for ours in OUR_LINES:
        if fields(ours)[2] not in present:
            kept.append(ours)
            changed = True
    kept.sort(key=sort_key)
    if changed:
        for i, row in enumerate(kept):
            parts = fields(row)
            if parts[0] == "Version":
                major, minor = parts[2].split(".")
                parts[2] = f"{major}.{int(minor) + 1}"
                kept[i] = ",".join(parts)
    return "\n".join([header, *kept]) + "\n", changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if the file would change, write nothing")
    ap.add_argument("path", nargs="?", default=DEFAULT)
    args = ap.parse_args()
    with open(args.path, encoding="utf-8") as f:
        text = f.read()
    out, changed = strip(text)
    if not changed:
        print(f"{args.path}: unchanged")
        return
    if args.check:
        sys.exit(f"{args.path}: would change; run without --check")
    with open(args.path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"{args.path}: updated, {len(text.splitlines()) - len(out.splitlines())} lines fewer, version {fields(out.splitlines()[1])[2]}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test**

```bash
python3 tests/fbt/test_strip_js_symbols.py
```

Expected: `strip js symbols: 14 of 14 checks passed` (13 of 13 where `upstream/dev` is absent, since the golden check is skipped there). If only the golden check fails, the sort order fbt uses differs from a plain name sort: read how `scripts/fbt/sdk.py` orders its entries (the `ApiEntries` dataclasses and where the CSV is written), match it in `sort_key`, and record what it was in the report. If the fork's own file fails "left as it is", the same applies.

- [ ] **Step 5: The command line, the runner, the commit**

```bash
python3 tools/strip_js_symbols.py --check
```

Expected: `... api_symbols.csv: unchanged`.

Append to `tools/run_host_tests.sh` the same block shape as for card prune, for `test_strip_js_symbols.py` with the output file `strip_js_symbols.txt` and the message `strip js symbols checks failed`. Run the runner: green.

```bash
git add tools/strip_js_symbols.py tests/fbt/test_strip_js_symbols.py tools/run_host_tests.sh
git commit -m "strip_js_symbols: the symbol table after a Momentum merge is upstream's file plus this script

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- tools/strip_js_symbols.py tests/fbt/test_strip_js_symbols.py tools/run_host_tests.sh
git push
```

---

