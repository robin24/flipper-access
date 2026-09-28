#!/usr/bin/env python3
"""Re-apply the fork's changes to targets/f7/api_symbols.csv after a Momentum merge.

    tools/strip_js_symbols.py [--check] [--upstream-version X.Y] [PATH]

The fork leaves the JavaScript engine out of the build (fbt_options.py, lib/SConscript), so its
API lines must leave the table too: every Header under lib/mjs/ and every Function or Variable
whose name starts with mjs_. The fork also exports the screen reader's calls (OUR_LINES), added
over two separate API rounds (upstream's version 87.1 became the fork's 87.3), so its API version
is upstream's major and minor with the minor raised by FORK_MINOR_STEP, for as long as those
exports keep to that many rounds. So after a merge that conflicts on this file, take upstream's
side and run this script, which turns upstream's file into the fork's. In the firmware checkout:

    git checkout --theirs targets/f7/api_symbols.csv
    ../tools/strip_js_symbols.py

The version is always upstream's own with the step added, never the step added to whatever the
file holds, so a run after a merge without a conflict here, where the file already has the fork's
version, keeps it. Upstream's version comes from the table of the merge in progress (MERGE_HEAD),
else from that of the pinned base commit (tools/momentum_base.py), or from --upstream-version.
The script is idempotent: on a file it already produced it changes nothing. One of our lines
counts as present when a row of the same kind has its name, so a Variable or a Header that
happens to share a name does not stand in for our Function. Rows keep fbt's order: the sections
Version, Header, Function, Variable, each sorted by name, so our lines are inserted at their
sorted place. --check exits 1 if the file would change. PATH defaults to the submodule's
targets/f7/api_symbols.csv. tests/fbt/test_strip_js_symbols.py checks all of this, and that the
file of the Momentum commit the fork builds on (tools/momentum-base.txt) becomes the fork's file
exactly.
"""
import argparse
import os
import subprocess
import sys

from momentum_base import base as momentum_base

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMWARE = os.path.join(ROOT, "Momentum-Firmware")
TABLE = "targets/f7/api_symbols.csv"
DEFAULT = os.path.join(FIRMWARE, *TABLE.split("/"))
SECTIONS = ("Version", "Header", "Function", "Variable")
# The fork's exports were added over two API rounds (87.1 to 87.3, one exported symbol per
# round). A future merge keeps this step unless the fork adds exports in a new round, in which
# case this constant should grow to match.
FORK_MINOR_STEP = 2
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


def version_of(text):
    """The table's API version, major.minor, from its Version row; None without one."""
    for row in text.split("\n"):
        if row.startswith("Version,"):
            return fields(row)[2]
    return None


def fork_version(upstream_version):
    """Upstream's major.minor with the minor raised by FORK_MINOR_STEP."""
    major, minor = upstream_version.split(".")
    return f"{major}.{int(minor) + FORK_MINOR_STEP}"


def upstream_table_version(firmware=FIRMWARE, pin=None):
    """Upstream's API version and where it came from: the table of the merge in progress
    (MERGE_HEAD), else that of the pinned base commit; (None, None) when the checkout has
    neither."""
    for ref, where in (("MERGE_HEAD", "the merge in progress"), (momentum_base(firmware, pin), "the pinned base commit")):
        if not ref:
            continue
        p = subprocess.run(["git", "-C", firmware, "show", f"{ref}:{TABLE}"], capture_output=True, text=True)
        if p.returncode == 0 and version_of(p.stdout):
            return version_of(p.stdout), where
    return None, None


def strip(text, upstream_version):
    """The file's text after the fork's changes, and whether it changed. The version becomes
    upstream_version, upstream's own, with FORK_MINOR_STEP added, whatever the text holds."""
    lines = text.rstrip("\n").split("\n")
    header, rows = lines[0], lines[1:]
    kept = [row for row in rows if not is_js(row)]
    changed = len(kept) != len(rows)
    present = {(fields(row)[0], fields(row)[2]) for row in kept}  # (kind, name)
    for ours in OUR_LINES:
        if (fields(ours)[0], fields(ours)[2]) not in present:
            kept.append(ours)
            changed = True
    kept.sort(key=sort_key)
    want = fork_version(upstream_version)
    for i, row in enumerate(kept):
        parts = fields(row)
        if parts[0] == "Version" and parts[2] != want:
            parts[2] = want
            kept[i] = ",".join(parts)
            changed = True
    return "\n".join([header, *kept]) + "\n", changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if the file would change, write nothing")
    ap.add_argument("--upstream-version", help="upstream's own API version, major.minor, instead of the merge's or the pinned base's")
    ap.add_argument("path", nargs="?", default=DEFAULT)
    args = ap.parse_args()
    if args.upstream_version:
        upstream, where = args.upstream_version, "--upstream-version"
    else:
        upstream, where = upstream_table_version()
    if upstream is None:
        sys.exit("cannot tell upstream's API version: no merge in progress and the pinned base commit is not in the "
                 "firmware checkout; give it with --upstream-version")
    with open(args.path, encoding="utf-8") as f:
        text = f.read()
    out, changed = strip(text, upstream)
    if not changed:
        print(f"{args.path}: unchanged")
        return
    if args.check:
        sys.exit(f"{args.path}: would change; run without --check")
    with open(args.path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"{args.path}: updated, {len(text.splitlines()) - len(out.splitlines())} lines fewer, version "
          f"{version_of(out)}: upstream's {upstream}, from {where}, and {FORK_MINOR_STEP}")


if __name__ == "__main__":
    main()
