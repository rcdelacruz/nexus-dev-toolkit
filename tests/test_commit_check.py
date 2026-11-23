"""Commit messages are checked by commitizen from the first commit, in every clone (nexus init)."""
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

import nexus_cli
from nexus_cli import app

runner = CliRunner()
_REAL_INSTALL = nexus_cli._install_commit_hook          # captured before the autouse fake replaces it
ROOT = Path(__file__).resolve().parent.parent
CFG = ".pre-commit-config.yaml"


def _git_init(p: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main", str(p)], check=True)
    subprocess.run(["git", "-C", str(p), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(p), "config", "user.name", "t"], check=True)
    return p


@pytest.mark.parametrize("role", ["product", "architect", "designer", "developer"])
def test_every_role_gets_the_check(tmp_path, role, _never_install_commit_hooks):
    _git_init(tmp_path)
    r = runner.invoke(app, ["init", str(tmp_path), "--role", role, "--graph-backend", "none"])
    assert r.exit_code == 0, r.output
    text = (tmp_path / CFG).read_text()
    assert "commitizen-tools/commitizen" in text and "id: commitizen" in text
    assert "commit-msg" in text                                    # default_install_hook_types
    assert _never_install_commit_hooks == [tmp_path]               # the hook goes into this clone


@pytest.mark.parametrize("tool", ["opencode", "codex"])
def test_other_tools_get_the_check_too(tmp_path, tool, _never_install_commit_hooks):
    _git_init(tmp_path)
    runner.invoke(app, ["init", str(tmp_path), "--tool", tool, "--graph-backend", "none"])
    assert (tmp_path / CFG).is_file() and _never_install_commit_hooks == [tmp_path]


def test_an_existing_config_is_never_edited(tmp_path, _never_install_commit_hooks):
    _git_init(tmp_path)
    ours = "repos:\n  - repo: local\n    hooks: []\n"
    (tmp_path / CFG).write_text(ours)
    r = runner.invoke(app, ["init", str(tmp_path), "--graph-backend", "none"])
    assert (tmp_path / CFG).read_text() == ours
    assert "no commitizen check" in r.output and _never_install_commit_hooks == []


def test_no_git_repo_says_what_to_do(tmp_path, _never_install_commit_hooks):
    r = runner.invoke(app, ["init", str(tmp_path), "--graph-backend", "none"])
    assert (tmp_path / CFG).is_file() and "not a git repository yet" in r.output
    assert _never_install_commit_hooks == []


def test_sync_sets_it_up_in_an_older_project(tmp_path, _never_install_commit_hooks):
    _git_init(tmp_path)
    runner.invoke(app, ["init", str(tmp_path), "--graph-backend", "none"])
    (tmp_path / CFG).unlink()
    _never_install_commit_hooks.clear()
    r = runner.invoke(app, ["sync", str(tmp_path)])
    assert (tmp_path / CFG).is_file() and _never_install_commit_hooks == [tmp_path], r.output


def test_commands_write_messages_commitizen_accepts():
    """Every commit message a nexus command writes starts with a Conventional Commits type."""
    import re
    types = {"feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"}
    found = []
    for f in (ROOT / "tools" / "epav" / "skills").glob("*.md"):
        for m in re.finditer(r'git commit -m "([^"$]+)"|commit \(`([^`]+)`\)', f.read_text()):
            msg = m.group(1) or m.group(2)
            found.append((f.name, msg))
            assert re.match(r"^[a-z]+(\([^)]+\))?!?: ", msg) and msg.split(":")[0].split("(")[0] in types, (f.name, msg)
    assert len(found) >= 5
    training = (ROOT / "public" / "training.html").read_text()
    for msg in re.findall(r'git commit -m "([^"]+)"', training):
        assert msg.split(":")[0].split("(")[0] in types, msg


def test_the_example_project_keeps_the_check():
    assert "id: commitizen" in (ROOT / "examples" / "clinic-appointments" / CFG).read_text()


@pytest.mark.network
def test_real_hook_refuses_a_bad_message_and_accepts_a_good_one(tmp_path, monkeypatch):
    if not (shutil.which("uvx") and shutil.which("git")):
        pytest.skip("needs uvx and git")
    monkeypatch.setattr(nexus_cli, "_install_commit_hook", _REAL_INSTALL)
    repo = _git_init(tmp_path / "repo")
    r = runner.invoke(app, ["init", str(repo), "--role", "product", "--graph-backend", "none"])
    assert "commit-msg check installed" in r.output, r.output
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    bad = subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "CareSlot: client pack, nexus setup"],
                         capture_output=True, text=True, timeout=600)
    assert bad.returncode != 0
    good = subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "chore: add client pack and nexus setup"],
                          capture_output=True, text=True, timeout=600)
    assert good.returncode == 0, good.stdout + good.stderr
