#!/bin/bash
# The release workflow's check, before the build, that the fork's checkout is the tagged commit
# and that the build will name itself after the tag (R2, R3).
#
#   tools/release_tag_check.sh TAG [REPOSITORY]
#
# REPOSITORY is the submodule Momentum-Firmware unless given. The tag is fetched explicitly from
# the repository's remote "origin", since a checkout at depth 1 carries a tag only while the
# tagged commit is the branch tip (R2); the fetch is at depth 1 when the checkout is shallow, so
# a full clone stays full, and origin's tag replaces a local one of the same name. Then every
# other tag of the checkout is deleted: git describe --tags --exact-match, with which the
# firmware's scripts/version.py names the build, prefers an annotated tag to a lightweight one
# and then goes by date, so with rc1 and the final tag on one commit the build could call itself
# rc1 (R3), and tools/card_prune.py would then delete the release just installed. As it deletes
# tags, the script is for the workflow's fresh checkout; a local clone gets them back with
# git fetch --tags. Exit 0 when HEAD is the tag's commit and git describe gives the tag, else 1
# with one sentence. Tested by tests/fbt/test_release_tag_check.py.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
fail() { echo "$1" >&2; exit 1; }
if [ $# -lt 1 ] || [ $# -gt 2 ] || [ -z "$1" ]; then
  fail "usage: tools/release_tag_check.sh TAG [REPOSITORY]"
fi
TAG="$1"
REPO="${2:-$ROOT/Momentum-Firmware}"

# The repository's own top level, so that the empty folder of a submodule that is not checked
# out does not stand for the project around it, whose tags would go
if ! TOP="$(git -C "$REPO" rev-parse --show-toplevel 2> /dev/null)" || [ "$TOP" != "$(cd "$REPO" && pwd -P)" ]; then
  fail "$REPO is not a checked-out repository of its own: git submodule update --init --depth 1 Momentum-Firmware"
fi
git check-ref-format "refs/tags/$TAG" || fail "\"$TAG\" is not a tag name"
URL="$(git -C "$REPO" remote get-url origin 2> /dev/null)" || fail "$REPO has no remote origin to fetch the tag $TAG from"

DEPTH=""
if [ "$(git -C "$REPO" rev-parse --is-shallow-repository)" = true ]; then DEPTH="--depth 1"; fi
# $DEPTH unquoted: two words or none
if ! git -C "$REPO" fetch --quiet --no-tags $DEPTH origin "+refs/tags/$TAG:refs/tags/$TAG" 2> /dev/null; then
  fail "could not fetch the tag $TAG from $URL: push it to the fork first"
fi

git -C "$REPO" for-each-ref --format='delete %(refname)' refs/tags \
  | { grep -vxF "delete refs/tags/$TAG" || true; } \
  | git -C "$REPO" update-ref --stdin

HEAD_COMMIT="$(git -C "$REPO" rev-parse --verify --quiet HEAD)" || fail "$REPO has no commit checked out"
TAG_COMMIT="$(git -C "$REPO" rev-parse --verify --quiet "refs/tags/$TAG^{commit}")" || fail "the tag $TAG names no commit"
if [ "$HEAD_COMMIT" != "$TAG_COMMIT" ]; then
  fail "the fork's tag $TAG is on commit ${TAG_COMMIT:0:9} but the checkout is at ${HEAD_COMMIT:0:9}, so tag the fork commit that the project records, or record the tagged one"
fi
DESCRIBED="$(git -C "$REPO" describe --tags --abbrev=0 --exact-match 2> /dev/null)" || DESCRIBED=""
if [ "$DESCRIBED" != "$TAG" ]; then
  fail "git describe names the build \"${DESCRIBED:-nothing}\" rather than $TAG"
fi
echo "the fork's tag $TAG is on the checkout's commit ${HEAD_COMMIT:0:9}, and the only tag left"
