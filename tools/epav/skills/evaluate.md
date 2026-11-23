# /evaluate

**EVALUATE** — Step 1 of the E→P→A→V cycle. Orient fully before writing any plan or code.

## Arguments

`/evaluate <task description, CSV path, or feature name>`

## Steps

### 1 — Orient with your knowledge graph (if one exists)

Check which backend this project has built, and use the matching query:

- `graphify-out/graph.json` exists → `graphify query "<task context from args>"`
- `.codegraph/codegraph.db` exists → `codegraph explore "<task context from args>"`
- If both exist, graphify is used by default — set `NEXUS_GRAPH_BACKEND=codegraph` to prefer codegraph instead (`nexus doctor` shows which is active).
- Neither exists → suggest `/graphify .` (or `codegraph init`) then continue without it.

Note which communities/symbols and high-degree nodes are in the blast radius.

### 2 — Load context in priority order

1. **CSV task** — if `docs/dev-tasks/` exists, load the matching row. Fields `user_story`, `description`, `acceptance_criteria`, `dependencies` are the context.
2. **AGENTS.md** — load coding standards from project root if present.
3. **Requirements** — the task's `trace_ids` (from `load_task`) point into `docs/requirements/` (product-wide); read those requirements and their acceptance criteria.
4. **Architecture doc** — `ingest_architecture_doc` with `module=<module>` (or scan `docs/arch-docs/<module>/`) for the relevant section; the stack is what its **Choice** lines say.
5. **Design** — if the task has UI, read `docs/designs/<module>/design.json` for the screens (DES-ids) it touches — or, when the designs were copied in without `/design`, the frames themselves (`ingest_design_export`, write=false).
6. **knowledge/** — check `knowledge/rules/`, `knowledge/patterns/`, `knowledge/prompts/dev/` for prior patterns.

If `load_task` returns a status other than `found` (`empty_fields`, `ambiguous`, `not_found`, `invalid_file`), report it and ask — never fill a blank field or pick a file yourself.

### 3 — Output this summary, nothing else

```
EVALUATE SUMMARY
────────────────
Task:        <what we are building>
Touches:     <files / modules / graph communities or symbols>
Depends on:  <what must already exist>
Constraints: <from AGENTS.md, arch doc, acceptance criteria>
Risk:        <god nodes or high-degree nodes in blast radius>
```

### 4 — Stop

Do NOT plan. Do NOT write code. End with:

> "Ready to /plan. Type `/plan` when you want the implementation blueprint."
