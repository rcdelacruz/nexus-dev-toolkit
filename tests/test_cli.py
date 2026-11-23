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
    monkeypatch.setattr("nexus_cli._fetch_releases", lambda: None)


@pytest.fixture(autouse=True)
def _never_install_for_real(monkeypatch):
    """No test may reinstall the developer's real nexus (`uv tool install …` / `pip install …`).
    Tests that check an install replace subprocess.run themselves."""
    import subprocess as _sp
    real = _sp.run

    def guard(cmd, *a, **k):
        words = list(cmd) if isinstance(cmd, (list, tuple)) else str(cmd).split()
        if "install" in words and ("tool" in words or "pip" in words):
            raise AssertionError(f"test tried a real install: {words}")
        return real(cmd, *a, **k)
    monkeypatch.setattr("nexus_cli.subprocess.run", guard)
    # a test runner launched through `uv run --with …` lives in uv's cache, like uvx — tests that
    # need the uvx path set it themselves
    monkeypatch.setattr("nexus_cli._via_uvx", lambda: False)


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
    plugin = tmp_project / ".opencode" / "plugins" / "graphify" / "index.ts"
    assert plugin.exists()
    assert "execute.after" in plugin.read_text()
    assert not (tmp_project / ".opencode" / "plugins" / "graphify.js").exists()


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
    assert "graphify" not in (tmp_project / ".claude" / "settings.json").read_text()
    assert "codegraph install && codegraph init" in result.output


def test_init_none_backend_skips_graphify_hook(tmp_project):
    result = runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "none"])
    assert result.exit_code == 0
    assert "graphify" not in (tmp_project / ".claude" / "settings.json").read_text()


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
    assert calls[0] == ["uv", "tool", "install", "--reinstall", "nexus-dev-toolkit"]  # never `uv tool upgrade`, never a pin
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


# ── init --tool codex ────────────────────────────────────────────────────────

try:  # noqa: E402 — test-only; runtime code stays 3.10-compatible
    import tomllib
except ModuleNotFoundError:  # Python 3.10: same API from the tomli backport
    import tomli as tomllib

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
    assert data["mcp_servers"]["nexus"]["command"] == "uvx"
    assert data["mcp_servers"]["nexus"]["args"][-1] == "nexus-mcp"


def test_init_codex_preserves_existing_config_toml(tmp_project):
    existing = 'model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "other"'
    (tmp_project / ".codex").mkdir()
    (tmp_project / ".codex" / "config.toml").write_text(existing)
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    text = (tmp_project / ".codex" / "config.toml").read_text()
    assert text.startswith(existing)
    data = tomllib.loads(text)
    assert set(data["mcp_servers"]) == {"other", "nexus"}


def test_init_codex_does_not_duplicate_nexus_mcp_entry(tmp_project):
    (tmp_project / ".codex").mkdir()
    (tmp_project / ".codex" / "config.toml").write_text('[mcp_servers.nexus]\ncommand = "custom"\n')
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    text = (tmp_project / ".codex" / "config.toml").read_text()
    assert text.count("[mcp_servers.nexus]") == 1
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
    assert "nexus entry present" in out
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
    # v4: the guide is added next to existing docs (never over them); nothing else is written
    assert sorted(f.name for f in arch.iterdir()) == ["ARCH.md", "ARCHITECTURE-GUIDE.md"]
    assert "docs/arch-docs/\n" not in result.output and "docs/arch-docs/ " not in result.output
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
    assert set(mcp["servers"]) == {"other", "nexus-mcp"}
    assert "nexus-mcp" not in mcp, "must not create a mixed flat + servers shape"


def test_init_opencode_flat_server_named_servers_stays_flat(tmp_project):
    """A v1 server literally named 'servers' has a 'type' key — it is not a v2 servers map."""
    (tmp_project / "opencode.json").write_text(json.dumps(
        {"mcp": {"servers": {"type": "local", "command": ["x"]}}}
    ))
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    mcp = json.loads((tmp_project / "opencode.json").read_text())["mcp"]
    assert "nexus-mcp" in mcp
    assert mcp["servers"] == {"type": "local", "command": ["x"]}


def test_doctor_opencode_accepts_mcp_servers_shape(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    (tmp_project / "opencode.json").write_text(json.dumps(
        {"mcp": {"servers": {"nexus-mcp": {"type": "local", "command": ["uvx"]}}}}
    ))
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "opencode.json" in out and "nexus entry present" in out


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
    assert "is a v2 plugin" in out and "run nexus sync" in out


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


# ── v4: manifest, safe sync, channels (rule 6) ───────────────────────────────

import nexus_cli  # noqa: E402
from tools import channel as _channel  # noqa: E402


def _manifest(root):
    return json.loads((root / ".nexus" / "manifest.json").read_text())


def test_init_records_manifest_for_every_builtin(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    m = _manifest(tmp_project)
    assert m["nexus_version"] == nexus_cli._VERSION
    assert set(m["files"]) == set(nexus_cli._builtin_files(tmp_project))
    assert ".claude/commands/evaluate.md" in m["files"]
    assert ".mcp.json" not in m["files"]          # merged user configs are never "owned"
    assert (tmp_project / ".nexus" / ".gitignore").read_text().splitlines()[-1] == "*"


def test_sync_backs_up_an_edited_builtin_before_replacing_it(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    f = tmp_project / ".claude" / "commands" / "plan.md"
    f.write_text("my team's own plan rules")
    result = runner.invoke(app, ["sync", str(tmp_project)])
    assert "previous copy saved" in _flat(result.output)
    backups = list((tmp_project / ".nexus" / "backup").rglob("plan.md"))
    assert len(backups) == 1 and backups[0].read_text() == "my team's own plan rules"
    assert f.read_text() == (nexus_cli._SKILLS_SRC / "plan.md").read_text()


def test_sync_does_not_back_up_untouched_files(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    runner.invoke(app, ["sync", str(tmp_project)])
    assert not (tmp_project / ".nexus" / "backup").exists()


def test_sync_removes_dropped_builtin_only_if_unedited(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    old = _manifest(tmp_project)
    for name, text in {"retired.md": "old skill", "retired-edited.md": "old skill"}.items():
        (tmp_project / ".claude" / "commands" / name).write_text(text)
        old["files"][f".claude/commands/{name}"] = _channel.sha("old skill")
    (tmp_project / ".claude" / "commands" / "retired-edited.md").write_text("old skill + my notes")
    (tmp_project / ".nexus" / "manifest.json").write_text(json.dumps(old))
    output = _flat(runner.invoke(app, ["sync", str(tmp_project)]).output)
    assert not (tmp_project / ".claude" / "commands" / "retired.md").exists()
    assert (tmp_project / ".claude" / "commands" / "retired-edited.md").exists()
    assert "removed" in output and "you edited it" in output


def test_sync_never_touches_files_it_did_not_write(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    mine = tmp_project / ".claude" / "commands" / "my-own-skill.md"
    mine.write_text("custom")
    runner.invoke(app, ["sync", str(tmp_project)])
    assert mine.read_text() == "custom"


def test_sync_moves_mcp_configs_to_the_cli_channel(tmp_project, monkeypatch):
    runner.invoke(app, ["init", str(tmp_project)])                       # written as stable/plain? depends on _VERSION
    monkeypatch.setattr(nexus_cli, "_VERSION", "4.0.0a2")
    runner.invoke(app, ["sync", str(tmp_project)])
    args = json.loads((tmp_project / ".mcp.json").read_text())["mcpServers"]["nexus"]["args"]
    assert args[args.index("--from") + 1] == "nexus-dev-toolkit>=4.0.0a0"
    monkeypatch.setattr(nexus_cli, "_VERSION", "4.0.0")
    runner.invoke(app, ["sync", str(tmp_project)])
    args = json.loads((tmp_project / ".mcp.json").read_text())["mcpServers"]["nexus"]["args"]
    assert args[args.index("--from") + 1] == "nexus-dev-toolkit"


def test_sync_moves_codex_and_opencode_mcp_too(tmp_project, monkeypatch):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    runner.invoke(app, ["init", str(tmp_project), "--tool", "opencode"])
    monkeypatch.setattr(nexus_cli, "_VERSION", "4.0.0a2")
    runner.invoke(app, ["sync", str(tmp_project)])
    assert '"nexus-dev-toolkit>=4.0.0a0"' in (tmp_project / ".codex" / "config.toml").read_text()
    oc = json.loads((tmp_project / "opencode.json").read_text())
    cmd = (oc["mcp"].get("servers") or oc["mcp"])["nexus-mcp"]["command"]
    assert "nexus-dev-toolkit>=4.0.0a0" in cmd


def test_sync_leaves_a_custom_mcp_command_alone(tmp_project, monkeypatch):
    runner.invoke(app, ["init", str(tmp_project)])
    (tmp_project / ".mcp.json").write_text(json.dumps({"mcpServers": {"nexus": {"command": "/opt/nexus-mcp", "args": []}}}))
    monkeypatch.setattr(nexus_cli, "_VERSION", "4.0.0a2")
    runner.invoke(app, ["sync", str(tmp_project)])
    assert json.loads((tmp_project / ".mcp.json").read_text())["mcpServers"]["nexus"] == {"command": "/opt/nexus-mcp", "args": []}


def test_doctor_warns_when_this_checkout_was_synced_by_a_newer_nexus(tmp_project, monkeypatch):
    runner.invoke(app, ["init", str(tmp_project)])
    m = _manifest(tmp_project)
    m["nexus_version"] = "4.0.0b1"
    (tmp_project / ".nexus" / "manifest.json").write_text(json.dumps(m))
    monkeypatch.setattr(nexus_cli, "_VERSION", "3.2.0")
    output = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "newer than the nexus you are running (v3.2.0)" in output and "nexus channel v4" in output


def test_doctor_reports_environment(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    assert "Python 3." in _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)


def test_update_on_pre_channel_follows_pre_releases(monkeypatch, tmp_project):
    monkeypatch.setattr(nexus_cli, "_VERSION", "4.0.0a1")
    monkeypatch.setattr("nexus_cli._fetch_releases", lambda: ["3.2.0", "4.0.0a1", "4.0.0a2"])
    calls = []
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda cmd, *a, **k: calls.append(cmd))
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert calls[0] == ["uv", "tool", "install", "--reinstall", "nexus-dev-toolkit>=4.0.0a0"]
    assert "4.0.0a2" in result.output


def test_update_graduates_to_stable_when_final_is_out(monkeypatch, tmp_project):
    monkeypatch.setattr(nexus_cli, "_VERSION", "4.0.0rc1")
    monkeypatch.setattr("nexus_cli._fetch_releases", lambda: ["3.2.0", "4.0.0rc1", "4.0.0"])
    calls = []
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda cmd, *a, **k: calls.append(cmd))
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["update"])
    assert calls[0] == ["uv", "tool", "install", "--reinstall", "nexus-dev-toolkit"]
    assert "stable channel" in _flat(result.output)


def test_update_failed_install_says_so(monkeypatch, tmp_project):
    monkeypatch.setattr("nexus_cli._fetch_latest_pypi_version", lambda: "99.0.0")
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: type("R", (), {"returncode": 1})())
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 1 and "Install failed" in result.output


def test_channel_stable_removes_v4_only_files_and_resets_mcp(monkeypatch, tmp_project):
    monkeypatch.setattr(nexus_cli, "_VERSION", "4.0.0a2")
    monkeypatch.setattr(nexus_cli, "_ADDED_IN_V4", ["plan.md"])     # pretend plan.md is a v4-only skill
    runner.invoke(app, ["init", str(tmp_project)])
    calls = []
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda cmd, *a, **k: calls.append(cmd))
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: f"/usr/bin/{name}")
    result = runner.invoke(app, ["channel", "stable", "--project", str(tmp_project)])
    assert result.exit_code == 0, result.output
    assert not (tmp_project / ".claude" / "commands" / "plan.md").exists()
    args = json.loads((tmp_project / ".mcp.json").read_text())["mcpServers"]["nexus"]["args"]
    assert args[args.index("--from") + 1] == "nexus-dev-toolkit"
    assert calls[0] == ["uv", "tool", "install", "--reinstall", "nexus-dev-toolkit"]
    assert calls[1] == ["/usr/bin/nexus", "sync", str(tmp_project.resolve())]


def test_channel_v4_installs_the_pre_release_range(monkeypatch, tmp_project):
    calls = []
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda cmd, *a, **k: calls.append(cmd))
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: f"/usr/bin/{name}")
    result = runner.invoke(app, ["channel", "v4", "--project", str(tmp_project)])
    assert result.exit_code == 0
    assert calls == [["uv", "tool", "install", "--reinstall", "nexus-dev-toolkit>=4.0.0a0"]]


def test_channel_rejects_unknown(tmp_project):
    assert runner.invoke(app, ["channel", "beta"]).exit_code == 1


def test_first_v4_sync_of_a_3x_project_keeps_edited_builtins(tmp_project):
    """A project synced by 3.x has no manifest, so nexus can't tell an edit from an older nexus
    copy — it keeps a copy of anything it replaces instead of guessing."""
    runner.invoke(app, ["init", str(tmp_project)])
    import shutil as _sh
    _sh.rmtree(tmp_project / ".nexus")                                   # as if synced by 3.x
    f = tmp_project / ".claude" / "commands" / "evaluate.md"
    f.write_text("team-specific evaluate steps")
    runner.invoke(app, ["sync", str(tmp_project)])
    backups = list((tmp_project / ".nexus" / "backup").rglob("evaluate.md"))
    assert len(backups) == 1 and backups[0].read_text() == "team-specific evaluate steps"


# ── v4: roles and guides ─────────────────────────────────────────────────────

def test_architect_role_gets_only_its_commands(tmp_project):
    r = runner.invoke(app, ["init", str(tmp_project), "--role", "architect"])
    assert r.exit_code == 0, r.output
    cmds = sorted(f.name for f in (tmp_project / ".claude" / "commands").iterdir())
    assert cmds == ["architect.md", "change-request.md", "commit.md", "create-pr.md", "requirements.md"]
    assert not (tmp_project / ".claude" / "agents").exists() or not any((tmp_project / ".claude" / "agents").iterdir())
    assert "graphify" not in (tmp_project / ".claude" / "settings.json").read_text()   # no graphify hook — no code
    assert (tmp_project / ".mcp.json").exists()                              # role commands use the MCP tools
    assert _manifest(tmp_project)["role"] == "architect"


def test_designer_role_on_codex(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex", "--role", "designer"])
    skills = sorted(d.name for d in (tmp_project / ".agents" / "skills").iterdir())
    assert skills == ["change-request", "commit", "create-pr", "design"]
    assert (tmp_project / ".agents" / "skills" / "design" / "agents" / "openai.yaml").exists()   # explicit-only
    assert not (tmp_project / ".codex" / "hooks.json").exists()


def test_sync_keeps_the_role(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--role", "designer"])
    runner.invoke(app, ["sync", str(tmp_project)])
    assert sorted(f.name for f in (tmp_project / ".claude" / "commands").iterdir()) == ["change-request.md", "commit.md", "create-pr.md", "design.md"]


def test_doctor_checks_the_role_set(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--role", "designer"])
    out = _flat(runner.invoke(app, ["doctor", str(tmp_project)]).output)
    assert "designer — commit, create-pr, design, change-request" in out
    assert "all 4 present" in out and "none needed (designer role)" in out


def test_unknown_role(tmp_project):
    assert runner.invoke(app, ["init", str(tmp_project), "--role", "boss"]).exit_code == 1


def test_guides_are_written_once_and_never_overwritten(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    for rel in ("docs/requirements/REQUIREMENTS-GUIDE.md", "docs/arch-docs/ARCHITECTURE-GUIDE.md", "docs/designs/DESIGN-GUIDE.md"):
        assert "```nexus-guide" in (tmp_project / rel).read_text()
    g = tmp_project / "docs" / "arch-docs" / "ARCHITECTURE-GUIDE.md"
    g.write_text("our own rules")
    runner.invoke(app, ["sync", str(tmp_project)])
    assert g.read_text() == "our own rules"
    assert "docs/arch-docs/ARCHITECTURE-GUIDE.md" not in _manifest(tmp_project)["files"]


def test_codeowners_is_a_template_not_live(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    assert (tmp_project / ".github" / "CODEOWNERS.nexus-template").exists()
    assert not (tmp_project / ".github" / "CODEOWNERS").exists()


def test_existing_codeowners_means_no_template(tmp_project):
    (tmp_project / ".github").mkdir()
    (tmp_project / ".github" / "CODEOWNERS").write_text("* @me\n")
    runner.invoke(app, ["init", str(tmp_project)])
    assert not (tmp_project / ".github" / "CODEOWNERS.nexus-template").exists()


def test_sync_adds_missing_guides_to_an_existing_project(tmp_project):
    runner.invoke(app, ["init", str(tmp_project)])
    (tmp_project / "docs" / "designs" / "DESIGN-GUIDE.md").unlink()
    out = _flat(runner.invoke(app, ["sync", str(tmp_project)]).output)
    assert (tmp_project / "docs" / "designs" / "DESIGN-GUIDE.md").exists() and "never overwritten" in out


def test_channel_stable_removes_the_real_v4_commands_on_every_tool(monkeypatch, tmp_project):
    monkeypatch.setattr(nexus_cli, "_VERSION", "4.0.0b1")
    runner.invoke(app, ["init", str(tmp_project)])
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex"])
    (tmp_project / ".claude" / "commands" / "architect.md").write_text("our edits")   # edited → kept
    monkeypatch.setattr("nexus_cli.subprocess.run", lambda *a, **k: None)
    monkeypatch.setattr("nexus_cli.shutil.which", lambda name: f"/usr/bin/{name}")
    out = _flat(runner.invoke(app, ["channel", "stable", "--project", str(tmp_project)]).output)
    cmds = {f.name for f in (tmp_project / ".claude" / "commands").iterdir()}
    assert {"design.md", "requirements.md", "change-request.md"}.isdisjoint(cmds)
    assert "architect.md" in cmds and "you edited it" in out
    assert not (tmp_project / ".agents" / "skills" / "design").exists()       # whole Codex skill folder
    assert "evaluate.md" in cmds                                              # 3.x skills stay


def test_product_role_gets_brd_prd_and_templates(tmp_project):
    r = runner.invoke(app, ["init", str(tmp_project), "--role", "product"])
    assert r.exit_code == 0, r.output
    cmds = sorted(f.name for f in (tmp_project / ".claude" / "commands").iterdir())
    assert cmds == ["brd.md", "change-request.md", "commit.md", "create-pr.md", "prd.md", "requirements.md"]
    for name in ("BRD-TEMPLATE.md", "PRD-TEMPLATE.md"):
        assert (tmp_project / "docs" / "requirements" / "templates" / name).is_file()
    assert _manifest(tmp_project)["role"] == "product"


def test_brd_and_prd_are_explicit_only_on_codex(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex", "--role", "product"])
    for name in ("brd", "prd"):
        assert (tmp_project / ".agents" / "skills" / name / "agents" / "openai.yaml").is_file()


def test_nexus_mcp_from_points_configs_at_a_local_build(tmp_project, monkeypatch):
    monkeypatch.setenv("NEXUS_MCP_FROM", str(tmp_project / "checkout"))
    runner.invoke(app, ["init", str(tmp_project)])
    args = json.loads((tmp_project / ".mcp.json").read_text())["mcpServers"]["nexus"]["args"]
    assert args[args.index("--from") + 1] == str((tmp_project / "checkout").resolve())
    monkeypatch.delenv("NEXUS_MCP_FROM")
    runner.invoke(app, ["sync", str(tmp_project)])          # sync leaves a local source alone
    args = json.loads((tmp_project / ".mcp.json").read_text())["mcpServers"]["nexus"]["args"]
    assert args[args.index("--from") + 1] == str((tmp_project / "checkout").resolve())


@pytest.mark.parametrize("role", ["developer", "product", "architect", "designer"])
def test_init_approves_the_nexus_mcp_server_for_every_role(tmp_project, role):
    runner.invoke(app, ["init", str(tmp_project), "--role", role, "--graph-backend", "none"])
    s = json.loads((tmp_project / ".claude" / "settings.json").read_text())
    assert s["enabledMcpjsonServers"] == ["nexus"] and "mcp__nexus__*" in s["permissions"]["allow"]


def test_settings_merge_keeps_the_users_keys(tmp_project):
    (tmp_project / ".claude").mkdir()
    (tmp_project / ".claude" / "settings.json").write_text(json.dumps(
        {"model": "opus", "permissions": {"allow": ["Bash(npm test)"]}, "enabledMcpjsonServers": ["db"]}))
    runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "graphify"])
    s = json.loads((tmp_project / ".claude" / "settings.json").read_text())
    assert s["model"] == "opus" and s["enabledMcpjsonServers"] == ["db", "nexus"]
    assert s["permissions"]["allow"] == ["Bash(npm test)", "mcp__nexus__*"]
    assert "graphify update" in json.dumps(s["hooks"])
    runner.invoke(app, ["sync", str(tmp_project)])                         # idempotent
    assert json.loads((tmp_project / ".claude" / "settings.json").read_text()) == s


def test_mcp_config_runs_a_locally_installed_build(tmp_project, monkeypatch, tmp_path):
    wheel = tmp_path / "nexus_dev_toolkit-4.0.0a1-py3-none-any.whl"
    wheel.write_text("x")
    monkeypatch.setattr(nexus_cli, "_local_build", lambda: str(wheel))
    monkeypatch.delenv("NEXUS_MCP_FROM", raising=False)
    runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "none"])
    args = json.loads((tmp_project / ".mcp.json").read_text())["mcpServers"]["nexus"]["args"]
    assert args[args.index("--from") + 1] == str(wheel)


@pytest.mark.parametrize("role, first", [("product", "/brd"), ("architect", "/architect"), ("designer", "/design"), ("developer", "/scaffold")])
def test_init_names_the_roles_first_command(tmp_project, role, first):
    out = runner.invoke(app, ["init", str(tmp_project), "--role", role, "--graph-backend", "none"]).output
    assert first in out.split("Done.")[-1]


# ── a preview installed from git ─────────────────────────────────────────────

_GIT = "https://github.com/rcdelacruz/nexus-dev-toolkit"


def _git_info(commit):
    return {"url": _GIT, "vcs_info": {"vcs": "git", "commit_id": commit, "requested_revision": "v4-preview"}}


def test_update_on_a_git_install_reinstalls_the_branch_not_pypi(monkeypatch):
    commits = iter(["a" * 40, "b" * 40])
    state = {"info": _git_info(next(commits))}
    monkeypatch.setattr(nexus_cli, "_direct_url", lambda: state["info"])
    monkeypatch.setattr(nexus_cli, "_fetch_releases", lambda: pytest.fail("a git install must not ask PyPI"))
    monkeypatch.setattr(nexus_cli.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    ran = []

    def fake_run(cmd, *a, **k):
        ran.append(cmd)
        state["info"] = _git_info(next(commits))
        return type("R", (), {"returncode": 0})()
    monkeypatch.setattr(nexus_cli.subprocess, "run", fake_run)
    out = _flat(runner.invoke(app, ["update"]).output)
    assert ran == [["uv", "tool", "install", "--reinstall", f"git+{_GIT}@v4-preview"]]
    assert "aaaaaaa → bbbbbbb" in out and "nexus sync" in out


def test_sync_moves_a_git_mcp_entry_to_the_installed_commit(tmp_project, monkeypatch):
    monkeypatch.delenv("NEXUS_MCP_FROM", raising=False)
    monkeypatch.setattr(nexus_cli, "_direct_url", lambda: _git_info("a" * 40))
    runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "none"])
    frm = lambda: (lambda a: a[a.index("--from") + 1])(  # noqa: E731
        json.loads((tmp_project / ".mcp.json").read_text())["mcpServers"]["nexus"]["args"])
    assert frm() == f"git+{_GIT}@{'a' * 40}"
    monkeypatch.setattr(nexus_cli, "_direct_url", lambda: _git_info("b" * 40))   # after nexus update
    runner.invoke(app, ["sync", str(tmp_project)])
    assert frm() == f"git+{_GIT}@{'b' * 40}"
    monkeypatch.setattr(nexus_cli, "_direct_url", lambda: {})                     # nexus channel stable
    monkeypatch.setattr(nexus_cli.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())
    runner.invoke(app, ["channel", "stable", "--project", str(tmp_project)], input="n\n")
    assert frm() == "nexus-dev-toolkit"


def _no_install(*a, **k):
    pytest.fail("running through uvx must never install")


def test_update_through_the_nexus4_alias_installs_nothing(tmp_project, monkeypatch):
    # `alias nexus4="uvx --refresh --from 'git+…@v4-preview' nexus"`: `nexus4 update` once replaced
    # the person's installed nexus 3 with the preview
    monkeypatch.setattr(nexus_cli, "_via_uvx", lambda: True)
    monkeypatch.setattr(nexus_cli, "_direct_url", lambda: _git_info("a" * 40))
    monkeypatch.setattr(nexus_cli, "_install", _no_install)
    monkeypatch.setattr(nexus_cli, "_fetch_releases", lambda: pytest.fail("nothing to look up"))
    out = _flat(runner.invoke(app, ["update"]).output)
    assert "nothing to install" in out and "nexus4 sync" in out


def test_channel_through_the_nexus4_alias_switches_the_project_only(tmp_project, monkeypatch):
    monkeypatch.delenv("NEXUS_MCP_FROM", raising=False)
    monkeypatch.setattr(nexus_cli, "_direct_url", lambda: _git_info("a" * 40))
    runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "none"])
    monkeypatch.setattr(nexus_cli, "_via_uvx", lambda: True)
    monkeypatch.setattr(nexus_cli, "_install", _no_install)
    r = runner.invoke(app, ["channel", "stable", "--project", str(tmp_project)])
    assert r.exit_code == 0 and "installed nexus is unchanged" in _flat(r.output)
    args = json.loads((tmp_project / ".mcp.json").read_text())["mcpServers"]["nexus"]["args"]
    assert args[args.index("--from") + 1] == "nexus-dev-toolkit"


def test_via_uvx_reads_uvs_cache_layout(monkeypatch):
    monkeypatch.undo()   # drop the autouse stub; test the real check
    monkeypatch.setattr(nexus_cli.sys, "prefix", "/Users/x/.cache/uv/archive-v0/igOoFvcLzKcEwq5G")
    assert nexus_cli._via_uvx()
    monkeypatch.setattr(nexus_cli.sys, "prefix", "/Users/x/.local/share/uv/tools/nexus-dev-toolkit")
    assert not nexus_cli._via_uvx()


# ── .gitignore / .graphifyignore ─────────────────────────────────────────────

def _lines(p: Path) -> list[str]:
    return [l for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")]


def test_init_writes_both_ignore_files(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "graphify"])
    assert {".claude/", "graphify-out/"} <= set(_lines(tmp_project / ".gitignore"))
    graph = _lines(tmp_project / ".graphifyignore")
    # measured in a real run: a vendored htmx.min.js and .nexus/manifest.json were 138 of 1021 graph nodes
    assert ".nexus/" in graph and "*.min.js" in graph and "package-lock.json" in graph


def test_ignore_files_only_ever_gain_missing_lines(tmp_project):
    (tmp_project / ".gitignore").write_text("# ours\n.env\n/graphify-out\nnode_modules/")   # no trailing newline
    (tmp_project / ".graphifyignore").write_text("docs/legacy/\n*.min.js\n")
    runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "graphify"])
    git = (tmp_project / ".gitignore").read_text()
    assert git.startswith("# ours\n.env\n/graphify-out\nnode_modules/\n")       # untouched, in order
    assert _lines(tmp_project / ".gitignore").count(".claude/") == 1 and "graphify-out/" not in git  # /graphify-out counts
    graph = _lines(tmp_project / ".graphifyignore")
    assert graph[:2] == ["docs/legacy/", "*.min.js"] and graph.count("*.min.js") == 1 and ".nexus/" in graph
    before = (git, (tmp_project / ".graphifyignore").read_text())
    runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "graphify"])
    runner.invoke(app, ["sync", str(tmp_project)])
    assert before == ((tmp_project / ".gitignore").read_text(), (tmp_project / ".graphifyignore").read_text())


def test_roles_without_a_graph_get_no_graphifyignore(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--role", "product"])
    assert ".claude/" in _lines(tmp_project / ".gitignore")
    assert not (tmp_project / ".graphifyignore").exists()


def test_codex_ignores_its_own_folders(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--tool", "codex", "--graph-backend", "none"])
    assert {".codex/", ".agents/", "graphify-out/"} <= set(_lines(tmp_project / ".gitignore"))
    assert not (tmp_project / ".graphifyignore").exists()


def test_sync_brings_an_older_project_up_to_date(tmp_project):
    runner.invoke(app, ["init", str(tmp_project), "--graph-backend", "graphify"])
    (tmp_project / ".gitignore").unlink()
    (tmp_project / ".graphifyignore").write_text("vendor/\n")
    runner.invoke(app, ["sync", str(tmp_project)])
    assert ".claude/" in _lines(tmp_project / ".gitignore")
    assert _lines(tmp_project / ".graphifyignore")[0] == "vendor/" and ".nexus/" in _lines(tmp_project / ".graphifyignore")
