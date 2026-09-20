# tools/

Developer guide to the Python package behind `nexus-mcp` — the MCP server
`nexus init` wires into `.mcp.json`/`opencode.json`, and the built-in skill
and subagent prompts that `nexus init`/`nexus sync` copy into a project's
`.claude/`/`.opencode/` directories.

## Layout

```
tools/
├── epav/
│   ├── arch_ingest.py       ingest_architecture_doc
│   ├── task_loader.py       load_task
│   ├── project_rules.py     generate_project_rules
│   ├── package_resolver.py  resolve_package_versions
│   ├── graph_backend.py     graphify/codegraph detection + query (shared)
│   ├── judgment.py          TypeSafe/Jev fail-soft client wrapper (shared)
│   ├── __init__.py          register_epav_tools() -- entry point onto the MCP server
│   └── skills/*.md          built-in skill prompts (EPAV cycle + reviewers + git/PR)
└── agents/*.md              built-in subagent personas (reviewers, pr-verifier)
```

## How it fits together

```
nexus init  →  writes .mcp.json: {"command": "uvx", "args": [..., "--from",
                "nexus-dev-toolkit", "nexus-mcp"]}
                     │
Claude Code launches the MCP server via that command
                     │
nexus_server.py  →  FastMCP("nexus-dev-toolkit") + register_epav_tools(mcp)
                     │
tools/epav/__init__.py  →  registers all 4 tool functions below onto `mcp`
```

Separately, `nexus init`/`nexus sync` copy `tools/epav/skills/*.md` into
`.claude/commands/` (or `.opencode/commands/`) and `tools/agents/*.md` into
`.claude/agents/`, using the `_BUILTIN_SKILLS`/`_BUILTIN_AGENTS` lists in
`nexus_cli.py` — a CI test asserts every file in those two directories has a
matching entry in those lists (and vice versa), so add to both together
when you add a new built-in skill or agent.

A skill (prose Claude reads directly, e.g. `scaffold.md`) references an MCP
tool by name when it wants Claude to call it (e.g. `scaffold.md` calls
`ingest_architecture_doc` then `resolve_package_versions`). This is
guidance, not a rigid call graph enforced anywhere — a skill can also just
read a file directly instead of calling a tool (`evaluate.md`'s CSV
handling reads the fields inline rather than always naming `load_task`
explicitly). If you rename a tool or change its output shape, grep
`tools/epav/skills/*.md` for the old name/field before assuming nothing
references it.

## The MCP tools

Every tool follows the same contract: a `@mcp.tool()`-decorated async or
sync function, registered by a `register_<name>_tool(mcp)` function, whose
docstring **is** the tool description the calling LLM sees (keep it
accurate — it's not internal documentation, it's the interface). Every one
wraps its body in `try/except Exception` and returns `json.dumps({"error":
...})` on failure rather than raising — a tool that raises breaks the whole
MCP call for the caller with a stack trace instead of a message it can act
on or show the user.

| Tool | File | Does |
|---|---|---|
| `ingest_architecture_doc` | `arch_ingest.py` | Reads arch doc(s), extracts sections by category (stack/auth/security/data-model/...), classifies `project_shape` and `has_infrastructure_component`, writes `knowledge/rules/arch-summary.md` |
| `load_task` | `task_loader.py` | Finds a CSV under `docs/dev-tasks/`, maps its columns onto the standard task fields regardless of header names, returns one row structured for `/evaluate` (plus a graphify/codegraph blast-radius query on the description) |
| `generate_project_rules` | `project_rules.py` | Reads `knowledge/rules/arch-summary.md` (or a given doc), infers the stack, writes `AGENTS.md` + `knowledge/rules/coding-standards.md` |
| `resolve_package_versions` | `package_resolver.py` | Runs the real package manager/IaC tool in a temp dir and returns exact pinned versions — see the IaC section below for the three tools that don't fit the plain "install then read a lockfile" shape |

### `graph_backend.py` (shared, not a tool itself)

Used by `task_loader.py` for blast-radius context, and referenced from
`evaluate.md`/`plan.md`/`validate.md`. Picks between graphify and codegraph
so callers never hardcode which one is active:

- `detect_backend(root)` — `NEXUS_GRAPH_BACKEND` env var wins if set *and*
  that backend's graph actually exists; otherwise a built graph beats a
  merely-installed tool, and graphify wins ties.
- `run_query(text, backend=None, root=...)` — returns `None` on any
  failure (no backend, subprocess error, timeout) — callers treat that as
  "no graph context available," never as an error to surface.
- `has_graphify_hook(root)` — whether the PostToolUse auto-update hook is
  wired into `.claude/settings.json` or `.opencode/plugins/graphify.js`.

## TypeSafe / Jev integration

Four of the five tools call out to [TypeSafe](https://docs.typesafe.ai)'s
Jev model for judgments that used to
be done with hardcoded keyword/substring matching against free-text input
(an arch doc, a CSV header, a stack hint). Each replaced a real, verified
silent-failure mode — not a hypothetical one — where the old heuristic
matched on `hint.lower() in hint_lower`, ignored the file entirely, or
picked whatever came first in a `for pm in registry` scan.

| Tool | Judgment | Old failure mode |
|---|---|---|
| `arch_ingest.py` | which architecture category a doc section belongs to | a heading like "RBAC Rules" matched no keyword and got silently merged into the previous section |
| `arch_ingest.py` | `project_shape` / `has_infrastructure_component` | no equivalent existed — every project was assumed to be a Figma-driven UI app |
| `project_rules.py` | which of ~30 stack tags an arch doc mentions | only 8 hardcoded frameworks were recognized |
| `package_resolver.py` | which package manager / IaC tool fits a stack hint | non-JS/Python/Go/Rust hints (Terraform, Ansible, Helm) silently defaulted to npm |
| `task_loader.py` | which canonical task field a CSV column maps to | a CSV with headers like "Ticket, Story, AC" produced entirely empty fields |

**It's optional, deliberately.** `typesafe-sdk` is in `[project.optional-dependencies]`
(the `typesafe` extra), not the base `dependencies` — a plain `pip install
nexus-dev-toolkit` never pulls it in. Every call site follows the same
pattern:

```python
from tools.epav import judgment

if judgment.Choice is None:        # typesafe-sdk not installed
    return fallback_heuristic(...)

result = await judgment.system_one_async(state=..., questions={...})
if result is None:                 # no TYPESAFE_API_KEY, network error, etc.
    return fallback_heuristic(...)
```

`judgment.py` centralizes this: it imports `Choice`/`Noul`/`Score` from
`typesafe_sdk` at module load and sets them to `None` on `ImportError`, and
`system_one()`/`system_one_async()` catch every exception (missing key,
timeout, rate limit) and return `None`. **Every call site must check for
`None` before constructing a `Choice`/`Noul` object** — a module-level
`from typesafe_sdk import Choice` in any of the four files above would
crash `import tools.epav` entirely when the extra isn't installed, which is
exactly the failure this pattern exists to avoid.

Enable it via `nexus init --typesafe` (writes `nexus-dev-toolkit[typesafe]`
into the `--from` spec `uvx` uses to launch `nexus-mcp`) plus a
`TYPESAFE_API_KEY` env var. `nexus doctor` reports whether it's wired up
and whether the key is set.

**Design lessons learned building this** (worth reading before adding a new
judgment call):
- Batch independent questions about *different* short strings (e.g. N
  headings) by embedding each one's literal text directly in its own
  `instructions`, never by referencing a shared list through an index —
  batching many structurally identical questions over an indexed array
  risked the model binding an answer to the wrong index (observed: two
  adjacent headings' classifications shifted by one position).
- A `Choice`'s confidence reflects certainty *among the options it was
  given*, not whether the option set is complete. Against Terraform/Ansible
  hints, a 9-option registry with no IaC entries returned confidently wrong
  answers (0.76–1.00) for the closest available option — adding the missing
  options fixed it; a higher confidence threshold would not have.
- Classifying on a heading's title alone fails for generic titles ("Architecture",
  "Overview") whose *body* carries the real signal — give the judgment a
  content snippet, not just a label.
- Keep known rules, exact lookups, and strictly-specified machine formats
  (npm's `name@version`, a lockfile's own grammar) in plain code — the
  three IaC tools below need real parsing, not judgment, because their
  formats are fully specified.

## IaC package-manager resolution

`package_resolver.py` also covers three DevOps tools whose resolution
mechanics genuinely differ from an application package manager's "install
then read a lockfile" shape (this part is plain deterministic code, not a
TypeSafe judgment):

- **Terraform / OpenTofu** — `"source@constraint"` (providers only).
  Whichever binary (`terraform` or `tofu`) is on `PATH` is used; both write
  the same `.terraform.lock.hcl`, but at different registry hosts
  (`registry.terraform.io` vs. `registry.opentofu.org`) — the lock-file
  regex matches either.
- **Helm** — `"name@version@repo_url"`. Helm has no central registry, so a
  chart with no repository URL is reported as an error, not guessed at.
- **Ansible** — `"namespace.name:constraint"` (collections only).
  `ansible-galaxy` has no resolve-to-lockfile step, so this installs then
  introspects with `ansible-galaxy collection list` to discover the exact
  version that got installed.

`project_shape: "infrastructure"` and `has_infrastructure_component: true`
(from `ingest_architecture_doc`) are what tell `/scaffold` to generate IaC
deliverables instead of, or alongside, application boilerplate — see
`tools/epav/skills/scaffold.md` for the exact branching.

## Writing or extending a tool

1. Add the function to an existing module, or a new `tools/epav/<name>.py`
   with a `register_<name>_tool(mcp: FastMCP) -> None` function.
2. Decorate the tool function with `@mcp.tool()`. Write the docstring as
   the interface spec (args, return JSON shape) — it's what the calling
   model reads to know how to use the tool.
3. Wrap the body in `try/except Exception`, returning
   `json.dumps({"error": ...})` on failure. Log unexpected exceptions with
   `logger.exception(...)` before returning the error JSON.
4. If the tool needs to interpret free-text input against a fixed set of
   categories, check whether that's a TypeSafe candidate (see above) before
   reaching for keyword matching — and if it's genuinely a strictly-specified
   format instead (a config file grammar, a well-known CLI's output), keep
   it as plain deterministic parsing.
5. Register it in `tools/epav/__init__.py`'s `register_epav_tools()`.
6. Add tests (see below) — new judgment calls need both a TypeSafe-path
   test (mocked) and a fallback-path test.
7. If a built-in skill should call it, reference the tool by its exact
   registered name in the relevant `tools/epav/skills/*.md` file.

## Local dev workflow

```bash
uv pip install -e ".[dev,typesafe]"   # editable install, test + TypeSafe deps
uv run pytest tests/ -v               # or: .venv/bin/python3 -m pytest -q

# Run the MCP server directly (e.g. for the MCP inspector):
uv run nexus-mcp
```

This repo dogfoods itself: `.claude/commands/` and `.claude/agents/` here
are a **synced copy** of `tools/epav/skills/` and `tools/agents/`, not the
source of truth. After editing a skill or agent source file, run
`python -m nexus_cli sync` (or `nexus sync` if installed) to propagate the
change — otherwise a `/scaffold` (etc.) run in this repo's own Claude Code
session will use the stale copy.

## Testing

- `tests/test_server.py` — tool registration onto the MCP server.
- `tests/test_typesafe_judgments.py` — the TypeSafe-backed judgments,
  mocking `judgment.system_one`/`system_one_async` (never hitting the real
  API) and covering both the AI path and the fallback path for each.
- `tests/test_iac_package_resolvers.py` — the deterministic IaC
  parsing/orchestration, mocking `subprocess.run` (CI has none of
  `terraform`/`tofu`/`helm`/`ansible-galaxy` installed).
- `tests/test_cli.py` — `nexus init`/`sync`/`doctor`/etc.; interactive
  y/N-style prompts are tested by calling the command function directly
  (e.g. `nexus_cli.init(...)`), not via `CliRunner.invoke()`, since
  `invoke()` redirects `sys.stdin` itself and silently defeats a
  `_FakeTTY` monkeypatch.

CI installs `typesafe-sdk` explicitly (`--with typesafe-sdk` in
`.github/workflows/test.yml`) even though it's an optional runtime extra —
without it, `judgment.Choice`/`Noul` are `None` and every test short-circuits
to its fallback path before the mocked `system_one*` call is ever reached,
silently skipping the code the test claims to cover. If you add a new
TypeSafe-backed test, run it once with `typesafe-sdk` uninstalled locally
(`uv pip uninstall --python .venv/bin/python typesafe-sdk`) to confirm it
actually fails closed instead of passing for the wrong reason.

## The `.md` files aren't code

`tools/epav/skills/*.md` and `tools/agents/*.md` are prose that Claude (or
another AI coding agent) reads directly and follows with full contextual
judgment — they are not parsed by any Python here. Don't look for parsing
logic to "improve" in them; there isn't any, and there isn't meant to be
(verified by actually reading all 20 of them, not assumed from the file
extension).
