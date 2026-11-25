"""Packaging checks for shared/tools/prepare_site.sh and shared/tools/anki_wheels.sh:
- an older fork checkout without WEIGHTS-NOTICE.md, or with no model folders,
  packages without failing; when WEIGHTS-NOTICE.md is present it goes into
  actual model folders only (not __pycache__)
- trimming *.pth and *.int8.bin or removing _aqt/rwkv_inference stops the build
  if a file listed in aqt/rwkv_model.py's RWKV_MODEL_FILES is missing afterwards
  (including when aqt/rwkv_inference itself is absent)
- anki_wheels.sh stops without writing kioku-source when either the anki or
  the aqt wheel is missing after ./ninja wheels"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PREPARE_SITE = ROOT / "shared" / "tools" / "prepare_site.sh"
ANKI_WHEELS = ROOT / "shared" / "tools" / "anki_wheels.sh"
ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Kioku",
    "GIT_AUTHOR_EMAIL": "kioku@example.invalid",
    "GIT_COMMITTER_NAME": "Kioku",
    "GIT_COMMITTER_EMAIL": "kioku@example.invalid",
}


def _git(folder: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(folder), *args],
        env=ENV,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_wheel(path: Path, files: dict[str, bytes | str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def _setup_shared(tmp_path: Path) -> Path:
    shared = tmp_path / "shared"
    (shared / "tools").mkdir(parents=True)
    (shared / "patches").mkdir(parents=True)
    shutil.copy(PREPARE_SITE, shared / "tools")
    shutil.copy(ANKI_WHEELS, shared / "tools")
    (shared / "versions.env").write_text(
        "PYTHON_VERSION=3.13\n"
        "ANKI_PY_VERSION=26.9.4\n"
        "MARKUPSAFE_VERSION=1\n"
        "ORJSON_VERSION=1\n"
    )
    (shared / "requirements.txt").write_text("pure==0\n")
    (shared / "patches" / "anki-test.patch").write_text("# test patch\n")
    return shared


def _setup_sdist(tmp_path: Path) -> Path:
    sdist = tmp_path / "sdist"
    (sdist / "markupsafe-1" / "src" / "markupsafe").mkdir(parents=True)
    (sdist / "markupsafe-1" / "src" / "markupsafe" / "__init__.py").write_text("")
    (sdist / "markupsafe-1" / "src" / "markupsafe" / "_speedups.c").write_text("")
    (sdist / "orjson-1" / "pysrc" / "orjson").mkdir(parents=True)
    (sdist / "orjson-1" / "pysrc" / "orjson" / "__init__.py").write_text("")
    return sdist


def _setup_fake_python(tmp_path: Path) -> Path:
    """Wrapper around sys.executable that satisfies `pip download` offline with
    a dummy wheel and delegates every other invocation (including -I -c)."""
    dummy_whl = tmp_path / "pure-0-py3-none-any.whl"
    _write_wheel(dummy_whl, {"pure/__init__.py": ""})
    wrapper = tmp_path / "fake_python.sh"
    wrapper.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        'if [ "${1:-}" = -m ] && [ "${2:-}" = pip ]; then\n'
        '    while [ "$#" -gt 0 ]; do\n'
        '        if [ "$1" = -d ]; then\n'
        '            mkdir -p "$2"\n'
        f'            cp "{dummy_whl}" "$2/"\n'
        "            exit 0\n"
        "        fi\n"
        "        shift\n"
        "    done\n"
        "    exit 1\n"
        "fi\n"
        f'exec "{sys.executable}" "$@"\n'
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return wrapper


def _setup_anki_with_wheels(
    tmp_path: Path, shared: Path, aqt_files: dict[str, bytes | str]
) -> Path:
    anki = tmp_path / "anki"
    _git(tmp_path, "init", "-q", "-b", "main", str(anki))
    (anki / "README").write_text("anki\n")
    _git(anki, "add", ".")
    _git(anki, "commit", "-q", "-m", "init")
    head = _git(anki, "rev-parse", "HEAD")
    patch_hash = subprocess.run(
        ["git", "hash-object", "--stdin"],
        input=(shared / "patches" / "anki-test.patch").read_bytes(),
        env=ENV,
        check=True,
        capture_output=True,
    ).stdout.decode().strip()
    wheels = anki / "out" / "wheels"
    _write_wheel(wheels / "anki-26.9.4-py3-none-any.whl", {"anki/__init__.py": ""})
    _write_wheel(wheels / "aqt-26.9.4-py3-none-any.whl", aqt_files)
    (wheels / "kioku-source").write_text(f"{head} {patch_hash}\n")
    return anki


def _run_prepare(
    tmp_path: Path, aqt_files: dict[str, bytes | str]
) -> tuple[subprocess.CompletedProcess[str], Path]:
    shared = _setup_shared(tmp_path)
    sdist = _setup_sdist(tmp_path)
    python = _setup_fake_python(tmp_path)
    anki = _setup_anki_with_wheels(tmp_path, shared, aqt_files)
    site = tmp_path / "site"
    res = subprocess.run(
        [str(shared / "tools" / "prepare_site.sh"), str(python), str(sdist), str(site), str(anki)],
        env=ENV,
        capture_output=True,
        text=True,
    )
    return res, site


def test_prepare_site_without_weights_notice_succeeds(tmp_path: Path) -> None:
    """Older compatible fork commit (e.g. d6da559b3): has model folders, no
    WEIGHTS-NOTICE.md."""
    res, site = _run_prepare(
        tmp_path,
        {
            "aqt/rwkv_model.py": (
                "from pathlib import Path\n"
                'RWKV_MODEL_FILES = {"legacy": Path("legacy.bin"), "sm92": Path("sm92/weights.f32.bin")}\n'
            ),
            "aqt/rwkv_inference/legacy.bin": b"ok",
            "aqt/rwkv_inference/legacy.pth": b"drop",
            "aqt/rwkv_inference/sm92/weights.f32.bin": b"ok",
            "aqt/rwkv_inference/sm92/weights.int8.bin": b"drop",
            "_aqt/rwkv_inference/sm92/weights.f32.bin": b"dup",
        },
    )
    assert res.returncode == 0, res.stderr
    rwkv = site / "aqt" / "rwkv_inference"
    assert (rwkv / "legacy.bin").is_file()
    assert (rwkv / "sm92" / "weights.f32.bin").is_file()
    assert not (rwkv / "legacy.pth").exists()
    assert not (rwkv / "sm92" / "weights.int8.bin").exists()
    assert not (site / "_aqt" / "rwkv_inference").exists()


def test_prepare_site_copies_weights_notice_to_model_dirs_only(tmp_path: Path) -> None:
    res, site = _run_prepare(
        tmp_path,
        {
            "aqt/rwkv_model.py": (
                "from pathlib import Path\n"
                'RWKV_MODEL_FILES = {"sm118": Path("sm118/weights.f32.bin")}\n'
            ),
            "aqt/rwkv_inference/WEIGHTS-NOTICE.md": "notice\n",
            "aqt/rwkv_inference/sm118/weights.f32.bin": b"ok",
            "aqt/rwkv_inference/__pycache__/mod.pyc": b"pyc",
        },
    )
    assert res.returncode == 0, res.stderr
    rwkv = site / "aqt" / "rwkv_inference"
    assert (rwkv / "sm118" / "WEIGHTS-NOTICE.md").read_text() == "notice\n"
    assert not (rwkv / "__pycache__" / "WEIGHTS-NOTICE.md").exists()


def test_prepare_site_with_weights_notice_and_no_model_subdirs(tmp_path: Path) -> None:
    res, site = _run_prepare(
        tmp_path,
        {
            "aqt/rwkv_model.py": (
                "from pathlib import Path\n"
                'RWKV_MODEL_FILES = {"legacy": Path("legacy.bin")}\n'
            ),
            "aqt/rwkv_inference/WEIGHTS-NOTICE.md": "notice\n",
            "aqt/rwkv_inference/legacy.bin": b"ok",
        },
    )
    assert res.returncode == 0, res.stderr
    assert (site / "aqt" / "rwkv_inference" / "legacy.bin").is_file()


def test_prepare_site_fails_when_referenced_model_was_trimmed(tmp_path: Path) -> None:
    """If the fork points RWKV_MODEL_FILES at an int8 file that prepare_site.sh
    deletes, packaging must stop and name the missing file."""
    res, _site = _run_prepare(
        tmp_path,
        {
            "aqt/rwkv_model.py": (
                "from pathlib import Path\n"
                'RWKV_MODEL_FILES = {"sm118": Path("sm118/weights.int8.bin")}\n'
            ),
            "aqt/rwkv_inference/sm118/weights.int8.bin": b"int8",
        },
    )
    assert res.returncode != 0
    assert "sm118/weights.int8.bin" in res.stderr


def test_prepare_site_fails_when_rwkv_inference_dir_is_missing(tmp_path: Path) -> None:
    """If a wheel layout change puts weights only under _aqt/rwkv_inference,
    removing _aqt/rwkv_inference must not silently ship a bundle with no models."""
    res, _site = _run_prepare(
        tmp_path,
        {
            "aqt/rwkv_model.py": (
                "from pathlib import Path\n"
                'RWKV_MODEL_FILES = {"sm118": Path("sm118/weights.f32.bin")}\n'
            ),
            "_aqt/rwkv_inference/sm118/weights.f32.bin": b"only-in-_aqt",
        },
    )
    assert res.returncode != 0
    assert "sm118/weights.f32.bin" in res.stderr


@pytest.mark.parametrize("missing", ["anki", "aqt"])
def test_anki_wheels_stops_without_stamp_when_a_wheel_is_missing(
    tmp_path: Path, missing: str
) -> None:
    shared = _setup_shared(tmp_path)
    anki = tmp_path / "anki"
    _git(tmp_path, "init", "-q", "-b", "main", str(anki))
    present = "aqt" if missing == "anki" else "anki"
    ninja = anki / "ninja"
    ninja.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "mkdir -p out/wheels\n"
        f"touch out/wheels/{present}-26.9.4-py3-none-any.whl\n"
    )
    ninja.chmod(ninja.stat().st_mode | stat.S_IXUSR)
    _git(anki, "add", ".")
    _git(anki, "commit", "-q", "-m", "init")

    res = subprocess.run(
        [str(shared / "tools" / "anki_wheels.sh"), str(anki)],
        env=ENV,
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert missing in res.stderr
    assert not (anki / "out" / "wheels" / "kioku-source").exists()


def test_anki_wheels_writes_stamp_and_caches_when_both_exist(tmp_path: Path) -> None:
    shared = _setup_shared(tmp_path)
    anki = tmp_path / "anki"
    _git(tmp_path, "init", "-q", "-b", "main", str(anki))
    calls = tmp_path / "ninja_calls"
    ninja = anki / "ninja"
    ninja.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        f'echo call >> "{calls}"\n'
        "mkdir -p out/wheels\n"
        "touch out/wheels/anki-26.9.4-py3-none-any.whl out/wheels/aqt-26.9.4-py3-none-any.whl\n"
    )
    ninja.chmod(ninja.stat().st_mode | stat.S_IXUSR)
    _git(anki, "add", ".")
    _git(anki, "commit", "-q", "-m", "init")

    for _ in range(2):
        res = subprocess.run(
            [str(shared / "tools" / "anki_wheels.sh"), str(anki)],
            env=ENV,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stderr
    assert (anki / "out" / "wheels" / "kioku-source").is_file()
    assert calls.read_text().splitlines() == ["call"]
