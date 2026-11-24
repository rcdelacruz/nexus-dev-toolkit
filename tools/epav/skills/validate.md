# /validate

**VALIDATE** — Step 4 of the E→P→A→V cycle. Verify the implementation before calling it done.

## Prerequisite

APPLY must be complete.

## Steps

### 1 — Knowledge graph blast radius check

- `graphify-out/graph.json` exists → `graphify query "<what we just built>"`
- `.codegraph/codegraph.db` exists → `codegraph explore "<what we just built>"`
- Neither exists → skip, and note in VALIDATE COMPLETE that this check was unavailable.

Check: does anything that references the changed files now behave unexpectedly? Flag any community/symbol boundary crossings that weren't in the plan.

### 2 — Run the project's checks

Run every check the project defines and read the output — never report a check you didn't run:
- The commands are in `AGENTS.md` → `## Commands` (`/scaffold` writes them): lint, format check, type check, tests, build. No such section → use the stack's row in `/scaffold`'s Ecosystem reference (Build gate, Lint / format) and the project's test runner, and say that AGENTS.md lacks the commands.
- Run them one by one. For each: the command, its exit code, and for a failure the lines that matter.
- A failing check is a `[BLOCKER]`. A check that can't run here (a missing tool, a service that isn't up) is reported as **not run** with the reason — never as passed.
- New behaviour needs a test: an acceptance criterion with no test that exercises it is at most `PARTIAL`.

### 3 — Check against acceptance criteria

Load the acceptance criteria from the CSV task (or EVALUATE summary). For each criterion:

```
[ ] <criterion> — PASS / FAIL / PARTIAL
```

### 4 — Classify all issues found

```
[BLOCKER]   — prevents merge, must fix now
[FIX NOW]   — significant issue, fix before moving to next task
[BACKLOG]   — minor, log to knowledge/retros/ and defer
```

### 5 — Fix all BLOCKERs and FIX NOWs before continuing

Do not move to the next task until the implementation passes all acceptance criteria.

### 6 — If a pattern was discovered, contribute it back

If APPLY revealed a better approach or a non-obvious constraint:

```bash
# Append to knowledge/patterns/ or knowledge/rules/coding-standards.md
```

### 7 — When clean

Every check passed and every criterion is PASS → run `set_task_status` with `task_id=<id>`, `status="Done"` (only that row changes; it reaches `main` with this task's pull request). Anything left FAIL/PARTIAL or not run → leave the status as it is and say why.

```
VALIDATE COMPLETE
─────────────────
Checks run:       lint ✓, types ✓, tests ✓ (42 passed), build ✓   ← or "not run: <why>"
Criteria passed:  N/N
Issues fixed:     <list>
Backlog items:    <list added to knowledge/retros/>
```

> "Validate passed. Recommended next: `/code-review` — a separate reviewer reads your changes and often finds what the checks above don't. Then review the changes yourself (`git diff`), `/commit` and `/create-pr`."

Always end with that recommendation, but don't start `/code-review` yourself — the user decides.

**Never commit, push or open a pull request.** When done, stop: the user reviews the changes (`git diff`) and runs `/commit` and then `/create-pr` — each shows what it will do and waits for their yes.
