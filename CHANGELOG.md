# Changelog

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
