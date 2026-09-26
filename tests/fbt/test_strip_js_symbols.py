#!/usr/bin/env python3
"""tools/strip_js_symbols.py: the JavaScript engine's lines leave targets/f7/api_symbols.csv,
the fork's exported lines are present at their sorted place, a row of another kind that shares
one of their names does not stand in for them, the version is upstream's with the minor raised by
FORK_MINOR_STEP (2, one per API round the fork has exported symbols in so far: 90.4 becomes
90.6), and the script is idempotent. The golden check: the merge base's file (upstream's) becomes
the fork's file exactly; it is skipped without upstream/dev (CI). Run from the project root:
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
    return subprocess.run(["git", "-C", FIRMWARE, *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)


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
check("Version,+,90.6,," in lines, "the minor version is raised by the fork's step of two, not by one")
check(not any("mjs" in line for line in lines), "every JavaScript line is gone")
for ours in OUR_LINES:
    check(ours in lines, f"our line is present: {ours[:40]}")
functions = [line.split(",")[2] for line in lines if line.startswith("Function,")]
check(functions == sorted(functions), "functions stay sorted by name")
check(functions[0] == "button_panel_item_set_name" and functions[-1] == "zz_last", "our lines sit at their sorted place")
check(out.endswith("\n") and not out.endswith("\n\n"), "one trailing newline")
again, changed_again = strip(out)
check(again == out and not changed_again, "idempotent: a second run changes nothing")
clash, _ = strip(SYNTHETIC.replace("Variable,+,zz_var,int,", "Variable,+,input_set_filter,int,\nVariable,+,zz_var,int,"))
check('Function,-,input_set_filter,void,"InputFilterCallback, void*"' in clash.split("\n"),
      "our line is added when only a row of another kind has its name")

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
