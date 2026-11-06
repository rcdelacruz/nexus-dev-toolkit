# Verifying OpenCode v2 loads what nexus writes — no model, no login

Unit tests prove nexus *writes* the right files; they don't prove OpenCode *loads* them.
Run these in the project `nexus init --tool opencode` just wrote (measured on v2.2.5):

```bash
opencode debug agents                  # JSON: reviewers must show "mode": "subagent"
opencode api command.list              # {"data":[{"name":…}]} — all built-in skills
opencode plugin list                   # nexus.graphify · local · …/.opencode/plugins/graphify
opencode mcp list                      # nexus-mcp registered
opencode --standalone --print-logs --log-level warn plugin list 2>&1 | grep "failed to load plugin"
```

No output from the last grep = every plugin loaded. `opencode api` takes an OpenAPI operation id
(`opencode api GET /openapi.json > file` lists them — redirect to a file, piping truncates).

## What each failure looked like

- **Agents missing from `debug agents` entirely** → frontmatter not closed. The closing `---`
  must be on its own line; it was once glued onto the last field (`…changes.---`).
- **Agents listed as `primary`** → add `mode: subagent` to the frontmatter.
- **`failed to load plugin … must export a default definition with an id and an effect or setup
  function`** → v1-style named export. v2 wants `export default { id, setup(ctx) }` in a
  directory plugin (`.opencode/plugins/<name>/index.ts`). v1 plugins don't run on v2.
- **"No plugins found" / "No MCP servers configured"** (global plugins and servers missing
  too) → *not* a failure. The first `opencode plugin|mcp list` against a directory OpenCode
  hasn't seen yet returns empty (measured twice, once with and once without `opencode.json`);
  the second call returns the real result. **Always run a check twice before concluding
  something isn't loaded.** (`debug agents` was not affected: it returned the built-ins on the
  first call, and the broken-frontmatter result held across three consecutive calls.)
- **`mcp list` shows `nexus-mcp  connected`** → the real MCP handshake worked on v2 (not just
  that the config parsed).

## What this can't show

A plugin's `execute.after` hook only fires on a *model-driven* tool call. `session.shell`
(`opencode api session.shell`) runs the plugin's `setup` but does **not** fire `execute.after`
— measured. Say "load-verified" rather than claiming the hook fires unless a real tool call
was observed.

## Hygiene

- `opencode api session.create` writes a session into the user's global `opencode.db`; delete
  it afterwards (`opencode api session.remove --param sessionID=…`).
- `~/.config/opencode/opencode.json` can hold plaintext API keys — `opencode debug config`
  masks them, `cat` doesn't. Don't dump the raw file.
- `v2` replaces the v1 binary (same `opencode` command), so v1 behaviour can't be re-tested on
  the same machine once v2 is installed — rely on the migration docs and say so.
