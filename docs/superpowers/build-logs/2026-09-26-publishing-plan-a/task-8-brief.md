### Task 8: `tools/upstream_check.sh` and its test

**Files:**
- Create: `tools/upstream_check.sh`, `tests/fbt/test_upstream_check.py`
- Modify: `tools/run_host_tests.sh`

**Interfaces:**
- Produces: `tools/upstream_check.sh [--repo DIR] [--upstream REF] [--ours REF] [--no-fetch]`, exit 0 when there is nothing to merge or the dry run is clean, 2 on conflicts, 1 on an error.

- [ ] **Step 1: Write the failing test**

Create `tests/fbt/test_upstream_check.py`:

```python
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
```

- [ ] **Step 2: Run it to see it fail**

```bash
python3 tests/fbt/test_upstream_check.py
```

Expected: failures (the script does not exist; bash reports it and the checks fail).

- [ ] **Step 3: Write the script**

Create `tools/upstream_check.sh` and make it executable (`chmod +x`):

```bash
#!/bin/bash
# What a merge of Momentum's branch into the fork's branch would meet, without touching the
# working tree.
#
#   tools/upstream_check.sh [--repo DIR] [--upstream REF] [--ours REF] [--no-fetch]
#
# Defaults: the submodule Momentum-Firmware, upstream/dev, HEAD. The upstream remote is fetched
# first unless --no-fetch. Prints the merge base, how many commits are new upstream, the fork's
# footprint, the files changed on both sides since the base, and the conflicts of a dry-run
# merge (git merge-tree --write-tree, git 2.38 or newer). Exit 0 when there is nothing to merge
# or the dry run is clean, 2 on conflicts, 1 on an error. Tested by
# tests/fbt/test_upstream_check.py. After a real merge, run tools/strip_js_symbols.py and
# tools/subghz_manifest.py --verify-upstream, then the host tests and a build.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
REPO="$ROOT/Momentum-Firmware"
UPSTREAM="upstream/dev"
OURS="HEAD"
FETCH=1
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --upstream) UPSTREAM="$2"; shift 2 ;;
    --ours) OURS="$2"; shift 2 ;;
    --no-fetch) FETCH=0; shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
cd "$REPO"
if [ "$FETCH" = 1 ]; then
  git fetch --quiet "${UPSTREAM%%/*}"
fi
if ! BASE=$(git merge-base "$OURS" "$UPSTREAM" 2>/dev/null); then
  echo "no merge base between $OURS and $UPSTREAM" >&2
  exit 1
fi
AHEAD=$(git rev-list --count "$OURS..$UPSTREAM")
ON_TOP=$(git rev-list --count "$UPSTREAM..$OURS")
ADDED=$(git diff --name-only --diff-filter=A "$BASE" "$OURS" | wc -l | tr -d ' ')
MODIFIED=$(git diff --name-only --diff-filter=M "$BASE" "$OURS" | wc -l | tr -d ' ')
echo "merge base: $(git log -1 --format='%h %ad %s' --date=short "$BASE")"
echo "upstream $UPSTREAM: $AHEAD new commits; ours $OURS: $ON_TOP commits on top"
echo "our footprint since the base: $ADDED added, $MODIFIED modified files"
if [ "$AHEAD" = 0 ]; then
  echo "nothing to merge"
  exit 0
fi
echo "files changed on both sides:"
comm -12 <(git diff --name-only "$BASE" "$OURS" | sort) <(git diff --name-only "$BASE" "$UPSTREAM" | sort) | sed 's/^/  /'
set +e
OUT=$(git merge-tree --write-tree --name-only --no-messages "$OURS" "$UPSTREAM" 2>&1)
STATUS=$?
set -e
case "$STATUS" in
  0) echo "dry-run merge: clean"; exit 0 ;;
  1) echo "dry-run merge: conflicts in:"; echo "$OUT" | tail -n +2 | sed '/^$/d; s/^/  /'; exit 2 ;;
  *) echo "dry-run merge failed: $OUT" >&2; exit 1 ;;
esac
```

- [ ] **Step 4: Run the test**

```bash
python3 tests/fbt/test_upstream_check.py
```

Expected: `upstream check: 9 of 9 checks passed`. If the "1 commits on top" or the footprint wording differs, fix the script's text, not the test.

- [ ] **Step 5: Run it for real, add it to the runner, commit**

```bash
tools/upstream_check.sh
```

Expected today: the merge base `d3f89dfe2` of 2026-08-18, `0 new commits`, the footprint `24 added, 53 modified files`, then `nothing to merge`, exit 0. Record the output in the report.

Append the runner block for `test_upstream_check.py` (output `upstream_check.txt`, message `upstream check checks failed`), run the runner, then:

```bash
git add tools/upstream_check.sh tests/fbt/test_upstream_check.py tools/run_host_tests.sh
git commit -m "upstream_check: what a Momentum merge would meet, from a dry run

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- tools/upstream_check.sh tests/fbt/test_upstream_check.py tools/run_host_tests.sh
git push
```

---

