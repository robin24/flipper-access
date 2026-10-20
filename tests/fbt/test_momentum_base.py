#!/usr/bin/env python3
"""tools/momentum_base.py: the commit the golden checks compare with is the pinned one when the
checkout has it, and none otherwise. The pin is right while it is in the history of HEAD, held
by a branch of upstream or a tag mntm-*, and no older than the merge base of HEAD with
upstream/dev: a merge from Momentum that leaves the old pin fails, a pin at one of the fork's own
commits fails, and a pin at a release tag on a branch other than dev passes. Without upstream/dev, as in
the continuous build, the pin is not judged; a shallow checkout finds an old pin all the same,
but takes no "not in the history" that its cut may cause. The real pin, tools/momentum-base.txt,
is one full commit hash and right for this checkout. Run from the project root:
python3 tests/fbt/test_momentum_base.py"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from momentum_base import base, pin_problem, pinned  # noqa: E402

FIRMWARE = os.path.join(ROOT, "Momentum-Firmware")
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false",
                           "-C", repo, *args], check=True, capture_output=True, text=True).stdout.strip()


with tempfile.TemporaryDirectory() as tmp:
    # Momentum's A and its next commit C on upstream/dev; the fork's B on top of A as HEAD.
    repo = os.path.join(tmp, "firmware")
    os.makedirs(repo)
    git(repo, "init", "-q", "-b", "screen-reader")
    git(repo, "commit", "-q", "--allow-empty", "-m", "A")
    a = git(repo, "rev-parse", "HEAD")
    c = git(repo, "commit-tree", "-p", a, "-m", "C", f"{a}^{{tree}}")
    git(repo, "update-ref", "refs/remotes/upstream/dev", c)
    git(repo, "commit", "-q", "--allow-empty", "-m", "B")
    b = git(repo, "rev-parse", "HEAD")

    check(base(repo, pin=a) == a, "the pinned commit the checkout has")
    check(base(repo, pin="0" * 40) is None, "nothing for a pin the checkout lacks")
    check(base(os.path.join(tmp, "nowhere"), pin=a) is None, "nothing outside a checkout")
    check(pin_problem(repo, pin=a) is None, "the pin at the fork's base is right")
    check(pin_problem(repo, pin=c) is not None, "a pin outside the history of HEAD is wrong")
    check(pin_problem(repo, pin=b) is not None and "own" in pin_problem(repo, pin=b),
          f"a pin at the fork's own commit is wrong: {pin_problem(repo, pin=b)}")

    # The fork merges C: the old pin is stale, C is right.
    git(repo, "merge", "-q", "--no-edit", c)
    check(pin_problem(repo, pin=a) is not None and "older" in pin_problem(repo, pin=a),
          f"after a merge, the old pin is older than the merge base: {pin_problem(repo, pin=a)}")
    check(pin_problem(repo, pin=c) is None, "after a merge, the merged commit is right")

    # A release tag on a branch beside dev, R made from C, merged into the fork: R is right.
    r = git(repo, "commit-tree", "-p", c, "-m", "R", f"{c}^{{tree}}")
    git(repo, "merge", "-q", "--no-edit", r)
    check(pin_problem(repo, pin=r) is not None, "without its tag, R is taken for the fork's own")
    git(repo, "tag", "mntm-001", r)
    check(pin_problem(repo, pin=r) is None, "a release tag off dev is right when merged")
    check(pin_problem(repo, pin=c) is None, "the dev commit it came from passes too, as the check cannot tell them apart")
    check(pin_problem(repo, pin=git(repo, "rev-parse", "HEAD")) is not None, "the merge commit, the fork's own, is wrong")

    git(repo, "update-ref", "-d", "refs/remotes/upstream/dev")
    check(pin_problem(repo, pin=a) is None, "without upstream/dev the pin is not judged")

    # A clone of the fork's tip three commits deep: the two merges, R, and then B and C, their
    # parent A cut off; upstream/dev at R.
    shallow = os.path.join(tmp, "shallow")
    git(repo, "config", "uploadpack.allowAnySHA1InWant", "true")
    git(tmp, "clone", "-q", "--depth", "3", f"file://{repo}", shallow)
    git(shallow, "update-ref", "refs/remotes/upstream/dev", r)
    check(pin_problem(shallow, pin=r) is None, "in a shallow checkout, the merge base itself is right")
    check(pin_problem(shallow, pin=c) is not None, "in a shallow checkout, a pin older than the merge base is found")
    # A fetched alone: in the history of HEAD, but the cut hides it, so the "no" is not taken.
    git(shallow, "fetch", "-q", "--depth", "1", "origin", a)
    check(base(shallow, pin=a) == a and pin_problem(shallow, pin=a) is None,
          "in a shallow checkout, a pin whose place the cut hides is not judged")
    check(pin_problem(shallow, pin=git(shallow, "rev-parse", "HEAD")) is not None,
          "in a shallow checkout, a pin at the fork's own commit is found")

check(pinned(os.path.join(ROOT, "no-such-file")) is None, "no pin without the file")
pin = pinned()
check(pin is not None and re.fullmatch(r"[0-9a-f]{40}", pin) is not None,
      f"tools/momentum-base.txt holds one full commit hash: {pin!r}")
problem = pin_problem(FIRMWARE)
check(problem is None, f"{problem}: after a merge from Momentum, pin the merged tag's commit (docs/developer-notes.md, "
      "Merging Momentum)")
judged = base(FIRMWARE) is not None and subprocess.run(
    ["git", "-C", FIRMWARE, "merge-base", "upstream/dev", "HEAD"], capture_output=True).returncode == 0
print(f"momentum base: {checks - failures} of {checks} checks passed, the pin "
      + ("judged against upstream/dev" if judged else "not judged: no upstream/dev or no pinned commit in this checkout"))
sys.exit(1 if failures else 0)
