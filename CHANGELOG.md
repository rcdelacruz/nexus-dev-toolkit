# Changelog

## [4.0.0a1] - 2026-11-22

First pre-release of nexus 4 (branch `v4`). Install: `curl -fsSL https://nexus.coderstudio.co/install.sh | NEXUS_CHANNEL=v4 bash` or `uv tool install 'nexus-dev-toolkit>=4.0.0a0'`. 3.x users are not affected: installers and `nexus update` on 3.x never pick pre-releases.

### Added
- Release channels. `nexus update` on a pre-release follows the next pre-release (a1 → a2 → b1 → rc1) and moves you to the stable channel once 4.0.0 is out. `nexus channel show | v4 | stable` switches the CLI and the current project together; going back to stable removes v4-only files nexus wrote (never ones you edited) and resets the MCP config. Upgrades use `uv tool install --reinstall` with a version range — never `uv tool upgrade` (can silently do nothing) and never a pin (never upgrades).
- MCP configs follow the CLI's channel. Plain `uvx --from nexus-dev-toolkit` picks the newest stable even when you run a pre-release, so on the pre channel nexus writes `--from 'nexus-dev-toolkit>=4.0.0a0'`; `nexus sync` moves existing `.mcp.json`, `opencode.json` and `.codex/config.toml` entries (custom commands are left alone).
- Project manifest `.nexus/manifest.json`, one per checkout (git-ignored): the nexus version and role that last synced it and the hash of every file nexus wrote. `nexus sync` now backs up a built-in you edited (`.nexus/backup/`, git-ignored) before replacing it, and removes files nexus no longer ships only if they're unedited. `nexus doctor` shows the version and role the checkout was set up with.
- Shared format definitions (`tools/epav/formats/`): task files, traceability IDs, guides, `design.json`, change-request records — each defined once with its own format version, read leniently, written in one documented layout.
- Traceability IDs follow the project's own scheme (defaults: `US-`, `FR-<AREA>-`, `NFR-`, `NFR-SEC-`, `AC-`, epics `E001`, `ADR-…-001`). `load_task` returns `trace_ids` found in the task.
- Stack from explicit decisions: `detect_from_choices()` reads `**Choice**:` lines and the "Choice" column of decision tables, ignoring superseded/rejected choices, "e.g." examples and quoted remarks.

- Role commands, each running EVALUATE → PLAN → stop for approval → APPLY → VALIDATE and committing only `docs/` before opening a pull request (or stopping at the commit when the repo has no remote):
  - `/requirements [source]` — import or write the product's requirements into `docs/requirements/` with stable IDs in the project's own scheme; moves BRD/PRD files out of `docs/arch-docs/`.
  - `/architect <app>` — architecture document + ADRs following the team's guide, every requirement covered, decisions on `**Choice**` lines — and **the product split into epics**: one ADR file per epic (`Epic: E001 — <name>`, `Covers: US-…, FR-…`), every story and functional requirement in exactly one epic. Designs and dev tasks (one CSV per epic) follow the epics.
  - `/design <app>` — optional. `--system <path>` creates every screen, epic by epic, from the designer's own design system (tokens, components, rules, or a Claude Design design-system export) and nothing else; with an export path it reviews an existing export (folder or .zip) against the design guide and the requirements. Writes `design.json`. Designers who work in Claude Design (Claude Desktop) or Figma Make can skip it: copy the export into `docs/designs/<app>/` and `/scaffold` reads it directly.
  - `/change-request <CR-id> "<title>"` — edit requirements → architecture → designs first, then record exactly which IDs changed and which dev tasks they affect.
- `/brd` and `/prd` for product owners and business analysts — write the product's Business and Product Requirements Documents (one each, for the whole product: `docs/requirements/BRD.md`, `PRD.md`; `/brd` takes a problem description, files with the product's requirements, or nothing) from templates (`docs/requirements/templates/`), interviewing for anything the sources don't say (never invented): business rules `BR-001…` with success metrics, then personas, user stories with acceptance criteria and functional/non-functional requirements, each citing the business rule it serves. `/requirements` stays the importer for documents you already have.
- Team training (docs page *Team Training*) and a CareSlot client pack (`examples/careslot-client-pack/`, downloadable as `careslot-client-pack.zip`): a real team — product owner, architect, designer, tech lead, developers, a facilitator — builds CareSlot with the real commands in one shared GitHub repo, each person in their own clone with their own `--role`, work reaching `main` through reviewed pull requests, ending with the client's change request. The finished `examples/clinic-appointments` is what a run looks like.
- `nexus init` / `nexus sync` approve the nexus MCP server and its tools in `.claude/settings.json` (`enabledMcpjsonServers`, `permissions.allow: mcp__nexus__*`), merged into what's there. Claude Code applies them once the folder is trusted, so the "New MCP server found" question and the per-call prompts go away — the folder-trust question stays (a repository can't approve itself).
- A nexus installed from git (`uv tool install 'git+https://github.com/rcdelacruz/nexus-dev-toolkit@v4-preview'`) or a local wheel writes MCP configs that run that same build — a git install as `git+…@<commit>`, identical on every teammate's machine, so a team can try a build before it is on PyPI. `nexus update` on a git install reinstalls the newest commit of its branch, and `nexus sync` then moves the project's MCP entry to that commit; `nexus channel stable` goes back to PyPI.
- Example project `examples/clinic-appointments` ("CareSlot", made up): BRD → PRD → architecture + ADRs (Django + htmx, deliberately not React) → designs (frames, tokens, a React export kept as reference) → the tech lead's Day 0 scaffold (Django 5.2.19, versions pinned by resolve_package_versions, `manage.py check` passes) → dev tasks planned against that code, with TRACE_IDS → change request CR-001, with a role-by-role WALKTHROUGH.md and a CR-002 exercise. Its generated parts come from nexus's own tools (`scripts/build_example.py`) and CI runs nexus's checks on it.
- `nexus init --role developer|product|architect|designer`. Product owners get `/brd`, `/prd`, `/requirements`, `/change-request`; architects and designers get only their commands and the MCP server — no reviewer agents, no graphify hooks. `sync` and `doctor` follow the role recorded in `.nexus/manifest.json`.
- Per-project guides, written once and never overwritten: `docs/requirements/REQUIREMENTS-GUIDE.md`, `docs/arch-docs/ARCHITECTURE-GUIDE.md` (9-section template, ADR template, team patterns), `docs/designs/DESIGN-GUIDE.md` (export format, states, breakpoints, colours from tokens). Each has a `nexus-guide` block with the rules and severities the role commands check; without a project guide, nexus's defaults (the same rules) apply. A CODEOWNERS template is written to `.github/CODEOWNERS.nexus-template` (not live until you rename it).
- MCP tool `ingest_design_export`: reads HTML frames, token CSS (light/dark), tailwind.config, tokens.json and code exports (React/Next/Vite/Vue/Svelte/Angular/Flutter — also without package.json) from a folder or zip, by content; skips build output; matches frame colours to tokens (hex/rgb/hsl/oklch); pairs frames with components; keeps screen IDs (DES-001…) stable across re-imports; previews by default.
- MCP tools `record_change_request` (reads the git diff of `docs/` and judges each changed line by the ID it is about — the ID it starts with, or its section heading's — so IDs merely mentioned don't count → changed/added/removed requirement IDs → the dev-task rows that trace to them; writes `docs/change-requests/CR-xxx.json`) and `trace_tasks` (proposes and fills the optional `TRACE_IDS` column from the IDs a task already cites; lists a CR's affected rows). `/dev-tasks-planner cr <CR-id>` re-plans only those rows.
- `ingest_architecture_doc` follows the project's guide: section names, the stack from `**Choice**` lines and Choice tables (prose mentions are labelled unconfirmed), only ARCH/ADR files (BRD/PRD files in arch-docs are skipped with a note), one module at a time (`module=`), explicit status with the missing sections.
- `load_task` with only a task ID (`/evaluate BOOK-004`) uses the one task file that has that ID; an ID in several files is reported as ambiguous with the files listed. `/dev-tasks-planner` gives task IDs that are unique across a module's CSVs (an epic prefix: `BOOK-001`, `SCHED-001`) and checks it.
- `ingest_architecture_doc` returns the `epics`: one per ADR file (an `Epic: E005 — <name>` line, or the file name `ADR-<PROJECT>-E005-<Name>-v1.0.md`), with its id, name, slug and the IDs on its `Covers:` line; the newest version of an epic's file wins.

### Fixed
- Stack detection ignores what a Choice line says it does not use ("Django + htmx, not a React SPA", "templates instead of the React export", "the React export is a reference only").
- `ingest_design_export`: a note that a screen does not have a state ("empty: not applicable", "no disabled state") no longer counts as that state.
- `ingest_design_export`: route pages written in plain `.js`/`.ts` (Next.js `app/<route>/page.js`, `pages/*.js`, SvelteKit `+page.ts`) are screens — a Next.js export copied in on its own gave 0 screens. Design-system / style-guide pages are not screens.
- `load_task` could not read task files with uppercase headers (`TASK_ID`, `USER_STORY`…) — the layout `/dev-tasks-planner` itself writes. It returned "not found" or blank fields without an error. Headers are now matched in any case/spacing, with or without an Excel BOM. Every result has a `status` (`found`, `empty_fields`, `not_found`, `ambiguous`, `no_file`, `invalid_file`, `out_of_range`); blank required fields are reported, never passed on silently; a name that matches files in several modules lists them instead of picking one.
- Stack detection: "React Native" no longer also reports "React".
- `record_change_request`: a new story added with its acceptance criteria is listed as added, not changed.
- `resolve_package_versions` runs package managers in a worker thread, so a long resolve no longer blocks the MCP server's other tools.

### Changed
- `.nexus/` is per checkout and git-ignores itself: each person's manifest records their own role and the files nexus wrote for it, so teammates with different roles in one repository never overwrite each other's.
- After `nexus init`, the "type …" hint names the role's own first command (`/brd`, `/architect <app>`, `/design <app>`; `/scaffold` for the tech lead).
- `nexus init` and `nexus sync` now add the three guide files to `docs/` when they are missing (3.x created folders only). Existing files are never touched or overwritten.
- `/scaffold` reads the design summary instead of the never-shipped `ingest_figma_zip`, and builds the UI in the stack the architecture doc chose — reusing a React export only when that stack is React.
- CI runs the tests on Python 3.10, 3.11, 3.12 and 3.13 (was 3.12 only). Publishing to PyPI now waits for those tests to pass (3.2.0 was published while a test failed). Pre-releases publish from `v4` only, stable releases from `main` only.
- `scripts/release.py` checks the whole release checklist and builds + tests a clean checkout before anything is pushed.
- `install.sh`: `NEXUS_CHANNEL=v4`.

## [3.2.1] - 2026-11-23

### Fixed
- `load_task` could not read the task CSVs `/dev-tasks-planner` writes. Their headers are upper case (`TASK_ID`, `DESCRIPTION`, …), and `load_task` only looked up lower-case names, so a task ID was "not found" and a loaded row came back with an empty task ID, description and acceptance criteria. Headers are now matched regardless of case, spaces, hyphens or a byte-order mark (`TASK_ID`, `Task ID` and `task-id` all read as `task_id`), and task IDs match regardless of case. `_all_fields` keeps the CSV's own column names.

## [3.2.0] - 2026-11-22

### Added
- Stack detection for most of the world's stacks: `generate_project_rules` now reads the stack from a data catalog (`tools/epav/stack_catalog.json`, 221 technologies across languages, frameworks, databases, mobile, cloud, IaC and more) instead of 8 hardcoded tags. Adding a stack is a JSON entry, not code. Matching is whole-word, so "t3" no longer matches inside other words and "go" never matches inside "mongo". Names that are also English words (Go, Rails, Swift) match only when capitalised. The stack line lists technologies in the order the doc mentions them.
- `resolve_package_versions` supports 22 package managers: npm, pnpm, yarn, bun, pip, uv, poetry, pipenv, composer, bundler, dotnet, swiftpm, cocoapods, mix, cabal, conan, maven, gradle, sbt, pub, go, cargo. Each one runs the real tool in a temp directory and reads the lock file it writes; maven, gradle and sbt read Maven Central, and CocoaPods reads its trunk API. All 22 resolved a real package before release.
- The result now carries a `status`: `resolved`, `partial`, `failed`, `unsupported` (unknown package manager or a stack it can't detect — it no longer falls back to npm) or `tool_missing` (with the install hint). In every non-resolved case the instructions say to stop and never write versions from memory.
- `/scaffold` is stack-neutral: an Ecosystem reference table (manifest, lock file, install, build, lint, pre-commit hooks per ecosystem) and design-token formats per UI stack replace the Next.js-only steps.

### Fixed
- `resolve_package_versions` returned no versions for Go and Dart/Flutter (no module/project was initialised in the temp directory). Both now resolve.
- Version specs: `~5.1` and exact `5.2.3` pins are read correctly for Python, and pre-releases (alpha, beta, RC, milestone, snapshot) are skipped when picking the newest version.

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
