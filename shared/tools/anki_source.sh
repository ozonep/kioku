#!/bin/bash
# Check out Anki's source into <dir> and apply shared/patches/anki-*.patch:
# Anki's release ANKI_TAG (shared/versions.env), or with --fork the Anki
# FSRS-7 fork that the iPhone and iPad build, ANKI_FORK_REPO at
# ANKI_FORK_COMMIT (shared/anki-fork.env). Run again after those change: a
# checkout of another release or commit is replaced (its target/ and out/ are
# kept, so Rust and Anki's own build rebuild incrementally), and the patches
# are reapplied onto clean sources when they changed.
# Env, with --fork: KIOKU_ANKI_REPO, KIOKU_ANKI_COMMIT build another clone or
#      commit of the fork, e.g. the desktop fork next to this repository, as
#      it is committed now (from this repository's folder):
#        KIOKU_ANKI_REPO=../anki KIOKU_ANKI_COMMIT=HEAD ios/tools/build.sh
#      A clone's path is relative to the current directory; a commit is a
#      hash (all 40 digits for a URL), or a branch, tag or HEAD of that
#      repository.
# Usage: anki_source.sh [--fork] <dir>
set -euo pipefail
SHARED=$(cd "$(dirname "$0")/.." && pwd)
source "$SHARED/versions.env"
FORK=false
if [ "${1:-}" = --fork ]; then
    FORK=true
    shift
fi
DIR=$1

# replace <command...>: the command checks Anki out into $DIR.new, which
# replaces $DIR but keeps its builds: Rust's target/ and Anki's out/
# (anki_wheels.sh knows whether its wheels are of this commit). $DIR may hold
# another checkout, or target/ alone (restored by CI's Rust cache).
replace() {
    rm -rf "$DIR.new"
    "$@"
    git -C "$DIR.new" submodule update -q --init --depth 1
    for kept in target out; do
        if [ -d "$DIR/$kept" ]; then
            mv "$DIR/$kept" "$DIR.new/"
        fi
    done
    rm -rf "$DIR" && mv "$DIR.new" "$DIR"
}

if ! $FORK; then
    SOURCE="Anki $ANKI_TAG"
    if [ "$(git -C "$DIR" describe --tags --exact-match 2> /dev/null)" != "$ANKI_TAG" ]; then
        replace git -c advice.detachedHead=false clone -q --depth 1 --branch "$ANKI_TAG" \
            https://github.com/ankitects/anki "$DIR.new"
    fi
else
    source "$SHARED/anki-fork.env"
    REPO=${KIOKU_ANKI_REPO:-$ANKI_FORK_REPO}
    COMMIT=${KIOKU_ANKI_COMMIT:-$ANKI_FORK_COMMIT}
    # a local clone (a URL has a colon)
    if [ -d "$REPO" ]; then
        REPO=$(cd "$REPO" && pwd)
    elif [[ $REPO != *:* ]]; then
        echo "No Anki clone at $REPO (relative to $PWD)" >&2
        exit 1
    fi
    # a branch, tag or HEAD: the commit it names now
    if [[ ! $COMMIT =~ ^[0-9a-f]{40}$ ]]; then
        if [ -d "$REPO" ]; then
            resolved=$(git -C "$REPO" rev-parse --verify -q "$COMMIT^{commit}" || true)
        else
            # ls-remote also lists refs that only end in /$COMMIT: take the
            # exact one, in git rev-parse's order (HEAD or a full name, refs/,
            # tags, heads, remotes, remotes/*/HEAD); an annotated tag's commit
            # is its peeled ^{} entry
            resolved=$(git ls-remote -- "$REPO" "$COMMIT" "$COMMIT^{}" \
                "refs/remotes/$COMMIT/HEAD" "refs/remotes/$COMMIT/HEAD^{}" | awk -v name="$COMMIT" '
                { sha[$2] = $1 }
                END {
                    refs[1] = name
                    refs[2] = "refs/" name
                    refs[3] = "refs/tags/" name
                    refs[4] = "refs/heads/" name
                    refs[5] = "refs/remotes/" name
                    refs[6] = "refs/remotes/" name "/HEAD"
                    for (i = 1; i <= 6; i++) {
                        if ((refs[i] "^{}") in sha) { print sha[refs[i] "^{}"]; exit }
                        if (refs[i] in sha) { print sha[refs[i]]; exit }
                    }
                }')
        fi
        if [ -z "$resolved" ]; then
            echo "$REPO has no commit $COMMIT" >&2
            exit 1
        fi
        COMMIT=$resolved
    fi
    SOURCE="the Anki fork at $COMMIT"
    # GitHub serves any commit of a repository by its hash; set origin so
    # relative submodule URLs resolve beside the source repository
    fetch() {
        git init -q "$DIR.new"
        git -C "$DIR.new" remote add origin "$REPO"
        git -C "$DIR.new" fetch -q --depth 1 origin "$COMMIT"
        git -C "$DIR.new" -c advice.detachedHead=false checkout -q FETCH_HEAD
    }
    if [ "$(git -C "$DIR" rev-parse HEAD 2> /dev/null)" != "$COMMIT" ]; then
        replace fetch
    fi
fi

applied() {
    for patch in "$SHARED"/patches/anki-*.patch; do
        git -C "$DIR" apply -R --check "$patch" 2> /dev/null || return 1
    done
}
if ! applied; then
    # back to the checkout's sources (target/ and out/ are ignored, so kept)
    git -C "$DIR" checkout -q -- .
    git -C "$DIR" clean -fdq
    for patch in "$SHARED"/patches/anki-*.patch; do
        if ! git -C "$DIR" apply "$patch"; then
            echo "$patch does not apply to $SOURCE; see shared/patches/README.md" >&2
            exit 1
        fi
    done
fi
