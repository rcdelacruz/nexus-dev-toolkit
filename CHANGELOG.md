# Changelog

## [3.0.0] - 2026-06-21

### Added
- Initial release
- `nexus setup` — one-command project init + MCP config + sync
- `nexus init` — initialize `.nexus/` in any project
- `nexus sync` — sync `.nexus/` skills and rules to Claude Code, Cursor, GitHub Copilot, Windsurf
- `nexus skill add/list` — manage custom skills
- `nexus rule add/list` — manage project rules
- `nexus update` — self-update via uv or pip
- Built-in skills: `/scaffold`, `/evaluate`, `/plan`, `/apply`, `/validate`, `/epav`
- MCP server with 4 tools: `ingest_architecture_doc`, `load_task`, `generate_project_rules`, `resolve_package_versions`
- Sync adapters for Claude Code, Cursor, GitHub Copilot, Windsurf
