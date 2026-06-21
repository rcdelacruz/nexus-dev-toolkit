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
app.add_typer(skill_app, name="skill")
app.add_typer(rule_app, name="rule")

console = Console()

_VERSION = "3.1.0"

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


@app.callback(invoke_without_command=True)
def _callback(ctx: typer.Context) -> None:
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

@app.command()
def init(
    project_dir: str = typer.Argument(".", help="Project directory to initialize"),
) -> None:
    """Initialize .claude/commands/, .claude/settings.json, and knowledge/ in a project."""
    root = Path(project_dir).resolve()
    console.print(f"  [cyan]▶[/cyan]  Initializing nexus in [bold]{root}[/bold]\n")

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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
