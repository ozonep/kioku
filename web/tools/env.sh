# Sourced by the tools: paths to web/ and to the Kioku repository around it
# (github.com/krmanik/kioku), which provides the shared kioku Python package
# (shared/python), the site-packages, PyQt6 sdists and sip-build of the iOS
# build (ios/build/site, ios/deps/sdist, ios/.venv), host Qt
# (ios/deps/qt/<ver>/macos) and the versions (shared/versions.env: Anki's
# Python, Qt and PyQt6). KIOKU_REPO overrides it.
#
# The apps run the Anki FSRS-7 fork; the web variant still runs upstream
# Anki (ANKI_TAG): its own checkout in deps/anki (tools/fetch_deps.sh) and
# Anki's wheels from PyPI (tools/prepare_site.sh). The fork's newer tokio,
# mio, socket2 and reqwest would need new emscripten patches (patches/),
# and its RWKV models (48 MB) don't fit Cloudflare's 25 MiB per file.
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
KIOKU_REPO=${KIOKU_REPO:-$ROOT/..}
KIOKU_REPO=$(cd "$KIOKU_REPO" && pwd)
source "$KIOKU_REPO/shared/versions.env"
ANKI_SRC=$ROOT/deps/anki
