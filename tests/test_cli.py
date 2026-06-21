import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nexus_cli import app, _BUILTIN_SKILLS, _KNOWLEDGE_DIRS

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
    result = runner.invoke(app, ["skill", "add", "code-review", "--dir", str(tmp_project)])
    assert result.exit_code == 0
    skill_file = tmp_project / ".claude" / "commands" / "code-review.md"
    assert skill_file.exists()
    assert "/code-review" in skill_file.read_text()


def test_skill_add_idempotent(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    runner.invoke(app, ["skill", "add", "code-review", "--dir", str(tmp_project)])
    result = runner.invoke(app, ["skill", "add", "code-review", "--dir", str(tmp_project)])
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
