import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nexus_cli import app, _BUILTIN_SKILLS, _BUILTIN_AGENTS, _KNOWLEDGE_DIRS

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
    assert "nexus" in data["mcpServers"]
    assert data["mcpServers"]["nexus"]["command"] == "uvx"


def test_init_mcp_json_omits_typesafe_extra_by_default(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    data = json.loads((tmp_project / ".mcp.json").read_text())
    assert data["mcpServers"]["nexus"]["args"][2] == "nexus-dev-toolkit"


def test_init_typesafe_flag_adds_extra_to_mcp_json(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--typesafe"])
    assert result.exit_code == 0
    data = json.loads((tmp_project / ".mcp.json").read_text())
    assert data["mcpServers"]["nexus"]["args"][2] == "nexus-dev-toolkit[typesafe]"
    assert "TYPESAFE_API_KEY" in _flat(result.output)


def test_init_no_typesafe_flag_omits_extra(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--no-typesafe"])
    data = json.loads((tmp_project / ".mcp.json").read_text())
    assert data["mcpServers"]["nexus"]["args"][2] == "nexus-dev-toolkit"


def test_init_typesafe_flag_opencode(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode", "--typesafe"])
    data = json.loads((tmp_project / "opencode.json").read_text())
    assert "nexus-dev-toolkit[typesafe]" in data["mcp"]["nexus-mcp"]["command"]


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
    assert data["mcpServers"]["nexus"]["args"][2] == "nexus-dev-toolkit[typesafe]"


def test_init_typesafe_interactive_prompt_empty_defaults_no(monkeypatch, tmp_project):
    import nexus_cli
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    monkeypatch.setattr("sys.stdin", _FakeTTY())
    monkeypatch.setattr("nexus_cli.console.input", lambda prompt: "")
    nexus_cli.init(str(tmp_project), tool="claude", graph_backend=None, typesafe=None)
    data = json.loads((tmp_project / ".mcp.json").read_text())
    assert data["mcpServers"]["nexus"]["args"][2] == "nexus-dev-toolkit"


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
    plugin = tmp_project / ".opencode" / "plugins" / "graphify.js"
    assert plugin.exists()
    assert "tool.execute.after" in plugin.read_text()


def test_init_opencode_creates_opencode_json(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    config = tmp_project / "opencode.json"
    assert config.exists()
    data = json.loads(config.read_text())
    assert "nexus-mcp" in data["mcp"]
    assert data["mcp"]["nexus-mcp"]["type"] == "local"
    assert data["mcp"]["nexus-mcp"]["command"][0] == "uvx"


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
    assert "nexus-dev-toolkit" not in result.output


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
    assert "nexus sync" in _flat(result.output)


def test_update_shows_sync_reminder_even_when_already_up_to_date(monkeypatch):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: nexus_cli._VERSION)
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "nexus sync" in _flat(result.output)


def test_update_with_sync_flag_skips_reminder(monkeypatch, tmp_project):
    import nexus_cli
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: nexus_cli._VERSION)
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["update", "--sync"])
    assert result.exit_code == 0
    assert "Run nexus sync" not in result.output
    assert "isn't a nexus project" in result.output


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
    """After an actual upgrade, sync must run as a fresh `nexus sync` process, not in-process —
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
    assert calls[0] == ["uv", "tool", "upgrade", "nexus-dev-toolkit"]
    assert calls[1] == ["/usr/bin/nexus", "sync", str(tmp_project.resolve())]


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
    assert "Run nexus sync" not in output


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
    assert "nexus sync" in output


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
