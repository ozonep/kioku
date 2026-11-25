"""shared/tools/anki_source.sh --fork checks out the commit a name has in the
fork's repository, as git rev-parse finds it, whether the repository is a URL
(the script reads git ls-remote) or a local clone, and keeps the builds
(target/, out/) of the checkout it replaces. It checked out the nested tag
foo/main's commit for main, and a folder given with a trailing slash was
deleted, builds and all."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "shared" / "tools" / "anki_source.sh"
# git without the user's config (commit signing, hooks)
ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Kioku",
    "GIT_AUTHOR_EMAIL": "kioku@example.invalid",
    "GIT_COMMITTER_NAME": "Kioku",
    "GIT_COMMITTER_EMAIL": "kioku@example.invalid",
}
PATCH = """\
diff --git a/kioku.txt b/kioku.txt
new file mode 100644
--- /dev/null
+++ b/kioku.txt
@@ -0,0 +1 @@
+patched
"""


def git(folder: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(folder), *args], env=ENV, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit_of(fork: Path, name: str) -> str:
    return git(fork, "rev-parse", f"{name}^{{commit}}")


@pytest.fixture
def fork(tmp_path: Path) -> Path:
    """tmp_path/src: main a commit ahead of the branch codex/main, the
    annotated tags v1 and foo/main, and a tag and a branch both named both.
    tmp_path/shared: the script, pinned to src's main, with a patch that adds
    kioku.txt."""
    src = tmp_path / "src"
    git(tmp_path, "init", "-q", "-b", "main", str(src))
    (src / ".gitignore").write_text("/target\n/out\n")  # as Anki's
    for text in ("one", "two"):
        (src / "a.txt").write_text(text)
        git(src, "add", ".")
        git(src, "commit", "-q", "-m", text)
    git(src, "branch", "codex/main", "HEAD~1")
    git(src, "tag", "-a", "-m", "v1", "v1", "HEAD~1")
    git(src, "tag", "-a", "-m", "foo/main", "foo/main", "HEAD~1")
    git(src, "tag", "both", "HEAD~1")
    git(src, "branch", "both", "HEAD")

    shared = tmp_path / "shared"
    (shared / "tools").mkdir(parents=True)
    shutil.copy(SCRIPT, shared / "tools")
    (shared / "versions.env").write_text("ANKI_TAG=0\n")
    (shared / "anki-fork.env").write_text(
        f"ANKI_FORK_REPO={src.as_uri()}\nANKI_FORK_COMMIT={commit_of(src, 'main')}\n"
    )
    (shared / "patches").mkdir()
    (shared / "patches" / "anki-test.patch").write_text(PATCH)
    return src


def source(fork: Path, folder: str, commit: str = "", repo: str = "", cwd: Path | None = None):
    # empty: the pins in anki-fork.env
    env = {**ENV, "KIOKU_ANKI_COMMIT": commit, "KIOKU_ANKI_REPO": repo}
    script = fork.parent / "shared" / "tools" / "anki_source.sh"
    return subprocess.run(
        [str(script), "--fork", folder], cwd=cwd or fork.parent, env=env, capture_output=True, text=True
    )


@pytest.mark.parametrize("how", ["url", "clone"])
def test_names_resolve_as_git_rev_parse(fork: Path, how: str) -> None:
    repo = fork.as_uri() if how == "url" else str(fork)
    anki = fork.parent / "anki"
    names = ["HEAD", "main", "codex/main", "refs/heads/codex/main", "v1", "foo/main", "both"]
    for name in names + [commit_of(fork, "v1")]:
        run = source(fork, str(anki), name, repo)
        assert run.returncode == 0, (name, run.stderr)
        assert git(anki, "rev-parse", "HEAD") == commit_of(fork, name), name
        assert (anki / "kioku.txt").read_text() == "patched\n", name


def test_unknown_names_stop(fork: Path) -> None:
    short = git(fork, "rev-parse", "--short", "HEAD")  # a URL's needs all 40 digits
    for repo, name in [(fork.as_uri(), "nope"), (str(fork), "nope"), (fork.as_uri(), short)]:
        run = source(fork, str(fork.parent / "anki"), name, repo)
        assert run.returncode == 1 and "has no commit" in run.stderr, (repo, name, run.stderr)


def test_clone_path_is_relative_to_the_current_folder(fork: Path) -> None:
    kioku = fork.parent / "kioku"
    kioku.mkdir()
    run = source(fork, "anki", "v1", "../src", cwd=kioku)
    assert run.returncode == 0, run.stderr
    assert git(kioku / "anki", "rev-parse", "HEAD") == commit_of(fork, "v1")
    run = source(fork, "anki", "v1", "src", cwd=kioku)
    assert run.returncode == 1 and "No Anki clone at src" in run.stderr


@pytest.mark.parametrize("slash", ["", "/", "//"])
def test_another_commit_keeps_the_builds(fork: Path, slash: str) -> None:
    anki = fork.parent / "anki"
    assert source(fork, str(anki), "v1").returncode == 0
    (anki / "target" / "release").mkdir(parents=True)
    (anki / "out").mkdir()
    (anki / "out" / "buildhash").write_text("old")
    # the pinned commit; a trailing slash as tab completion adds
    run = source(fork, f"{anki}{slash}")
    assert run.returncode == 0, run.stderr
    assert git(anki, "rev-parse", "HEAD") == commit_of(fork, "main")
    assert (anki / "target" / "release").is_dir()
    assert (anki / "out" / "buildhash").read_text() == "old"
    assert (anki / "kioku.txt").exists()
    assert sorted(p.name for p in fork.parent.iterdir()) == ["anki", "shared", "src"]
