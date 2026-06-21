# nexus-dev-toolkit

LLM-agnostic developer workflow toolkit. Gives any team a structured Day 0 scaffold and repeatable Day 1 feature cycle — across Claude Code, Cursor, GitHub Copilot, and Windsurf.

```bash
curl -fsSL https://raw.githubusercontent.com/rcdelacruz/nexus-dev-toolkit/main/public/install.sh | bash
```

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
# One-liner
curl -fsSL https://raw.githubusercontent.com/rcdelacruz/nexus-dev-toolkit/main/public/install.sh | bash

# Or via uv
uv tool install nexus-dev-toolkit

# Or via pip
pip install nexus-dev-toolkit
```

---

## Quick Start

```bash
# Initialize a project
cd my-project
nexus setup

# Type /scaffold in your AI assistant to begin Day 0
```

That's it. `nexus setup` creates `.nexus/`, writes your MCP config, and syncs skills to your detected LLM tool.

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

`nexus setup` writes this automatically. Manual config goes in `.mcp.json` (Claude Code project) or `~/Library/Application Support/Claude/claude_desktop_config.json` (Claude Desktop on macOS).

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
│   ├── scaffold.md       ← built-in
│   ├── evaluate.md       ← built-in
│   └── my-code-review.md ← yours
├── rules/
│   └── api-standards.md  ← yours
└── settings.json
```

```bash
nexus skill add my-code-review
# Edit .nexus/skills/my-code-review.md
nexus sync
# → .claude/commands/my-code-review.md
# → .cursor/rules/skill-my-code-review.mdc
# → .github/copilot-instructions.md (merged)
# → .windsurfrules (merged)
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

MIT
