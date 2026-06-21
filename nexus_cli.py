import json
import shutil
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="nexus", no_args_is_help=True, help="nexus-dev-toolkit — LLM-agnostic developer workflow toolkit")
skill_app = typer.Typer(name="skill", no_args_is_help=True, help="Manage skills in .nexus/skills/")
rule_app = typer.Typer(name="rule", no_args_is_help=True, help="Manage rules in .nexus/rules/")
app.add_typer(skill_app, name="skill")
app.add_typer(rule_app, name="rule")

console = Console()

# ── Built-in skills shipped with the package ──────────────────────────────────

_SKILLS_SRC = Path(__file__).parent / "tools" / "epav" / "skills"

_BUILTIN_SKILLS = [
    "scaffold.md",
    "evaluate.md",
    "plan.md",
    "apply.md",
    "validate.md",
    "epav.md",
]

# ── .nexus structure ──────────────────────────────────────────────────────────

_NEXUS_DIRS = [
    ".nexus/skills",
    ".nexus/rules",
    ".nexus/knowledge/rules",
    ".nexus/knowledge/patterns",
    ".nexus/knowledge/prompts/dev",
    ".nexus/knowledge/retros",
]

_NEXUS_SETTINGS = {
    "version": "1",
    "tools": ["claude"],
}

# ── MCP config per tool ───────────────────────────────────────────────────────

_MCP_BLOCK = {
    "nexus": {
        "command": "uvx",
        "args": ["--refresh", "--from", "nexus-dev-toolkit", "nexus-mcp"],
    }
}

_MCP_CONFIG_PATHS = {
    "claude-code-project": ".mcp.json",
    "claude-desktop-macos": str(Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"),
    "claude-desktop-windows": str(Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"),
    "cursor": str(Path.home() / ".cursor" / "mcp.json"),
}


def _detect_ide() -> str:
    """Best-effort IDE detection from environment."""
    cwd = Path.cwd()
    if (cwd / ".cursor").exists() or (cwd / ".cursorrules").exists():
        return "cursor"
    if (cwd / ".claude").exists() or (cwd / ".mcp.json").exists():
        return "claude-code-project"
    return "claude-code-project"  # safest default


def _write_mcp_config(config_path: str) -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except Exception:
            pass
    existing.setdefault("mcpServers", {}).update(_MCP_BLOCK)
    path.write_text(json.dumps(existing, indent=2))


def _init_nexus(project_dir: Path) -> list[str]:
    """Create .nexus/ structure and copy built-in skills."""
    created = []

    for d in _NEXUS_DIRS:
        target = project_dir / d
        target.mkdir(parents=True, exist_ok=True)

    # Copy built-in skills
    skills_dest = project_dir / ".nexus" / "skills"
    for skill_name in _BUILTIN_SKILLS:
        src = _SKILLS_SRC / skill_name
        dest = skills_dest / skill_name
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)
            created.append(str(dest.relative_to(project_dir)))

    # Write .nexus/settings.json
    settings_path = project_dir / ".nexus" / "settings.json"
    if not settings_path.exists():
        settings_path.write_text(json.dumps(_NEXUS_SETTINGS, indent=2))
        created.append(".nexus/settings.json")

    return created


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command()
def setup(
    project_dir: str = typer.Argument(".", help="Project directory to initialize"),
    tool: str = typer.Option("", "--tool", "-t", help="LLM tool: claude | cursor | copilot | windsurf"),
) -> None:
    """One-command setup: init project, write MCP config, sync skills."""
    from tools.sync import sync_all

    root = Path(project_dir).resolve()
    console.print(f"\n  [cyan]▶[/cyan]  Setting up nexus in [bold]{root}[/bold]\n")

    # Init .nexus/
    created = _init_nexus(root)
    for f in created:
        console.print(f"  [green]✓[/green]  {f}")

    # Write MCP config
    detected_ide = tool or _detect_ide()
    config_path = _MCP_CONFIG_PATHS.get(detected_ide, ".mcp.json")
    _write_mcp_config(str(root / config_path) if not Path(config_path).is_absolute() else config_path)
    console.print(f"  [green]✓[/green]  MCP config → {config_path}")

    # Sync to LLM tool
    results = sync_all(str(root), tools=[tool] if tool else None)
    for t, files in results.items():
        for f in files:
            rel = Path(f).relative_to(root) if Path(f).is_absolute() else f
            console.print(f"  [green]✓[/green]  [{t}] {rel}")

    console.print(f"\n  [bold green]Done.[/bold green] Open [bold]{root}[/bold] in your editor and type [cyan]/scaffold[/cyan]\n")


@app.command()
def init(
    project_dir: str = typer.Argument(".", help="Project directory to initialize"),
) -> None:
    """Initialize .nexus/ in a project directory."""
    root = Path(project_dir).resolve()
    console.print(f"\n  [cyan]▶[/cyan]  Initializing .nexus/ in [bold]{root}[/bold]\n")

    created = _init_nexus(root)
    for f in created:
        console.print(f"  [green]✓[/green]  {f}")

    if not created:
        console.print("  [yellow]·[/yellow]  Already initialized — nothing to do")

    console.print(f"\n  Run [cyan]nexus sync[/cyan] to push skills to your LLM tool.\n")


@app.command()
def sync(
    project_dir: str = typer.Argument(".", help="Project directory"),
    tool: str = typer.Option("", "--tool", "-t", help="Force a specific tool: claude | cursor | copilot | windsurf"),
) -> None:
    """Sync .nexus/ skills and rules to the detected LLM tool(s)."""
    from tools.sync import sync_all

    root = Path(project_dir).resolve()
    console.print(f"\n  [cyan]▶[/cyan]  Syncing .nexus/ → LLM tools\n")

    results = sync_all(str(root), tools=[tool] if tool else None)

    if not results:
        console.print("  [yellow]·[/yellow]  No LLM tools detected. Use [cyan]--tool claude[/cyan] to force.\n")
        return

    for t, files in results.items():
        console.print(f"  [bold]{t}[/bold]")
        for f in files:
            try:
                rel = Path(f).relative_to(root)
            except ValueError:
                rel = f
            console.print(f"    [green]✓[/green]  {rel}")

    console.print()


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
    """Create a new skill in .nexus/skills/."""
    root = Path(project_dir).resolve()
    dest = root / ".nexus" / "skills" / f"{name}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        console.print(f"  [yellow]·[/yellow]  {dest.relative_to(root)} already exists")
        return

    dest.write_text(_SKILL_TEMPLATE.format(name=name), encoding="utf-8")
    console.print(f"  [green]✓[/green]  Created {dest.relative_to(root)}")
    console.print(f"  [dim]Edit it, then run [cyan]nexus sync[/cyan] to push to your LLM tool.[/dim]")


@skill_app.command("list")
def skill_list(
    project_dir: str = typer.Option(".", "--dir", "-d"),
) -> None:
    """List all skills in .nexus/skills/."""
    root = Path(project_dir).resolve()
    skills_dir = root / ".nexus" / "skills"

    if not skills_dir.exists():
        console.print("  [yellow]·[/yellow]  No .nexus/skills/ found. Run [cyan]nexus init[/cyan] first.")
        return

    skills = sorted(skills_dir.glob("*.md"))
    if not skills:
        console.print("  [yellow]·[/yellow]  No skills yet. Run [cyan]nexus skill add <name>[/cyan]")
        return

    table = Table(show_header=True, header_style="dim")
    table.add_column("Skill", style="cyan")
    table.add_column("Source")

    builtins = {s for s in _BUILTIN_SKILLS}
    for s in skills:
        source = "built-in" if s.name in builtins else "custom"
        table.add_row(f"/{s.stem}", source)

    console.print(table)


# ── rule subcommands ──────────────────────────────────────────────────────────

_RULE_TEMPLATE = """\
# {name}

_Project rule — enforced across all LLM tools via `nexus sync`._

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
    """Create a new rule in .nexus/rules/."""
    root = Path(project_dir).resolve()
    dest = root / ".nexus" / "rules" / f"{name}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        console.print(f"  [yellow]·[/yellow]  {dest.relative_to(root)} already exists")
        return

    dest.write_text(_RULE_TEMPLATE.format(name=name), encoding="utf-8")
    console.print(f"  [green]✓[/green]  Created {dest.relative_to(root)}")
    console.print(f"  [dim]Edit it, then run [cyan]nexus sync[/cyan] to push to your LLM tool.[/dim]")


@rule_app.command("list")
def rule_list(
    project_dir: str = typer.Option(".", "--dir", "-d"),
) -> None:
    """List all rules in .nexus/rules/."""
    root = Path(project_dir).resolve()
    rules_dir = root / ".nexus" / "rules"

    if not rules_dir.exists():
        console.print("  [yellow]·[/yellow]  No .nexus/rules/ found. Run [cyan]nexus init[/cyan] first.")
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
