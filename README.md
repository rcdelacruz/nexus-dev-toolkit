# nexus-dev-toolkit


Developer workflow toolkit for Claude Code, OpenCode and Codex. Gives any team a structured Day 0 scaffold and repeatable Day 1 feature cycle via the EPAV methodology.

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

**OpenCode v2** _(instead of, or alongside, Claude Code)_ — `https://opencode.ai/install` only installs v1:
```bash
curl -fsSL https://opencode.ai/v2/install | bash   # new install
opencode upgrade --major                           # or: upgrade an existing v1 install
```
Remove a package-managed v1 (npm, brew, …) first. After upgrading, run `nexus sync` in each project — details under [What `nexus init` Creates](#what-nexus-init-creates).

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

**codegraph** _(alternative to graphify)_ — a different knowledge-graph tool EPAV skills can use instead. Pick one, not both; `nexus doctor` warns if it finds graphs from both built in the same project.

```bash
npm i -g @colbymchenry/codegraph
codegraph install   # wires codegraph into Claude Code / OpenCode / etc.
```

### 2. Install nexus-dev-toolkit

```bash
uv tool install nexus-dev-toolkit
```

Check it installed:
```bash
nexus --version   # prints nexus-dev-toolkit vX.Y.Z
uv tool list      # lists the nexus and nexus-mcp commands
```
`command not found`? Run `uv tool update-shell` and restart your terminal. If `--version` prints a different name, another package is providing a `nexus` command — `uv tool list` shows which.

### 3. Initialize your project

```bash
cd my-project
nexus init .                                        # Claude Code (default), prompts for graphify/codegraph/none + TypeSafe
nexus init . --tool opencode                        # OpenCode
nexus init . --tool codex                           # Codex
nexus init . --graph-backend codegraph              # skip the graph-backend prompt, use codegraph
nexus init . --typesafe                             # skip the TypeSafe prompt, enable it
```


**TypeSafe/Jev** _(optional)_ — replaces a handful of hardcoded keyword-matching
heuristics in the EPAV tools (which architecture-doc section is about auth vs.
security, which of ~30 stack tags an arch doc mentions, which package manager
or IaC tool fits a free-text hint, which CSV column means "acceptance
criteria") with an actual judgment call. Every one of those tools works
exactly the same without it — TypeSafe is off by default, `pip install
nexus-dev-toolkit` never installs it, and every judgment falls back to the
original heuristic if it isn't enabled or the API call fails. Enable at init
with `--typesafe` (or answer `y` at the prompt), then set `TYPESAFE_API_KEY`
(get one at https://console.typesafe.ai/). `nexus doctor` reports whether
it's wired up and whether the key is set. See `tools/README.md` for how it's
implemented.

**Quick try-out** (training and demos) — practise on a throwaway project first; nothing real is touched.

1. **Create the project.** This also creates the folder, so there's nothing to set up first.
2. **Describe the app to build.** `/scaffold` needs to know what it's building. In a real project that's your architecture document, saved in `docs/arch-docs/`. For this try-out, paste the sample below — it saves a short todo-app description into that folder.
3. **Check the setup and open the project in OpenCode.** `nexus doctor` lists each item as working, missing or broken — a `⚠` is fine for optional things; a `✗` needs fixing before you go on.
4. **Type `/scaffold` inside OpenCode.** It starts by reviewing the sample (the EVALUATE phase), then stops and waits — you check what it found, then type the next command.

```bash
# 1. create the project
nexus init ~/nexus-test-opencode --tool opencode --graph-backend graphify

# 2. save the sample as docs/arch-docs/ARCH.md
cd ~/nexus-test-opencode
cat > docs/arch-docs/ARCH.md <<'EOF'
# Nexus Todo - Architecture

A small three-tier todo app used for training.

## Design goals
A modern, minimal UI with a feature-rich UX: clean on screen, but with
inline editing, filters (all / active / done), keyboard shortcuts and
dark mode.

## Tech stack
- Presentation: React 19, Vite, TypeScript, Tailwind CSS (client/)
- Application: Node.js, Express REST API (server/)
- Data: SQLite via better-sqlite3 (migrations/)

## Data model
todos(id, title, completed, created_at)

## API
GET /api/todos, POST /api/todos
PATCH /api/todos/:id, DELETE /api/todos/:id

## Auth
Single-user demo, no login.

## Error handling
JSON body { "error": { "code", "message" } } with the right HTTP status.

## Security
Validate every request body on the server. Parameterised SQL only.
EOF

# 3. check the setup, then open the project in OpenCode
nexus doctor   # checks the setup (✓ ok, ⚠ optional, ✗ fix)
opencode       # opens OpenCode in this project
```
Then, inside OpenCode (step 4):
```
/scaffold → (review) → /plan → (review) → /apply → (review) → /validate
```
Delete the folder when you're done.

### 4. Place your reference docs

`nexus init` creates these folders for you (it never touches files already in `docs/`). Before running `/scaffold`, put everything Claude needs in them:

```
docs/
├── arch-docs/   ← architecture doc, ADRs
├── dev-tasks/   ← task CSVs — read by /evaluate and the load_task MCP tool
├── designs/     ← design exports (e.g. Figma export ZIP)
└── requirements/ ← BRD, PRD, user stories — the what and why
```

Keep requirements out of `arch-docs/`: `ingest_architecture_doc` scans that whole folder, so a PRD there gets parsed as architecture. See the [docs folder guide](https://nexus.coderstudio.co/docs#docs-folder) for what reads each folder.

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

After `/scaffold` completes, build whichever backend you chose at init:
```
/graphify .                              # if you chose graphify
codegraph install && codegraph init      # if you chose codegraph, run in your terminal
```

This generates `graphify-out/graph.json` or `.codegraph/codegraph.db` — EPAV skills use whichever is present, or fall back to full file reads if neither is built yet. Run `nexus doctor` any time to check which backend is active.

---

## The Workflow

### Day 0 — `/scaffold` (once per project)

Produces a production-grade project from your architecture document — plus a Figma design, for a project with a UI: correct stack, mock auth, mock data, design system, AGENTS.md — zero external dependencies. Runs `npm install && npm run dev` (or equivalent) from commit one. For an infrastructure-shaped project (Terraform/OpenTofu, Helm, Ansible), there's no Figma/UI/mock-auth step at all — it generates the IaC modules/playbooks/charts instead, validated with `plan`/`lint`/`template`, never `apply`d against real cloud accounts on Day 0.

### Day 1 — EPAV (every feature, every sprint)

```
/evaluate <task>  →  /plan  →  /apply  →  /validate
```

Each step is a built-in skill in `.claude/commands/`. Every task starts from the dev tasks CSV. Every task ends with acceptance criteria verified.

---

## What `nexus init` Creates

`settings.json`/`graphify.js` below are only created if you pick graphify (the default) at the `--graph-backend` prompt. Pick codegraph instead and neither is scaffolded — codegraph wires and syncs itself via `codegraph install && codegraph init`.

**Claude Code** (`nexus init .`):
```
.claude/
├── commands/          ← EPAV skills + 5 reviewer skills (/code-review, etc.)
├── agents/            ← 5 reviewer subagents (code-reviewer, database-reviewer, etc.)
└── settings.json      ← PostToolUse: graphify auto-updates after every file edit (graphify backend only)
knowledge/
├── rules/             ← coding standards, arch decisions
├── patterns/          ← reusable implementation patterns
├── prompts/dev/       ← task prompt templates
└── retros/            ← retrospective notes
docs/                  ← arch-docs/, dev-tasks/, designs/, requirements/ (empty folders, existing files untouched)
.mcp.json              ← MCP server config
```

**OpenCode** (`nexus init . --tool opencode`):
```
.opencode/
├── commands/          ← same EPAV skills + reviewer skills
├── agents/            ← same reviewer subagents (adapted for OpenCode, marked `mode: subagent`)
└── plugins/
    └── graphify/index.ts  ← graphify auto-update after every tool run (graphify backend only)
knowledge/             ← same structure
docs/                  ← same structure
opencode.json          ← MCP server config
```

Verified on OpenCode v2.2.5; v1 projects keep the v1 layout. Commands, agents and `opencode.json` are written the same for both; only the graphify plugin differs — `nexus init`/`nexus sync` read `opencode --version` and write `.opencode/plugins/graphify/index.ts` for v2 or `.opencode/plugins/graphify.js` for v1 (v2 if it can't tell). `nexus sync` never deletes the other form, and `nexus doctor` flags a plugin your installed OpenCode won't run.

**Installing or upgrading OpenCode** (see [OpenCode's migration guide](https://opencode.ai/v2/docs/migrate-v1/)):
```bash
curl -fsSL https://opencode.ai/v2/install | bash   # install v2 (https://opencode.ai/install only installs v1)
opencode upgrade --major                           # upgrade an existing v1 install to v2
nexus sync                                         # then, in each project: repairs agent files, adds the v2 plugin
```
The v2 installer replaces the v1 binary (both live in `~/.opencode/bin`); remove a package-managed v1 (npm, brew, …) first. v1 and v2 read the same config files, so don't point v1 at a config you've converted to v2's native shape.

**Codex** (`nexus init . --tool codex`):
```
.agents/skills/<name>/
├── SKILL.md           ← same EPAV + reviewer skills — invoke with $evaluate, $plan, …
└── agents/openai.yaml ← EPAV steps only: blocks implicit invocation, so Codex never starts $apply on its own
.codex/
├── agents/*.toml      ← same reviewer subagents (converted to Codex TOML)
├── config.toml        ← [mcp_servers.nexus] (appended — your existing config is never rewritten)
└── hooks.json         ← PostToolUse: graphify auto-update (graphify backend only)
knowledge/             ← same structure
docs/                  ← same structure
```

Codex only loads project `.codex/` config and hooks for **trusted** projects — trust the project when Codex asks.

---

## Commands

```bash
nexus init .                      # Claude Code — set up .claude/ + knowledge/ + .mcp.json
nexus init . --tool opencode      # OpenCode — set up .opencode/ + knowledge/ + opencode.json
nexus init . --tool codex         # Codex — set up .agents/skills/ + .codex/ + knowledge/
nexus --version                   # show installed version
nexus update                      # update the CLI itself; asks whether to also sync in a real terminal
nexus update --sync               # skip the prompt, always sync the current project's skills/agents too
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

Add `[typesafe]` to the package name (`"nexus-dev-toolkit[typesafe]"`) to enable
TypeSafe/Jev-powered detection — `nexus init --typesafe` does this for you.

### MCP Tools

| Tool | Purpose |
|---|---|
| `ingest_architecture_doc` | Load arch doc → `knowledge/rules/arch-summary.md`; also classifies `project_shape` (web_app, mobile_app, backend_api, infrastructure, data_pipeline, cli_or_library) and `has_infrastructure_component`, so `/scaffold` knows whether to generate a UI shell, IaC deliverables, or both |
| `load_task` | Load a CSV task row into context — maps whatever column headers your CSV actually uses onto the standard task fields |
| `generate_project_rules` | Generate `AGENTS.md` from arch doc |
| `resolve_package_versions` | Resolve exact versions via the real tool — npm/pnpm/yarn/pub/go/cargo/maven/gradle/pip, or Terraform/OpenTofu, Helm, and Ansible for infrastructure-shaped projects |

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
