# /plan

**PLAN** — Step 2 of the E→P→A→V cycle. Produce a blueprint. No code yet.

## Prerequisite

EVALUATE must have run first. If it hasn't, run `/evaluate <task>` before continuing.

## Steps

### 1 — Blast radius check

```bash
graphify path "<primary file/module>" "<secondary file/module>"
```

Run for every significant file the plan will touch. State what else will be affected.

### 2 — Write the implementation blueprint

Structure the plan as numbered steps:

```
PLAN
────
1. <file or module> — <what changes and why>
2. <file or module> — <what changes and why>
...

Files created:   <list>
Files modified:  <list>
Files deleted:   <list>

Blast radius:    <from graphify — what else references these>
God nodes touched: <list any with degree > 10>
```

### 3 — State constraints

List which AGENTS.md rules and architecture decisions apply to this plan.

### 4 — Stop and wait

Do NOT write code. End with:

> "Waiting for approval. Reply `/apply` to implement, or give feedback to revise the plan."
