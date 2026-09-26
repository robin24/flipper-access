#!/usr/bin/env python3
"""tools/upstream_check.sh against a throwaway repository: a base commit, a branch "ours" that
changes A and adds C, a branch "theirs" that changes A and B (a conflict on A), a branch
"theirs_clean" that changes only B. The script must count the new commits, list the files
changed on both sides, name the conflicts of the dry-run merge, and exit 2, 0 and 0. With the
fetch on, a ref without a slash, such as a release tag, is fetched from the remote "upstream"
with its tags, and a ref with a slash from the remote named before the slash. An option given
last without its value ends with one sentence and exit 1. The dry run needs git merge-tree
--write-tree, git 2.38 or newer; with an older git the test says it skipped and exits 0. Run
from the project root: python3 tests/fbt/test_upstream_check.py"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "tools", "upstream_check.sh")
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false",
                    "-c", "tag.gpgSign=false", "-C", repo, *args], check=True, capture_output=True, text=True)


def write(repo, name, text):
    with open(os.path.join(repo, name), "w") as f:
        f.write(text)


def run_script(*args):
    p = subprocess.run(["bash", SCRIPT, *args], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def run_check(repo, upstream, ours, fetch=False):
    return run_script("--repo", repo, "--upstream", upstream, "--ours", ours, *([] if fetch else ["--no-fetch"]))


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
    probe = subprocess.run(["git", "-C", repo, "merge-tree", "--write-tree", "base", "base"], capture_output=True, text=True)
    if probe.returncode != 0:
        print("skipped the upstream check tests: git merge-tree --write-tree needs git 2.38 or newer")
        sys.exit(0)
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

    # Two remotes that "r" has not fetched yet: "upstream" with a release tag, "other" with a branch.
    for name in ("upstream", "other"):
        remote = os.path.join(tmp, name)
        git(tmp, "clone", "-q", "-b", "theirs_clean", repo, remote)
        write(remote, "D", f"d from {name}\n")
        git(remote, "add", ".")
        git(remote, "commit", "-q", "-m", f"new in {name}")
        if name == "upstream":
            git(remote, "tag", "mntm-013")
        else:
            git(remote, "branch", "newer")
        git(repo, "remote", "add", name, remote)

    code, out = run_check(repo, "mntm-013", "ours", fetch=True)
    check(code == 0 and "upstream mntm-013: 2 new commits; ours ours: 1 commits on top" in out and "dry-run merge: clean" in out,
          f"a tag is fetched from the remote upstream with its tags:\n{out}")
    code, out = run_check(repo, "other/newer", "ours", fetch=True)
    check(code == 0 and "upstream other/newer: 2 new commits" in out and "dry-run merge: clean" in out,
          f"a ref with a slash is fetched from the remote named before the slash:\n{out}")

    for option in ("--repo", "--upstream", "--ours"):
        code, out = run_script("--no-fetch", option)
        said = out.strip()
        check(code == 1 and len(said.splitlines()) == 1 and option in said and "unbound" not in said,
              f"{option} given last without a value: one sentence and exit 1, got {code}:\n{said}")

print(f"upstream check: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
