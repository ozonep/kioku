#!/bin/bash
# Assemble the site-packages that the iOS and native Android apps bundle:
# Anki's Python packages (aqt is pure Python with the web assets compiled,
# anki's wheel is only used for its Python files), the pure-Python
# dependencies, and the Python halves of orjson and markupsafe (their native
# parts are built into the app or not needed). Anki's packages are PyPI's
# wheels of ANKI_PY_VERSION, or with <anki dir> the wheels that
# shared/tools/anki_wheels.sh builds from that checkout: the iPhone and iPad
# take the Anki fork's (shared/tools/anki_source.sh --fork), which PyPI
# doesn't have.
# Usage: prepare_site.sh <python with pip> <sdist dir> <output dir> [<anki dir>]
set -euo pipefail
SHARED=$(cd "$(dirname "$0")/.." && pwd)
source "$SHARED/versions.env"
PYTHON=$1
SDIST=$2
SITE=$3
ANKI=${4:-}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

grep -vE '^(orjson|rpds-py|markupsafe)==|^ *#' "$SHARED/requirements.txt" > "$TMP/pure.txt"
mkdir -p "$TMP/anki"
if [ -n "$ANKI" ]; then
    "$SHARED/tools/anki_wheels.sh" "$ANKI"
    cp "$ANKI"/out/wheels/aqt-*.whl "$ANKI"/out/wheels/anki-*.whl "$TMP/anki/"
else
    echo "aqt==$ANKI_PY_VERSION" >> "$TMP/pure.txt"
    "$PYTHON" -m pip download -q --no-deps --only-binary :all: \
        --platform manylinux_2_35_x86_64 -d "$TMP/anki" "anki==$ANKI_PY_VERSION"
fi
rm -rf "$SITE" && mkdir -p "$SITE"
"$PYTHON" -m pip download -q --no-deps --only-binary :all: \
    --platform any --python-version "$PYTHON_VERSION" --implementation py --abi none \
    -d "$TMP/wheels" -r "$TMP/pure.txt"
# -DD: today's time, not the wheel's fixed one (2020-02-02 in Anki's wheels),
# so a file of the same size in a new release or build isn't skipped by rsync -a
for w in "$TMP"/wheels/*.whl "$TMP"/anki/*.whl; do unzip -qo -DD "$w" -d "$SITE"; done
find "$SITE" -name '*.so' -delete

# The fork's RWKV models: the app reads them from aqt/rwkv_inference
# (aqt.rwkv_scheduler) with Anki's Rust core. _aqt/rwkv_inference only has
# the build's copies of the same files, and the PyTorch checkpoint and the
# int8 files are for the fork's benchmarks (PyTorch isn't in the apps):
# 84 of aqt's 132 MB. The weights' notice (not under Anki's license) goes
# beside every model that ships, as Anki's build puts it (when the checkout
# has it).
rm -rf "$SITE/_aqt/rwkv_inference"
RWKV=$SITE/aqt/rwkv_inference
if [ -d "$RWKV" ]; then
    find "$RWKV" \( -name '*.pth' -o -name '*.int8.bin' \) -delete
    if [ -f "$RWKV/WEIGHTS-NOTICE.md" ]; then
        for model in "$RWKV"/*/; do
            [ -d "$model" ] || continue
            [ "$(basename "$model")" = __pycache__ ] && continue
            cp "$RWKV/WEIGHTS-NOTICE.md" "$model"
        done
    fi
    "$PYTHON" -I -c 'import pathlib, runpy, sys
aqt = pathlib.Path(sys.argv[1])
gone = [str(f) for f in runpy.run_path(str(aqt / "rwkv_model.py"))["RWKV_MODEL_FILES"].values()
        if not (aqt / "rwkv_inference" / f).is_file()]
sys.exit(f"the bundle lost RWKV models the app loads: {gone}" if gone else 0)' "$SITE/aqt"
fi

cp -R "$SDIST/markupsafe-$MARKUPSAFE_VERSION/src/markupsafe" "$SITE/"
rm -f "$SITE/markupsafe/_speedups.c"
cp -R "$SDIST/orjson-$ORJSON_VERSION/pysrc/orjson" "$SITE/"
