#!/usr/bin/env python3
"""tools/source_bundle.sh against a throwaway repository in the place of the fork: "fork" with
one submodule, lib/sub, which has a submodule of its own, deep/inner, all checked out, and the
tag sonar-1.2.3 on the fork (R10).

The checks: the bundle is a gzipped tar whose every entry is under sonar-1.2.3-source/, with the
fork's files and the submodules' files inside, the nested one included, as they are at the tag:
neither the fork's commit after the tag nor a newer commit checked out in the submodule since
then reaches the bundle. The script prints each submodule's path and the commit it bundled, for
the release notes. A submodule that is not checked out, a tag the fork lacks, and a call without
its two arguments each fail with one sentence and leave no bundle.
Run from the project root: python3 tests/fbt/test_source_bundle.py"""
import os
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "tools", "source_bundle.sh")
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def git(repo, *args):
    # protocol.file.allow: git 2.38.1 and newer refuse local submodules without it
    p = subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false",
                        "-c", "tag.gpgSign=false", "-c", "init.defaultBranch=main", "-c", "protocol.file.allow=always",
                        "-C", repo, *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} in {repo}: {p.stderr.strip()}")
    return p.stdout.strip()


def commit(repo, name, text):
    path = os.path.join(repo, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", text.strip())
    return git(repo, "rev-parse", "HEAD")


def run_bundle(*args):
    p = subprocess.run(["bash", SCRIPT, *args], capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr.strip()


def one_sentence(said):
    return len(said.splitlines()) == 1 and "fatal" not in said and "unbound" not in said


with tempfile.TemporaryDirectory() as tmp:
    inner = os.path.join(tmp, "inner")
    sub = os.path.join(tmp, "sub")
    fork = os.path.join(tmp, "fork")
    for repo in (inner, sub, fork):
        git(tmp, "init", "-q", repo)
    inner_commit = commit(inner, "inner.txt", "inner at the tag\n")
    git(sub, "submodule", "add", "-q", inner, "deep/inner")
    sub_commit = commit(sub, "sub.txt", "sub at the tag\n")
    commit(fork, "fork.txt", "fork at the tag\n")
    git(fork, "submodule", "add", "-q", sub, "lib/sub")
    git(fork, "submodule", "update", "--init", "--recursive")
    git(fork, "commit", "-q", "-m", "the submodule")
    git(fork, "tag", "-a", "-m", "sonar-1.2.3", "sonar-1.2.3")

    # After the tag: a new fork commit, and a newer submodule commit checked out but not recorded
    commit(fork, "fork.txt", "fork after the tag\n")
    commit(sub, "sub.txt", "sub after the tag\n")
    git(os.path.join(fork, "lib", "sub"), "fetch", "-q", "origin", "main")
    git(os.path.join(fork, "lib", "sub"), "checkout", "-q", "--detach", "FETCH_HEAD")

    out = os.path.join(tmp, "out", "sonar-1.2.3-source.tar.gz")
    os.makedirs(os.path.dirname(out))
    code, printed, said = run_bundle("sonar-1.2.3", out, fork)
    check(code == 0, f"the bundle is made, got {code}: {said}")
    check(printed.splitlines() == [f"lib/sub {sub_commit}", f"lib/sub/deep/inner {inner_commit}"],
          f"each submodule's path and bundled commit is printed:\n{printed}")
    files = {}
    names = []
    if os.path.isfile(out):
        with tarfile.open(out, "r:gz") as tar:
            for member in tar.getmembers():
                names.append(member.name)
                if member.isfile():
                    files[member.name] = tar.extractfile(member).read().decode()
    top = "sonar-1.2.3-source/"
    check(names and all(n == top.rstrip("/") or n.startswith(top) for n in names), f"every entry is under {top}: {names}")
    check(files.get(top + "fork.txt") == "fork at the tag\n", f"the fork's file is as at the tag: {files.get(top + 'fork.txt')!r}")
    check(files.get(top + "lib/sub/sub.txt") == "sub at the tag\n",
          f"the submodule's file is as the tag records it: {files.get(top + 'lib/sub/sub.txt')!r}")
    check(files.get(top + "lib/sub/deep/inner/inner.txt") == "inner at the tag\n",
          f"the nested submodule's file is inside: {files.get(top + 'lib/sub/deep/inner/inner.txt')!r}")
    check(not any("/.git/" in n or n.endswith("/.git") for n in names), f"no .git entry: {names}")

    # A clone of the fork whose submodule is not checked out
    plain = os.path.join(tmp, "plain-clone")
    git(tmp, "clone", "-q", fork, plain)
    missing = os.path.join(tmp, "missing.tar.gz")
    code, printed, said = run_bundle("sonar-1.2.3", missing, plain)
    check(code == 1 and one_sentence(said) and "lib/sub" in said,
          f"a submodule that is not checked out fails with one sentence naming it, got {code}: {said}")
    check(not os.path.exists(missing), "and leaves no bundle")

    code, printed, said = run_bundle("sonar-9.9.9", missing, fork)
    check(code == 1 and one_sentence(said) and "sonar-9.9.9" in said,
          f"a tag the fork lacks fails with one sentence, got {code}: {said}")
    check(not os.path.exists(missing), "and leaves no bundle")

    code, printed, said = run_bundle("sonar-1.2.3")
    check(code == 1 and one_sentence(said) and "usage" in said, f"one argument: the usage line and exit 1, got {code}: {said}")

print(f"source bundle: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
