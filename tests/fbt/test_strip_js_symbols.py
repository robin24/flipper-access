#!/usr/bin/env python3
"""tools/strip_js_symbols.py: the JavaScript engine's lines leave targets/f7/api_symbols.csv,
the fork's exported lines are present at their sorted place, a row of another kind that shares
one of their names does not stand in for them, the version is upstream's with the minor raised by
FORK_MINOR_STEP (2, one per API round the fork has exported symbols in so far: 90.4 becomes
90.6), from upstream's own version and never from the file's, so a table that already has the
fork's version keeps it (the double raise of the review, T3), and the script is idempotent.
Upstream's version comes from the merge in progress, else the pinned base commit, else the
command line, and without any the script says so in one sentence. The golden check: the file of the Momentum commit the fork
builds on, pinned in tools/momentum-base.txt (tools/momentum_base.py), becomes the fork's file
exactly; it is skipped when the checkout lacks that commit. Run from the project root:
python3 tests/fbt/test_strip_js_symbols.py"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from momentum_base import base as momentum_base  # noqa: E402
from strip_js_symbols import OUR_LINES, strip, upstream_table_version, version_of  # noqa: E402

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

out, changed = strip(SYNTHETIC, "90.4")
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
again, changed_again = strip(out, "90.4")
check(again == out and not changed_again, "idempotent: a second run changes nothing")
clash, _ = strip(SYNTHETIC.replace("Variable,+,zz_var,int,", "Variable,+,input_set_filter,int,\nVariable,+,zz_var,int,"), "90.4")
check('Function,-,input_set_filter,void,"InputFilterCallback, void*"' in clash.split("\n"),
      "our line is added when only a row of another kind has its name")

# The fork's own table after a merge without a conflict here that brought one new JavaScript row:
# the row goes, and the version stays the fork's, upstream's 90.4 and 2, not raised again
merged = out.replace("Function,+,zz_last,void,void", "Function,+,mjs_new,void,void\nFunction,+,zz_last,void,void")
fixed, changed_merged = strip(merged, "90.4")
check(changed_merged and fixed == out, "a clean merge's new JavaScript row goes, and the version stays 90.6")
check(version_of(fixed) == "90.6", f"not raised twice: {version_of(fixed)}")
moved, changed_moved = strip(out, "90.5")
check(changed_moved and version_of(moved) == "90.7", "upstream's version moved on: the fork's follows it, 90.7")
check(version_of("entry,status,name,type,params\nHeader,+,a.h,,\n") is None, "no version without a Version row")

with tempfile.TemporaryDirectory() as tmp:
    # A firmware checkout in the middle of a merge whose upstream table has 90.5
    def tgit(*args):
        return subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c",
                               "commit.gpgsign=false", "-C", repo, *args], capture_output=True, text=True)
    repo = os.path.join(tmp, "Momentum-Firmware")
    os.makedirs(os.path.join(repo, "targets", "f7"))
    table = os.path.join(repo, "targets", "f7", "api_symbols.csv")
    open(table, "w").write(SYNTHETIC)
    tgit("init", "-q", "-b", "upstream")
    tgit("add", ".")
    tgit("commit", "-q", "-m", "upstream 90.4")
    base_commit = tgit("rev-parse", "HEAD").stdout.strip()
    tgit("checkout", "-q", "-b", "screen-reader")
    open(table, "w").write(out)
    tgit("commit", "-q", "-am", "the fork's table")
    tgit("checkout", "-q", "upstream")
    open(table, "w").write(SYNTHETIC.replace("90.4", "90.5"))
    tgit("commit", "-q", "-am", "upstream 90.5")
    tgit("checkout", "-q", "screen-reader")
    tgit("merge", "--no-commit", "upstream")
    check(tgit("rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0, "the throwaway merge is in progress")
    check(upstream_table_version(repo) == ("90.5", "the merge in progress"),
          f"during a merge, the merged table's version: {upstream_table_version(repo)}")
    tgit("merge", "--abort")
    check(upstream_table_version(repo, pin=base_commit) == ("90.4", "the pinned base commit"),
          f"after it, the pinned base commit's: {upstream_table_version(repo, pin=base_commit)}")
    check(upstream_table_version(repo, pin="0" * 40) == (None, None), "neither: none")

    # The script itself, beside a firmware folder that is no checkout
    os.makedirs(os.path.join(tmp, "copy", "tools"))
    os.makedirs(os.path.join(tmp, "copy", "Momentum-Firmware"))
    for name in ("strip_js_symbols.py", "momentum_base.py"):
        shutil.copy(os.path.join(ROOT, "tools", name), os.path.join(tmp, "copy", "tools"))
    script = os.path.join(tmp, "copy", "tools", "strip_js_symbols.py")
    target = os.path.join(tmp, "table.csv")
    open(target, "w").write(SYNTHETIC)
    p = subprocess.run([sys.executable, script, target], capture_output=True, text=True)
    said = p.stderr.strip()
    check(p.returncode == 1 and len(said.splitlines()) == 1 and "--upstream-version" in said and "Traceback" not in said,
          f"no upstream version to be had: one sentence and exit 1, got {p.returncode}: {said}")
    check(open(target).read() == SYNTHETIC, "and the file is left alone")
    p = subprocess.run([sys.executable, script, "--upstream-version", "90.4", target], capture_output=True, text=True)
    check(p.returncode == 0 and "version 90.6: upstream's 90.4, from --upstream-version, and 2" in p.stdout,
          f"--upstream-version: {p.stdout.strip()}")
    check(open(target).read() == out, "the table written is the fork's")

current = open(CSV, encoding="utf-8").read()

base = momentum_base(FIRMWARE)
if base is None:
    print("skipped the golden check: the pinned base commit is not in this checkout")
else:
    upstream = git("show", f"{base}:targets/f7/api_symbols.csv").stdout
    same, changed_current = strip(current, version_of(upstream))
    check(same == current and not changed_current, "the fork's own file is left as it is")
    golden, _ = strip(upstream, version_of(upstream))
    if golden != current:
        import difflib

        for line in list(difflib.unified_diff(golden.splitlines(), current.splitlines(), "script", "fork", lineterm=""))[:20]:
            print(line)
    check(golden == current, "golden: the base commit's file becomes the fork's file exactly")

print(f"strip js symbols: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
