# nexus-dev-toolkit


Developer workflow toolkit for Claude Code. Gives any team a structured Day 0 scaffold and repeatable Day 1 feature cycle via the EPAV methodology.

**[Documentation](https://nexus.coderstudio.co/docs)**

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
nexus init .                    # Claude Code (default)
nexus init . --tool opencode    # OpenCode
```

### 4. Place your reference docs

Before running `/scaffold`, put everything Claude needs in `docs/`:

```
docs/
├── arch-docs/   ← architecture doc, ADRs
├── figma/       ← Figma export ZIP
├── brd/         ← Business Requirements Document
└── prd/         ← Product Requirements Document
```

### 5. Start Day 0

Open the project in Claude Code and run:
```
/scaffold
```

`/scaffold` runs EVALUATE first then stops. You drive each phase by typing the next command:

```
/scaffold → (review) → /plan → (review) → /apply → (review) → /validate
```

### 6. Build the knowledge graph

After `/scaffold` completes, run in Claude Code:
```
/graphify .
```

This generates `graphify-out/graph.json` — required by all EPAV skills before starting Day 1.

---

## The Workflow

### Day 0 — `/scaffold` (once per project)

Produces a production-grade project from your architecture document and Figma design: correct stack, mock auth, mock data, design system, AGENTS.md — zero external dependencies. Runs `npm install && npm run dev` (or equivalent) from commit one.

### Day 1 — EPAV (every feature, every sprint)

```
/evaluate <task>  →  /plan  →  /apply  →  /validate
```

Each step is a built-in skill in `.claude/commands/`. Every task starts from the dev tasks CSV. Every task ends with acceptance criteria verified.

---

## What `nexus init` Creates

**Claude Code** (`nexus init .`):
```
.claude/
├── commands/          ← EPAV skills + 5 reviewer skills (/code-review, etc.)
├── agents/            ← 5 reviewer subagents (code-reviewer, database-reviewer, etc.)
└── settings.json      ← PostToolUse: graphify auto-updates after every file edit
knowledge/
├── rules/             ← coding standards, arch decisions
├── patterns/          ← reusable implementation patterns
├── prompts/dev/       ← task prompt templates
└── retros/            ← retrospective notes
.mcp.json              ← MCP server config
```

**OpenCode** (`nexus init . --tool opencode`):
```
.opencode/
├── commands/          ← same EPAV skills + reviewer skills
├── agents/            ← same reviewer subagents (adapted for OpenCode)
└── plugins/
    └── graphify.js    ← tool.execute.after: graphify auto-update
knowledge/             ← same structure
opencode.json          ← MCP server config
```

---

## Commands

```bash
nexus init .                      # Claude Code — set up .claude/ + knowledge/ + .mcp.json
nexus init . --tool opencode      # OpenCode — set up .opencode/ + knowledge/ + opencode.json
nexus --version                   # show installed version
nexus update                      # update to latest version
nexus sync                        # sync built-in skills & agents to latest (custom files untouched)
nexus doctor                      # validate project setup

nexus skill list                  # list all skills in .claude/commands/
nexus skill add my-review         # create a custom skill

nexus agent list                  # list all subagents in .claude/agents/
nexus agent add my-agent          # create a custom subagent

nexus rule list                   # list all rules in knowledge/rules/
nexus rule add api-standards      # create a project rule
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
