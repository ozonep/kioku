#!/bin/bash
# Build Anki's Python packages, the aqt and anki wheels, from the source that
# shared/tools/anki_source.sh --fork checked out, with Anki's own build
# (RELEASE=1 ./ninja wheels: minified web pages, as Anki's releases), into
# <anki dir>/out/wheels. PyPI only has upstream Anki's wheels, and the fork's
# Python code has to come from the same commit as its Rust core: they check
# each other's build hash (out/buildhash: the release build writes the
# commit's, as ios/tools/build_rust.sh does).
#
# Does nothing when the wheels there were built from the same commit and
# Kioku patches (out/wheels/kioku-source), e.g. restored by CI's cache.
#
# Needs what Anki's build needs (docs-site/developers/development.mdx in
# Anki's source): rustup, ninja or n2, rsync and a network connection; the
# build downloads Node, protoc, uv and its Python itself.
# Usage: anki_wheels.sh <anki dir>
set -euo pipefail
SHARED=$(cd "$(dirname "$0")/.." && pwd)
DIR=$(cd "$1" && pwd)
WHEELS=$DIR/out/wheels

have() { compgen -G "$WHEELS/$1-*.whl" > /dev/null; }
SOURCE="$(git -C "$DIR" rev-parse HEAD) $(cat "$SHARED"/patches/anki-*.patch | git hash-object --stdin)"
if [ "$(cat "$WHEELS/kioku-source" 2> /dev/null)" = "$SOURCE" ] && have anki && have aqt; then
    exit 0
fi

cd "$DIR"
echo "Building Anki's wheels at $(git rev-parse HEAD) (a few minutes the first time)"
rm -rf "$WHEELS"
RELEASE=1 ./ninja wheels
have anki && have aqt
echo "$SOURCE" > "$WHEELS/kioku-source"
