---
name: monitoring-review
description: Review observability gaps, error tracking, logging, metrics, and alerting to ensure production issues are caught and diagnosable, when the user asks (/monitoring-review) — never started on its own.
---

**monitoring-review** — a read-only review of observability (error tracking, logging, metrics, alerting, tracing), by the `monitoring-reviewer` agent.

## When to use

When the user asks (`/monitoring-review`). Don't start it on your own.

## Steps

### 1 — Scope the review

Default scope is "what changed": uncommitted/staged changes plus any commits ahead of the base branch. If the user names files, paths, or asks for the whole codebase, use that instead.

### 2 — Gather the project's context

The reviewer checks the change against what the project decided, not only against general good practice. Collect, and pass in the agent's prompt (paths and IDs, not whole files — it reads them itself):
- **The task** — the branch name or the conversation gives the task ID (`feat/BOOK-004-…`) → `load_task`: acceptance criteria, `trace_ids`, dependencies. No task → say so.
- **Requirements** — the files in `docs/requirements/` that hold those trace IDs (`grep -rl "US-003" docs/requirements`).
- **Architecture** — the epic's ADR file(s) and the ARCH doc in `docs/arch-docs/<module>/` (`ingest_architecture_doc` with `module=` lists them); the decisions are the `**Choice**` lines.
- **Design** — for UI changes: `docs/designs/<module>/design.json` (screens by DES ID, tokens) or the exported frames and the token file the scaffold uses.
- **Rules** — `AGENTS.md` (Commands, Coding standards, Design system) and `knowledge/rules/`.
- **The knowledge graph** — if `graphify-out/graph.json` exists, tell the agent to use it: graphify indexes the docs as well as the code, so `graphify query "<task / changed module>"` finds the requirements, ADRs and code that belong to the change, and `graphify path "<changed file>" "<other>"` / `graphify explain "<symbol>"` show what calls the changed code. (`.codegraph/` instead → `codegraph explore` / `codegraph impact`.)

### 3 — Delegate to the monitoring-reviewer agent

Launch the `monitoring-reviewer` agent (Agent tool, `subagent_type: "monitoring-reviewer"`) with the scope, the context from step 2, and any focus the user named. The agent holds the full checklist and the output format (a `## Repo Context` block, then the findings JSON); it reviews read-only. On a tool without subagents, read `.claude/agents/monitoring-reviewer.md` (or your tool's copy) and follow it yourself.

### 4 — Output

Relay the agent's `## Repo Context` block and its findings. Don't add findings it didn't verify, and don't drop any.

### 5 — Fixes wait for the user

The review only reports. Fix nothing until the user says which findings to fix; it never commits or pushes.
