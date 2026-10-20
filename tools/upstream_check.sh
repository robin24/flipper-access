#!/bin/bash
# What a merge of Momentum's branch into the fork's branch would meet, without touching the
# working tree.
#
#   tools/upstream_check.sh [--repo DIR] [--upstream REF] [--ours REF] [--no-fetch]
#
# Defaults: the submodule Momentum-Firmware, upstream/dev, HEAD. Unless --no-fetch, the upstream
# ref's remote is fetched first, with its tags: the part of the ref before the first slash, or the
# remote "upstream" for a ref without one, such as a release tag (--upstream mntm-013, the usual
# check before merging a release). Prints the merge base, how many commits are new upstream, the
# fork's footprint, the files changed on both sides since the base, and the conflicts of a
# dry-run merge (git merge-tree --write-tree, git 2.38 or newer). Exit 0 when there is nothing to
# merge or the dry run is clean, 2 on conflicts, 1 on an error, an option without its value, a
# remote that is missing and a fetch that fails included, each said in one sentence. Tested by tests/fbt/test_upstream_check.py. After a real merge, run
# tools/strip_js_symbols.py and tools/subghz_manifest.py --verify-upstream, then the host tests
# and a build; docs/developer-notes.md has the whole routine under Merging Momentum.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
REPO="$ROOT/Momentum-Firmware"
UPSTREAM="upstream/dev"
OURS="HEAD"
FETCH=1
# An option given last, without its value, is named in one sentence rather than tripping set -u.
no_value() { echo "$1 needs a value after it" >&2; exit 1; }
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) [ $# -ge 2 ] || no_value "$1"; REPO="$2"; shift 2 ;;
    --upstream) [ $# -ge 2 ] || no_value "$1"; UPSTREAM="$2"; shift 2 ;;
    --ours) [ $# -ge 2 ] || no_value "$1"; OURS="$2"; shift 2 ;;
    --no-fetch) FETCH=0; shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
cd "$REPO"
if [ "$FETCH" = 1 ]; then
  case "$UPSTREAM" in
    */*) REMOTE="${UPSTREAM%%/*}" ;;
    *) REMOTE=upstream ;;
  esac
  if ! git remote get-url "$REMOTE" > /dev/null 2>&1; then
    echo "no remote \"$REMOTE\" in $REPO; for Momentum's: git -C \"$REPO\" remote add upstream https://github.com/Next-Flip/Momentum-Firmware.git" >&2
    exit 1
  fi
  if ! git fetch --quiet --tags "$REMOTE" 2> /dev/null; then
    echo "could not fetch the remote \"$REMOTE\" ($(git remote get-url "$REMOTE")): is the network there?" >&2
    exit 1
  fi
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
