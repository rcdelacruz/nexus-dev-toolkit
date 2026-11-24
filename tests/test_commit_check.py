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
    assert not (tmp_path / CFG).exists() and _never_install_commit_hooks == [], r.output     # only listed
    r = runner.invoke(app, ["sync", str(tmp_path), "--add-missing"])
    assert (tmp_path / CFG).is_file() and _never_install_commit_hooks == [tmp_path], r.output


def test_commands_write_messages_commitizen_accepts():
    """Every commit message a nexus command writes starts with a Conventional Commits type."""
    import re
    types = {"feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"}
    found = []
    for f in (ROOT / "tools" / "epav" / "skills").glob("*.md"):
        for m in re.finditer(r'git commit -m "([^"$]+)"|commit \(`([^`]+)`\)|Suggested commit message: `([^`]+)`', f.read_text()):
            msg = m.group(1) or m.group(2) or m.group(3)
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
    hooks = repo / ".git" / "hooks"
    assert "pre-commit" in (hooks / "pre-commit").read_text() and "pre-commit" in (hooks / "commit-msg").read_text()
    assert "on in this clone" in runner.invoke(app, ["doctor", str(repo)]).output
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    bad = subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "CareSlot: client pack, nexus setup"],
                         capture_output=True, text=True, timeout=600)
    assert bad.returncode != 0
    good = subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "chore: add client pack and nexus setup"],
                          capture_output=True, text=True, timeout=600)
    assert good.returncode == 0, good.stdout + good.stderr


def test_doctor_reports_a_missing_check(tmp_path):
    _git_init(tmp_path)
    runner.invoke(app, ["init", str(tmp_path), "--graph-backend", "none"])
    out = runner.invoke(app, ["doctor", str(tmp_path)]).output
    assert "Commit check" in out and "not installed in this clone" in out      # the install was faked


def test_no_command_commits_by_itself():
    """Only /commit commits and only /create-pr pushes or opens a pull request — the owner's rule:
    every other command writes, checks and stops, so nothing reaches git unreviewed."""
    import re
    for f in (ROOT / "tools" / "epav" / "skills").glob("*.md"):
        if f.name in ("commit.md", "create-pr.md"):
            continue
        text = f.read_text()
        text = text.replace('GIT_INDEX_FILE="$t" git add -A', "")   # /code-review's fingerprint: a throw-away index
        assert not re.search(r"git commit\b|git push\b|gh pr create|git add\b", text), f.name
        if f.name not in ("evaluate.md", "epav.md"):              # they create a task branch, on a yes
            assert "git switch -c" not in text, f.name


def test_commit_and_pr_wait_for_a_human_yes():
    """Owner's rule: commit, push and PR happen only after a person has reviewed them."""
    skills = ROOT / "tools" / "epav" / "skills"
    for name, gate, act in (("commit.md", "READY TO COMMIT", "git commit -m"),
                            ("create-pr.md", "READY — nothing is committed or pushed yet", "git push -u")):
        text = (skills / name).read_text()
        assert gate in text and "explicit yes" in text, name
        assert text.index(gate) < text.index(act), f"{name}: the yes must come before the git step"


def test_code_review_is_recommended_after_validate_never_started():
    """Owner's rule: after /validate, recommend /code-review; don't start it automatically."""
    skills = ROOT / "tools" / "epav" / "skills"
    v = (skills / "validate.md").read_text()
    assert "Recommended next: `/code-review`" in v and "don't start `/code-review` yourself" in v
    assert "Don't start it yourself" in (skills / "epav.md").read_text()
    for f in (skills / "code-review.md", ROOT / "tools" / "agents" / "code-reviewer.md"):
        assert "proactively" not in f.read_text().lower(), f.name
    training = (ROOT / "public" / "training.html").read_text()
    step = training[training.index("Build one task"):]
    step = step[:step.index("</div>\n      </div>")]
    assert step.index('skill">/code-review') < step.index("/commit")


def test_evaluate_recommends_a_task_branch_and_waits():
    """/evaluate and /epav recommend a branch named from the task; it is created only on a yes."""
    skills = ROOT / "tools" / "epav" / "skills"
    for name in ("evaluate.md", "epav.md"):
        text = (skills / name).read_text()
        assert "feat/BOOK-004" in text or "branch recommendation" in text, name
        assert "only" in text[text.index("git switch -c") - 200:text.index("git switch -c") + 80], name
    assert "<type>/<TASK-ID>-<short-slug>" in (skills / "evaluate.md").read_text()


def _fingerprint_cmd(skill):
    text = (ROOT / "tools" / "epav" / "skills" / skill).read_text()
    return next(l.strip() for l in text.splitlines() if l.strip().startswith("t=$(mktemp -u)"))


def test_create_pr_reuses_an_earlier_review_of_the_same_files():
    skills = ROOT / "tools" / "epav" / "skills"
    assert _fingerprint_cmd("code-review.md") == _fingerprint_cmd("create-pr.md")
    cr = (skills / "code-review.md").read_text()
    assert "nexus-code-review" in cr and "tree <the fingerprint>" in cr
    pr = (skills / "create-pr.md").read_text()
    assert "Same fingerprint as the record" in pr and "don't review again" in pr
    assert pr.index("### 3 — Code review") < pr.index("### 4 — Show it all") < pr.index("git commit -m")


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_the_fingerprint_matches_the_commit_and_stages_nothing(tmp_path):
    """Measured on a real repo: the fingerprint taken before /commit equals the commit's tree."""
    cmd = _fingerprint_cmd("code-review.md")
    run = lambda *a: subprocess.run(a, cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    run("git", "init", "-q"); run("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "chore: start")
    (tmp_path / ".gitignore").write_text("*.log\n"); (tmp_path / "x.log").write_text("noise")
    (tmp_path / "a.py").write_text("a = 1\n"); run("git", "add", ".gitignore")
    staged = run("git", "diff", "--cached", "--name-only")
    fp = run("bash", "-c", cmd)
    assert run("git", "diff", "--cached", "--name-only") == staged            # nothing staged by it
    run("git", "add", "-A"); run("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "feat: a")
    assert fp == run("git", "rev-parse", "HEAD^{tree}")
    (tmp_path / "a.py").write_text("a = 2\n")
    assert run("bash", "-c", cmd) != fp                                        # an edit means a new review
    empty = tmp_path / "fresh"; empty.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=empty, check=True); (empty / "b.txt").write_text("b")
    assert subprocess.run(["bash", "-c", cmd], cwd=empty, capture_output=True, text=True).stdout.strip()   # works before the first commit


def test_claude_code_asks_before_git_steps(tmp_path):
    """Claude Code itself prompts before git commit / push / gh pr create (ask beats allow, even in auto mode)."""
    import json
    assert runner.invoke(app, ["init", str(tmp_path), "--graph-backend", "none"]).exit_code == 0
    s = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert s["permissions"]["ask"] == nexus_cli._GIT_ASK_RULES
    assert "Git steps ask first" in runner.invoke(app, ["doctor", str(tmp_path)]).output


def test_ask_rules_merge_into_existing_settings(tmp_path):
    import json
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"ask": ["Bash(rm *)", "Bash(git push *)"]}}))
    nexus_cli._write_claude_settings(tmp_path, graphify_hook=False)
    ask = json.loads((tmp_path / ".claude" / "settings.json").read_text())["permissions"]["ask"]
    assert ask == ["Bash(rm *)", "Bash(git push *)", "Bash(git commit *)", "Bash(gh pr create *)", "Bash(gh pr review *)", "Bash(gh pr comment *)"]


def test_global_copies_are_reported(tmp_path, monkeypatch):
    home = tmp_path / "home-claude"; (home / "commands").mkdir(parents=True)
    (home / "commands" / "commit.md").write_text("# v3 /commit")
    monkeypatch.setattr(nexus_cli, "_GLOBAL_CLAUDE_DIR", home)
    proj = tmp_path / "p"; proj.mkdir()
    r = runner.invoke(app, ["init", str(proj), "--graph-backend", "none"])
    flat = " ".join(r.output.split())                           # rich wraps long lines
    assert "commands/: commit (1) — same names as this project's commands" in flat, r.output
    d = runner.invoke(app, ["doctor", str(proj)], env={"COLUMNS": "400"}).output
    assert "Global command copies" in d and "commands/: commit (1)" in d


def test_opencode_asks_before_git_steps_v2(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(nexus_cli, "_opencode_major", lambda: 2)
    assert runner.invoke(app, ["init", str(tmp_path), "--tool", "opencode", "--graph-backend", "none"]).exit_code == 0
    cfg = json.loads((tmp_path / "opencode.json").read_text())
    assert cfg["permissions"] == [{"action": "shell", "resource": c, "effect": "ask"} for c in nexus_cli._GIT_ASK_COMMANDS]
    assert not nexus_cli._write_opencode_ask_rules(tmp_path)              # second run adds nothing
    d = runner.invoke(app, ["doctor", str(tmp_path)], env={"COLUMNS": "300"}).output
    assert "Git steps ask first (OpenCode)" in d and "on — OpenCode asks" in d


def test_opencode_v1_file_keeps_its_shape(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(nexus_cli, "_opencode_major", lambda: 1)
    (tmp_path / "opencode.json").write_text(json.dumps({"permission": {"bash": "allow", "edit": "ask"}}))
    assert nexus_cli._write_opencode_ask_rules(tmp_path)
    cfg = json.loads((tmp_path / "opencode.json").read_text())
    assert cfg["permission"]["edit"] == "ask" and "permissions" not in cfg
    assert cfg["permission"]["bash"] == {"*": "allow", **{c: "ask" for c in nexus_cli._GIT_ASK_COMMANDS}}
    assert nexus_cli._opencode_asks_first(cfg)


def test_codex_asks_before_git_steps(tmp_path):
    assert runner.invoke(app, ["init", str(tmp_path), "--tool", "codex", "--graph-backend", "none"]).exit_code == 0
    rules = (tmp_path / nexus_cli._CODEX_RULES_REL).read_text()
    for pattern in ('["git", "commit"]', '["git", "push"]', '["gh", "pr", "create"]', '["gh", "pr", "review"]', '["gh", "pr", "comment"]'):
        assert f"pattern = {pattern}" in rules
    assert rules.count('decision = "prompt"') == 5
    d = runner.invoke(app, ["doctor", str(tmp_path)], env={"COLUMNS": "300"}).output
    assert "Git steps ask first (Codex)" in d and "on —" in d
    (tmp_path / nexus_cli._CODEX_RULES_REL).unlink()
    runner.invoke(app, ["sync", str(tmp_path)])
    assert (tmp_path / nexus_cli._CODEX_RULES_REL).read_text() == rules     # sync puts it back


def test_pr_review_covers_every_commit_and_posts_only_after_a_yes():
    s = (ROOT / "tools" / "epav" / "skills" / "pr-review.md").read_text()
    assert "every commit in the PR" in s and "git merge-base" in s
    assert "Without it" in s and ".nexus/reviews/" in s                      # no Artifact tool → Markdown
    assert "only after a yes" in s and "never post on your own" in s
    assert s.index("Post only after an explicit yes") > s.index("gh pr review <n> --approve")
    assert "every commit in the range" in (ROOT / "tools" / "agents" / "pr-verifier.md").read_text()
