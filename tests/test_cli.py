import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nexus_cli import app, _BUILTIN_SKILLS, _BUILTIN_AGENTS, _KNOWLEDGE_DIRS

runner = CliRunner()


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
    assert "all 11 present" in result.output
    assert "all 5 present" in result.output


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
