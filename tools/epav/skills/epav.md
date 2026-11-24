# /epav

**E→P→A→V** — Full cycle orchestrator. Runs all four steps in sequence with a gate before APPLY.

## Usage

`/epav [task ID | task description | CSV path]` — no argument: EVALUATE shows the ready tasks (`next_task`) and asks which one.

## Cycle

```
EVALUATE → PLAN → [approval gate] → APPLY → VALIDATE
```

## Steps

### Step 1 — EVALUATE

Follow the `/evaluate` skill exactly. Output the EVALUATE SUMMARY, including its branch recommendation (a new branch named from the task when the user is on `main`). Don't create the branch on your own.

### Step 2 — PLAN

Follow the `/plan` skill exactly. Output the blueprint with blast radius.

**GATE: Stop here. Do not proceed to APPLY until the user explicitly approves.**

Say:
> "Plan ready. Reply **go** or `/apply` to implement, or give feedback to revise."

Still on `main`? Add: "Recommended first: the branch `<name>` for this task — say yes and I'll create it before APPLY." Create it (`git switch -c <name>`) only on that yes.

### Step 3 — APPLY (only after approval)

Follow the `/apply` skill exactly. Implement the plan step by step.

The active knowledge graph backend (graphify or codegraph) stays current automatically — via the PostToolUse hook for graphify, or codegraph's own sync daemon.

### Step 4 — VALIDATE

Follow the `/validate` skill exactly. Check all acceptance criteria, fix all BLOCKERs and FIX NOWs, contribute patterns back to knowledge/.

Then recommend `/code-review` — a separate reviewer reads the changes and often finds what VALIDATE doesn't. Don't start it yourself; the user decides.

## Git

**Never commit, push or open a pull request.** When done, stop: the user reviews the changes (`git diff`) and runs `/commit` and then `/create-pr` — each shows what it will do and waits for their yes.

## Abort at any step

If the user says "stop", "abort", or "cancel" at any point — stop immediately and summarize what was completed and what was not.

## Scope discipline

The EPAV cycle covers **one task at a time**. If additional work surfaces during APPLY, log it to `knowledge/retros/` and finish the current task first.
