#!/bin/bash
# A release's source bundle (R10): the fork at the tag with every submodule, nested ones
# included, each at the commit the tag records for it, in one gzipped tar whose entries are all
# under TAG-source/. git archive leaves submodules out, so each repository is archived on its own
# into a staging folder, which is then packed.
#
#   tools/source_bundle.sh TAG OUT [REPOSITORY]
#
# REPOSITORY is the submodule Momentum-Firmware unless given. Every submodule must be checked out
# with its recorded commit at hand, as fbt leaves them after a build (it runs git submodule update
# --init --recursive). Prints one line per submodule, its path in the fork and the commit
# bundled, for the release notes. Exit 1 with one sentence on an error, and no bundle then. The
# release workflow runs it on Linux; on a Mac, two names that differ only in case would meet in
# the staging folder. Tested by tests/fbt/test_source_bundle.py.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
fail() { echo "$1" >&2; exit 1; }
if [ $# -lt 2 ] || [ $# -gt 3 ] || [ -z "$1" ] || [ -z "$2" ]; then
  fail "usage: tools/source_bundle.sh TAG OUT [REPOSITORY]"
fi
TAG="$1"
REPO="${3:-$ROOT/Momentum-Firmware}"
NAME="$TAG-source"

# True when the folder is the top level of a repository of its own, not the empty folder of a
# submodule that is not checked out, which git would take for the repository around it
own_repository() {
  local top
  top="$(git -C "$1" rev-parse --show-toplevel 2> /dev/null)" && [ "$top" = "$(cd "$1" && pwd -P)" ]
}

own_repository "$REPO" || fail "$REPO is not a checked-out repository of its own"
git check-ref-format "refs/tags/$TAG" || fail "\"$TAG\" is not a tag name"
COMMIT="$(git -C "$REPO" rev-parse --verify --quiet "refs/tags/$TAG^{commit}")" || fail "$REPO has no tag $TAG"
OUT_DIR="$(cd "$(dirname "$2")" 2> /dev/null && pwd -P)" || fail "there is no folder $(dirname "$2") for the bundle"
OUT="$OUT_DIR/$(basename "$2")"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE" "$OUT.partial"' EXIT

# archive REPOSITORY COMMIT PATH: the repository's files at the commit into the staging folder,
# at PATH in the fork, then each submodule the commit records, the same way
archive() {
  local repo="$1" commit="$2" path="$3" entry mode type sha sub
  git -C "$repo" archive --format=tar --prefix="$NAME/$path" "$commit" | tar -xf - -C "$STAGE"
  # ls-tree -z: "<mode> <type> <object><tab><path>" and a NUL
  while IFS= read -r -d '' entry; do
    read -r mode type sha <<< "${entry%%$'\t'*}"
    [ "$type" = commit ] || continue
    sub="${entry#*$'\t'}"
    if ! own_repository "$repo/$sub" || ! git -C "$repo/$sub" cat-file -e "$sha^{commit}" 2> /dev/null; then
      fail "the submodule $path$sub is not checked out with its commit ${sha:0:9}: git submodule update --init --recursive in $REPO"
    fi
    echo "$path$sub $sha"
    archive "$repo/$sub" "$sha" "$path$sub/"
  done < <(git -C "$repo" ls-tree -r -z "$commit")
}

archive "$REPO" "$COMMIT" ""
# COPYFILE_DISABLE: no ._ files from a Mac's tar
COPYFILE_DISABLE=1 tar -czf "$OUT.partial" -C "$STAGE" "$NAME"
mv "$OUT.partial" "$OUT"
