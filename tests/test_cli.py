import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nexus_cli import app, _BUILTIN_SKILLS, _BUILTIN_AGENTS, _KNOWLEDGE_DIRS, _DOCS_DIRS

runner = CliRunner()


def _flat(output: str) -> str:
    """Collapse Rich's table borders/line-wrapping so substring checks survive wrapped cells."""
    cleaned = re.sub(r"[─-╿]", " ", output)
    return re.sub(r"\s+", " ", cleaned)


@pytest.fixture(autouse=True)
def _no_real_pypi_calls(monkeypatch):
    """doctor()/update() check PyPI for the latest version — never let tests hit the real
    network; tests that care about the version-check behavior override this locally."""
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: None)


@pytest.fixture(autouse=True)
def _opencode_v2_by_default(monkeypatch):
    """init/sync/doctor pick the OpenCode plugin form from the installed version. Pin it so tests
    don't depend on (or shell out to) whatever `opencode` the dev machine has; tests that care
    about v1 or 'not installed' override this locally."""
    monkeypatch.setattr("nexus_cli._opencode_major", lambda: 2)


@pytest.fixture()
def tmp_project(tmp_path):
    return tmp_path


def test_init_creates_commands(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project)])
    assert result.exit_code == 0
    commands_dir = tmp_project / ".claude" / "commands"
    assert commands_dir.exists()
    for skill in _BUILTIN_SKILLS:
        assert (commands_dir / skill).exists(), f"Missing skill: {skill}"


def test_init_creates_agents(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project)])
    assert result.exit_code == 0
    agents_dir = tmp_project / ".claude" / "agents"
    assert agents_dir.exists()
    for agent in _BUILTIN_AGENTS:
        assert (agents_dir / agent).exists(), f"Missing agent: {agent}"



def test_init_creates_knowledge_dirs(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    for d in _KNOWLEDGE_DIRS:
        assert (tmp_project / d).exists(), f"Missing dir: {d}"


def test_init_creates_settings_json(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    settings = tmp_project / ".claude" / "settings.json"
    assert settings.exists()
    data = json.loads(settings.read_text())
    assert "hooks" in data
    assert "PostToolUse" in data["hooks"]


def test_init_creates_mcp_json(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    mcp = tmp_project / ".mcp.json"
    assert mcp.exists()
    data = json.loads(mcp.read_text())
    assert "nexus-jev" in data["mcpServers"]
    assert data["mcpServers"]["nexus-jev"]["command"] == "uvx"


def test_init_mcp_json_omits_typesafe_extra_by_default(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    data = json.loads((tmp_project / ".mcp.json").read_text())
    assert data["mcpServers"]["nexus-jev"]["args"][2] == "nexus-dev-toolkit-jev"


def test_init_typesafe_flag_adds_extra_to_mcp_json(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--typesafe"])
    assert result.exit_code == 0
    data = json.loads((tmp_project / ".mcp.json").read_text())
    assert data["mcpServers"]["nexus-jev"]["args"][2] == "nexus-dev-toolkit-jev[typesafe]"
    assert "TYPESAFE_API_KEY" in _flat(result.output)


def test_init_no_typesafe_flag_omits_extra(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--no-typesafe"])
    data = json.loads((tmp_project / ".mcp.json").read_text())
    assert data["mcpServers"]["nexus-jev"]["args"][2] == "nexus-dev-toolkit-jev"


def test_init_typesafe_flag_opencode(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode", "--typesafe"])
    data = json.loads((tmp_project / "opencode.json").read_text())
    assert "nexus-dev-toolkit-jev[typesafe]" in data["mcp"]["nexus-jev-mcp"]["command"]


def test_init_typesafe_interactive_prompt_yes(monkeypatch, tmp_project):
    # runner.invoke() redirects sys.stdin itself during CLI dispatch, which
    # would silently defeat the _FakeTTY monkeypatch -- call the command
    # function directly instead, matching this file's established pattern
    # for testing interactive prompts (see test_update_interactive_prompt_*).
    import nexus_cli
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    monkeypatch.setattr("sys.stdin", _FakeTTY())
    monkeypatch.setattr("nexus_cli.console.input", lambda prompt: "y")
    nexus_cli.init(str(tmp_project), tool="claude", graph_backend=None, typesafe=None)
    data = json.loads((tmp_project / ".mcp.json").read_text())
    assert data["mcpServers"]["nexus-jev"]["args"][2] == "nexus-dev-toolkit-jev[typesafe]"


def test_init_typesafe_interactive_prompt_empty_defaults_no(monkeypatch, tmp_project):
    import nexus_cli
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    monkeypatch.setattr("sys.stdin", _FakeTTY())
    monkeypatch.setattr("nexus_cli.console.input", lambda prompt: "")
    nexus_cli.init(str(tmp_project), tool="claude", graph_backend=None, typesafe=None)
    data = json.loads((tmp_project / ".mcp.json").read_text())
    assert data["mcpServers"]["nexus-jev"]["args"][2] == "nexus-dev-toolkit-jev"


def test_init_idempotent(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["init", str(tmp_project)])
    assert result.exit_code == 0
    assert "Already initialized" in result.output


def test_skill_add(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["skill", "add", "my-custom-skill", "--dir", str(tmp_project)])
    assert result.exit_code == 0
    skill_file = tmp_project / ".claude" / "commands" / "my-custom-skill.md"
    assert skill_file.exists()
    assert "/my-custom-skill" in skill_file.read_text()


def test_skill_add_idempotent(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    runner.invoke(app, ["skill", "add", "my-custom-skill", "--dir", str(tmp_project)])
    result = runner.invoke(app, ["skill", "add", "my-custom-skill", "--dir", str(tmp_project)])
    assert result.exit_code == 0
    assert "already exists" in result.output


def test_skill_list(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["skill", "list", "--dir", str(tmp_project)])
    assert result.exit_code == 0
    assert "/scaffold" in result.output
    assert "/evaluate" in result.output


def test_rule_add(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["rule", "add", "api-standards", "--dir", str(tmp_project)])
    assert result.exit_code == 0
    rule_file = tmp_project / "knowledge" / "rules" / "api-standards.md"
    assert rule_file.exists()


def test_rule_list(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    runner.invoke(app, ["rule", "add", "api-standards", "--dir", str(tmp_project)])
    result = runner.invoke(app, ["rule", "list", "--dir", str(tmp_project)])
    assert result.exit_code == 0
    assert "api-standards" in result.output


def test_init_opencode_creates_commands(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    assert result.exit_code == 0
    commands_dir = tmp_project / ".opencode" / "commands"
    assert commands_dir.exists()
    for skill in _BUILTIN_SKILLS:
        assert (commands_dir / skill).exists(), f"Missing skill: {skill}"


def test_init_opencode_creates_agents(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    assert result.exit_code == 0
    agents_dir = tmp_project / ".opencode" / "agents"
    assert agents_dir.exists()
    for agent in _BUILTIN_AGENTS:
        assert (agents_dir / agent).exists(), f"Missing agent: {agent}"


def test_init_opencode_creates_plugin(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    plugin = tmp_project / ".opencode" / "plugins" / "graphify" / "index.ts"
    assert plugin.exists()
    assert "execute.after" in plugin.read_text()
    assert not (tmp_project / ".opencode" / "plugins" / "graphify.js").exists()


def test_init_opencode_creates_opencode_json(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    config = tmp_project / "opencode.json"
    assert config.exists()
    data = json.loads(config.read_text())
    assert "nexus-jev-mcp" in data["mcp"]
    assert data["mcp"]["nexus-jev-mcp"]["type"] == "local"
    assert data["mcp"]["nexus-jev-mcp"]["command"][0] == "uvx"


def test_init_opencode_idempotent(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    result = runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    assert result.exit_code == 0
    assert "Already initialized" in result.output


def test_init_unknown_tool(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--tool", "cursor"])
    assert result.exit_code == 1


# ── init: --graph-backend ────────────────────────────────────────────────────

def test_init_defaults_to_graphify_hook_noninteractive(tmp_project):
    """CliRunner has no tty, so omitting --graph-backend must match pre-existing behavior."""
    result = runner.invoke(app, ["init", str(tmp_project)])
    assert result.exit_code == 0
    assert (tmp_project / ".claude" / "settings.json").exists()


def test_init_codegraph_backend_skips_graphify_hook(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "codegraph"])
    assert result.exit_code == 0
    assert not (tmp_project / ".claude" / "settings.json").exists()
    assert "codegraph install && codegraph init" in result.output


def test_init_none_backend_skips_graphify_hook(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "none"])
    assert result.exit_code == 0
    assert not (tmp_project / ".claude" / "settings.json").exists()


def test_init_opencode_codegraph_backend_skips_plugin(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode", "--graph-backend", "codegraph"])
    assert result.exit_code == 0
    assert not (tmp_project / ".opencode" / "plugins" / "graphify.js").exists()
    assert not (tmp_project / ".opencode" / "plugins" / "graphify").exists()


def test_init_unknown_graph_backend(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "bogus"])
    assert result.exit_code == 1


# ── sync ──────────────────────────────────────────────────────────────────────

def test_sync_not_nexus_project(tmp_project):
    result = runner.invoke(app, ["sync", str(tmp_project)])
    assert result.exit_code == 1
    assert "Not a nexus project" in result.output


def test_sync_shows_ok_when_current(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["sync", str(tmp_project)])
    assert result.exit_code == 0
    assert "ok" in result.output


def test_sync_updates_modified_builtin(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    skill_file = tmp_project / ".claude" / "commands" / "scaffold.md"
    skill_file.write_text("# stale content")
    result = runner.invoke(app, ["sync", str(tmp_project)])
    assert result.exit_code == 0
    assert "updated" in result.output
    assert "stale content" not in skill_file.read_text()


def test_sync_skips_custom_files(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    custom = tmp_project / ".claude" / "commands" / "my-custom.md"
    custom.write_text("# custom skill")
    runner.invoke(app, ["sync", str(tmp_project)])
    assert custom.exists()
    assert custom.read_text() == "# custom skill"


def test_sync_opencode(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    result = runner.invoke(app, ["sync", str(tmp_project)])
    assert result.exit_code == 0
    assert ".opencode/commands" in result.output


# ── doctor ────────────────────────────────────────────────────────────────────

def test_doctor_not_initialized(tmp_project):
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    assert result.exit_code == 1
    assert "Not a nexus project" in result.output or "✗" in result.output


def test_doctor_healthy_project(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    assert result.exit_code == 0
    assert "✓" in result.output
    assert f"all {len(_BUILTIN_SKILLS)} present" in result.output
    assert f"all {len(_BUILTIN_AGENTS)} present" in result.output


def test_doctor_missing_skills(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    (tmp_project / ".claude" / "commands" / "scaffold.md").unlink()
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    assert result.exit_code == 0
    assert "missing" in result.output


def test_doctor_missing_graph(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    assert result.exit_code == 0
    assert "not built" in result.output


def test_doctor_shows_backend_conflict_note(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    output = _flat(result.output)
    assert result.exit_code == 0
    assert "alternatives, not companions" in output


# ── doctor: TypeSafe / Jev ───────────────────────────────────────────────────

def test_doctor_typesafe_not_enabled(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    output = _flat(result.output)
    assert "TypeSafe / Jev" in output
    assert "not enabled" in output


def test_doctor_typesafe_wired_but_no_api_key(tmp_project, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    runner.invoke(app, ["init", str(tmp_project), "--typesafe"])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    output = _flat(result.output)
    assert "TYPESAFE_API_KEY not set" in output


def test_doctor_typesafe_enabled_with_api_key(tmp_project, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    runner.invoke(app, ["init", str(tmp_project), "--typesafe"])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    output = _flat(result.output)
    assert "enabled" in output
    assert "TypeSafe-powered" in output


# ── version comparison ───────────────────────────────────────────────────────

def test_version_tuple_strips_local_suffix():
    import nexus_cli
    # e.g. the "-jev" experimental-branch disambiguation marker -- a bare
    # int() per dot-segment would raise on "9-jev" and silently disable the
    # outdated check entirely (caught by _is_outdated's own except clause).
    assert nexus_cli._version_tuple("3.1.9-jev") == (3, 1, 9)
    assert nexus_cli._version_tuple("3.1.9+build.5") == (3, 1, 9)


def test_is_outdated_still_detects_newer_pypi_version_with_local_suffix():
    import nexus_cli
    assert nexus_cli._is_outdated("3.1.9-jev", "99.0.0") is True
    assert nexus_cli._is_outdated("3.1.9-jev", "3.1.9-jev") is False


# ── doctor: version check ────────────────────────────────────────────────────

def test_doctor_shows_update_available(tmp_project, monkeypatch):
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: "99.0.0")
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    output = _flat(result.output)
    assert result.exit_code == 0
    assert "update available" in output
    assert "99.0.0" in output


def test_doctor_shows_up_to_date(tmp_project, monkeypatch):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: nexus_cli._VERSION)
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    output = _flat(result.output)
    assert result.exit_code == 0
    assert "up to date" in output


def test_doctor_skips_version_row_when_pypi_unreachable(tmp_project):
    # the autouse _no_real_pypi_calls fixture already mocks the fetch to None
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    assert result.exit_code == 0
    assert "nexus-dev-toolkit-jev" not in result.output


# ── built-in registration ────────────────────────────────────────────────────
# A skill/agent .md file living under tools/epav/skills/ or tools/agents/ but
# missing from _BUILTIN_SKILLS/_BUILTIN_AGENTS is exactly the bug that shipped
# in v3.1.5 (fixed in v3.1.7) and that update --sync's stale-process bug (fixed
# in v3.1.9) piggybacked on. These tests make "added the file, forgot the list
# entry" fail CI instead of silently shipping.

def test_all_skill_files_are_registered_as_builtin():
    on_disk = {p.name for p in Path("tools/epav/skills").glob("*.md")}
    assert on_disk == set(_BUILTIN_SKILLS), (
        f"tools/epav/skills/*.md and _BUILTIN_SKILLS disagree — "
        f"on disk but not registered: {on_disk - set(_BUILTIN_SKILLS)}; "
        f"registered but missing from disk: {set(_BUILTIN_SKILLS) - on_disk}"
    )


def test_all_agent_files_are_registered_as_builtin():
    on_disk = {p.name for p in Path("tools/agents").glob("*.md")}
    assert on_disk == set(_BUILTIN_AGENTS), (
        f"tools/agents/*.md and _BUILTIN_AGENTS disagree — "
        f"on disk but not registered: {on_disk - set(_BUILTIN_AGENTS)}; "
        f"registered but missing from disk: {set(_BUILTIN_AGENTS) - on_disk}"
    )


# ── update ────────────────────────────────────────────────────────────────────

def test_update_already_up_to_date_skips_upgrade(monkeypatch):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: nexus_cli._VERSION)
    called = {}
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: called.setdefault("ran", True))
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "Already up to date" in result.output
    assert "ran" not in called


def test_update_runs_upgrade_when_outdated(monkeypatch):
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: "99.0.0")
    called = {}
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: called.setdefault("ran", True))
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert called.get("ran") is True
    assert "nexus-jev sync" in _flat(result.output)


def test_update_shows_sync_reminder_even_when_already_up_to_date(monkeypatch):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: nexus_cli._VERSION)
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "nexus-jev sync" in _flat(result.output)


def test_update_with_sync_flag_skips_reminder(monkeypatch, tmp_project):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: nexus_cli._VERSION)
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["update", "--sync"])
    assert result.exit_code == 0
    assert "Run nexus-jev sync" not in result.output
    assert "isn't a nexus-jev project" in result.output


def test_update_with_sync_flag_syncs_current_project(monkeypatch, tmp_project):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: nexus_cli._VERSION)
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    runner.invoke(app, ["init", str(tmp_project)])
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["update", "-s"])
    assert result.exit_code == 0
    output = _flat(result.output)
    assert "Syncing built-ins" in output
    assert "scaffold.md" in output


def test_update_with_sync_flag_reexecs_sync_after_real_upgrade(monkeypatch, tmp_project):
    """After an actual upgrade, sync must run as a fresh `nexus-jev sync` process, not in-process —
    this process's own _BUILTIN_SKILLS/_BUILTIN_AGENTS were imported before the upgrade ran, so
    calling _sync_project() directly here would silently miss anything the upgrade just added."""
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: "99.0.0")
    calls = []
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda cmd, *a, **k: calls.append(cmd))
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: f"/usr/bin/{name}")

    def _boom(root):
        raise AssertionError("_sync_project must not run in-process after a real upgrade")
    monkeypatch.setattr("nexus_cli._sync_project", _boom)

    runner.invoke(app, ["init", str(tmp_project)])
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["update", "--sync"])

    assert result.exit_code == 0
    assert calls[0] == ["uv", "tool", "install", "nexus-dev-toolkit-jev", "--reinstall"]
    assert calls[1] == ["/usr/bin/nexus-jev", "sync", str(tmp_project.resolve())]


def test_update_sync_falls_back_in_process_when_nexus_not_on_path(monkeypatch, tmp_project):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: "99.0.0")
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    runner.invoke(app, ["init", str(tmp_project)])
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["update", "--sync"])
    assert result.exit_code == 0
    output = _flat(result.output)
    assert "Syncing built-ins" in output
    assert "scaffold.md" in output


class _FakeTTY:
    def isatty(self):
        return True


def test_update_interactive_prompt_yes_runs_sync(monkeypatch, tmp_project, capsys):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: nexus_cli._VERSION)
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    monkeypatch.setattr("sys.stdin", _FakeTTY())
    monkeypatch.setattr("nexus_cli.console.input", lambda prompt: "y")
    runner.invoke(app, ["init", str(tmp_project)])
    monkeypatch.chdir(tmp_project)

    nexus_cli.update(also_sync=False)

    output = _flat(capsys.readouterr().out)
    assert "Syncing built-ins" in output
    assert "Run nexus-jev sync" not in output


def test_update_interactive_prompt_no_shows_reminder(monkeypatch, tmp_project, capsys):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: nexus_cli._VERSION)
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    monkeypatch.setattr("sys.stdin", _FakeTTY())
    monkeypatch.setattr("nexus_cli.console.input", lambda prompt: "n")
    runner.invoke(app, ["init", str(tmp_project)])
    monkeypatch.chdir(tmp_project)

    nexus_cli.update(also_sync=False)

    output = _flat(capsys.readouterr().out)
    assert "Syncing built-ins" not in output
    assert "nexus-jev sync" in output


def test_update_interactive_prompt_empty_answer_defaults_no(monkeypatch, tmp_project, capsys):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: nexus_cli._VERSION)
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    monkeypatch.setattr("sys.stdin", _FakeTTY())
    monkeypatch.setattr("nexus_cli.console.input", lambda prompt: "")
    runner.invoke(app, ["init", str(tmp_project)])
    monkeypatch.chdir(tmp_project)

    nexus_cli.update(also_sync=False)

    output = _flat(capsys.readouterr().out)
    assert "Syncing built-ins" not in output


# ── doctor: graph backend detection ─────────────────────────────────────────

def _write_graphify_graph(project: Path) -> None:
    d = project / "graphify-out"
    d.mkdir(parents=True, exist_ok=True)
    (d / "graph.json").write_text("{}")


def _write_codegraph_graph(project: Path) -> None:
    d = project / ".codegraph"
    d.mkdir(parents=True, exist_ok=True)
    (d / "codegraph.db").write_text("")


def test_doctor_shows_codegraph_row(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    assert result.exit_code == 0
    assert "codegraph" in result.output


def test_doctor_both_graphs_present_defaults_to_graphify(tmp_project, monkeypatch):
    monkeypatch.delenv("NEXUS_GRAPH_BACKEND", raising=False)
    runner.invoke(app, ["init", str(tmp_project)])
    _write_graphify_graph(tmp_project)
    _write_codegraph_graph(tmp_project)
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    output = _flat(result.output)
    assert result.exit_code == 0
    assert "both graphify and codegraph graphs present" in output
    assert "using graphify" in output
    assert "graphify wins ties by default" in output


def test_doctor_override_forces_codegraph(tmp_project, monkeypatch):
    monkeypatch.setenv("NEXUS_GRAPH_BACKEND", "codegraph")
    runner.invoke(app, ["init", str(tmp_project)])
    _write_graphify_graph(tmp_project)
    _write_codegraph_graph(tmp_project)
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    output = _flat(result.output)
    assert result.exit_code == 0
    assert "using codegraph" in output
    assert "forced via NEXUS_GRAPH_BACKEND=codegraph" in output


def test_doctor_override_pointing_at_unbuilt_graph_warns(tmp_project, monkeypatch):
    monkeypatch.setenv("NEXUS_GRAPH_BACKEND", "codegraph")
    runner.invoke(app, ["init", str(tmp_project)])
    _write_graphify_graph(tmp_project)  # only graphify built — codegraph override has nothing to use
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    output = _flat(result.output)
    assert result.exit_code == 0
    assert "NEXUS_GRAPH_BACKEND" in output
    assert "ignoring override" in output
    # falls back to graphify since the override can't be honored
    assert "graphify-out/graph.json exists (graphify)" in output


def test_doctor_stale_graphify_hook_warns(tmp_project, monkeypatch):
    monkeypatch.delenv("NEXUS_GRAPH_BACKEND", raising=False)
    runner.invoke(app, ["init", str(tmp_project)])  # scaffolds the graphify PostToolUse hook
    _write_codegraph_graph(tmp_project)  # only codegraph is actually built
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    output = _flat(result.output)
    assert result.exit_code == 0
    assert "Stale hook" in output
    assert "codegraph is the active backend" in output


# ── init --tool codex ────────────────────────────────────────────────────────

import tomllib  # noqa: E402 — test-only; runtime code stays 3.10-compatible

_EPAV_SKILLS_WITHOUT_FRONTMATTER = [
    s for s in _BUILTIN_SKILLS
    if not (Path(__file__).parent.parent / "tools" / "epav" / "skills" / s).read_text().startswith("---")
]


def _frontmatter(text: str) -> dict:
    assert text.startswith("---"), "SKILL.md must start with frontmatter"
    fields = {}
    for line in text.split("---", 2)[1].splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip('"')
    return fields


def test_init_codex_creates_skills(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    assert result.exit_code == 0
    for skill in _BUILTIN_SKILLS:
        stem = Path(skill).stem
        skill_md = tmp_project / ".agents" / "skills" / stem / "SKILL.md"
        assert skill_md.exists(), f"Missing skill: {stem}"
        fields = _frontmatter(skill_md.read_text())
        assert fields.get("name") == stem
        assert fields.get("description"), f"{stem} has an empty description"


def test_init_codex_epav_skills_are_explicit_only(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    assert _EPAV_SKILLS_WITHOUT_FRONTMATTER, "expected some frontmatter-less EPAV skills"
    for skill in _BUILTIN_SKILLS:
        yaml_path = tmp_project / ".agents" / "skills" / Path(skill).stem / "agents" / "openai.yaml"
        if skill in _EPAV_SKILLS_WITHOUT_FRONTMATTER:
            assert "allow_implicit_invocation: false" in yaml_path.read_text()
        else:
            assert not yaml_path.exists(), f"{skill} should stay implicitly invocable"


def test_init_codex_creates_agent_tomls(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    for agent in _BUILTIN_AGENTS:
        toml_path = tmp_project / ".codex" / "agents" / f"{Path(agent).stem}.toml"
        assert toml_path.exists(), f"Missing agent: {agent}"
        data = tomllib.loads(toml_path.read_text())
        assert data["name"] and data["description"] and data["developer_instructions"]
        assert "model" not in data and "tools" not in data


def test_init_codex_creates_config_toml(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    data = tomllib.loads((tmp_project / ".codex" / "config.toml").read_text())
    assert data["mcp_servers"]["nexus-jev"]["command"] == "uvx"
    assert data["mcp_servers"]["nexus-jev"]["args"] == ["--refresh", "--from", "nexus-dev-toolkit-jev", "nexus-jev-mcp"]


def test_init_codex_preserves_existing_config_toml(tmp_project):
    existing = 'model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "other"'
    (tmp_project / ".codex").mkdir()
    (tmp_project / ".codex" / "config.toml").write_text(existing)
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    text = (tmp_project / ".codex" / "config.toml").read_text()
    assert text.startswith(existing)
    data = tomllib.loads(text)
    assert set(data["mcp_servers"]) == {"other", "nexus-jev"}


def test_init_codex_does_not_duplicate_nexus_mcp_entry(tmp_project):
    (tmp_project / ".codex").mkdir()
    (tmp_project / ".codex" / "config.toml").write_text('[mcp_servers.nexus-jev]\ncommand = "custom"\n')
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    text = (tmp_project / ".codex" / "config.toml").read_text()
    assert text.count("[mcp_servers.nexus-jev]") == 1
    assert 'command = "custom"' in text


def test_init_codex_creates_graphify_hook(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    data = json.loads((tmp_project / ".codex" / "hooks.json").read_text())
    entry = data["hooks"]["PostToolUse"][0]
    assert entry["matcher"] == "Edit|Write"
    assert "graphify update" in entry["hooks"][0]["command"]


def test_init_codex_merges_existing_hooks(tmp_project):
    (tmp_project / ".codex").mkdir()
    mine = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}]}}
    (tmp_project / ".codex" / "hooks.json").write_text(json.dumps(mine))
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    data = json.loads((tmp_project / ".codex" / "hooks.json").read_text())
    assert data["hooks"]["Stop"] == mine["hooks"]["Stop"]
    assert "PostToolUse" in data["hooks"]


def test_init_codex_codegraph_backend_skips_hook(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex", "--graph-backend", "codegraph"])
    assert not (tmp_project / ".codex" / "hooks.json").exists()
    assert (tmp_project / ".codex" / "config.toml").exists()


def test_init_codex_idempotent(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    result = runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    assert result.exit_code == 0
    assert "Already initialized" in result.output


def test_sync_codex_updates_modified_skill(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    skill_md = tmp_project / ".agents" / "skills" / "evaluate" / "SKILL.md"
    skill_md.write_text("stale")
    result = runner.invoke(app, ["sync", str(tmp_project)])
    assert result.exit_code == 0
    assert "updated" in result.output
    assert skill_md.read_text() != "stale"
    assert _frontmatter(skill_md.read_text())["name"] == "evaluate"


def test_doctor_codex_project(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    result = runner.invoke(app, ["doctor", str(tmp_project)])
    out = _flat(result.output)
    assert "yes (codex)" in out
    assert "nexus-jev entry present" in out
    assert f"all {len(_BUILTIN_SKILLS)} present" in out
    assert f"all {len(_BUILTIN_AGENTS)} present" in out


def test_codex_hook_counts_as_graphify_hook(tmp_project):
    from tools.epav import graph_backend
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    assert graph_backend.has_graphify_hook(tmp_project)


def test_init_codex_rewrites_skill_refs_to_dollar_syntax(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    apply_md = (tmp_project / ".agents" / "skills" / "apply" / "SKILL.md").read_text()
    assert "$validate" in apply_md and "`/validate`" not in apply_md
    # Claude Code output must keep the slash syntax
    runner.invoke(app, ["init", str(tmp_project)])
    assert "`/validate`" in (tmp_project / ".claude" / "commands" / "apply.md").read_text()


# ── init: docs/ scaffold ─────────────────────────────────────────────────────

@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_init_creates_docs_dirs(tmp_project, tool):
    result = runner.invoke(app, ["init", str(tmp_project), "--tool", tool])
    assert result.exit_code == 0
    for d in _DOCS_DIRS:
        assert (tmp_project / d).is_dir(), f"Missing {d} for --tool {tool}"
        assert f"{d}/" in result.output


def test_init_preserves_existing_docs(tmp_project):
    arch = tmp_project / "docs" / "arch-docs"
    arch.mkdir(parents=True)
    (arch / "ARCH.md").write_text("# my architecture\n")
    result = runner.invoke(app, ["init", str(tmp_project)])
    assert result.exit_code == 0
    assert (arch / "ARCH.md").read_text() == "# my architecture\n"
    assert list(arch.iterdir()) == [arch / "ARCH.md"]
    assert "docs/arch-docs/" not in result.output
    assert "docs/dev-tasks/" in result.output


def test_init_on_existing_project_adds_docs_dirs(tmp_project):
    import shutil
    runner.invoke(app, ["init", str(tmp_project)])
    shutil.rmtree(tmp_project / "docs")
    result = runner.invoke(app, ["init", str(tmp_project)])
    assert result.exit_code == 0
    assert "docs/arch-docs/" in result.output
    assert "Already initialized" not in result.output
    result = runner.invoke(app, ["init", str(tmp_project)])
    assert "Already initialized" in result.output


def test_doctor_docs_dirs_row(tmp_project):
    import shutil
    runner.invoke(app, ["init", str(tmp_project)])
    assert f"all {len(_DOCS_DIRS)} present" in _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    shutil.rmtree(tmp_project / "docs" / "requirements")
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "Docs dirs" in out and "docs/requirements" in out


# ── OpenCode v2 ──────────────────────────────────────────────────────────────

from nexus_cli import _opencode_major as _real_opencode_major, _strip_claude_frontmatter  # noqa: E402

_PLUGIN_V1 = Path(".opencode") / "plugins" / "graphify.js"
_PLUGIN_V2 = Path(".opencode") / "plugins" / "graphify" / "index.ts"


def _closed_frontmatter(text: str) -> tuple[list[str], str]:
    """Strict check: opening `---`, closing `---` on its own line. Returns (field lines, body)."""
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    assert match, "frontmatter must be opened and closed with --- on their own lines"
    return match.group(1).splitlines(), match.group(2)


def test_opencode_agents_have_closed_frontmatter_and_subagent_mode(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    for agent in _BUILTIN_AGENTS:
        fields, body = _closed_frontmatter((tmp_project / ".opencode" / "agents" / agent).read_text())
        assert any(line.startswith("name:") for line in fields), agent
        assert "mode: subagent" in fields, agent
        assert not any(line.startswith(("tools:", "model:")) for line in fields), agent
        assert body.strip(), f"{agent} lost its prompt body"


def test_strip_claude_frontmatter_is_idempotent_and_keeps_existing_mode():
    src = "---\nname: x\ndescription: d\ntools: Read\nmodel: sonnet\n---\n\nBody\n"
    once = _strip_claude_frontmatter(src)
    assert once == "---\nname: x\nmode: subagent\ndescription: d\n---\n\nBody\n"
    assert _strip_claude_frontmatter(once) == once
    assert "mode: primary" in _strip_claude_frontmatter("---\nname: x\nmode: primary\n---\n\nBody\n")
    assert _strip_claude_frontmatter("no frontmatter here") == "no frontmatter here"


def test_init_opencode_v1_writes_v1_plugin(tmp_project, monkeypatch):
    monkeypatch.setattr("nexus_cli._opencode_major", lambda: 1)
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    assert "tool.execute.after" in (tmp_project / _PLUGIN_V1).read_text()
    assert not (tmp_project / _PLUGIN_V2).exists()


def test_init_opencode_undetectable_version_defaults_to_v2(tmp_project, monkeypatch):
    monkeypatch.setattr("nexus_cli._opencode_major", lambda: None)
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    assert (tmp_project / _PLUGIN_V2).exists()
    assert not (tmp_project / _PLUGIN_V1).exists()


def test_v2_plugin_is_a_default_export_with_id_and_setup(tmp_project):
    """v2 rejects plugins without a default { id, setup } export; the v1 named-export shape fails."""
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    text = (tmp_project / _PLUGIN_V2).read_text()
    assert "export default {" in text and 'id: "nexus.graphify"' in text and "setup(ctx" in text
    assert "ctx.location.directory" in text and 'ctx.tool.hook("execute.after"' in text
    assert "execSync" not in text  # must not block the shared v2 service


@pytest.mark.parametrize("version_output, expected", [
    ("opencode v2.2.5\n", 2),
    ("1.0.7\n", 1),
    ("0.15.3\n", 0),
    ("garbage\n", None),
])
def test_opencode_major_parses_version_output(monkeypatch, version_output, expected):
    import types
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: "/fake/opencode")
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: types.SimpleNamespace(stdout=version_output))
    assert _real_opencode_major() == expected


def test_opencode_major_none_when_not_installed_or_failing(monkeypatch):
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: None)
    assert _real_opencode_major() is None

    def boom(*a, **k):
        raise OSError("exec failed")
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: "/fake/opencode")
    monkeypatch.setattr("nexus_cli.subprocess.run", boom)
    assert _real_opencode_major() is None


def test_sync_opencode_repairs_broken_agent_frontmatter(tmp_project):
    """Pre-fix versions glued the closing --- onto the last field, so OpenCode v2 never loaded the agent."""
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    agent = tmp_project / ".opencode" / "agents" / "code-reviewer.md"
    agent.write_text("---\nname: code-reviewer\ndescription: Reviews code.---\n\nBroken body\n")
    result = runner.invoke(app, ["sync", str(tmp_project)])
    assert result.exit_code == 0
    _closed_frontmatter(agent.read_text())
    assert "mode: subagent" in agent.read_text()
    assert "Broken body" not in agent.read_text()


def test_sync_opencode_v2_adds_v2_plugin_and_keeps_legacy(tmp_project, monkeypatch):
    monkeypatch.setattr("nexus_cli._opencode_major", lambda: 1)
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    assert (tmp_project / _PLUGIN_V1).exists() and not (tmp_project / _PLUGIN_V2).exists()

    monkeypatch.setattr("nexus_cli._opencode_major", lambda: 2)
    result = runner.invoke(app, ["sync", str(tmp_project)])
    assert result.exit_code == 0
    assert (tmp_project / _PLUGIN_V2).exists()
    assert (tmp_project / _PLUGIN_V1).exists(), "sync must never delete the other form"


def test_sync_opencode_v1_does_not_create_v2_plugin(tmp_project, monkeypatch):
    monkeypatch.setattr("nexus_cli._opencode_major", lambda: 1)
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    runner.invoke(app, ["sync", str(tmp_project)])
    assert (tmp_project / _PLUGIN_V1).exists()
    assert not (tmp_project / _PLUGIN_V2).exists()


def test_init_opencode_extends_existing_mcp_servers_shape(tmp_project):
    (tmp_project / "opencode.json").write_text(json.dumps(
        {"mcp": {"servers": {"other": {"type": "local", "command": ["x"]}}}}
    ))
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    mcp = json.loads((tmp_project / "opencode.json").read_text())["mcp"]
    assert set(mcp["servers"]) == {"other", "nexus-jev-mcp"}
    assert "nexus-jev-mcp" not in mcp, "must not create a mixed flat + servers shape"


def test_init_opencode_flat_server_named_servers_stays_flat(tmp_project):
    """A v1 server literally named 'servers' has a 'type' key — it is not a v2 servers map."""
    (tmp_project / "opencode.json").write_text(json.dumps(
        {"mcp": {"servers": {"type": "local", "command": ["x"]}}}
    ))
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    mcp = json.loads((tmp_project / "opencode.json").read_text())["mcp"]
    assert "nexus-jev-mcp" in mcp
    assert mcp["servers"] == {"type": "local", "command": ["x"]}


def test_doctor_opencode_accepts_mcp_servers_shape(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    (tmp_project / "opencode.json").write_text(json.dumps(
        {"mcp": {"servers": {"nexus-jev-mcp": {"type": "local", "command": ["uvx"]}}}}
    ))
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "opencode.json" in out and "nexus-jev entry present" in out


def test_doctor_opencode_v2_plugin_present(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "graphify plugin (OpenCode)" in out and "present (v2)" in out


def test_doctor_opencode_v2_warns_on_legacy_v1_plugin(tmp_project, monkeypatch):
    monkeypatch.setattr("nexus_cli._opencode_major", lambda: 1)
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])

    monkeypatch.setattr("nexus_cli._opencode_major", lambda: 2)
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "OpenCode v2 doesn't run it" in out

    runner.invoke(app, ["sync", str(tmp_project)])  # adds the v2 plugin; the legacy file stays
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "ignored by OpenCode v2" in out and "safe to delete" in out


def test_doctor_opencode_v1_warns_on_v2_only_plugin(tmp_project, monkeypatch):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])  # v2 plugin
    monkeypatch.setattr("nexus_cli._opencode_major", lambda: 1)
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "is a v2 plugin" in out and "run nexus-jev sync" in out


def test_doctor_opencode_no_plugin_row_for_codegraph_project(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode", "--graph-backend", "codegraph"])
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "graphify plugin (OpenCode)" not in out


def test_opencode_plugins_count_as_graphify_hook(tmp_project, monkeypatch):
    from tools.epav import graph_backend
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    assert graph_backend.has_graphify_hook(tmp_project)  # v2 form

    other = tmp_project / "v1"
    other.mkdir()
    monkeypatch.setattr("nexus_cli._opencode_major", lambda: 1)
    runner.invoke(app, ["init", str(other), "--tool", "opencode"])
    assert graph_backend.has_graphify_hook(other)  # v1 form


def test_opencode_install_command_is_the_v2_installer():
    """https://opencode.ai/install only installs OpenCode 1; v2 has its own installer URL."""
    from nexus_cli import _TOOL_CHECK
    assert _TOOL_CHECK["opencode"]["install"] == "curl -fsSL https://opencode.ai/v2/install | bash"


def test_doctor_opencode_not_found_hints_v2_installer(tmp_project, monkeypatch):
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: None if name == "opencode" else "/usr/bin/" + name)
    monkeypatch.setattr("nexus_cli._opencode_major", lambda: None)
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "https://opencode.ai/v2/install" in out
    assert "opencode.ai/install |" not in out


# ── Codex + jev identity ─────────────────────────────────────────────────────

def test_init_codex_typesafe_flag_adds_extra_to_config_toml(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex", "--typesafe"])
    data = tomllib.loads((tmp_project / ".codex" / "config.toml").read_text())
    assert data["mcp_servers"]["nexus-jev"]["args"][2] == "nexus-dev-toolkit-jev[typesafe]"


def test_doctor_codex_typesafe_wired_but_no_api_key(tmp_project, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex", "--typesafe"])
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "TypeSafe / Jev" in out and "TYPESAFE_API_KEY not set" in out


def test_no_tool_scaffolds_the_real_package_identity(tmp_project):
    """This build installs beside the real nexus-dev-toolkit; no generated config may point at it,
    or the real package's server would silently start in a jev project. Checked for every tool."""
    for tool in ("claude", "opencode", "codex"):
        runner.invoke(app, ["init", str(tmp_project), "--tool", tool, "--graph-backend", "none"])
    blobs = [
        (tmp_project / ".mcp.json").read_text(),
        (tmp_project / "opencode.json").read_text(),
        (tmp_project / ".codex" / "config.toml").read_text(),
    ]
    for blob in blobs:
        assert "nexus-dev-toolkit-jev" in blob
        assert "nexus-dev-toolkit\"" not in blob and '"nexus-mcp"' not in blob
