#!/usr/bin/env python3
"""tools/upstream_check.sh against a throwaway repository: a base commit, a branch "ours" that
changes A and adds C, a branch "theirs" that changes A and B (a conflict on A), a branch
"theirs_clean" that changes only B. The script must count the new commits, list the files
changed on both sides, name the conflicts of the dry-run merge, and exit 2, 0 and 0. Run from
the project root: python3 tests/fbt/test_upstream_check.py"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "tools", "upstream_check.sh")
failures = 0


def check(cond, what):
    global failures
    if not cond:
        failures += 1
        print("FAIL", what)


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-C", repo, *args],
                   check=True, capture_output=True, text=True)


def write(repo, name, text):
    with open(os.path.join(repo, name), "w") as f:
        f.write(text)


def run_check(repo, upstream, ours):
    p = subprocess.run(["bash", SCRIPT, "--repo", repo, "--upstream", upstream, "--ours", ours, "--no-fetch"],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def section(out, title):
    """The indented lines after a title line, up to the next unindented line."""
    lines = out.split(title + "\n", 1)[1].split("\n") if title + "\n" in out else []
    names = []
    for line in lines:
        if not line.startswith("  "):
            break
        names.append(line.strip())
    return names


with tempfile.TemporaryDirectory() as tmp:
    repo = os.path.join(tmp, "r")
    os.makedirs(repo)
    git(repo, "init", "-q", "-b", "base")
    write(repo, "A", "a\n")
    write(repo, "B", "b\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "checkout", "-q", "-b", "ours")
    write(repo, "A", "a ours\n")
    write(repo, "C", "c\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "ours")
    git(repo, "checkout", "-q", "-b", "theirs", "base")
    write(repo, "A", "a theirs\n")
    write(repo, "B", "b theirs\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "theirs")
    git(repo, "checkout", "-q", "-b", "theirs_clean", "base")
    write(repo, "B", "b clean\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "clean")
    git(repo, "checkout", "-q", "ours")

    code, out = run_check(repo, "theirs", "ours")
    check(code == 2, f"a conflict exits 2, got {code}:\n{out}")
    check("upstream theirs: 1 new commits; ours ours: 1 commits on top" in out, f"the counts line:\n{out}")
    check("our footprint since the base: 1 added, 1 modified files" in out, f"the footprint line:\n{out}")
    check(section(out, "files changed on both sides:") == ["A"], f"both sides changed A only:\n{out}")
    check(section(out, "dry-run merge: conflicts in:") == ["A"], f"the conflict is A:\n{out}")

    code, out = run_check(repo, "theirs_clean", "ours")
    check(code == 0 and "dry-run merge: clean" in out, f"a clean merge exits 0:\n{out}")
    check(section(out, "files changed on both sides:") == [], f"nothing changed on both sides:\n{out}")

    code, out = run_check(repo, "base", "ours")
    check(code == 0 and "nothing to merge" in out, f"nothing new exits 0:\n{out}")

    code, out = run_check(repo, "nonexistent", "ours")
    check(code == 1, f"a bad ref exits 1, got {code}")

print(f"upstream check: {9 - failures} of 9 checks passed")
sys.exit(1 if failures else 0)
