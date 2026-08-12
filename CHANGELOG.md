# Changelog

## [3.1.5] - 2026-08-12

### Added
- `/commit` and `/create-pr` skills (`tools/epav/skills/commit.md`, `create-pr.md`) — staged, well-formed commit creation and PR opening (with a mandatory `/code-review` gate before opening the PR). Documented in `public/docs.html` under Built-in Skills → Git.

### Changed
- `code-reviewer` agent and `/code-review` skill are now read-only: the agent reports findings via `ReportFindings` instead of editing files, defaults to scoping the review to what actually changed (git diff / commits ahead of base) instead of the whole repo, and verifies each finding against a concrete failure scenario before reporting it.

## [3.1.4] - 2026-07-18

### Added
- **codegraph support** — nexus now supports [codegraph](https://github.com/colbymchenry/codegraph) as an alternative to graphify for EPAV's knowledge-graph blast-radius checks. Pick one at `nexus init`'s interactive `--graph-backend` prompt (or pass `--graph-backend graphify|codegraph|none` to skip it); `nexus doctor` detects and reports which is active, and warns if both are installed/built in the same project (graphify wins ties by default; override with `NEXUS_GRAPH_BACKEND=codegraph`).
- `tools/epav/graph_backend.py` — shared detection/query-dispatch module used by `nexus doctor`, `load_task`, and the EPAV skill instructions.
- EPAV skills (`/evaluate`, `/plan`, `/apply`, `/validate`, `/epav`) now branch their knowledge-graph instructions between graphify and codegraph depending on which is active.
- `nexus doctor` and `nexus update` now check PyPI for the latest published version and flag when you're outdated; `public/index.html` and `public/docs.html` show the same reminder as a banner, checked client-side against PyPI directly.
- `nexus update --sync` / `-s` — also syncs the current directory's built-in skills/agents right after upgrading the CLI (skipped gracefully if the current directory isn't a nexus project). Without the flag, `nexus update` asks interactively whether to sync too (in a real terminal — scripted/CI runs skip the prompt and just print the reminder, same as `nexus init`'s existing prompts).

### Changed
- `nexus init` no longer unconditionally scaffolds the graphify `PostToolUse` hook — only when graphify is the chosen backend. codegraph manages its own sync daemon, so nothing is scaffolded for it.

## [3.1.3] - 2026-07-01

### Added
- `nexus sync` — sync built-in skills and agents to latest versions in an existing project; custom files are never touched
- `nexus doctor` — validate project setup: checks tool binaries, MCP config, built-in skills/agents, knowledge dirs, graphify install and graph

### Fixed
- `_check_and_offer_install()` now skips interactive prompt in non-interactive/CI environments (`sys.stdin.isatty()` check) — fixes GitHub Actions test failures

## [3.1.2] - 2026-07-01

### Added
- `nexus init --tool opencode` — full OpenCode support:
  - Copies skills to `.opencode/commands/`
  - Copies subagents to `.opencode/agents/` (Claude Code-only frontmatter stripped)
  - Writes `.opencode/plugins/graphify.js` for auto knowledge graph updates via `tool.execute.after`
  - Writes `opencode.json` with MCP server config
- Tool installation check: `nexus init` detects if Claude Code / OpenCode is missing and offers to install before proceeding
- Docs: OpenCode MCP config example, graphify plugin note in `/apply` section

## [3.1.1] - 2026-06-21

### Added
- `nexus --version` / `-V` flag to show installed version
- `nexus agent add <name>` — create a custom subagent in `.claude/agents/`
- `nexus agent list` — list all subagents in `.claude/agents/`
- Docs: "run inside your project folder" guidance in nexus init section
- Docs: commands table updated with agent subcommands and `--version`
- Docs: `nexus init` output tree now shows all reviewer skills and agents

## [3.1.0] - 2026-06-21

### Added
- 5 built-in reviewer skills: `/code-review`, `/database-review`, `/deployment-review`, `/performance-review`, `/monitoring-review` — copied to `.claude/commands/` on `nexus init`
- 5 built-in subagents copied to `.claude/agents/` on `nexus init` — stack-agnostic, review-focused
- Documentation URL added to PyPI project metadata

### Changed
- Package description updated to reflect Claude Code specificity (not LLM-agnostic)
- README aligned with docs.html: Day 0 flow, reference docs step, graphify step

### Fixed
- CI workflows upgraded to Node.js 24 native action versions (checkout@v7, setup-python@v6, setup-uv@v8.2.0)

## [3.0.1] - 2026-06-21

### Added
- ASCII logo displays when running `nexus` — cyan branded header with version

### Fixed
- graphify documented as prerequisite in README and docs with pros/cons trade-off
- install.sh: interactive graphify setup prompt with graceful non-interactive fallback
- CHANGELOG: corrected 3.0.0 entries to reflect actual v3 architecture

## [3.0.0] - 2026-06-21

### Added
- Initial release — Claude Code workflow toolkit, Day 0 + Day 1 EPAV methodology
- `nexus init` — writes `.claude/commands/`, `.claude/settings.json` (graphify PostToolUse hook), `knowledge/`, `.mcp.json` directly into any project
- `nexus skill add/list` — manage custom skills in `.claude/commands/`
- `nexus rule add/list` — manage project rules in `knowledge/rules/`
- `nexus update` — self-update via uv or pip
- Built-in skills: `/scaffold`, `/evaluate`, `/plan`, `/apply`, `/validate`, `/epav`
- MCP server with 4 tools: `ingest_architecture_doc`, `load_task`, `generate_project_rules`, `resolve_package_versions`
- `install.sh` — interactive installer with optional graphify setup prompt
- graphify integration: PostToolUse hook auto-updates knowledge graph after every file edit; EPAV skills query graph for blast radius and cross-file context
