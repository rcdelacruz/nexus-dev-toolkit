"""The v3 vs v4 page must name everything v4 ships — commands, agents, CLI commands, MCP tools — so it
can't silently fall behind. It can't catch a stale description: re-read the row when you change one."""
import re
from pathlib import Path

import nexus_cli

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "public" / "v3-vs-v4.html").read_text()


def test_every_slash_command_is_on_the_page():
    missing = [f"/{f.stem}" for f in (ROOT / "tools" / "epav" / "skills").glob("*.md") if f"/{f.stem}</code>" not in PAGE]
    assert not missing, f"add these to public/v3-vs-v4.html: {missing}"


def test_every_agent_is_on_the_page():
    missing = [f.stem for f in (ROOT / "tools" / "agents").glob("*.md") if f"<code>{f.stem}</code>" not in PAGE]
    assert not missing, f"add these to public/v3-vs-v4.html: {missing}"


def test_every_cli_command_is_on_the_page():
    names = {c.name or c.callback.__name__ for c in nexus_cli.app.registered_commands}
    missing = [n for n in names if f"nexus {n}" not in PAGE]
    assert not missing, f"add these to public/v3-vs-v4.html: {missing}"


def test_every_mcp_tool_is_on_the_page():
    tools = set()
    for f in (ROOT / "tools").rglob("*.py"):
        tools |= set(re.findall(r"@(?:mcp|server)\.tool\([^)]*\)\s*\n\s*(?:async\s+)?def\s+(\w+)", f.read_text()))
    assert len(tools) >= 7
    missing = [t for t in tools if f"<code>{t}</code>" not in PAGE]
    assert not missing, f"add these to public/v3-vs-v4.html: {missing}"


def test_every_role_is_on_the_page():
    assert all(r in PAGE for r in nexus_cli._ROLES)
