# /evaluate

**EVALUATE** — Step 1 of the E→P→A→V cycle. Orient fully before writing any plan or code.

## Arguments

`/evaluate <task description, CSV path, or feature name>`

## Steps

### 1 — Orient with graphify (if graph exists)

```bash
graphify query "<task context from args>"
```

Note which communities and god nodes are in the blast radius. If no graph exists, suggest `/graphify .` then continue.

### 2 — Load context in priority order

1. **CSV task** — if `docs/dev-tasks/` exists, load the matching row. Fields `user_story`, `description`, `acceptance_criteria`, `dependencies` are the context.
2. **AGENTS.md** — load coding standards from project root if present.
3. **Architecture doc** — scan `docs/arch-docs/` for the relevant section.
4. **knowledge/** — check `knowledge/rules/`, `knowledge/patterns/`, `knowledge/prompts/dev/` for prior patterns.

### 3 — Output this summary, nothing else

```
EVALUATE SUMMARY
────────────────
Task:        <what we are building>
Touches:     <files / modules / graphify communities>
Depends on:  <what must already exist>
Constraints: <from AGENTS.md, arch doc, acceptance criteria>
Risk:        <god nodes or high-degree nodes in blast radius>
```

### 4 — Stop

Do NOT plan. Do NOT write code. End with:

> "Ready to /plan. Type `/plan` when you want the implementation blueprint."
