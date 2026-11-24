#!/bin/bash
# Check out Anki's source, the fork ANKI_REPO at ANKI_COMMIT
# (shared/versions.env), into <dir> and apply shared/patches/anki-*.patch.
# Run again after ANKI_COMMIT changes: a checkout of another commit is
# replaced (its target/ and out/ are kept, so Rust and Anki's own build
# rebuild incrementally), and the patches are reapplied onto clean sources
# when they changed.
# Env: KIOKU_ANKI_REPO, KIOKU_ANKI_COMMIT build another clone or commit of the
#      fork than versions.env names, e.g. the desktop fork next to this
#      repository, as it is committed now:
#        KIOKU_ANKI_REPO=../anki KIOKU_ANKI_COMMIT=HEAD ios/tools/build.sh
#      A commit is a hash, or a branch, tag or HEAD of that repository.
# Usage: anki_source.sh <dir>
set -euo pipefail
SHARED=$(cd "$(dirname "$0")/.." && pwd)
source "$SHARED/versions.env"
DIR=$1
REPO=${KIOKU_ANKI_REPO:-$ANKI_REPO}
COMMIT=${KIOKU_ANKI_COMMIT:-$ANKI_COMMIT}

# a local clone may be given relative to the current directory
if [ -d "$REPO" ]; then
    REPO=$(cd "$REPO" && pwd)
fi
# a branch, tag or HEAD: the commit it names now
if [[ ! $COMMIT =~ ^[0-9a-f]{40}$ ]]; then
    if [ -d "$REPO" ]; then
        resolved=$(git -C "$REPO" rev-parse --verify -q "$COMMIT^{commit}" || true)
    else
        # an annotated tag's commit is its peeled ^{} entry
        resolved=$(git ls-remote "$REPO" "$COMMIT^{}" | awk 'NR == 1 {print $1}')
        [ -n "$resolved" ] || resolved=$(git ls-remote "$REPO" "$COMMIT" | awk 'NR == 1 {print $1}')
    fi
    if [ -z "$resolved" ]; then
        echo "$REPO has no commit $COMMIT" >&2
        exit 1
    fi
    COMMIT=$resolved
fi

if [ "$(git -C "$DIR" rev-parse HEAD 2> /dev/null)" != "$COMMIT" ]; then
    # $DIR may hold another commit, or target/ alone (restored by CI's Rust
    # cache). GitHub serves any commit of a repository by its hash.
    rm -rf "$DIR.new"
    git init -q "$DIR.new"
    git -C "$DIR.new" fetch -q --depth 1 "$REPO" "$COMMIT"
    git -C "$DIR.new" -c advice.detachedHead=false checkout -q FETCH_HEAD
    git -C "$DIR.new" submodule update -q --init --depth 1
    # keep the builds: Rust's target/ and Anki's out/ (anki_wheels.sh knows
    # whether its wheels are of this commit)
    for kept in target out; do
        if [ -d "$DIR/$kept" ]; then
            mv "$DIR/$kept" "$DIR.new/"
        fi
    done
    rm -rf "$DIR" && mv "$DIR.new" "$DIR"
fi

applied() {
    for patch in "$SHARED"/patches/anki-*.patch; do
        git -C "$DIR" apply -R --check "$patch" 2> /dev/null || return 1
    done
}
if ! applied; then
    # back to the fork's sources (target/ and out/ are ignored, so kept)
    git -C "$DIR" checkout -q -- .
    git -C "$DIR" clean -fdq
    for patch in "$SHARED"/patches/anki-*.patch; do
        if ! git -C "$DIR" apply "$patch"; then
            echo "$patch does not apply to Anki at $COMMIT; see shared/patches/README.md" >&2
            exit 1
        fi
    done
fi
