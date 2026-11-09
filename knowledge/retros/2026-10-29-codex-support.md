# Codex support (feat/codex-support) — backlog

- [BACKLOG] tests/test_cli.py imports `tomllib` (3.11+), but the package supports 3.10. CI runs 3.12 only, so this is invisible today; switch to `pytest.importorskip("tomllib")` per test or add a 3.10 CI job.
- [BACKLOG] `nexus skill add/list` and `nexus agent add/list` only manage `.claude/` — they ignore `.opencode/` and Codex's `.agents/skills/` / `.codex/agents/`.
- [BACKLOG] `init`/`sync`/`doctor` now branch three ways per tool; a per-tool spec table would remove the remaining duplication before a fourth tool is added.
