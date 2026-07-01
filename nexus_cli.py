import json
import shutil
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="nexus", no_args_is_help=False, help="nexus-dev-toolkit — Day 0 scaffold + Day 1 EPAV workflow for Claude Code")
skill_app = typer.Typer(name="skill", no_args_is_help=True, help="Manage skills in .claude/commands/")
rule_app = typer.Typer(name="rule", no_args_is_help=True, help="Manage rules in knowledge/rules/")
agent_app = typer.Typer(name="agent", no_args_is_help=True, help="Manage subagents in .claude/agents/")
app.add_typer(skill_app, name="skill")
app.add_typer(rule_app, name="rule")
app.add_typer(agent_app, name="agent")

console = Console()

_VERSION = "3.1.3"

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
]

_AGENTS_SRC = Path(__file__).parent / "tools" / "agents"

_BUILTIN_AGENTS = [
    "deployment-reviewer.md",
    "code-reviewer.md",
    "performance-reviewer.md",
    "monitoring-reviewer.md",
    "database-reviewer.md",
]


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

# ── MCP config ────────────────────────────────────────────────────────────────

_MCP_BLOCK = {
    "nexus": {
        "command": "uvx",
        "args": ["--refresh", "--from", "nexus-dev-toolkit", "nexus-mcp"],
    }
}

_OPENCODE_MCP_BLOCK = {
    "nexus-mcp": {
        "type": "local",
        "command": ["uvx", "--refresh", "--from", "nexus-dev-toolkit", "nexus-mcp"],
    }
}

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


def _init_project(project_dir: Path) -> list[str]:
    """
    nexus init — sets up:
      .claude/commands/     ← built-in skills
      .claude/agents/       ← built-in subagents
      .claude/settings.json ← PostToolUse graphify hook
      knowledge/            ← empty scaffold
    """
    created = []

    # .claude/commands/ — copy built-in skills
    commands_dir = project_dir / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    for skill_name in _BUILTIN_SKILLS:
        src = _SKILLS_SRC / skill_name
        dest = commands_dir / skill_name
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)
            created.append(f".claude/commands/{skill_name}")

    # .claude/agents/ — copy built-in subagents
    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    for agent_name in _BUILTIN_AGENTS:
        src = _AGENTS_SRC / agent_name
        dest = agents_dir / agent_name
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)
            created.append(f".claude/agents/{agent_name}")

    # .claude/settings.json — PostToolUse graphify hook
    settings_path = project_dir / ".claude" / "settings.json"
    if not settings_path.exists():
        settings_path.write_text(json.dumps(_CLAUDE_SETTINGS, indent=2))
        created.append(".claude/settings.json")

    # knowledge/ scaffold
    for d in _KNOWLEDGE_DIRS:
        target = project_dir / d
        target.mkdir(parents=True, exist_ok=True)

    return created


def _strip_claude_frontmatter(content: str) -> str:
    """Remove Claude Code-only frontmatter fields (tools, model) for OpenCode compatibility."""
    if not content.startswith("---"):
        return content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return content
    lines = [
        line for line in parts[1].splitlines()
        if not line.startswith("tools:") and not line.startswith("model:")
    ]
    return "---" + "\n".join(lines) + "---" + parts[2]


def _init_opencode(project_dir: Path) -> list[str]:
    """
    nexus init --tool opencode — sets up:
      .opencode/commands/   ← built-in skills
      .opencode/agents/     ← built-in subagents
      .opencode/plugins/    ← graphify PostToolUse hook
      opencode.json         ← MCP server config
      knowledge/            ← empty scaffold
    """
    created = []

    # .opencode/commands/ — copy built-in skills
    commands_dir = project_dir / ".opencode" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    for skill_name in _BUILTIN_SKILLS:
        src = _SKILLS_SRC / skill_name
        dest = commands_dir / skill_name
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)
            created.append(f".opencode/commands/{skill_name}")

    # .opencode/agents/ — copy built-in subagents, stripping Claude Code-only frontmatter
    agents_dir = project_dir / ".opencode" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for agent_name in _BUILTIN_AGENTS:
        src = _AGENTS_SRC / agent_name
        dest = agents_dir / agent_name
        if src.exists() and not dest.exists():
            dest.write_text(_strip_claude_frontmatter(src.read_text()), encoding="utf-8")
            created.append(f".opencode/agents/{agent_name}")

    # .opencode/plugins/graphify.js — PostToolUse hook
    plugins_dir = project_dir / ".opencode" / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    plugin_path = plugins_dir / "graphify.js"
    if not plugin_path.exists():
        plugin_path.write_text(_OPENCODE_GRAPHIFY_PLUGIN, encoding="utf-8")
        created.append(".opencode/plugins/graphify.js")

    # opencode.json — MCP server config
    opencode_json = project_dir / "opencode.json"
    existing: dict = {}
    if opencode_json.exists():
        try:
            existing = json.loads(opencode_json.read_text())
        except Exception:
            pass
    already_has_mcp = "nexus-mcp" in existing.get("mcp", {})
    existing.setdefault("$schema", "https://opencode.ai/config.json")
    existing.setdefault("mcp", {}).update(_OPENCODE_MCP_BLOCK)
    opencode_json.write_text(json.dumps(existing, indent=2))
    if not already_has_mcp:
        created.append("opencode.json")

    # knowledge/ scaffold
    for d in _KNOWLEDGE_DIRS:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    return created


def _write_mcp_config(project_dir: Path) -> str:
    mcp_path = project_dir / ".mcp.json"
    existing: dict = {}
    if mcp_path.exists():
        try:
            existing = json.loads(mcp_path.read_text())
        except Exception:
            pass
    existing.setdefault("mcpServers", {}).update(_MCP_BLOCK)
    mcp_path.write_text(json.dumps(existing, indent=2))
    return ".mcp.json"


# ── Commands ──────────────────────────────────────────────────────────────────

_SUPPORTED_TOOLS = ["claude", "opencode"]

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
        "install": "curl -fsSL https://opencode.ai/install | bash",
        "install_cmd": None,  # pipe install — run via shell
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

    answer = console.input(f"  Install {info['name']} now? [y/N] ").strip().lower()
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


@app.command()
def init(
    project_dir: str = typer.Argument(".", help="Project directory to initialize"),
    tool: str = typer.Option("claude", "--tool", "-t", help=f"AI coding tool to set up for ({', '.join(_SUPPORTED_TOOLS)})"),
) -> None:
    """Initialize nexus in a project directory. Defaults to Claude Code."""
    if tool not in _SUPPORTED_TOOLS:
        console.print(f"  [red]✗[/red]  Unknown tool '{tool}'. Supported: {', '.join(_SUPPORTED_TOOLS)}")
        raise typer.Exit(1)

    _check_and_offer_install(tool)

    root = Path(project_dir).resolve()
    console.print(f"  [cyan]▶[/cyan]  Initializing nexus for [bold]{tool}[/bold] in [bold]{root}[/bold]\n")

    if tool == "opencode":
        created = _init_opencode(root)
        for f in created:
            console.print(f"  [green]✓[/green]  {f}")
        if not created:
            console.print("  [yellow]·[/yellow]  Already initialized — nothing to do")
            return
        console.print(f"\n  [bold green]Done.[/bold green] Open [bold]{root}[/bold] in OpenCode and type [cyan]/scaffold[/cyan]\n")
    else:
        created = _init_project(root)
        for f in created:
            console.print(f"  [green]✓[/green]  {f}")
        if not created:
            console.print("  [yellow]·[/yellow]  Already initialized — nothing to do")
            return
        mcp = _write_mcp_config(root)
        console.print(f"  [green]✓[/green]  {mcp}")
        console.print(f"\n  [bold green]Done.[/bold green] Open [bold]{root}[/bold] in Claude Code and type [cyan]/scaffold[/cyan]\n")


@app.command()
def update() -> None:
    """Update nexus-dev-toolkit to the latest version."""
    console.print("\n  [cyan]▶[/cyan]  Updating nexus-dev-toolkit…\n")
    if shutil.which("uv"):
        subprocess.run(["uv", "tool", "upgrade", "nexus-dev-toolkit"])
    else:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "nexus-dev-toolkit"])
    console.print("\n  [green]✓[/green]  Done.\n")


@app.command()
def sync(
    project_dir: str = typer.Argument(".", help="Project directory to sync"),
) -> None:
    """Sync built-in skills and agents to their latest versions (custom files untouched)."""
    root = Path(project_dir).resolve()
    has_claude = (root / ".claude").is_dir()
    has_opencode = (root / ".opencode").is_dir()

    if not has_claude and not has_opencode:
        console.print("  [red]✗[/red]  Not a nexus project. Run [cyan]nexus init[/cyan] first.\n")
        raise typer.Exit(1)

    console.print(f"\n  [cyan]▶[/cyan]  Syncing built-ins in [bold]{root}[/bold]\n")

    table = Table(show_header=True, header_style="dim")
    table.add_column("File")
    table.add_column("Status")

    if has_claude:
        (root / ".claude" / "commands").mkdir(parents=True, exist_ok=True)
        (root / ".claude" / "agents").mkdir(parents=True, exist_ok=True)

        for fname in _BUILTIN_SKILLS:
            src = _SKILLS_SRC / fname
            if not src.exists():
                continue
            dst = root / ".claude" / "commands" / fname
            src_text = src.read_text(encoding="utf-8")
            if dst.exists() and dst.read_text(encoding="utf-8") == src_text:
                table.add_row(f".claude/commands/{fname}", "[dim green]ok[/dim green]")
            else:
                dst.write_text(src_text, encoding="utf-8")
                table.add_row(f".claude/commands/{fname}", "[cyan]updated[/cyan]")

        for fname in _BUILTIN_AGENTS:
            src = _AGENTS_SRC / fname
            if not src.exists():
                continue
            dst = root / ".claude" / "agents" / fname
            src_text = src.read_text(encoding="utf-8")
            if dst.exists() and dst.read_text(encoding="utf-8") == src_text:
                table.add_row(f".claude/agents/{fname}", "[dim green]ok[/dim green]")
            else:
                dst.write_text(src_text, encoding="utf-8")
                table.add_row(f".claude/agents/{fname}", "[cyan]updated[/cyan]")

    if has_opencode:
        (root / ".opencode" / "commands").mkdir(parents=True, exist_ok=True)
        (root / ".opencode" / "agents").mkdir(parents=True, exist_ok=True)
        (root / ".opencode" / "plugins").mkdir(parents=True, exist_ok=True)

        for fname in _BUILTIN_SKILLS:
            src = _SKILLS_SRC / fname
            if not src.exists():
                continue
            dst = root / ".opencode" / "commands" / fname
            src_text = src.read_text(encoding="utf-8")
            if dst.exists() and dst.read_text(encoding="utf-8") == src_text:
                table.add_row(f".opencode/commands/{fname}", "[dim green]ok[/dim green]")
            else:
                dst.write_text(src_text, encoding="utf-8")
                table.add_row(f".opencode/commands/{fname}", "[cyan]updated[/cyan]")

        for fname in _BUILTIN_AGENTS:
            src = _AGENTS_SRC / fname
            if not src.exists():
                continue
            dst = root / ".opencode" / "agents" / fname
            src_text = _strip_claude_frontmatter(src.read_text(encoding="utf-8"))
            if dst.exists() and dst.read_text(encoding="utf-8") == src_text:
                table.add_row(f".opencode/agents/{fname}", "[dim green]ok[/dim green]")
            else:
                dst.write_text(src_text, encoding="utf-8")
                table.add_row(f".opencode/agents/{fname}", "[cyan]updated[/cyan]")

        plugin_dst = root / ".opencode" / "plugins" / "graphify.js"
        if plugin_dst.exists() and plugin_dst.read_text(encoding="utf-8") == _OPENCODE_GRAPHIFY_PLUGIN:
            table.add_row(".opencode/plugins/graphify.js", "[dim green]ok[/dim green]")
        else:
            plugin_dst.write_text(_OPENCODE_GRAPHIFY_PLUGIN, encoding="utf-8")
            table.add_row(".opencode/plugins/graphify.js", "[cyan]updated[/cyan]")

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

    # ── Tool ─────────────────────────────────────────────────────────────────
    has_claude_bin = bool(shutil.which("claude"))
    has_opencode_bin = bool(shutil.which("opencode"))
    table.add_row("Claude Code", ok("installed") if has_claude_bin else warn("not found — install: npm install -g @anthropic-ai/claude-code"))
    table.add_row("OpenCode", ok("installed") if has_opencode_bin else warn("not found — install: curl -fsSL https://opencode.ai/install | bash"))

    # ── Project ──────────────────────────────────────────────────────────────
    has_claude_dir = (root / ".claude").is_dir()
    has_opencode_dir = (root / ".opencode").is_dir()
    initialized = has_claude_dir or has_opencode_dir
    table.add_row(
        "nexus initialized",
        ok(f"yes ({', '.join(filter(None, ['claude' if has_claude_dir else '', 'opencode' if has_opencode_dir else '']))})")
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
                if "nexus-mcp" in oc_data.get("mcp", {}):
                    table.add_row("opencode.json", ok("nexus entry present"))
                else:
                    table.add_row("opencode.json", warn("exists but no nexus-mcp entry"))
            except Exception:
                table.add_row("opencode.json", warn("invalid JSON"))

    # ── Skills & Agents ──────────────────────────────────────────────────────
    if has_claude_dir:
        cmd_dir = root / ".claude" / "commands"
        present = [f for f in _BUILTIN_SKILLS if (cmd_dir / f).exists()]
        missing = len(_BUILTIN_SKILLS) - len(present)
        if missing == 0:
            table.add_row("Built-in skills (Claude)", ok(f"all {len(_BUILTIN_SKILLS)} present"))
        else:
            table.add_row("Built-in skills (Claude)", warn(f"{missing} missing — run nexus sync"))

        ag_dir = root / ".claude" / "agents"
        present_ag = [f for f in _BUILTIN_AGENTS if (ag_dir / f).exists()]
        missing_ag = len(_BUILTIN_AGENTS) - len(present_ag)
        if missing_ag == 0:
            table.add_row("Built-in agents (Claude)", ok(f"all {len(_BUILTIN_AGENTS)} present"))
        else:
            table.add_row("Built-in agents (Claude)", warn(f"{missing_ag} missing — run nexus sync"))

    if has_opencode_dir:
        oc_cmd_dir = root / ".opencode" / "commands"
        present_oc = [f for f in _BUILTIN_SKILLS if (oc_cmd_dir / f).exists()]
        missing_oc = len(_BUILTIN_SKILLS) - len(present_oc)
        if missing_oc == 0:
            table.add_row("Built-in skills (OpenCode)", ok(f"all {len(_BUILTIN_SKILLS)} present"))
        else:
            table.add_row("Built-in skills (OpenCode)", warn(f"{missing_oc} missing — run nexus sync"))

        oc_ag_dir = root / ".opencode" / "agents"
        present_oc_ag = [f for f in _BUILTIN_AGENTS if (oc_ag_dir / f).exists()]
        missing_oc_ag = len(_BUILTIN_AGENTS) - len(present_oc_ag)
        if missing_oc_ag == 0:
            table.add_row("Built-in agents (OpenCode)", ok(f"all {len(_BUILTIN_AGENTS)} present"))
        else:
            table.add_row("Built-in agents (OpenCode)", warn(f"{missing_oc_ag} missing — run nexus sync"))

    # ── Knowledge ────────────────────────────────────────────────────────────
    missing_dirs = [d for d in _KNOWLEDGE_DIRS if not (root / d).is_dir()]
    if not missing_dirs:
        table.add_row("Knowledge dirs", ok(f"all {len(_KNOWLEDGE_DIRS)} present"))
    else:
        table.add_row("Knowledge dirs", warn(f"missing: {', '.join(missing_dirs)}"))

    # ── graphify ─────────────────────────────────────────────────────────────
    has_graphify = bool(shutil.which("graphify"))
    table.add_row("graphify", ok("installed") if has_graphify else warn("not installed — uv tool install graphifyy"))

    graph_path = root / "graphify-out" / "graph.json"
    if graph_path.exists():
        table.add_row("Knowledge graph", ok("graphify-out/graph.json exists"))
    else:
        table.add_row("Knowledge graph", warn("not built — run: graphify ."))

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
