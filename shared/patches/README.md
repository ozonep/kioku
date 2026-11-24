# Patches to Anki's source

Kioku builds the Anki FSRS-7 fork (`ANKI_REPO`, FSRS-7 and RWKV-Instant), not
an Anki release. `shared/tools/anki_source.sh` checks out the fork at
`ANKI_COMMIT` (`shared/versions.env`) and applies every `anki-*.patch` here;
both `fetch_deps.sh` and `shared/tests/run.sh` call it, and
`shared/tools/anki_wheels.sh` builds the fork's Python packages from that
checkout. Changing `ANKI_COMMIT` (and `ANKI_VERSION`, the fork's `.version`)
is enough to move to another commit: the next build replaces the checkout,
applies the patches again and builds new wheels.

To build a commit that isn't pushed yet, from the desktop fork next to this
repository: `KIOKU_ANKI_REPO=../anki KIOKU_ANKI_COMMIT=HEAD ios/tools/build.sh`
(any clone and any commit, branch or tag of it).

`anki-syncserver.patch` adds Kioku's sync server code:

- `rslib/src/sync/http_server/kioku.rs`: the server on a thread an app can
  stop and start again (`pylib/rsbridge/kioku.rs` gives it to Python);
- `rslib/src/sync/http_server/kioku/lossless.rs`: the server passes card data
  and presets on as clients sent them, so that the fork's FSRS-7 and RWKV
  state survives syncing through it, also from a newer fork than the one
  built in; `handlers.rs` uses its functions instead of `sync::collection`'s.

## Keeping patches easy to carry to the next commit

A patch conflicts only where it changes lines that Anki changes too, so:

- Put Kioku's code in **new files** (`kioku.rs` next to the file that needs
  it). New files never conflict.
- Change upstream files only by **anchor lines**: a `mod kioku;`, one call
  into Kioku's code, one replaced expression or `use`.
  `anki-syncserver.patch` changes seven lines of Anki's own files; the rest
  is new files.
- Prefer Python over patches. Kioku changes Anki's Python code at runtime
  (`shared/python/kioku/patches.py` and friends), which never conflicts.
  Replacement functions should take `*args, **kwargs` when they only wrap
  the original, so that new parameters pass through.

## When the fork moves

The daily `Anki update` workflow opens a pull request whose description has
the report of `shared/tools/anki_drift.py`: whether the patches apply, and
each Anki function Kioku replaces that changed (with the diff). To run it by
hand between two commits (or tags) of the fork:

```sh
git clone --filter=blob:none --no-checkout https://github.com/ozonep/anki /tmp/anki
python3 -I shared/tools/anki_drift.py /tmp/anki <old commit> <new commit>
```

If a patch no longer applies, check out the new commit, apply the patch with
`git apply --3way` or by hand, and regenerate it with
`git add -N . && git diff > shared/patches/<name>.patch`. Kioku's server
tests run with the fork's own sync tests:
`cargo test -p anki --lib sync::` in the checkout.
