#!/usr/bin/env python3
"""Re-apply the fork's changes to targets/f7/api_symbols.csv after a Momentum merge.

    tools/strip_js_symbols.py [--check] [PATH]

The fork leaves the JavaScript engine out of the build (fbt_options.py, lib/SConscript), so its
API lines must leave the table too: every Header under lib/mjs/ and every Function or Variable
whose name starts with mjs_. The fork also exports the screen reader's calls (OUR_LINES), added
over two separate API rounds (upstream's version 87.1 became the fork's 87.3), so its API version
is upstream's major and minor with the minor raised by FORK_MINOR_STEP, for as long as those
exports keep to that many rounds. So a merge takes upstream's file whole and runs this script on
it. The script is idempotent: on a file it already produced it changes nothing, and the version is
raised only when a JavaScript line was removed or one of our lines was missing. Rows keep fbt's
order: the sections Version, Header, Function, Variable, each sorted by name, so our lines are
inserted at their sorted place. --check exits 1 if the file would change. PATH defaults to the
submodule's targets/f7/api_symbols.csv. tests/fbt/test_strip_js_symbols.py checks all of this, and
that the merge base's file becomes the fork's file exactly.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = os.path.join(ROOT, "Momentum-Firmware", "targets", "f7", "api_symbols.csv")
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
                parts[2] = f"{major}.{int(minor) + FORK_MINOR_STEP}"
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
