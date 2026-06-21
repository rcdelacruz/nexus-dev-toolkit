# Changelog

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
