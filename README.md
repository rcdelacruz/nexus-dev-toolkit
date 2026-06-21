# nexus-dev-toolkit

[![PyPI version](https://img.shields.io/pypi/v/nexus-dev-toolkit)](https://pypi.org/project/nexus-dev-toolkit/)
[![Python](https://img.shields.io/pypi/pyversions/nexus-dev-toolkit)](https://pypi.org/project/nexus-dev-toolkit/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

LLM-agnostic developer workflow toolkit. Gives any team a structured Day 0 scaffold and repeatable Day 1 feature cycle — across Claude Code, Cursor, GitHub Copilot, and Windsurf.

---

## Why

Every team re-invents the same wheel: how do we give our AI assistant the right context? How do we keep skills and rules in sync across devs using different tools? How do we stop ad-hoc prompting and start shipping consistently?

`nexus-dev-toolkit` solves this with two things:

1. **`.nexus/`** — a single source of truth for your project's skills, rules, and knowledge. Tool-agnostic.
2. **`nexus sync`** — translates `.nexus/` to wherever your team works: `.claude/commands/`, `.cursor/rules/`, `.github/copilot-instructions.md`, `.windsurfrules`.

---

## The Workflow

### Day 0 — Scaffold once

```
/scaffold
```

EVALUATE → PLAN → APPLY → VALIDATE. Produces a production-grade project: mock auth, mock data, design system, AGENTS.md, zero external dependencies. Runs with `npm install && npm run dev` (or equivalent for your stack) from the first commit.

### Day 1 — Ship features with EPAV

Every feature follows the same four steps:

```
/evaluate   →   /plan   →   /apply   →   /validate
```

No ad-hoc prompting. No drift. Every dev on the team follows the same cycle.

---

## Install

**Requirements:** Python 3.10+, `uv` (recommended) or `pip`

```bash
# Recommended
uv tool install nexus-dev-toolkit

# Or via pip
pip install nexus-dev-toolkit
```

---

## Quick Start

```bash
# Go to your project
cd my-project

# One-command setup: init .nexus/, write MCP config, sync to your LLM tool
nexus setup

# Then open your AI assistant and type:
# /scaffold
```

`nexus setup` detects your LLM tool automatically (Claude Code, Cursor, etc.) and wires everything in one step.

---

## Commands

```bash
nexus setup                  # init + MCP config + sync (one command)
nexus init                   # init .nexus/ only
nexus sync                   # push .nexus/ → detected LLM tool(s)
nexus sync --tool cursor     # force a specific tool

nexus skill add code-review  # create a custom skill
nexus skill list             # list all skills

nexus rule add api-standards # create a project rule
nexus rule list              # list all rules

nexus update                 # update to latest version
```

---

## MCP Server

For Claude Code and Claude Desktop, the MCP server exposes tools that power the EPAV cycle:

```json
{
  "mcpServers": {
    "nexus": {
      "command": "uvx",
      "args": ["--refresh", "--from", "nexus-dev-toolkit", "nexus-mcp"]
    }
  }
}
```

`nexus setup` writes this automatically. Manual config goes in:
- `.mcp.json` — Claude Code (project-level)
- `~/Library/Application Support/Claude/claude_desktop_config.json` — Claude Desktop (macOS)
- `~/.cursor/mcp.json` — Cursor

### MCP Tools

| Tool | Purpose |
|---|---|
| `ingest_architecture_doc` | Load arch doc into knowledge/ |
| `load_task` | Load a task from the CSV into context |
| `generate_project_rules` | Generate AGENTS.md from arch doc |
| `resolve_package_versions` | Resolve exact package versions via real PM |

---

## Built-in Skills

| Skill | Trigger | Purpose |
|---|---|---|
| `/scaffold` | Day 0 | One-time project setup |
| `/evaluate` | Day 1 | Orient on a task, load context |
| `/plan` | Day 1 | Blueprint — no code yet |
| `/apply` | Day 1 | Implement the approved plan |
| `/validate` | Day 1 | Verify against acceptance criteria |
| `/epav` | Any | Full EPAV cycle guide |

---

## Custom Skills and Rules

Skills and rules live in `.nexus/` and are yours to own:

```
.nexus/
├── skills/
│   ├── scaffold.md           ← built-in
│   ├── evaluate.md           ← built-in
│   └── my-code-review.md     ← yours
├── rules/
│   └── api-standards.md      ← yours
└── settings.json
```

```bash
nexus skill add my-code-review
# Edit .nexus/skills/my-code-review.md
nexus sync
# Syncs to all detected LLM tools automatically
```

---

## Supported LLM Tools

| Tool | Output |
|---|---|
| Claude Code | `.claude/commands/` + `.claude/settings.json` |
| Cursor | `.cursor/rules/*.mdc` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Windsurf | `.windsurfrules` |

Auto-detected from your project. Override with `nexus sync --tool <name>`.

---

## License

[MIT](LICENSE)
