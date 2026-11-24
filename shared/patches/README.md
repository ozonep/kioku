# Patches to Anki's source

`shared/tools/anki_source.sh` checks out Anki and applies every
`anki-*.patch` here: Anki at `ANKI_TAG` (`shared/versions.env`) for native
Android, or with `--fork` the Anki FSRS-7 fork at `ANKI_FORK_COMMIT`
(`shared/anki-fork.env`) for the iPhone and iPad and the host tests
(`shared/tests/run.sh`). Changing `ANKI_TAG` or `ANKI_FORK_COMMIT` is enough
to move to another release or commit: the next build replaces the checkout
and applies the patches again.

## The Anki fork

The iPhone and iPad build the fork's Rust core from that checkout and its
Python packages too (`shared/tools/anki_wheels.sh`: PyPI only has upstream
Anki's). Move the fork by hand, to the commit the desktop fork you sync with
runs: set `ANKI_FORK_COMMIT` and `ANKI_FORK_VERSION` (the fork's `.version`
there). The fork's Python, Qt, PyQt6 and package pins must be the ones in
`shared/versions.env` and `requirements.txt` (`shared/tools/anki_pins.py
check`, `update`). The iOS build stops when they differ, e.g. on the `Anki
update` workflow's pull requests, which move those files to Anki's next
release. The phone's sync server keeps only the card data and preset options
its own build knows, so the phone and the desktop should run the same
commit.

To build a commit that isn't pushed yet, from the desktop fork next to this
repository (run from this repository's folder):
`KIOKU_ANKI_REPO=../anki KIOKU_ANKI_COMMIT=HEAD ios/tools/build.sh`
(any clone, and any commit, branch or tag of it).

## Keeping patches easy to carry to the next release

A patch conflicts only where it changes lines that Anki changes too, so:

- Put Kioku's code in **new files** (`kioku.rs` next to the file that needs
  it). New files never conflict.
- Change upstream files only by **anchor lines**: a `mod kioku;`, one call
  into Kioku's code, one replaced expression. `anki-syncserver.patch`
  changes four lines of Anki's own files; the rest is new files.
- Prefer Python over patches. Kioku changes Anki's Python code at runtime
  (`shared/python/kioku/patches.py` and friends), which never conflicts.
  Replacement functions should take `*args, **kwargs` when they only wrap
  the original, so that new parameters pass through.

## When a new release arrives

The daily `Anki update` workflow opens a pull request whose description has
the report of `shared/tools/anki_drift.py`: whether the patches apply, and
each Anki function Kioku replaces that changed (with the diff). To run it by
hand:

```sh
git clone --filter=blob:none --no-checkout https://github.com/ankitects/anki /tmp/anki
git -C /tmp/anki fetch origin tag 26.08.1 tag 26.09.3
python3 -I shared/tools/anki_drift.py /tmp/anki 26.08.1 26.09.3
```

The workflow follows Anki's releases, not the fork. Before you move the
fork, run the report between its two commits in the desktop fork's clone,
with Python 3.12 or newer:
`python3 -I shared/tools/anki_drift.py ../anki <old commit> <new commit>`.

If a patch no longer applies, check out the new tag, apply the patch with
`git apply --3way` or by hand, and regenerate it with
`git add -N . && git diff > shared/patches/<name>.patch`.
