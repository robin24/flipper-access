#!/usr/bin/env python3
"""The generator's words against the device's: every string of the firmware and every bubble
text, with some edge cases, goes through the pronunciation layer and is split as
tools/voice_build.py splits it (expansion_words) and as the device does
(tests/host/voice_words.c: speech_voice_next_word over the same expansion). Line by line, the words
the generator makes clips for are exactly the device's words that can be a clip name (up to 16
lower case letters, or a digit), and every word's card folder, FNV-1a modulo 64, is the same on
both sides. Needs VOICE_WORDS, the helper tools/run_host_tests.sh builds, and a C compiler for the
expander. Run from the project root: python3 tests/fbt/test_voice_parity.py"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import voice_build as vb  # noqa: E402

failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


EDGE = [
    "Don't panic.", "(hello) \"quoted\" [bracketed]", "Keys found: 5/32", "O'Brien's", "e-mail",
    "Wi-Fi 3.5V 100% #1 2nd", "a/b", "NFC", "--", "Café", "rock'n'roll", "It's 12:30", "...",
    "supercalifragilisticexpialidocious", "sixteenletterswd", "seventeenletterss", "x", "7",
]

helper = os.environ.get("VOICE_WORDS")
if not helper:
    print("skipped the parity checks: no VOICE_WORDS, which tools/run_host_tests.sh builds")
else:
    lines = sorted(set(vb.firmware_strings()) | set(vb.bubble_texts()) | set(EDGE))
    text = "\n".join(lines) + "\n"
    with tempfile.TemporaryDirectory() as d:
        expanded = subprocess.run([vb.build_expander(d)], input=text, capture_output=True, text=True, check=True).stdout.splitlines()
    device = subprocess.run([helper], input=text, capture_output=True, text=True, check=True).stdout.splitlines()
    check(len(expanded) == len(device) and len(device) >= len(lines),
          f"one line out per line in, on both sides: {len(expanded)}, {len(device)}, {len(lines)}")
    differ, folders, words = [], [], 0
    for made, found in zip(expanded, device):
        pairs = [w.rsplit("/", 1) for w in found.split()]
        words += len(pairs)
        theirs = {w for w, _ in pairs if vb.WORD_RE.match(w)}
        ours, _ = vb.expansion_words(made)
        if ours != theirs:
            differ.append((made, sorted(ours - theirs), sorted(theirs - ours)))
        folders += [(w, hh, vb.bucket(w)) for w, hh in pairs if vb.bucket(w) != hh]
    check(not differ, f"{len(differ)} lines where the generator's words are not the device's; the first: {differ[:3]}")
    check(not folders, f"{len(folders)} words whose folder differs; the first: {folders[:3]}")
    check(words > 10000, f"a real sample: {words} words of {len(lines)} lines")

print(f"voice parity: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
