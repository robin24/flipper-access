#!/usr/bin/env python3
"""tools/release_tag_check.sh against throwaway repositories: a bare "origin" in the place of the
fork on GitHub, with commits and tags pushed to it, and clones of it at depth 1 in the place of
the release workflow's submodule checkout (R2, R3).

The checks: a tag pushed after the clone, on the commit the clone has, passes, as the script
fetches it itself; so does a tag on a commit behind the branch tip that the clone checked out by
its hash, which a clone at depth 1 never carries (R2). A tag one commit behind the checkout
fails with one sentence, and so do a tag that origin lacks, a local tag that disagrees with
origin's, a path that is no repository of its own (the folder of a submodule that is not checked
out, whose parent's tags stay), and a call without its tag. With rc1 and the final tag on one
commit, lightweight and annotated in each mix, the check for the final tag passes and leaves only
that tag, so git describe names the build after it (R3). A full clone stays full.
Run from the project root: python3 tests/fbt/test_release_tag_check.py"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "tools", "release_tag_check.sh")
# The command the firmware's scripts/version.py names a build with
DESCRIBE = ("describe", "--tags", "--abbrev=0", "--exact-match")
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def git(repo, *args, ok=True):
    p = subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false",
                        "-c", "tag.gpgSign=false", "-c", "init.defaultBranch=main", "-C", repo, *args],
                       capture_output=True, text=True)
    if ok and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} in {repo}: {p.stderr.strip()}")
    return p.stdout.strip()


def commit(repo, text):
    with open(os.path.join(repo, "file.txt"), "w") as f:
        f.write(text + "\n")
    git(repo, "add", "file.txt")
    git(repo, "commit", "-q", "-m", text)
    return git(repo, "rev-parse", "HEAD")


def tag(repo, name, at, annotated=True):
    if annotated:
        git(repo, "tag", "-a", "-m", name, name, at)
    else:
        git(repo, "tag", name, at)
    git(repo, "push", "-q", "origin", f"refs/tags/{name}")


def clone(tmp, name, depth=True):
    path = os.path.join(tmp, name)
    git(tmp, "clone", "-q", *(["--depth", "1"] if depth else []), "--branch", "main", "file://" + ORIGIN, path)
    return path


def run_check(*args):
    p = subprocess.run(["bash", SCRIPT, *args], capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def one_sentence(said):
    return len(said.splitlines()) == 1 and "fatal" not in said and "unbound" not in said


def tags(repo):
    return git(repo, "tag", "-l").split()


def described(repo):
    return git(repo, *DESCRIBE, ok=False)


with tempfile.TemporaryDirectory() as tmp:
    ORIGIN = os.path.join(tmp, "origin.git")
    work = os.path.join(tmp, "work")
    git(tmp, "init", "-q", "--bare", ORIGIN)
    # A clone at depth 1 fetches a commit behind the tip by its hash, as git submodule update does
    git(ORIGIN, "config", "uploadpack.allowAnySHA1InWant", "true")
    git(tmp, "init", "-q", work)
    git(work, "remote", "add", "origin", ORIGIN)
    c1 = commit(work, "one")
    c2 = commit(work, "two")
    c3 = commit(work, "three")
    git(work, "push", "-q", "origin", "main")

    # A tag pushed after the clone, on the commit the clone has
    a = clone(tmp, "a")
    tag(work, "sonar-1.0.0", c3)
    check(tags(a) == [], f"the clone does not carry the tag pushed after it: {tags(a)}")
    code, said = run_check("sonar-1.0.0", a)
    check(code == 0, f"a tag on the checkout's commit passes, got {code}: {said}")
    check(described(a) == "sonar-1.0.0", f"git describe then gives the tag: {described(a)!r}")
    check(git(a, "rev-parse", "--is-shallow-repository") == "true", "the shallow clone stays shallow")

    # R2: the tag on a commit behind the branch tip, checked out by its hash as the submodule is
    tag(work, "sonar-0.9.0", c2)
    b = clone(tmp, "b")
    git(b, "fetch", "-q", "--depth", "1", "origin", c2)
    git(b, "checkout", "-q", "--detach", c2)
    check("sonar-0.9.0" not in tags(b), f"a clone at depth 1 lacks a tag behind the tip (R2): {tags(b)}")
    code, said = run_check("sonar-0.9.0", b)
    check(code == 0, f"the tag behind the tip is fetched and passes, got {code}: {said}")
    check(described(b) == "sonar-0.9.0", f"git describe then gives it: {described(b)!r}")

    # A tag one commit behind the checkout
    c = clone(tmp, "c")
    code, said = run_check("sonar-0.9.0", c)
    check(code == 1 and one_sentence(said) and "sonar-0.9.0" in said and c2[:9] in said and c3[:9] in said,
          f"a tag one commit behind the checkout fails with one sentence naming both commits, got {code}: {said}")

    # A tag that origin lacks
    code, said = run_check("sonar-9.9.9", c)
    check(code == 1 and one_sentence(said) and "sonar-9.9.9" in said,
          f"a tag that origin lacks fails with one sentence, got {code}: {said}")

    # A local tag on the checkout's commit while origin's tag of that name is elsewhere
    tag(work, "sonar-0.8.0", c1)
    d = clone(tmp, "d")
    git(d, "tag", "sonar-0.8.0", "HEAD")
    code, said = run_check("sonar-0.8.0", d)
    check(code == 1 and one_sentence(said), f"a local tag that disagrees with origin's fails, got {code}: {said}")

    # A full clone stays full, and loses every other tag
    e = clone(tmp, "e", depth=False)
    check(len(tags(e)) == 3, f"the full clone carries the three tags: {tags(e)}")
    code, said = run_check("sonar-1.0.0", e)
    check(code == 0 and tags(e) == ["sonar-1.0.0"], f"a full clone passes and keeps only the tag, got {code}: {said} {tags(e)}")
    check(git(e, "rev-parse", "--is-shallow-repository") == "false", "the full clone stays full")

    # R3: rc1 and the final tag on one commit, in each mix of lightweight and annotated, pushed
    # before the clone, which then carries both
    for i, (rc_annotated, final_annotated) in enumerate(((True, False), (False, True), (True, True))):
        kinds = f"rc1 {'annotated' if rc_annotated else 'lightweight'}, final {'annotated' if final_annotated else 'lightweight'}"
        tip = commit(work, kinds)
        git(work, "push", "-q", "origin", "main")
        version = f"sonar-2.{i}.0"
        tag(work, version + "-rc1", tip, rc_annotated)
        tag(work, version, tip, final_annotated)
        f = clone(tmp, version)
        check(sorted(tags(f)) == [version, version + "-rc1"], f"{kinds}: the clone carries both tags: {tags(f)}")
        if rc_annotated and not final_annotated:
            check(described(f) == version + "-rc1", f"{kinds}: before the check the build would call itself rc1: {described(f)!r}")
        code, said = run_check(version, f)
        check(code == 0, f"{kinds}: the check for the final tag passes, got {code}: {said}")
        check(tags(f) == [version], f"{kinds}: only the final tag is left: {tags(f)}")
        check(described(f) == version, f"{kinds}: git describe gives the final tag: {described(f)!r}")

    # The folder of a submodule that is not checked out: git would find the parent repository,
    # whose tags must stay
    parent = os.path.join(tmp, "parent")
    git(tmp, "init", "-q", parent)
    commit(parent, "parent")
    git(parent, "tag", "parent-tag")
    os.makedirs(os.path.join(parent, "Momentum-Firmware"))
    code, said = run_check("sonar-1.0.0", os.path.join(parent, "Momentum-Firmware"))
    check(code == 1 and one_sentence(said), f"an empty submodule folder fails with one sentence, got {code}: {said}")
    check(tags(parent) == ["parent-tag"], f"the parent repository keeps its tags: {tags(parent)}")

    code, said = run_check()
    check(code == 1 and one_sentence(said) and "usage" in said, f"no tag: the usage line and exit 1, got {code}: {said}")
    code, said = run_check("sonar-1.0.0", a, "extra")
    check(code == 1 and one_sentence(said) and "usage" in said, f"three arguments: the usage line and exit 1, got {code}: {said}")

print(f"release tag check: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
