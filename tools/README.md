# tools/

Python package behind `nexus-mcp` (the MCP server `nexus init` wires into
`.mcp.json`/`opencode.json`). This is the implementation of the EPAV MCP
tools that the `/evaluate`, `/plan`, `/apply`, `/validate`, and `/scaffold`
skills call — the skills themselves (prose Claude reads and follows) live
in `tools/epav/skills/*.md`, not here.

```
tools/
├── epav/
│   ├── arch_ingest.py       ingest_architecture_doc
│   ├── task_loader.py       load_task
│   ├── project_rules.py     generate_project_rules
│   ├── package_resolver.py  resolve_package_versions
│   ├── graph_backend.py     graphify/codegraph detection + query (shared)
│   ├── judgment.py          TypeSafe/Jev fail-soft client wrapper (shared)
│   └── skills/*.md          built-in skill prompts (copied into .claude/commands/
│                            or .opencode/commands/ by `nexus init`/`nexus sync`)
└── agents/*.md              built-in subagent personas (copied into .claude/agents/
                             or .opencode/agents/ the same way)
```

`register_epav_tools()` in `tools/epav/__init__.py` registers all four tools
onto the `FastMCP` server — that's the entry point if you're tracing how a
tool call reaches its implementation.

## The `.md` files aren't code

`tools/epav/skills/*.md` and `tools/agents/*.md` are prose that Claude (or
another AI coding agent) reads directly and follows with full contextual
judgment — they are not parsed by any Python here. Don't look for parsing
logic to "improve" in them; there isn't any, and there isn't meant to be
(verified by actually reading all 20 of them — see the TypeSafe section
below for why that distinction matters).

## TypeSafe / Jev integration

Four of the five tools call out to [TypeSafe](https://docs.typesafe.ai)'s
Jev model for judgments that used to be done with hardcoded keyword/
substring matching against free-text input (an arch doc, a CSV header, a
stack hint). Each replaced a real, verified silent-failure mode — not a
hypothetical one — where the old heuristic matched on `hint.lower() in
hint_lower`, ignored the file entirely, or picked whatever came first in a
`for pm in registry` scan.

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

## IaC package-manager resolution

`package_resolver.py` also covers three DevOps tools whose resolution
mechanics genuinely differ from an application package manager's "install
then read a lockfile" shape (this part is plain deterministic code, not a
TypeSafe judgment — each format is fully specified):

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

## Testing

`tests/test_typesafe_judgments.py` covers the TypeSafe-backed judgments
(mocking `judgment.system_one`/`system_one_async`, never hitting the real
API) and `tests/test_iac_package_resolvers.py` covers the deterministic IaC
parsing/orchestration (mocking `subprocess.run`, since CI has none of
`terraform`/`tofu`/`helm`/`ansible-galaxy` installed).

CI installs `typesafe-sdk` explicitly (`--with typesafe-sdk` in
`.github/workflows/test.yml`) even though it's an optional runtime extra —
without it, `judgment.Choice`/`Noul` are `None` and every test short-circuits
to its fallback path before the mocked `system_one*` call is ever reached,
silently skipping the code the test claims to cover. If you add a new
TypeSafe-backed test, run it once with `typesafe-sdk` uninstalled locally to
confirm it actually fails closed instead of passing for the wrong reason.
