# nexus-dev-toolkit

[![PyPI version](https://img.shields.io/pypi/v/nexus-dev-toolkit)](https://pypi.org/project/nexus-dev-toolkit/)
[![Python](https://img.shields.io/pypi/pyversions/nexus-dev-toolkit)](https://pypi.org/project/nexus-dev-toolkit/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Developer workflow toolkit for Claude Code. Gives any team a structured Day 0 scaffold and repeatable Day 1 feature cycle via the EPAV methodology.

---

## Why

Ad-hoc AI prompting doesn't scale. Every dev prompts differently, context drifts, and nobody knows what the AI was told last sprint.

nexus-dev-toolkit gives your team a single workflow:

- **Day 0** — scaffold the project once, production-grade, zero credentials needed
- **Day 1** — every feature follows the same four steps: evaluate → plan → apply → validate

Every skill, every rule, every pattern lives in the project repo — versioned, shared, and enforced.

---

## Setup

### 1. Install prerequisites

**uv** (recommended package manager):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Claude Code:**
```bash
npm install -g @anthropic-ai/claude-code
claude login
```

**graphify** _(strongly recommended)_ — builds a queryable knowledge graph of your codebase. EPAV skills query this graph to understand blast radius and cross-file dependencies before touching any code.

| | With graphify | Without graphify |
|---|---|---|
| Context loading | Scoped subgraph — fast, low token cost | Full file reads — slow, high token cost |
| Blast radius | Accurate, graph-backed | Best-effort, grep-based |
| Auto-update | PostToolUse hook keeps graph current | N/A |
| EPAV skills | Full capability | Degraded but functional |

```bash
uv tool install graphifyy   # PyPI package name has double y; command is "graphify"
graphify install             # registers /graphify skill into Claude Code
```

### 2. Install nexus-dev-toolkit

```bash
uv tool install nexus-dev-toolkit
```

### 3. Initialize your project

```bash
cd my-project
nexus init .
```

### 4. Build the knowledge graph

Open the project in Claude Code and run:
```
/graphify .
```

This generates `graphify-out/graph.json` — required by all EPAV skills.

### 5. Start Day 0

```
/scaffold
```

---

## The Workflow

### Day 0 — `/scaffold` (once per project)

EVALUATE → PLAN → APPLY → VALIDATE. Produces a production-grade project from your architecture document and Figma design: correct stack, mock auth, mock data, design system, AGENTS.md — zero external dependencies. Runs `npm install && npm run dev` (or equivalent) from commit one.

### Day 1 — EPAV (every feature, every sprint)

```
/evaluate   →   /plan   →   /apply   →   /validate
```

Each step is a built-in skill in `.claude/commands/`. Every task starts from the dev tasks CSV. Every task ends with acceptance criteria verified.

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
└── settings.json      ← PostToolUse: graphify auto-updates after every file edit
knowledge/
├── rules/             ← coding standards, arch decisions
├── patterns/          ← reusable implementation patterns
├── prompts/dev/       ← task prompt templates
└── retros/            ← retrospective notes
.mcp.json              ← MCP server config
```

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

## MCP Server

`nexus init` writes `.mcp.json` automatically. For Claude Desktop, add manually:

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
