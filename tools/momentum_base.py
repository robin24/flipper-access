"""The Momentum commit the fork builds on, for the checks that compare the fork's files with
Momentum's at that commit: the golden checks of tests/fbt/test_strip_js_symbols.py and
test_subghz_manifest.py, and tools/subghz_manifest.py --verify-upstream.

tools/momentum-base.txt pins it: the commit of the Momentum release last merged into the fork.
The continuous build's checkout is shallow, so it fetches that one commit alone. After a merge
from Momentum the pin becomes the merged tag's commit (docs/device-notes.md, Merging Momentum);
tests/fbt/test_momentum_base.py fails while the pin is not in the fork's history or is older
than the merge base with upstream/dev, so a merge that leaves the old pin is noticed."""
import os
import subprocess

PIN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "momentum-base.txt")


def pinned(pin_file=PIN_FILE):
    """The pinned commit, the file's first line; None without the file."""
    try:
        with open(pin_file, encoding="utf-8") as f:
            return f.readline().strip() or None
    except OSError:
        return None


def _git(firmware, *args):
    p = subprocess.run(["git", "-C", firmware, *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def base(firmware, pin=None):
    """The pinned commit (pin, else the pin file's) when the checkout has it, else None."""
    pin = pin or pinned()
    if pin and _git(firmware, "cat-file", "-e", f"{pin}^{{commit}}") is not None:
        return pin
    return None


def pin_problem(firmware, pin=None):
    """Why the pin is not the commit the fork builds on, or None. The pin must be in the history
    of HEAD; Momentum's, held by a branch of upstream or a tag mntm-*, not a commit of the fork's
    own; and no older than the merge base of HEAD with upstream/dev, which a release tag on a
    branch beside dev is not. Returns None where the checkout cannot tell: without the pinned
    commit or without upstream/dev. In a shallow checkout the cut can hide the pin's place in
    the history of HEAD, so a "not in the history" is not taken there. The other two hold in any
    checkout: "older" is a found path, and a right pin is the merge base, which upstream/dev holds
    by the path just found, or a tagged commit, which its tag holds."""
    pin = base(firmware, pin)
    shared = _git(firmware, "merge-base", "upstream/dev", "HEAD") if pin else None
    if not shared:
        return None
    shallow = _git(firmware, "rev-parse", "--is-shallow-repository") != "false"
    if _git(firmware, "merge-base", "--is-ancestor", pin, "HEAD") is None:
        return None if shallow else f"the pinned commit {pin[:9]} is not in the history of HEAD"
    if not _git(firmware, "for-each-ref", "--contains", pin, "--format=%(refname)", "refs/remotes/upstream/", "refs/tags/mntm-*"):
        return f"the pinned commit {pin[:9]} is the fork's own: no branch of upstream and no tag mntm-* holds it"
    if pin != shared and _git(firmware, "merge-base", "--is-ancestor", pin, shared) is not None:
        return f"the pin {pin[:9]} is older than the merge base with upstream/dev, {shared[:9]}"
    return None
