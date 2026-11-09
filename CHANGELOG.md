# Changelog

## [jev 3.1.12] - 2026-11-09

`nexus-dev-toolkit-jev` (commands `nexus-jev` / `nexus-jev-mcp`) catches up with the stable `nexus-dev-toolkit` 3.1.10 – 3.1.12. This build has its own version line; the number happens to match the stable release it was synced with.

### Added
- OpenCode v2 support: the graphify plugin is written as `.opencode/plugins/graphify/index.ts` on v2 (`graphify.js` on v1, chosen from `opencode --version`); `init` extends an existing `opencode.json` already on v2's `mcp.servers` shape (as `nexus-jev-mcp`); `doctor` reports the OpenCode version, accepts both MCP shapes and warns about a plugin the installed OpenCode won't run.
- `nexus-jev init --tool codex` — skills in `.agents/skills/`, reviewer subagents as `.codex/agents/*.toml`, the MCP server appended to `.codex/config.toml` as `[mcp_servers.nexus-jev]` (installs `nexus-dev-toolkit-jev`, with the `[typesafe]` extra under `--typesafe`), and a graphify `PostToolUse` hook. `doctor` reports TypeSafe wiring found in the Codex config too.
- `init` creates `docs/arch-docs/`, `docs/dev-tasks/`, `docs/designs/` and `docs/requirements/` (folders only; existing files untouched), with a `doctor` row.

### Fixed
- OpenCode reviewer subagents never loaded on v2 (closing frontmatter `---` glued onto the last field) and registered as primary agents; they are now written correctly and marked `mode: subagent`. Run `nexus-jev sync` in existing projects.
- The OpenCode install hint pointed at the v1-only installer; it now uses `https://opencode.ai/v2/install`.

### Changed
- Codex and OpenCode generated config never reference the stable package (`nexus-dev-toolkit` / `nexus-mcp`); a test now checks every tool's config for that.

---

Entries below are the shared history from the stable package up to the fork point, followed by its later releases as they were merged.

## [3.1.12] - 2026-11-06

### Added
- OpenCode v2 support, verified on v2.2.5 (v1 keeps its layout). Commands, agents and `opencode.json` are written the same for v1 and v2; the graphify plugin is the one piece that differs, because v2 doesn't run v1 plugins. `nexus init` / `nexus sync` read `opencode --version` and write `.opencode/plugins/graphify/index.ts` for v2 or `.opencode/plugins/graphify.js` for v1 (v2 when the version can't be detected). `nexus sync` never deletes the other form. The v2 plugin runs `graphify update` asynchronously and coalesces overlapping runs, so it can't stall OpenCode v2's shared background service.
- `nexus init` extends an existing `opencode.json` that is already on v2's `mcp.servers` shape instead of creating a mixed flat + `servers` file. New files keep the flat `mcp` map, which v2 accepts.
- `nexus doctor`: shows the installed OpenCode major version, accepts both `mcp` and `mcp.servers` for the `nexus-mcp` entry, and warns when the graphify plugin on disk is one your installed OpenCode won't run (or a legacy `graphify.js` v2 ignores).

- README and docs: a "Quick try-out" for training and demos — `nexus init ~/nexus-test-opencode --tool opencode --graph-backend graphify` (creates the folder, no prompts), a small sample architecture doc for `/scaffold` to read, then `nexus doctor`, `opencode` and the `/scaffold` flow.
- README and docs: how to install or upgrade to OpenCode v2 (`curl -fsSL https://opencode.ai/v2/install | bash`, `opencode upgrade --major`) — in the Setup steps and next to the OpenCode layout — and to run `nexus sync` in each project afterwards. The nexus-dev-toolkit Setup step also gets install-check commands (`nexus --version`, `uv tool list`), since other packages (e.g. `nexus-toolkit`) install a `nexus` command too.

### Fixed
- Docs page layout: a wide code line no longer pushes a whole Setup step (and its code blocks) past the column edge — the "Install graphify" and "Build the knowledge graph" steps had the same overflow before this release. The content column is also wider (max 820px → 1100px) and now shrinks with the window instead of forcing a sideways scroll.
- `nexus init --tool opencode` offered to install OpenCode with `https://opencode.ai/install`, and `nexus doctor` hinted the same command — that installer only installs OpenCode 1. Both now use `https://opencode.ai/v2/install`.
- OpenCode reviewer subagents never loaded on v2: the frontmatter written to `.opencode/agents/*.md` had its closing `---` glued onto the last field (`…after code changes.---`), so it was never closed — 0 of the 6 agents registered on OpenCode v2.2.5. The closing delimiter now sits on its own line. Run `nexus sync` in existing projects to repair them.
- OpenCode agents are now marked `mode: subagent`. Without it, v2 registers them as primary agents rather than subagents.
- The graphify auto-update hook was silently dead on OpenCode v2 (`failed to load plugin: Plugin must export a default definition with an id and an effect or setup function`).

## [3.1.11] - 2026-10-29

### Added
- `nexus init` (all tools) creates `docs/arch-docs/`, `docs/dev-tasks/`, `docs/designs/` and `docs/requirements/` — the folders the workflow reads reference docs from. Folders only: existing files in `docs/` are never touched. Re-running `init` on an existing project adds any missing ones. `nexus doctor` shows a warn-only "Docs dirs" row.

## [3.1.10] - 2026-10-29

### Added
- `nexus init --tool codex` — sets up nexus for OpenAI Codex: skills in `.agents/skills/<name>/SKILL.md` (EPAV steps get `agents/openai.yaml` with `allow_implicit_invocation: false` so Codex never starts `$apply`/`$commit` on its own), reviewer subagents converted to `.codex/agents/*.toml`, the nexus MCP server appended to `.codex/config.toml` (existing config never rewritten), and a graphify `PostToolUse` hook in `.codex/hooks.json`. `nexus sync` and `nexus doctor` understand Codex projects.

### Changed
- `code-reviewer` agent and `/code-review` skill fall back to printing findings as a numbered list when the Claude Code-only `ReportFindings` tool isn't available (OpenCode, Codex).

## [3.1.9] - 2026-09-15

### Fixed
- `nexus update --sync` (and the interactive "also sync?" prompt) silently missed any skill/agent added in the exact version just installed. Root cause: after the upgrade subprocess completed, sync ran in the same process using `_BUILTIN_SKILLS`/`_BUILTIN_AGENTS` as they were imported at process start — i.e. the pre-upgrade list — so a just-added built-in never got copied even though the on-disk package was already correct. `update` now re-execs `nexus sync` as a fresh process after a real upgrade, so it always reflects the version actually installed. A plain `nexus sync` (no preceding upgrade) was never affected.

## [3.1.8] - 2026-09-15

### Added
- `pr-review` skill and `pr-verifier` agent — deep-verify a specific commit/PR by SHA or GitHub URL against its own claims: reads every changed file's real diff, cross-references project specs/docs, and actually builds/tests the code in an isolated git worktree instead of trusting the commit message or a green CI badge.
- `dev-tasks-planner` skill — generates or reconciles `docs/dev-tasks/*.csv` files for a module/epic from its architecture doc + ADRs, following the same EVALUATE → PLAN → APPLY → VALIDATE cycle as `/scaffold`, with STATUS values reconciled against real repo state rather than the ARCH doc in the abstract.

### Fixed
- `tests/test_cli.py::test_doctor_healthy_project` asserted a hardcoded built-in skill/agent count; now derives the expected counts from `_BUILTIN_SKILLS`/`_BUILTIN_AGENTS` so it can't drift again.

## [3.1.7] - 2026-08-20

### Fixed
- `nexus install`/`nexus update --sync`/`nexus sync`/`nexus doctor` now recognize `commit.md` and `create-pr.md` as built-in skills. They were added to `tools/epav/skills/` in v3.1.5 but never added to `nexus_cli.py`'s `_BUILTIN_SKILLS` list, so they were silently skipped during install/sync and not detected by `nexus doctor`.

## [3.1.6] - 2026-08-13

### Fixed
- **Critical:** pin `mcp[cli]` to `<2.0.0`. `mcp` 2.0.0 (published 2026-07-28) removed/relocated `mcp.server.fastmcp`, which `tools/epav/__init__.py` imports — this broke `nexus` for anyone doing a fresh install or running `nexus update`/`uvx --refresh` on or after that date, with `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`. v3.1.5 shipped with this dependency unpinned; upgrade to v3.1.6 to fix. Migrating to the `mcp` 2.0.0 API is tracked as follow-up work.

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
