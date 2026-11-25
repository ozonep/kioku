#!/bin/bash
# Host tests for Kioku's Python code (shared/tests) on the build machine:
# in a venv, the Python packages of the Anki fork that the iPhone and iPad
# run, the wheels built from build/host-tests/anki (shared/anki-fork.env with
# shared/patches/ applied, shared/tools/anki_wheels.sh), so their rsbridge
# has Kioku's sync server without touching an iOS build's ios/deps/anki. No
# device needed.
# Usage: shared/tests/run.sh [pytest args]
# Env: PYTHON (default python$PYTHON_VERSION from shared/versions.env, Anki's),
#      KIOKU_ANKI_REPO, KIOKU_ANKI_COMMIT (shared/tools/anki_source.sh)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
source "$ROOT/shared/versions.env"
WORK=$ROOT/build/host-tests
ANKI_SRC=$WORK/anki
VENV=$WORK/venv
PYTHON=${PYTHON:-python$PYTHON_VERSION}

mkdir -p "$WORK"
"$ROOT/shared/tools/anki_source.sh" --fork "$ANKI_SRC"
"$ROOT/shared/tools/anki_wheels.sh" "$ANKI_SRC"

venv_python=$("$VENV/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)
if [ "$venv_python" != "$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')" ]; then
    "$PYTHON" -m venv --clear "$VENV"
fi
# aqt[qt]: PyQt6 and Qt at the versions Anki pins. Each commit of the fork has
# the same version number, so the wheels go in again when they were rebuilt.
ANKI_WHEEL=$(ls "$ANKI_SRC"/out/wheels/anki-*.whl)
AQT_WHEEL=$(ls "$ANKI_SRC"/out/wheels/aqt-*.whl)
wanted="$(cat "$ANKI_SRC/out/wheels/kioku-source") $QT_VERSION"
if [ "$(cat "$VENV/kioku-anki" 2>/dev/null)" != "$wanted" ]; then
    "$VENV/bin/pip" install -q --resume-retries 10 "$ANKI_WHEEL" "aqt[qt] @ file://$AQT_WHEEL" pytest
    "$VENV/bin/pip" install -q --force-reinstall --no-deps "$ANKI_WHEEL" "$AQT_WHEEL"
    echo "$wanted" > "$VENV/kioku-anki"
fi

cd "$ROOT/shared/tests"
exec "$VENV/bin/python" -m pytest -q -p no:cacheprovider "$@"
