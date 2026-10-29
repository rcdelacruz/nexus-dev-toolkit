# Verifying a new `nexus init --tool` target without logging in

## Use the tool's own config loader, isolated from the user's real config

Unit tests prove nexus *writes* the right files; they don't prove the target tool
*loads* them. For Codex this is checkable with no account and without touching
`~/.codex`:

```bash
CODEX_HOME=<tmp>/codexhome        # config.toml with [projects."<abs path>"] trust_level = "trusted"
codex mcp list                    # project .codex/config.toml MCP servers (trusted projects only)
codex debug prompt-input "hi"     # model-visible prompt: implicit skill list + custom agents
codex doctor                      # MCP handshake + config health
```

What this can't show: explicit `$skill` invocation (mentions resolve in the TUI,
not in `prompt-input`) and hooks actually firing — both need an authenticated
session. Say so instead of claiming end-to-end coverage.

## Convert tool-specific syntax, not just file formats

Skill bodies carry invocation syntax ("Type `/plan`"). Codex uses `$plan`, and
`/` is its own built-in command namespace — so the conversion must rewrite
references to built-in skills (`_SKILL_REF_RE` in `nexus_cli.py`), with a
lookbehind so paths like `docs/scaffold` survive. Caught only by grepping the
generated output, not by any format test.
