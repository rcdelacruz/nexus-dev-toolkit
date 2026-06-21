# nexus-dev-toolkit

[![PyPI version](https://img.shields.io/pypi/v/nexus-dev-toolkit)](https://pypi.org/project/nexus-dev-toolkit/)
[![Python](https://img.shields.io/pypi/pyversions/nexus-dev-toolkit)](https://pypi.org/project/nexus-dev-toolkit/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Developer workflow toolkit for AI-assisted development. Gives any team a structured Day 0 scaffold and repeatable Day 1 feature cycle via the EPAV methodology.

---

## Why

Ad-hoc AI prompting doesn't scale. Every dev prompts differently, context drifts, and nobody knows what the AI was told last sprint.

`nexus-dev-toolkit` gives your team a single workflow:

- **Day 0** — scaffold the project once, production-grade, zero credentials needed
- **Day 1** — every feature follows the same four steps: evaluate → plan → apply → validate

Every skill, every rule, every pattern lives in the project repo — versioned, shared, and enforced.

---

## The Workflow

### Day 0 — `/scaffold` (once per project)

```
nexus init <project-dir>
```

Sets up `.claude/commands/`, `.claude/settings.json`, and `knowledge/`. Then in Claude Code:

```
/scaffold
```

EVALUATE → PLAN → APPLY → VALIDATE. Produces a production-grade project: correct stack from your arch doc, mock auth, mock data, design system, AGENTS.md — all from your architecture document. Runs with `npm install && npm run dev` (or equivalent) from commit one.

### Day 1 — EPAV (every feature, every sprint)

```
/evaluate   →   /plan   →   /apply   →   /validate
```

Each step is a built-in skill in `.claude/commands/`. Every task starts with a row from the dev tasks CSV. Every task ends with acceptance criteria verified.

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
cd my-project
nexus init .
```

Then open the project in Claude Code and type `/scaffold`.

---

## Commands

```bash
nexus init .                 # set up .claude/commands/ + knowledge/ + .mcp.json
nexus skill add code-review  # create a custom skill in .claude/commands/
nexus skill list             # list all skills
nexus rule add api-standards # create a rule in knowledge/rules/
nexus rule list              # list all rules
nexus update                 # update to latest version
```

---

## What `nexus init` Creates

```
.claude/
├── commands/
│   ├── scaffold.md    ← /scaffold  — Day 0 one-time setup
│   ├── evaluate.md    ← /evaluate  — orient on a task
│   ├── plan.md        ← /plan      — blueprint, no code
│   ├── apply.md       ← /apply     — implement the plan
│   ├── validate.md    ← /validate  — verify acceptance criteria
│   └── epav.md        ← /epav      — full cycle guide
└── settings.json      ← PostToolUse hook: graphify auto-updates after every file edit
knowledge/
├── rules/             ← coding standards, arch decisions
├── patterns/          ← reusable implementation patterns
├── prompts/dev/       ← task prompt templates
└── retros/            ← retrospective notes
.mcp.json              ← MCP server config
```

---

## MCP Server

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

`nexus init` writes `.mcp.json` automatically.

### MCP Tools

| Tool | Purpose |
|---|---|
| `ingest_architecture_doc` | Load arch doc → `knowledge/rules/arch-summary.md` |
| `load_task` | Load a CSV task row into context |
| `generate_project_rules` | Generate `AGENTS.md` from arch doc |
| `resolve_package_versions` | Resolve exact package versions via real package manager |

---

## Custom Skills

```bash
nexus skill add my-code-review
# Edit .claude/commands/my-code-review.md
# Type /my-code-review in Claude Code
```

Custom skills live alongside built-in skills in `.claude/commands/` — versioned in your repo, shared across the team.

---

## License

[MIT](LICENSE)
