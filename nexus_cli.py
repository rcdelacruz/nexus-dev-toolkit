import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from tools import channel
from tools.epav import graph_backend

app = typer.Typer(name="nexus", no_args_is_help=False, help="nexus-dev-toolkit — Day 0 scaffold + Day 1 EPAV workflow for Claude Code, OpenCode and Codex")
skill_app = typer.Typer(name="skill", no_args_is_help=True, help="Manage skills in .claude/commands/")
rule_app = typer.Typer(name="rule", no_args_is_help=True, help="Manage rules in knowledge/rules/")
agent_app = typer.Typer(name="agent", no_args_is_help=True, help="Manage subagents in .claude/agents/")
app.add_typer(skill_app, name="skill")
app.add_typer(rule_app, name="rule")
app.add_typer(agent_app, name="agent")

console = Console()

_VERSION = "4.0.0a1"


def _fetch_latest_pypi_version() -> str | None:
    """Fetch the latest published version from PyPI. None on any failure — offline, timeout,
    bad response — never raises."""
    try:
        with urllib.request.urlopen(
            "https://pypi.org/pypi/nexus-dev-toolkit/json", timeout=3
        ) as resp:
            return json.loads(resp.read())["info"]["version"]
    except Exception:
        return None


def _fetch_releases() -> list[str] | None:
    """Every published version (pre-releases included). None on any failure — never raises."""
    return channel.fetch_releases()


def _is_outdated(installed: str, latest: str) -> bool:
    """Pre-release aware (4.0.0a1 < 4.0.0b1 < 4.0.0). False for malformed versions — don't false-alarm."""
    return channel.is_newer(latest, installed)


_LOGO = """\
[cyan]███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗[/cyan]
[cyan]████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝[/cyan]
[cyan]██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗[/cyan]
[cyan]██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║[/cyan]
[cyan]██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║[/cyan]
[cyan]╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝[/cyan]
[dim white]dev toolkit[/dim white]  [dim cyan]v{version}[/dim cyan]"""


def _print_logo() -> None:
    from rich.padding import Padding
    console.print()
    console.print(Padding(_LOGO.format(version=_VERSION), (0, 2)))
    console.print()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"nexus-dev-toolkit v{_VERSION}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _callback(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit."),
) -> None:
    if ctx.invoked_subcommand is None:
        _print_logo()
        console.print(ctx.get_help())

# ── Built-in skills shipped with the package ──────────────────────────────────

_SKILLS_SRC = Path(__file__).parent / "tools" / "epav" / "skills"

_BUILTIN_SKILLS = [
    "scaffold.md",
    "evaluate.md",
    "plan.md",
    "apply.md",
    "validate.md",
    "epav.md",
    "code-review.md",
    "database-review.md",
    "deployment-review.md",
    "performance-review.md",
    "monitoring-review.md",
    "commit.md",
    "create-pr.md",
    "pr-review.md",
    "dev-tasks-planner.md",
    "requirements.md",
    "architect.md",
    "design.md",
    "change-request.md",
    "brd.md",
    "prd.md",
]

_AGENTS_SRC = Path(__file__).parent / "tools" / "agents"

_BUILTIN_AGENTS = [
    "deployment-reviewer.md",
    "code-reviewer.md",
    "performance-reviewer.md",
    "monitoring-reviewer.md",
    "database-reviewer.md",
    "pr-verifier.md",
]

# ── Roles ─────────────────────────────────────────────────────────────────────
# `nexus init --role …` installs only what that role uses. Developers get everything (as in
# 3.x, plus the role commands). Architects and designers never open code: no reviewer agents,
# no graphify hooks — only their commands, the MCP server and the guides.
_ROLES = ("developer", "product", "architect", "designer")
_ROLE_SKILLS = {
    "product": ["brd.md", "prd.md", "requirements.md", "change-request.md"],
    "architect": ["requirements.md", "architect.md", "change-request.md"],
    "designer": ["design.md", "change-request.md"],
}


def _role_skills(role: str) -> list[str]:
    return list(_BUILTIN_SKILLS) if role not in _ROLE_SKILLS else [s for s in _BUILTIN_SKILLS if s in _ROLE_SKILLS[role]]


def _role_agents(role: str) -> list[str]:
    return list(_BUILTIN_AGENTS) if role not in _ROLE_SKILLS else []


_TEMPLATES_SRC = Path(__file__).parent / "tools" / "templates"
_GUIDES = {
    "docs/requirements/REQUIREMENTS-GUIDE.md": "REQUIREMENTS-GUIDE.md",
    "docs/arch-docs/ARCHITECTURE-GUIDE.md": "ARCHITECTURE-GUIDE.md",
    "docs/designs/DESIGN-GUIDE.md": "DESIGN-GUIDE.md",
    "docs/requirements/templates/BRD-TEMPLATE.md": "BRD-TEMPLATE.md",
    "docs/requirements/templates/PRD-TEMPLATE.md": "PRD-TEMPLATE.md",
    # Not .github/CODEOWNERS: placeholder team names would be live on the next push. The team
    # fills in real names, then renames it (the guide pages say how).
    ".github/CODEOWNERS.nexus-template": "CODEOWNERS",
}


def _write_guides(project_dir: Path) -> list[str]:
    """Copy the guide templates into docs/ (and the CODEOWNERS template) — only where missing.
    They belong to the team from then on: never overwritten, never in the manifest."""
    created = []
    for rel, name in _GUIDES.items():
        dst, src = project_dir / rel, _TEMPLATES_SRC / name
        if rel.endswith("nexus-template") and (project_dir / ".github" / "CODEOWNERS").exists():
            continue
        if src.is_file() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            created.append(rel)
    return created


# ── .claude/settings.json ────────────────────────────────────────────────────

_CLAUDE_SETTINGS = {
    "hooks": {
        "PostToolUse": [
            {
                "matcher": ".*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "graphify update . --force 2>/dev/null || true"
                    }
                ]
            }
        ]
    }
}

# ── knowledge/ scaffold ───────────────────────────────────────────────────────

_KNOWLEDGE_DIRS = [
    "knowledge/rules",
    "knowledge/patterns",
    "knowledge/prompts/dev",
    "knowledge/retros",
]

# ── docs/ scaffold ────────────────────────────────────────────────────────────
# Where the workflow expects reference docs: arch_ingest reads docs/arch-docs/,
# load_task and /evaluate read docs/dev-tasks/, /scaffold uses docs/designs/. docs/requirements/
# (BRD, PRD) is deliberately separate from arch-docs/ — ingest_architecture_doc scans that whole
# folder, so requirements docs there would be parsed as architecture.

_DOCS_DIRS = [
    "docs/arch-docs",
    "docs/dev-tasks",
    "docs/designs",
    "docs/requirements",
]

# ── MCP config ────────────────────────────────────────────────────────────────

# The MCP server must run the same channel as the CLI that wrote the config: plain
# `uvx --from nexus-dev-toolkit` resolves the newest STABLE release even when the user is on a
# 4.0.0 pre-release (measured), so the pre channel writes `nexus-dev-toolkit>=4.0.0a0`.
def _mcp_args() -> list[str]:
    # NEXUS_MCP_FROM points MCP configs at a local checkout or wheel — for testing an unreleased
    # nexus (e.g. the v4 branch) before it is on PyPI. `nexus sync` never rewrites such entries.
    source = os.environ.get("NEXUS_MCP_FROM", "").strip()
    if source:
        return ["--refresh", "--from", str(Path(source).expanduser().resolve()), "nexus-mcp"]
    local = _local_build()
    if local:
        return ["--refresh", "--from", local, "nexus-mcp"]
    return ["--refresh", "--from", channel.mcp_from(_VERSION), "nexus-mcp"]


def _direct_url() -> dict:
    """The installed distribution's direct_url.json (PEP 610) — {} for PyPI installs."""
    try:
        import importlib
        from importlib.metadata import distribution
        importlib.invalidate_caches()
        raw = distribution("nexus-dev-toolkit").read_text("direct_url.json")
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def _git_install() -> dict | None:
    """{url, commit, ref} when this nexus was installed from git (`…@v4-preview` → ref
    "v4-preview"), else None."""
    info = _direct_url()
    vcs = info.get("vcs_info") or {}
    if vcs.get("vcs") == "git" and vcs.get("commit_id") and info.get("url"):
        return {"url": info["url"], "commit": vcs["commit_id"], "ref": vcs.get("requested_revision", "")}
    return None


def _local_build() -> str:
    """Where this nexus came from when it isn't PyPI: a git install (`uv tool install
    'git+https://…/nexus-dev-toolkit@v4-preview'`) → `git+…@<commit>`, the same on every machine; a
    local wheel (`uv tool install ./dist/…whl`) → its path. MCP configs then run that same build.
    "" for PyPI installs and checkouts."""
    info = _direct_url()
    url = info.get("url", "")
    git = _git_install()
    if git:
        # installed from git (e.g. a preview branch teammates install before a release): every
        # machine gets the same `git+…@<commit>` in the shared .mcp.json — no local paths
        return f"git+{git['url']}@{git['commit']}"
    if not url.startswith("file://") or info.get("dir_info", {}).get("editable"):
        return ""
    from urllib.parse import unquote, urlparse
    path = Path(unquote(urlparse(url).path))
    return str(path) if path.exists() else ""


def _mcp_block() -> dict:
    return {"nexus": {"command": "uvx", "args": _mcp_args()}}


def _opencode_mcp_block() -> dict:
    return {"nexus-mcp": {"type": "local", "command": ["uvx", *_mcp_args()]}}

_OPENCODE_GRAPHIFY_PLUGIN = """\
// .opencode/plugins/graphify.js
// Auto-updates the graphify knowledge graph after every tool execution.
import { execSync } from "node:child_process"

export const GraphifyPlugin = async ({ directory }) => {
  return {
    "tool.execute.after": async () => {
      try {
        execSync("graphify update . --force", { cwd: directory, stdio: "ignore" })
      } catch (_) {}
    },
  }
}
"""

# OpenCode v2 does not run the v1 plugin above ("Plugin must export a default definition with an
# id and an effect or setup function"). A v2 local plugin is a directory with an index.ts that
# default-exports { id, setup(ctx) }. The update runs async and coalesces overlapping calls:
# v2 hooks run inside a shared background service, so a blocking execSync would stall every
# session's tool calls for the duration of `graphify update`.
_OPENCODE_GRAPHIFY_PLUGIN_V2 = """\
// .opencode/plugins/graphify/index.ts
// Auto-updates the graphify knowledge graph after every tool execution (OpenCode v2).
import { execFile } from "node:child_process"

export default {
  id: "nexus.graphify",
  async setup(ctx: any) {
    const cwd = ctx.location.directory
    let running = false
    let queued = false

    const update = () => {
      if (running) {
        queued = true
        return
      }
      running = true
      execFile("graphify", ["update", ".", "--force"], { cwd }, () => {
        running = false
        if (queued) {
          queued = false
          update()
        }
      })
    }

    await ctx.tool.hook("execute.after", async () => {
      update()
    })
  },
}
"""

_OPENCODE_PLUGIN_V1 = ".opencode/plugins/graphify.js"
_OPENCODE_PLUGIN_V2 = ".opencode/plugins/graphify/index.ts"
_OPENCODE_PLUGINS = {
    _OPENCODE_PLUGIN_V1: _OPENCODE_GRAPHIFY_PLUGIN,
    _OPENCODE_PLUGIN_V2: _OPENCODE_GRAPHIFY_PLUGIN_V2,
}


# ── Codex ─────────────────────────────────────────────────────────────────────

def _codex_mcp_toml() -> str:
    args = ", ".join(json.dumps(a) for a in _mcp_args())
    return f'[mcp_servers.nexus]\ncommand = "uvx"\nargs = [{args}]\n'

_CODEX_HOOKS = {
    "hooks": {
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": "graphify update . --force 2>/dev/null || true"
                    }
                ]
            }
        ]
    }
}

# EPAV steps are user-driven — Codex must never start /apply or /commit on its own.
_CODEX_EXPLICIT_ONLY_YAML = """\
policy:
  allow_implicit_invocation: false
"""


def _create_scaffold_dirs(project_dir: Path) -> list[str]:
    """Create knowledge/ and docs/ folders. Folders only — never writes a file, so an existing
    docs/ is left exactly as it was. Returns the docs/ folders that didn't exist before."""
    for d in _KNOWLEDGE_DIRS:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    created = []
    for d in _DOCS_DIRS:
        target = project_dir / d
        if not target.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            created.append(f"{d}/")
    return created + _write_guides(project_dir)


# Claude Code asks "New MCP server found in this project: nexus" and then for every tool call. These
# keys answer both once the folder is trusted (Claude Code ignores them in an untrusted folder — a
# repository can't approve itself — so the folder-trust question is the one prompt left).
_MCP_APPROVAL = {"enabledMcpjsonServers": ["nexus"], "permissions": {"allow": ["mcp__nexus__*"]}}


def _write_claude_settings(project_dir: Path, graphify_hook: bool) -> bool:
    """Merge nexus's keys into .claude/settings.json without touching anything else in it. True if changed."""
    path = project_dir / ".claude" / "settings.json"
    try:
        data = json.loads(path.read_text()) if path.is_file() else {}
    except Exception:
        return False                                       # unreadable: leave the user's file alone
    before = json.dumps(data, sort_keys=True)
    servers = data.setdefault("enabledMcpjsonServers", [])
    if "nexus" not in servers:
        servers.append("nexus")
    allow = data.setdefault("permissions", {}).setdefault("allow", [])
    if not any(a in ("mcp__nexus", "mcp__nexus__*") for a in allow):
        allow.append("mcp__nexus__*")
    if graphify_hook and "graphify update" not in json.dumps(data.get("hooks", {})):
        data.setdefault("hooks", {}).setdefault("PostToolUse", []).extend(_CLAUDE_SETTINGS["hooks"]["PostToolUse"])
    if json.dumps(data, sort_keys=True) == before:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def _init_project(project_dir: Path, backend: str = "graphify", role: str = "developer") -> list[str]:
    """
    nexus init — sets up:
      .claude/commands/     ← built-in skills
      .claude/agents/       ← built-in subagents
      .claude/settings.json ← PostToolUse graphify hook (only when backend == "graphify")
      knowledge/            ← empty scaffold
    """
    created = []

    # .claude/commands/ — copy built-in skills
    commands_dir = project_dir / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    for skill_name in _role_skills(role):
        src = _SKILLS_SRC / skill_name
        dest = commands_dir / skill_name
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)
            created.append(f".claude/commands/{skill_name}")

    # .claude/agents/ — copy built-in subagents
    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    for agent_name in _role_agents(role):
        src = _AGENTS_SRC / agent_name
        dest = agents_dir / agent_name
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)
            created.append(f".claude/agents/{agent_name}")

    # .claude/settings.json — approve the nexus MCP server and its tools (every role), plus the
    # PostToolUse graphify hook for developers (codegraph syncs itself, no hook needed)
    if _write_claude_settings(project_dir, graphify_hook=backend == "graphify" and role == "developer"):
        created.append(".claude/settings.json")

    # knowledge/ + docs/ scaffold
    created += _create_scaffold_dirs(project_dir)

    return created


_FRONTMATTER_RE = re.compile(r"---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.DOTALL)


def _strip_claude_frontmatter(content: str) -> str:
    """Adapt a Claude Code subagent for OpenCode: drop the Claude-only fields (tools, model) and
    mark it `mode: subagent` — OpenCode v2 otherwise registers it as a primary agent. The closing
    `---` always lands on its own line; without it OpenCode v2 never loads the agent."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return content
    lines = [line for line in match.group(1).splitlines() if not line.startswith(("tools:", "model:"))]
    if not any(line.startswith("mode:") for line in lines):
        at = next((i + 1 for i, line in enumerate(lines) if line.startswith("name:")), 0)
        lines.insert(at, "mode: subagent")
    return "---\n" + "\n".join(lines) + "\n---\n" + content[match.end():]


def _opencode_major() -> int | None:
    """Major version of the installed OpenCode (v1 prints e.g. 1.0.7, v2 prints `opencode v2.2.5`).
    None if it isn't installed or its output can't be parsed."""
    binary = shutil.which("opencode")
    if not binary:
        return None
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return None
    found = re.search(r"(\d+)\.\d+\.\d+", out)
    return int(found.group(1)) if found else None


def _opencode_plugin_relpath(major: int | None) -> str:
    """Where the graphify plugin lives for this OpenCode major. Undetectable → v2, the current release."""
    return _OPENCODE_PLUGIN_V1 if major is not None and major < 2 else _OPENCODE_PLUGIN_V2


def _init_opencode(project_dir: Path, backend: str = "graphify", role: str = "developer") -> list[str]:
    """
    nexus init --tool opencode — sets up:
      .opencode/commands/   ← built-in skills
      .opencode/agents/     ← built-in subagents
      .opencode/plugins/    ← graphify hook, v1 or v2 form by installed OpenCode (only when backend == "graphify")
      opencode.json         ← MCP server config
      knowledge/            ← empty scaffold
    """
    created = []

    # .opencode/commands/ — copy built-in skills
    commands_dir = project_dir / ".opencode" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    for skill_name in _role_skills(role):
        src = _SKILLS_SRC / skill_name
        dest = commands_dir / skill_name
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)
            created.append(f".opencode/commands/{skill_name}")

    # .opencode/agents/ — copy built-in subagents, stripping Claude Code-only frontmatter
    agents_dir = project_dir / ".opencode" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for agent_name in _role_agents(role):
        src = _AGENTS_SRC / agent_name
        dest = agents_dir / agent_name
        if src.exists() and not dest.exists():
            dest.write_text(_strip_claude_frontmatter(src.read_text()), encoding="utf-8")
            created.append(f".opencode/agents/{agent_name}")

    # graphify plugin — v1: .opencode/plugins/graphify.js, v2: .opencode/plugins/graphify/index.ts
    # (codegraph syncs itself, no hook needed)
    if backend == "graphify" and role == "developer":
        plugin_rel = _opencode_plugin_relpath(_opencode_major())
        plugin_path = project_dir / plugin_rel
        if not plugin_path.exists():
            plugin_path.parent.mkdir(parents=True, exist_ok=True)
            plugin_path.write_text(_OPENCODE_PLUGINS[plugin_rel], encoding="utf-8")
            created.append(plugin_rel)

    # opencode.json — MCP server config. New files use the flat v1 `mcp` map, which v2 accepts and
    # normalizes; an existing file already on the v2 `mcp.servers` shape is extended in that shape.
    opencode_json = project_dir / "opencode.json"
    existing: dict = {}
    if opencode_json.exists():
        try:
            existing = json.loads(opencode_json.read_text())
        except Exception:
            pass
    mcp_map = existing.setdefault("mcp", {})
    servers = mcp_map.get("servers")
    # A v1 server literally named "servers" has a "type" key; a v2 servers map never does.
    target = servers if isinstance(servers, dict) and "type" not in servers else mcp_map
    already_has_mcp = "nexus-mcp" in target
    existing.setdefault("$schema", "https://opencode.ai/config.json")
    target.update(_opencode_mcp_block())
    opencode_json.write_text(json.dumps(existing, indent=2))
    if not already_has_mcp:
        created.append("opencode.json")

    # knowledge/ + docs/ scaffold
    created += _create_scaffold_dirs(project_dir)

    return created


def _split_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse a simple `key: value` frontmatter block. ({}, content) if there isn't one."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    fields = {}
    for line in parts[1].splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields, parts[2].lstrip("\n")


# "/plan" → "$plan": Codex invokes skills with $, and "/" belongs to its own built-in commands.
# The lookbehind skips paths like docs/scaffold or ./plan.
_SKILL_REF_RE = re.compile(r"(?<![\w/.])/(" + "|".join(re.escape(Path(s).stem) for s in _BUILTIN_SKILLS) + r")\b")


def _to_codex_skill(skill_name: str, content: str) -> tuple[str, str | None]:
    """Convert a nexus skill to a Codex SKILL.md. Skills without frontmatter are the user-driven
    EPAV steps — they get generated frontmatter plus an openai.yaml that blocks implicit invocation."""
    content = _SKILL_REF_RE.sub(r"$\1", content)
    fields, body = _split_frontmatter(content)
    if fields.get("name") and fields.get("description"):
        return content, None
    name = Path(skill_name).stem
    description = next(
        (line.replace("**", "").strip() for line in body.splitlines() if line.strip() and not line.startswith("#")),
        f"nexus {name} skill",
    )
    frontmatter = f"---\nname: {name}\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n\n"
    return frontmatter + body, _CODEX_EXPLICIT_ONLY_YAML


def _to_codex_agent(agent_name: str, content: str) -> str:
    """Convert a nexus subagent (markdown + frontmatter) to a Codex agent TOML. Claude Code-only
    fields (tools, model) are dropped — the agent inherits the parent session's model."""
    fields, body = _split_frontmatter(content)
    name = fields.get("name") or Path(agent_name).stem
    # Multi-line literal string keeps the prompt readable; fall back to an escaped basic string
    # in the unlikely case the body itself contains '''.
    instructions = json.dumps(body, ensure_ascii=False) if "'''" in body else f"'''\n{body}'''"
    return (
        f"name = {json.dumps(name, ensure_ascii=False)}\n"
        f"description = {json.dumps(fields.get('description', ''), ensure_ascii=False)}\n"
        f"developer_instructions = {instructions}\n"
    )


def _write_codex_mcp_config(project_dir: Path) -> bool:
    """Append the nexus MCP block to .codex/config.toml. Text-level only — Python 3.10 has no
    tomllib, and appending never rewrites the user's TOML. True if the block was added."""
    config = project_dir / ".codex" / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    existing = config.read_text(encoding="utf-8") if config.exists() else ""
    if "[mcp_servers.nexus]" in existing:
        return False
    if existing and not existing.endswith("\n"):
        existing += "\n"
    if existing:
        existing += "\n"
    config.write_text(existing + _codex_mcp_toml(), encoding="utf-8")
    return True


def _write_codex_hooks(project_dir: Path) -> bool:
    """Merge the graphify PostToolUse hook into .codex/hooks.json. True if it was added."""
    hooks_path = project_dir / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if hooks_path.exists():
        try:
            existing = json.loads(hooks_path.read_text())
        except Exception:
            return False  # never clobber a hooks file we can't parse
    if "graphify update" in json.dumps(existing):
        return False
    existing.setdefault("hooks", {}).setdefault("PostToolUse", []).extend(_CODEX_HOOKS["hooks"]["PostToolUse"])
    hooks_path.write_text(json.dumps(existing, indent=2))
    return True


def _init_codex(project_dir: Path, backend: str = "graphify", role: str = "developer") -> list[str]:
    """
    nexus init --tool codex — sets up:
      .agents/skills/<name>/ ← built-in skills (SKILL.md, plus agents/openai.yaml for EPAV steps)
      .codex/agents/         ← built-in subagents as TOML
      .codex/config.toml     ← MCP server config (appended, never rewritten)
      .codex/hooks.json      ← graphify PostToolUse hook (only when backend == "graphify")
      knowledge/             ← empty scaffold
    """
    created = []

    # .agents/skills/<name>/SKILL.md — Codex's project skill location
    skills_dir = project_dir / ".agents" / "skills"
    for skill_name in _role_skills(role):
        src = _SKILLS_SRC / skill_name
        dest_dir = skills_dir / Path(skill_name).stem
        dest = dest_dir / "SKILL.md"
        if src.exists() and not dest.exists():
            skill_md, openai_yaml = _to_codex_skill(skill_name, src.read_text(encoding="utf-8"))
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(skill_md, encoding="utf-8")
            if openai_yaml:
                (dest_dir / "agents").mkdir(exist_ok=True)
                (dest_dir / "agents" / "openai.yaml").write_text(openai_yaml, encoding="utf-8")
            created.append(f".agents/skills/{dest_dir.name}/SKILL.md")

    # .codex/agents/<name>.toml — built-in subagents converted to Codex's TOML format
    agents_dir = project_dir / ".codex" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for agent_name in _role_agents(role):
        src = _AGENTS_SRC / agent_name
        dest = agents_dir / f"{Path(agent_name).stem}.toml"
        if src.exists() and not dest.exists():
            dest.write_text(_to_codex_agent(agent_name, src.read_text(encoding="utf-8")), encoding="utf-8")
            created.append(f".codex/agents/{dest.name}")

    if _write_codex_mcp_config(project_dir):
        created.append(".codex/config.toml")

    # .codex/hooks.json — graphify hook (codegraph syncs itself, no hook needed)
    if backend == "graphify" and role == "developer" and _write_codex_hooks(project_dir):
        created.append(".codex/hooks.json")

    # knowledge/ + docs/ scaffold
    created += _create_scaffold_dirs(project_dir)

    return created


def _write_mcp_config(project_dir: Path) -> str:
    mcp_path = project_dir / ".mcp.json"
    existing: dict = {}
    if mcp_path.exists():
        try:
            existing = json.loads(mcp_path.read_text())
        except Exception:
            pass
    existing.setdefault("mcpServers", {}).update(_mcp_block())
    mcp_path.write_text(json.dumps(existing, indent=2))
    return ".mcp.json"


# ── Commands ──────────────────────────────────────────────────────────────────

_SUPPORTED_TOOLS = ["claude", "opencode", "codex"]

_TOOL_CHECK = {
    "claude": {
        "bin": "claude",
        "name": "Claude Code",
        "install": "npm install -g @anthropic-ai/claude-code && claude login",
        "install_cmd": ["npm", "install", "-g", "@anthropic-ai/claude-code"],
    },
    "opencode": {
        "bin": "opencode",
        "name": "OpenCode",
        "install": "curl -fsSL https://opencode.ai/v2/install | bash",  # /install only installs OpenCode 1
        "install_cmd": None,  # pipe install — run via shell
    },
    "codex": {
        "bin": "codex",
        "name": "Codex",
        "install": "npm install -g @openai/codex",
        "install_cmd": ["npm", "install", "-g", "@openai/codex"],
    },
}


def _check_and_offer_install(tool: str) -> None:
    info = _TOOL_CHECK[tool]
    if shutil.which(info["bin"]):
        return

    console.print(f"  [yellow]⚠[/yellow]  {info['name']} not found — you need it to use nexus.\n")

    if not sys.stdin.isatty():
        console.print(f"  [dim]Install manually: {info['install']}[/dim]\n")
        return

    answer = console.input(f"  Install {info['name']} now? {escape('[y/N]')} ").strip().lower()
    if answer != "y":
        console.print(f"  [dim]Skipping. Install manually: {info['install']}[/dim]\n")
        return

    console.print(f"  [cyan]▶[/cyan]  Installing {info['name']}…\n")
    if info["install_cmd"]:
        result = subprocess.run(info["install_cmd"])
    else:
        result = subprocess.run(info["install"], shell=True)

    if result.returncode == 0:
        console.print(f"  [green]✓[/green]  {info['name']} installed.\n")
    else:
        console.print(f"  [red]✗[/red]  Install failed. Run manually: {info['install']}\n")


_GRAPH_BACKENDS = {
    "graphify": "existing default — this scaffolds the PostToolUse hook that auto-updates it",
    "codegraph": "you run `codegraph install && codegraph init` yourself — it syncs itself, no hook needed",
    "none": "skip for now — set either up later, `nexus doctor` will detect it",
}


# What each role types first after `nexus init` (a developer who isn't the tech lead starts with
# /evaluate once the tech lead's /scaffold is merged — the tech lead runs /scaffold once, Day 0).
_FIRST_COMMAND = {"developer": "scaffold", "product": "brd", "architect": "architect <app>", "designer": "design <app>"}


def _resolve_graph_backend(explicit: str | None) -> str:
    if explicit:
        if explicit not in _GRAPH_BACKENDS:
            console.print(f"  [red]✗[/red]  Unknown --graph-backend '{explicit}'. Choose from: {', '.join(_GRAPH_BACKENDS)}")
            raise typer.Exit(1)
        return explicit

    if not sys.stdin.isatty():
        return "graphify"  # unchanged behavior for CI/scripted `nexus init`

    console.print("  Which knowledge graph do you want nexus to wire up?")
    console.print("    [cyan]1[/cyan] graphify   (default)")
    console.print("    [cyan]2[/cyan] codegraph")
    console.print("    [cyan]3[/cyan] skip for now")
    answer = console.input(f"  Choice {escape('[1]')}: ").strip()
    return {"2": "codegraph", "3": "none"}.get(answer, "graphify")


@app.command()
def init(
    project_dir: str = typer.Argument(".", help="Project directory to initialize"),
    tool: str = typer.Option("claude", "--tool", "-t", help=f"AI coding tool to set up for ({', '.join(_SUPPORTED_TOOLS)})"),
    graph_backend: str = typer.Option(None, "--graph-backend", "-g", help=f"Knowledge graph tool to wire up ({', '.join(_GRAPH_BACKENDS)}). Prompts interactively if omitted."),
    role: str = typer.Option("developer", "--role", "-r", help=f"Who uses this checkout ({', '.join(_ROLES)}). architect/designer get only their commands — no code tooling."),
) -> None:
    """Initialize nexus in a project directory. Defaults to Claude Code."""
    if tool not in _SUPPORTED_TOOLS:
        console.print(f"  [red]✗[/red]  Unknown tool '{tool}'. Supported: {', '.join(_SUPPORTED_TOOLS)}")
        raise typer.Exit(1)
    if role not in _ROLES:
        console.print(f"  [red]✗[/red]  Unknown role '{role}'. Choose from: {', '.join(_ROLES)}")
        raise typer.Exit(1)

    _check_and_offer_install(tool)

    backend = _resolve_graph_backend(graph_backend) if role == "developer" else "none"   # no code to graph

    root = Path(project_dir).resolve()
    console.print(f"  [cyan]▶[/cyan]  Initializing nexus for [bold]{tool}[/bold] in [bold]{root}[/bold]\n")

    if tool == "opencode":
        created = _init_opencode(root, backend, role)
        _record_manifest(root, role)
        for f in created:
            console.print(f"  [green]✓[/green]  {f}")
        if not created:
            console.print("  [yellow]·[/yellow]  Already initialized — nothing to do")
            return
        console.print(f"\n  [bold green]Done.[/bold green] Open [bold]{root}[/bold] in OpenCode and type [cyan]/{_FIRST_COMMAND[role]}[/cyan]\n")
    elif tool == "codex":
        created = _init_codex(root, backend, role)
        _record_manifest(root, role)
        for f in created:
            console.print(f"  [green]✓[/green]  {f}")
        if not created:
            console.print("  [yellow]·[/yellow]  Already initialized — nothing to do")
            return
        console.print(f"\n  [bold green]Done.[/bold green] Run [bold]codex[/bold] in [bold]{root}[/bold], trust the project when asked (.codex/ config and hooks only load in trusted projects), and type [cyan]${_FIRST_COMMAND[role]}[/cyan]\n")
    else:
        created = _init_project(root, backend, role)
        _record_manifest(root, role)
        for f in created:
            console.print(f"  [green]✓[/green]  {f}")
        if not created:
            console.print("  [yellow]·[/yellow]  Already initialized — nothing to do")
            return
        mcp = _write_mcp_config(root)
        console.print(f"  [green]✓[/green]  {mcp}")
        console.print(f"\n  [bold green]Done.[/bold green] Open [bold]{root}[/bold] in Claude Code and type [cyan]/{_FIRST_COMMAND[role]}[/cyan]\n")

    if backend == "codegraph":
        console.print("  [cyan]→[/cyan]  Next: run [bold]codegraph install && codegraph init[/bold] to wire codegraph into this project (it manages its own auto-sync — no hook needed).\n")


def _via_uvx() -> bool:
    """True when this nexus runs from uvx's throwaway environment (e.g. the `nexus4` alias) rather
    than an installed tool. Installing from here would replace the person's installed `nexus`."""
    return any(part.startswith(("archive-v", "builds-v")) for part in Path(sys.prefix).parts)


def _install(spec: str) -> bool:
    """Install `spec` as the nexus tool. `uv tool install --reinstall`, never `uv tool upgrade`
    (which can silently do nothing). True on success."""
    have_uv = bool(shutil.which("uv"))
    cmd = channel.install_command(spec, have_uv)
    if not have_uv:
        cmd = [sys.executable, "-m", *cmd]
    result = subprocess.run(cmd)
    return getattr(result, "returncode", 0) == 0


def _sync_in_fresh_process(root: Path) -> bool:
    """Run `nexus sync` from the newly installed version. This process's own built-in lists were
    imported before the install, so syncing in-process would miss anything new in that version."""
    nexus_bin = shutil.which("nexus")
    if nexus_bin:
        subprocess.run([nexus_bin, "sync", str(root)])
        return True
    console.print(
        "  [yellow]⚠[/yellow]  Couldn't find [bold]nexus[/bold] on PATH to re-run sync in a fresh "
        "process — syncing in-process instead, which may miss anything added in this exact "
        "upgrade. Run [cyan]nexus sync[/cyan] again afterward to be sure.\n"
    )
    return False


@app.command()
def update(
    also_sync: bool = typer.Option(False, "--sync", "-s", help="Also sync built-in skills/agents in the current directory after upgrading."),
) -> None:
    """Update nexus-dev-toolkit. Stays on your channel: stable, or the 4.0 pre-releases (which move
    you to stable automatically once 4.0.0 is out). Installed from a git branch (a preview):
    reinstalls the newest commit on that branch."""
    if _via_uvx():
        console.print("\n  [green]✓[/green]  This nexus runs through uvx (e.g. the nexus4 alias): every run already "
                      "fetches the newest build, so there is nothing to install. Your installed "
                      "[bold]nexus[/bold] is left as it is.\n")
        if also_sync:
            table = _sync_project(Path(".").resolve())
            if table is not None:
                console.print(table)
        else:
            console.print("  [dim]Run sync the same way in each project (e.g. [/dim][cyan]nexus4 sync[/cyan][dim]) — "
                          "it points the project's MCP server at the newest commit.[/dim]\n")
        return
    git = _git_install()
    if git:
        _update_from_git(git)
        if also_sync:
            root = Path(".").resolve()
            if not _sync_in_fresh_process(root):
                table = _sync_project(root)
                if table is not None:
                    console.print(table)
        else:
            console.print("  [dim]Then run [/dim][cyan]nexus sync[/cyan][dim] in each project — it points the "
                          "project's MCP server at the new commit.[/dim]\n")
        return
    releases = _fetch_releases()
    if releases is not None:
        target = channel.pick_update(_VERSION, releases)
        known = True
    else:  # full release list unavailable — fall back to PyPI's latest stable
        latest = _fetch_latest_pypi_version()
        known = latest is not None
        target = latest if latest and _is_outdated(_VERSION, latest) else None

    upgraded = False
    if known and target is None:
        console.print(f"\n  [green]✓[/green]  Already up to date (v{_VERSION}, {channel.channel_of(_VERSION)} channel).\n")
    else:
        spec = channel.install_spec(target) if target else channel.install_spec(_VERSION)
        what = f"v{target}" if target else "the latest version (couldn't reach PyPI to check)"
        if target and channel.is_prerelease(_VERSION) and not channel.is_prerelease(target):
            console.print(f"\n  [cyan]▶[/cyan]  {target} is released — moving you from the pre-release to the stable channel.")
        console.print(f"\n  [cyan]▶[/cyan]  Updating nexus-dev-toolkit to {what}…\n")
        if _install(spec):
            console.print("\n  [green]✓[/green]  Done.\n")
            upgraded = True
        else:
            console.print("\n  [red]✗[/red]  Install failed — nothing changed. Output is above.\n")
            raise typer.Exit(1)

    if not also_sync:
        if sys.stdin.isatty():
            answer = console.input(f"  Also sync built-in skills/agents in the current directory? {escape('[y/N]')} ").strip().lower()
            also_sync = answer == "y"

        if not also_sync:
            console.print(
                "  [dim]This only updated the nexus CLI itself. Run [/dim][cyan]nexus sync[/cyan][dim] in each "
                "project to pull the updated skills/agents into .claude/ or .opencode/ — or pass "
                "[/dim][cyan]--sync[/cyan][dim] next time to do both at once.[/dim]\n"
            )
            return

    root = Path(".").resolve()

    if upgraded and _sync_in_fresh_process(root):
        return

    table = _sync_project(root)
    if table is None:
        console.print("  [yellow]⚠[/yellow]  Current directory isn't a nexus project — skipping sync.\n")
        return

    console.print(f"  [cyan]▶[/cyan]  Syncing built-ins in [bold]{root}[/bold]\n")
    console.print(table)
    console.print()


def _update_from_git(git: dict) -> None:
    ref = git["ref"]
    spec = f"git+{git['url']}@{ref}" if ref else f"git+{git['url']}"
    console.print(f"\n  [cyan]▶[/cyan]  Installed from git ({escape(ref or 'default branch')}, commit "
                  f"{git['commit'][:7]}) — reinstalling the newest commit…\n")
    if not _install(spec):
        console.print("\n  [red]✗[/red]  Install failed — nothing changed. Output is above.\n")
        raise typer.Exit(1)
    after = _git_install()
    new = after["commit"][:7] if after else "?"
    if after and after["commit"] == git["commit"]:
        console.print(f"\n  [green]✓[/green]  Already the newest commit on {escape(ref or 'the branch')} ({new}).\n")
    else:
        console.print(f"\n  [green]✓[/green]  Updated: {git['commit'][:7]} → {new}.\n")


# Built-in skill files that exist only from 4.0 on. Switching a project back to the stable 3.x
# channel removes them (if unedited) — 3.x's own sync can't, it doesn't know they exist.
_ADDED_IN_V4: list[str] = ["requirements.md", "architect.md", "design.md", "change-request.md", "brd.md", "prd.md"]


@app.command(name="channel")
def channel_cmd(
    target: str = typer.Argument("show", help="show | stable | v4"),
    project_dir: str = typer.Option(".", "--project", "-p", help="Project to switch along with the CLI"),
) -> None:
    """Show or switch the release channel: stable, or v4 (the 4.0 pre-releases)."""
    root = Path(project_dir).resolve()
    if target == "show":
        m = channel.load_manifest(root)
        console.print(f"\n  nexus-dev-toolkit v{_VERSION} — {channel.channel_of(_VERSION)} channel")
        if m.nexus_version:
            console.print(f"  This project was last synced by v{m.nexus_version}.")
        console.print("  Switch with: [cyan]nexus channel v4[/cyan] or [cyan]nexus channel stable[/cyan]\n")
        return
    if target not in ("stable", "v4"):
        console.print(f"  [red]✗[/red]  Unknown channel '{target}'. Use: stable | v4")
        raise typer.Exit(1)

    if target == "stable" and channel.is_prerelease(_VERSION):
        # Undo what only this version wrote, before handing the project to the stable CLI.
        old = channel.load_manifest(root)
        stems = {Path(n).stem for n in _ADDED_IN_V4}
        # .claude/commands/design.md, .agents/skills/design/SKILL.md, …/design/agents/openai.yaml
        v4_only = {rel for rel in old.files if Path(rel).name in _ADDED_IN_V4 or stems & set(Path(rel).parts[:-1])}
        removed, kept = channel.prune(root, channel.Manifest(files={r: old.files[r] for r in v4_only}), set())
        for rel in removed:
            console.print(f"  [cyan]·[/cyan]  removed {rel} (v4 only)")
        for rel in kept:
            console.print(f"  [yellow]⚠[/yellow]  kept {rel} — v4 only, but you edited it")
        # 3.x's sync never rewrites MCP configs, so point them back at stable now — otherwise the
        # project's MCP server would keep running the pre-release under a 3.x CLI.
        mcp_table = Table(show_header=False)
        _refresh_mcp_configs(root, mcp_table, want=channel.PACKAGE)
        if mcp_table.row_count:
            console.print(mcp_table)
        channel.save_manifest(root, old.nexus_version or _VERSION,
                              {r: h for r, h in old.files.items() if r not in removed})

    if _via_uvx():  # the alias: switch the project only — never replace the installed nexus
        if target == "v4":
            table = _sync_project(root)
            if table is not None:
                console.print(table)
            console.print(f"\n  [green]✓[/green]  Project on the v4 channel. Your installed [bold]nexus[/bold] is unchanged.\n")
        else:
            console.print("\n  [green]✓[/green]  Project switched back to stable. Your installed [bold]nexus[/bold] is "
                          "unchanged — run [cyan]nexus sync[/cyan] with it here to finish.\n")
        return
    spec = channel.PACKAGE if target == "stable" else f"{channel.PACKAGE}>=4.0.0a0"
    console.print(f"\n  [cyan]▶[/cyan]  Installing {spec}…\n")
    if not _install(spec):
        console.print("\n  [red]✗[/red]  Install failed — your previous version is still installed.\n")
        raise typer.Exit(1)
    if any((root / d).is_dir() for d in (".claude", ".opencode", ".codex")):
        _sync_in_fresh_process(root)  # the new version rewrites skills + the MCP config for its channel
    console.print(f"\n  [green]✓[/green]  Switched to the {target} channel.\n")


def _sync_file(table: Table, dst: Path, text: str, label: str,
               root: Path | None = None, old: "channel.Manifest | None" = None, stamp: str = "") -> None:
    """Write text to dst unless it's already identical, and record the result in table. A file
    the user edited after nexus wrote it is backed up under .nexus/backup/ before it's replaced."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.read_text(encoding="utf-8") == text:
        table.add_row(label, "[dim green]ok[/dim green]")
        return
    note = ""
    # Back up whenever the current file may hold edits: edited since nexus wrote it, or not in
    # the manifest at all (projects synced before manifests existed) — nexus can't tell an older
    # nexus copy from a user's change there, so it keeps a copy rather than guess.
    if root is not None and old is not None and dst.exists() and (
            label not in old.files or channel.is_edited(root, label, old)):
        saved = channel.backup(root, label, stamp or None)
        note = f" (previous copy saved to {saved.relative_to(root)})"
    tmp = dst.with_name(dst.name + ".nexus-tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(dst)  # all-or-nothing
    table.add_row(label, f"[cyan]updated[/cyan]{escape(note)}")


def _builtin_files(root: Path, role: str | None = None) -> dict[str, str]:
    """Every file nexus owns in this project, with the exact text this version ships — for each
    tool set up here (.claude/, .opencode/, .codex/). Merged user configs (.mcp.json,
    opencode.json, settings.json, .codex/config.toml, hooks.json) are not in this list."""
    role = role or channel.load_manifest(root).role or "developer"
    skills, agents = _role_skills(role), _role_agents(role)
    files: dict[str, str] = {}
    if (root / ".claude").is_dir():
        for fname in skills:
            src = _SKILLS_SRC / fname
            if src.exists():
                files[f".claude/commands/{fname}"] = src.read_text(encoding="utf-8")
        for fname in agents:
            src = _AGENTS_SRC / fname
            if src.exists():
                files[f".claude/agents/{fname}"] = src.read_text(encoding="utf-8")
    if (root / ".opencode").is_dir():
        for fname in skills:
            src = _SKILLS_SRC / fname
            if src.exists():
                files[f".opencode/commands/{fname}"] = src.read_text(encoding="utf-8")
        for fname in agents:
            src = _AGENTS_SRC / fname
            if src.exists():
                files[f".opencode/agents/{fname}"] = _strip_claude_frontmatter(src.read_text(encoding="utf-8"))
        # The plugin for the installed OpenCode major, plus any other stock plugin already on disk.
        # Never deleted: a repo can have teammates on different OpenCode majors, and removing the
        # other form would flip-flop it in git on every sync.
        wanted = _opencode_plugin_relpath(_opencode_major())
        for plugin_rel, plugin_text in _OPENCODE_PLUGINS.items():
            if (plugin_rel == wanted and role == "developer") or (root / plugin_rel).exists():
                files[plugin_rel] = plugin_text
    if (root / ".codex").is_dir():
        for fname in skills:
            src = _SKILLS_SRC / fname
            if not src.exists():
                continue
            stem = Path(fname).stem
            skill_md, openai_yaml = _to_codex_skill(fname, src.read_text(encoding="utf-8"))
            files[f".agents/skills/{stem}/SKILL.md"] = skill_md
            if openai_yaml:
                files[f".agents/skills/{stem}/agents/openai.yaml"] = openai_yaml
        for fname in agents:
            src = _AGENTS_SRC / fname
            if src.exists():
                files[f".codex/agents/{Path(fname).stem}.toml"] = _to_codex_agent(fname, src.read_text(encoding="utf-8"))
    return files


def _record_manifest(root: Path, role: str = "developer") -> None:
    """Write .nexus/manifest.json: this version, the role, and the hash of every file nexus ships here."""
    channel.save_manifest(root, _VERSION, {rel: channel.sha(text) for rel, text in _builtin_files(root, role).items()}, role)


_UVX_FROM = re.compile(r'("--from",\s*)"(?:nexus-dev-toolkit[^"]*|git\+[^"]*nexus-dev-toolkit[^"]*)"')


def _ours(source: str) -> bool:
    """An MCP `--from` value nexus wrote: the PyPI package or a git install of it. Local paths
    (NEXUS_MCP_FROM, a wheel) are left alone."""
    return source.startswith("nexus-dev-toolkit") or (source.startswith("git+") and "nexus-dev-toolkit" in source)


def _refresh_mcp_configs(root: Path, table: Table, want: str | None = None) -> None:
    """Point existing nexus MCP entries at a channel (default: this CLI's). Only entries nexus
    wrote (uvx --from nexus-dev-toolkit… or git+…nexus-dev-toolkit@…) are touched; custom
    commands are left alone. A git-installed CLI points them at its own commit."""
    want = want or _mcp_args()[2]
    mcp_path = root / ".mcp.json"
    if mcp_path.is_file():
        try:
            data = json.loads(mcp_path.read_text())
            args = data.get("mcpServers", {}).get("nexus", {}).get("args", [])
            if "--from" in args:
                i = args.index("--from") + 1
                if i < len(args) and _ours(args[i]) and args[i] != want:
                    args[i] = want
                    mcp_path.write_text(json.dumps(data, indent=2))
                    table.add_row(".mcp.json", f"[cyan]updated[/cyan] (MCP server: {escape(want)})")
        except Exception:
            table.add_row(".mcp.json", "[yellow]unreadable — not changed[/yellow]")
    oc = root / "opencode.json"
    if oc.is_file():
        try:
            data = json.loads(oc.read_text())
            mcp_map = data.get("mcp", {})
            servers = mcp_map.get("servers")
            target = servers if isinstance(servers, dict) and "type" not in servers else mcp_map
            cmd = target.get("nexus-mcp", {}).get("command", [])
            if "--from" in cmd:
                i = cmd.index("--from") + 1
                if i < len(cmd) and _ours(cmd[i]) and cmd[i] != want:
                    cmd[i] = want
                    oc.write_text(json.dumps(data, indent=2))
                    table.add_row("opencode.json", f"[cyan]updated[/cyan] (MCP server: {escape(want)})")
        except Exception:
            table.add_row("opencode.json", "[yellow]unreadable — not changed[/yellow]")
    cx = root / ".codex" / "config.toml"
    if cx.is_file():
        text = cx.read_text(encoding="utf-8")
        block = re.search(r"(?ms)^\[mcp_servers\.nexus\]\n.*?(?=^\[|\Z)", text)
        if block:
            new_block = _UVX_FROM.sub(lambda m: f'{m.group(1)}"{want}"', block.group(0))
            if new_block != block.group(0):
                cx.write_text(text[:block.start()] + new_block + text[block.end():], encoding="utf-8")
                table.add_row(".codex/config.toml", f"[cyan]updated[/cyan] (MCP server: {escape(want)})")


def _sync_project(root: Path) -> Table | None:
    """Sync built-in skills/agents into root. None if root isn't a nexus project (none of
    .claude/, .opencode/ or .codex/ present) — callers decide how to handle that case.

    Also: backs up edited built-ins before replacing them, removes files nexus wrote earlier but
    no longer ships (only if unedited), points MCP configs at this CLI's channel, and records
    .nexus/manifest.json."""
    has_claude = (root / ".claude").is_dir()
    has_opencode = (root / ".opencode").is_dir()
    has_codex = (root / ".codex").is_dir()

    if not has_claude and not has_opencode and not has_codex:
        return None

    table = Table(show_header=True, header_style="dim")
    table.add_column("File")
    table.add_column("Status")

    old = channel.load_manifest(root)
    for problem in old.problems:
        table.add_row(str(channel.MANIFEST), f"[yellow]{escape(problem)}[/yellow]")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    role = old.role or "developer"
    files = _builtin_files(root, role)
    for rel, text in files.items():
        _sync_file(table, root / rel, text, rel, root, old, stamp)

    if has_claude and _write_claude_settings(root, graphify_hook=False):
        table.add_row(".claude/settings.json", "[cyan]updated[/cyan] (nexus MCP server and tools approved)")

    if has_codex and (root / ".codex" / "hooks.json").exists():
        # Only re-add the graphify hook where the project already opted into one.
        added = _write_codex_hooks(root)
        table.add_row(".codex/hooks.json", "[cyan]updated[/cyan]" if added else "[dim green]ok[/dim green]")

    removed, kept = channel.prune(root, old, set(files))
    for rel in removed:
        table.add_row(rel, "[cyan]removed[/cyan] (no longer shipped by nexus)")
    for rel in kept:
        table.add_row(rel, "[yellow]kept — no longer shipped, but you edited it; delete it yourself if unused[/yellow]")

    for rel in _write_guides(root):
        table.add_row(rel, "[cyan]created[/cyan] (yours to edit — never overwritten)")
    _refresh_mcp_configs(root, table)
    channel.save_manifest(root, _VERSION, {rel: channel.sha(text) for rel, text in files.items()}, role)
    return table


@app.command()
def sync(
    project_dir: str = typer.Argument(".", help="Project directory to sync"),
) -> None:
    """Sync built-in skills and agents to their latest versions (custom files untouched)."""
    root = Path(project_dir).resolve()
    table = _sync_project(root)
    if table is None:
        console.print("  [red]✗[/red]  Not a nexus project. Run [cyan]nexus init[/cyan] first.\n")
        raise typer.Exit(1)

    console.print(f"\n  [cyan]▶[/cyan]  Syncing built-ins in [bold]{root}[/bold]\n")
    console.print(table)
    console.print()


@app.command()
def doctor(
    project_dir: str = typer.Argument(".", help="Project directory to check"),
) -> None:
    """Validate the nexus project setup and show what's working or missing."""
    root = Path(project_dir).resolve()

    table = Table(show_header=True, header_style="dim", show_lines=False)
    table.add_column("Check", style="dim white")
    table.add_column("Status")

    has_failure = False

    def ok(msg: str) -> str:
        return f"[green]✓[/green]  {msg}"

    def warn(msg: str) -> str:
        return f"[yellow]⚠[/yellow]  {msg}"

    def fail(msg: str) -> str:
        nonlocal has_failure
        has_failure = True
        return f"[red]✗[/red]  {msg}"

    # ── nexus ────────────────────────────────────────────────────────────────
    releases = _fetch_releases() if channel.is_prerelease(_VERSION) else None
    if releases is not None:
        target = channel.pick_update(_VERSION, releases)
        reachable = True
    else:
        latest_version = _fetch_latest_pypi_version()
        reachable = latest_version is not None
        target = latest_version if latest_version and _is_outdated(_VERSION, latest_version) else None
    if reachable:
        chan = channel.channel_of(_VERSION)
        if target:
            table.add_row("nexus-dev-toolkit", warn(f"update available: v{_VERSION} → v{target} (run: nexus update)"))
        else:
            table.add_row("nexus-dev-toolkit", ok(f"up to date (v{_VERSION}{', pre-release channel' if chan == 'pre' else ''})"))

    manifest = channel.load_manifest(root)
    if manifest.nexus_version:
        if channel.is_newer(manifest.nexus_version, _VERSION):
            table.add_row("Project synced by", warn(
                f"v{manifest.nexus_version}, newer than the nexus you are running (v{_VERSION}): run "
                + ("nexus update" if channel.is_prerelease(manifest.nexus_version) == channel.is_prerelease(_VERSION)
                   else ("nexus channel v4" if channel.is_prerelease(manifest.nexus_version) else "nexus update"))))
        elif channel.is_newer(_VERSION, manifest.nexus_version):
            table.add_row("Project synced by", warn(f"v{manifest.nexus_version} — run nexus sync to bring it to v{_VERSION}"))
        else:
            table.add_row("Project synced by", ok(f"v{manifest.nexus_version}"))
    for problem in manifest.problems:
        table.add_row("Project manifest", warn(problem))

    uv_path = shutil.which("uv")
    uv_ver = ""
    if uv_path:
        try:
            uv_ver = subprocess.run([uv_path, "--version"], capture_output=True, text=True, timeout=5).stdout.split()[1]
        except Exception:
            uv_ver = "?"
    env = f"Python {sys.version.split()[0]}" + (f", uv {uv_ver}" if uv_path else ", uv not found")
    table.add_row("Environment", ok(env) if sys.version_info >= (3, 10) else fail(env + " — nexus needs Python 3.10+"))

    # ── Tool ─────────────────────────────────────────────────────────────────
    has_claude_bin = bool(shutil.which("claude"))
    has_opencode_bin = bool(shutil.which("opencode"))
    has_codex_bin = bool(shutil.which("codex"))
    table.add_row("Claude Code", ok("installed") if has_claude_bin else warn("not found — install: npm install -g @anthropic-ai/claude-code"))
    opencode_major = _opencode_major()  # None when not installed or unparseable
    opencode_label = f"installed (v{opencode_major})" if opencode_major is not None else "installed"
    table.add_row("OpenCode", ok(opencode_label) if has_opencode_bin else warn(f"not found — install: {_TOOL_CHECK['opencode']['install']}"))
    table.add_row("Codex", ok("installed") if has_codex_bin else warn("not found — install: npm install -g @openai/codex"))

    # ── Project ──────────────────────────────────────────────────────────────
    has_claude_dir = (root / ".claude").is_dir()
    has_opencode_dir = (root / ".opencode").is_dir()
    has_codex_dir = (root / ".codex").is_dir()
    initialized = has_claude_dir or has_opencode_dir or has_codex_dir
    tools_found = ['claude' if has_claude_dir else '', 'opencode' if has_opencode_dir else '', 'codex' if has_codex_dir else '']
    table.add_row(
        "nexus initialized",
        ok(f"yes ({', '.join(filter(None, tools_found))})")
        if initialized else fail("no — run nexus init")
    )

    # MCP config — Claude Code
    if has_claude_dir:
        mcp_path = root / ".mcp.json"
        if not mcp_path.exists():
            table.add_row(".mcp.json", fail("missing"))
        else:
            try:
                mcp_data = json.loads(mcp_path.read_text())
                if "nexus" in mcp_data.get("mcpServers", {}):
                    table.add_row(".mcp.json", ok("nexus entry present"))
                else:
                    table.add_row(".mcp.json", warn("exists but no nexus entry"))
            except Exception:
                table.add_row(".mcp.json", warn("invalid JSON"))

    # MCP config — OpenCode
    if has_opencode_dir:
        oc_json = root / "opencode.json"
        if not oc_json.exists():
            table.add_row("opencode.json", fail("missing"))
        else:
            try:
                oc_data = json.loads(oc_json.read_text())
                oc_mcp = oc_data.get("mcp", {})
                oc_servers = oc_mcp.get("servers")  # v2 shape: mcp.servers; v1 shape: flat mcp
                if "nexus-mcp" in oc_mcp or (isinstance(oc_servers, dict) and "nexus-mcp" in oc_servers):
                    table.add_row("opencode.json", ok("nexus entry present"))
                else:
                    table.add_row("opencode.json", warn("exists but no nexus-mcp entry"))
            except Exception:
                table.add_row("opencode.json", warn("invalid JSON"))

        # graphify plugin — judged from what's on disk, against the installed OpenCode major
        has_plugin_v1 = (root / _OPENCODE_PLUGIN_V1).exists()
        has_plugin_v2 = (root / _OPENCODE_PLUGIN_V2).exists()
        if opencode_major is not None and opencode_major >= 2:
            if has_plugin_v1 and not has_plugin_v2:
                table.add_row("graphify plugin (OpenCode)", warn(f"{_OPENCODE_PLUGIN_V1} is a v1 plugin — OpenCode v2 doesn't run it, run nexus sync"))
            elif has_plugin_v1:
                table.add_row("graphify plugin (OpenCode)", warn(f"legacy {_OPENCODE_PLUGIN_V1} is ignored by OpenCode v2 (it logs a warning at startup) — safe to delete"))
            elif has_plugin_v2:
                table.add_row("graphify plugin (OpenCode)", ok("present (v2)"))
        elif opencode_major is not None:
            if has_plugin_v2 and not has_plugin_v1:
                table.add_row("graphify plugin (OpenCode)", warn(f"{_OPENCODE_PLUGIN_V2} is a v2 plugin — OpenCode v{opencode_major} doesn't run it, run nexus sync"))
            elif has_plugin_v1:
                table.add_row("graphify plugin (OpenCode)", ok("present (v1)"))
        elif has_plugin_v1 or has_plugin_v2:
            table.add_row("graphify plugin (OpenCode)", ok("present"))

    # MCP config — Codex (text check: no tomllib on Python 3.10)
    if has_codex_dir:
        codex_config = root / ".codex" / "config.toml"
        if not codex_config.exists():
            table.add_row(".codex/config.toml", fail("missing"))
        elif "[mcp_servers.nexus]" in codex_config.read_text(encoding="utf-8"):
            table.add_row(".codex/config.toml", ok("nexus entry present"))
        else:
            table.add_row(".codex/config.toml", warn("exists but no [mcp_servers.nexus] entry"))

    # ── Skills & Agents ──────────────────────────────────────────────────────
    role = manifest.role or "developer"
    role_skills, role_agents = _role_skills(role), _role_agents(role)
    if role != "developer":
        table.add_row("Role", ok(f"{role} — {', '.join(Path(s).stem for s in role_skills)}"))
    if has_claude_dir:
        cmd_dir = root / ".claude" / "commands"
        present = [f for f in role_skills if (cmd_dir / f).exists()]
        missing = len(role_skills) - len(present)
        if missing == 0:
            table.add_row("Built-in skills (Claude)", ok(f"all {len(role_skills)} present"))
        else:
            table.add_row("Built-in skills (Claude)", warn(f"{missing} missing — run nexus sync"))

        ag_dir = root / ".claude" / "agents"
        present_ag = [f for f in role_agents if (ag_dir / f).exists()]
        missing_ag = len(role_agents) - len(present_ag)
        if missing_ag == 0:
            table.add_row("Built-in agents (Claude)", ok(f"all {len(role_agents)} present" if role_agents else f"none needed ({role} role)"))
        else:
            table.add_row("Built-in agents (Claude)", warn(f"{missing_ag} missing — run nexus sync"))

    if has_opencode_dir:
        oc_cmd_dir = root / ".opencode" / "commands"
        present_oc = [f for f in role_skills if (oc_cmd_dir / f).exists()]
        missing_oc = len(role_skills) - len(present_oc)
        if missing_oc == 0:
            table.add_row("Built-in skills (OpenCode)", ok(f"all {len(role_skills)} present"))
        else:
            table.add_row("Built-in skills (OpenCode)", warn(f"{missing_oc} missing — run nexus sync"))

        oc_ag_dir = root / ".opencode" / "agents"
        present_oc_ag = [f for f in role_agents if (oc_ag_dir / f).exists()]
        missing_oc_ag = len(role_agents) - len(present_oc_ag)
        if missing_oc_ag == 0:
            table.add_row("Built-in agents (OpenCode)", ok(f"all {len(role_agents)} present" if role_agents else f"none needed ({role} role)"))
        else:
            table.add_row("Built-in agents (OpenCode)", warn(f"{missing_oc_ag} missing — run nexus sync"))

    if has_codex_dir:
        cx_skills_dir = root / ".agents" / "skills"
        present_cx = [f for f in role_skills if (cx_skills_dir / Path(f).stem / "SKILL.md").exists()]
        missing_cx = len(role_skills) - len(present_cx)
        if missing_cx == 0:
            table.add_row("Built-in skills (Codex)", ok(f"all {len(role_skills)} present"))
        else:
            table.add_row("Built-in skills (Codex)", warn(f"{missing_cx} missing — run nexus sync"))

        cx_ag_dir = root / ".codex" / "agents"
        present_cx_ag = [f for f in role_agents if (cx_ag_dir / f"{Path(f).stem}.toml").exists()]
        missing_cx_ag = len(role_agents) - len(present_cx_ag)
        if missing_cx_ag == 0:
            table.add_row("Built-in agents (Codex)", ok(f"all {len(role_agents)} present" if role_agents else f"none needed ({role} role)"))
        else:
            table.add_row("Built-in agents (Codex)", warn(f"{missing_cx_ag} missing — run nexus sync"))

    # ── Knowledge ────────────────────────────────────────────────────────────
    missing_dirs = [d for d in _KNOWLEDGE_DIRS if not (root / d).is_dir()]
    if not missing_dirs:
        table.add_row("Knowledge dirs", ok(f"all {len(_KNOWLEDGE_DIRS)} present"))
    else:
        table.add_row("Knowledge dirs", warn(f"missing: {', '.join(missing_dirs)}"))

    missing_docs = [d for d in _DOCS_DIRS if not (root / d).is_dir()]
    if not missing_docs:
        table.add_row("Docs dirs", ok(f"all {len(_DOCS_DIRS)} present"))
    else:
        table.add_row("Docs dirs", warn(f"missing: {', '.join(missing_docs)} — run nexus init"))

    # ── Knowledge graph backends ────────────────────────────────────────────
    has_graphify = graph_backend.backend_installed("graphify")
    table.add_row("graphify", ok("installed") if has_graphify else warn("not installed — uv tool install graphifyy"))

    has_codegraph = graph_backend.backend_installed("codegraph")
    table.add_row("codegraph", ok("installed") if has_codegraph else warn("not installed — npm i -g @colbymchenry/codegraph"))

    graphify_built = graph_backend.graph_exists("graphify", root)
    codegraph_built = graph_backend.graph_exists("codegraph", root)
    override = graph_backend.get_override()
    active = graph_backend.detect_backend(root)

    if graphify_built and codegraph_built:
        if override in graph_backend.BACKEND_NAMES and graph_backend.graph_exists(override, root):
            reason = f"forced via {graph_backend.ENV_VAR}={override}"
        else:
            reason = "graphify wins ties by default"
        table.add_row("Knowledge graph", warn(f"both graphify and codegraph graphs present — using {active} ({reason})"))
    elif graphify_built or codegraph_built:
        built = "graphify" if graphify_built else "codegraph"
        output = "graphify-out/graph.json" if built == "graphify" else ".codegraph/codegraph.db"
        table.add_row("Knowledge graph", ok(f"{output} exists ({built})"))
    else:
        table.add_row("Knowledge graph", warn("not built — run: graphify . (or codegraph init)"))

    if override and (override not in graph_backend.BACKEND_NAMES or not graph_backend.graph_exists(override, root)):
        table.add_row(
            graph_backend.ENV_VAR,
            warn(f"set to '{override}' but its graph isn't built — ignoring override, run the matching init/build command"),
        )

    if graph_backend.has_graphify_hook(root) and codegraph_built and active == "codegraph":
        table.add_row("Stale hook", warn("graphify PostToolUse hook present but codegraph is the active backend — harmless no-op, remove manually if unwanted"))

    console.print()
    console.print("  [dim]Some tools below are alternatives, not companions (e.g. graphify vs codegraph) — nexus flags conflicts here when both are present.[/dim]")
    console.print()
    console.print(table)
    console.print()

    if has_failure:
        raise typer.Exit(1)


# ── skill subcommands ─────────────────────────────────────────────────────────

_SKILL_TEMPLATE = """\
# /{name}

**{name}** — describe what this skill does.

## When to use

Describe the trigger or context.

## Steps

### 1 — First step

What to do.

### 2 — Second step

What to do next.

### 3 — Output

What the AI should produce when done.
"""


@skill_app.command("add")
def skill_add(
    name: str = typer.Argument(..., help="Skill name (e.g. 'code-review')"),
    project_dir: str = typer.Option(".", "--dir", "-d"),
) -> None:
    """Create a new skill in .claude/commands/."""
    root = Path(project_dir).resolve()
    dest = root / ".claude" / "commands" / f"{name}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        console.print(f"  [yellow]·[/yellow]  .claude/commands/{name}.md already exists")
        return

    dest.write_text(_SKILL_TEMPLATE.format(name=name), encoding="utf-8")
    console.print(f"  [green]✓[/green]  Created .claude/commands/{name}.md")
    console.print(f"  [dim]Edit it and type [cyan]/{name}[/cyan] in Claude Code.[/dim]")


@skill_app.command("list")
def skill_list(
    project_dir: str = typer.Option(".", "--dir", "-d"),
) -> None:
    """List all skills in .claude/commands/."""
    root = Path(project_dir).resolve()
    commands_dir = root / ".claude" / "commands"

    if not commands_dir.exists():
        console.print("  [yellow]·[/yellow]  No .claude/commands/ found. Run [cyan]nexus init[/cyan] first.")
        return

    skills = sorted(commands_dir.glob("*.md"))
    if not skills:
        console.print("  [yellow]·[/yellow]  No skills yet. Run [cyan]nexus skill add <name>[/cyan]")
        return

    table = Table(show_header=True, header_style="dim")
    table.add_column("Skill", style="cyan")
    table.add_column("Source")

    builtins = set(_BUILTIN_SKILLS)
    for s in skills:
        source = "built-in" if s.name in builtins else "custom"
        table.add_row(f"/{s.stem}", source)

    console.print(table)


# ── rule subcommands ──────────────────────────────────────────────────────────

_RULE_TEMPLATE = """\
# {name}

_Project rule — read by AI tools via AGENTS.md._

## Rules

- Rule one
- Rule two
- Rule three

## Rationale

Why these rules exist.
"""


@rule_app.command("add")
def rule_add(
    name: str = typer.Argument(..., help="Rule name (e.g. 'api-standards')"),
    project_dir: str = typer.Option(".", "--dir", "-d"),
) -> None:
    """Create a new rule in knowledge/rules/."""
    root = Path(project_dir).resolve()
    dest = root / "knowledge" / "rules" / f"{name}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        console.print(f"  [yellow]·[/yellow]  knowledge/rules/{name}.md already exists")
        return

    dest.write_text(_RULE_TEMPLATE.format(name=name), encoding="utf-8")
    console.print(f"  [green]✓[/green]  Created knowledge/rules/{name}.md")


@rule_app.command("list")
def rule_list(
    project_dir: str = typer.Option(".", "--dir", "-d"),
) -> None:
    """List all rules in knowledge/rules/."""
    root = Path(project_dir).resolve()
    rules_dir = root / "knowledge" / "rules"

    if not rules_dir.exists():
        console.print("  [yellow]·[/yellow]  No knowledge/rules/ found. Run [cyan]nexus init[/cyan] first.")
        return

    rules = sorted(rules_dir.glob("*.md"))
    if not rules:
        console.print("  [yellow]·[/yellow]  No rules yet. Run [cyan]nexus rule add <name>[/cyan]")
        return

    table = Table(show_header=True, header_style="dim")
    table.add_column("Rule", style="cyan")
    for r in rules:
        table.add_row(r.stem)
    console.print(table)


# ── agent subcommands ─────────────────────────────────────────────────────────

_AGENT_TEMPLATE = """\
---
name: {name}
description: Describe when Claude should spawn this agent (role, not action — e.g. "reviews X for Y")
---

# {name}

## Role

Describe what this agent does.

## Steps

### 1 — Discover context

Read CLAUDE.md, project manifest, and relevant source files.

### 2 — Perform task

What the agent should do.

### 3 — Output

What the agent should return when done.
"""


@agent_app.command("add")
def agent_add(
    name: str = typer.Argument(..., help="Agent name (e.g. 'security-reviewer')"),
    project_dir: str = typer.Option(".", "--dir", "-d"),
) -> None:
    """Create a new subagent in .claude/agents/."""
    root = Path(project_dir).resolve()
    dest = root / ".claude" / "agents" / f"{name}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        console.print(f"  [yellow]·[/yellow]  .claude/agents/{name}.md already exists")
        return

    dest.write_text(_AGENT_TEMPLATE.format(name=name), encoding="utf-8")
    console.print(f"  [green]✓[/green]  Created .claude/agents/{name}.md")
    console.print(f"  [dim]Edit the description so Claude knows when to spawn it.[/dim]")


@agent_app.command("list")
def agent_list(
    project_dir: str = typer.Option(".", "--dir", "-d"),
) -> None:
    """List all subagents in .claude/agents/."""
    root = Path(project_dir).resolve()
    agents_dir = root / ".claude" / "agents"

    if not agents_dir.exists():
        console.print("  [yellow]·[/yellow]  No .claude/agents/ found. Run [cyan]nexus init[/cyan] first.")
        return

    agents = sorted(agents_dir.glob("*.md"))
    if not agents:
        console.print("  [yellow]·[/yellow]  No agents yet. Run [cyan]nexus agent add <name>[/cyan]")
        return

    table = Table(show_header=True, header_style="dim")
    table.add_column("Agent", style="cyan")
    table.add_column("Source")

    builtins = set(_BUILTIN_AGENTS)
    for a in agents:
        source = "built-in" if a.name in builtins else "custom"
        table.add_row(a.stem, source)

    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
