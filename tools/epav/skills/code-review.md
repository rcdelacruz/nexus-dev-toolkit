---
name: code-review
description: Review the current code changes for quality, bugs and best practices when the user asks (/code-review) — recommended after /validate, never started on its own.
---

**code-review** — run a read-only review of the current code changes and report findings.

## When to use

Invoke when the user asks for a code review (`/code-review`, "review my changes"). Don't start it on your own: `/validate` and `/epav` recommend it, and the user decides.

## Steps

### 1 — Scope the review

Default scope is "what changed": uncommitted/staged changes plus any commits ahead of the base branch. If the user names specific files, paths, or asks for a full-codebase review, pass that as the scope instead.

### 2 — Delegate to the code-reviewer agent

Launch the `code-reviewer` agent (Agent tool, `subagent_type: "code-reviewer"`) with a prompt stating the scope from Step 1 and any focus areas the user mentioned (e.g. "focus on the auth changes"). The agent discovers repo context itself, reviews read-only, and reports findings via `ReportFindings` — do not ask it to edit code. If the `ReportFindings` tool isn't available (non-Claude Code tools), the agent prints the findings as a numbered list instead.

### 3 — Output

Relay the agent's `## Repo Context` block and its reported findings to the user. Do not add findings of your own that the agent didn't verify, and do not silently drop findings it reported.

### 4 — Fixes wait for the user

The review only reports. Fix nothing until the user says which findings to fix. After a fix, run `/validate` and `/code-review` again. In the developer loop it's recommended after `/validate` and before `/commit`; it never commits or pushes.

### 5 — Record the review

So `/create-pr` doesn't review the same changes again (in this session or a later one), write down what was reviewed. Take a fingerprint of the files as they are now — this uses a throw-away index, so nothing is staged or changed:

```bash
t=$(mktemp -u); cp "$(git rev-parse --git-path index)" "$t" 2>/dev/null; GIT_INDEX_FILE="$t" git add -A && GIT_INDEX_FILE="$t" git write-tree; rm -f "$t"
```

Write `$(git rev-parse --git-path nexus-code-review)` (inside `.git/`, never committed) with four lines:

```
tree <the fingerprint>
critical <number of critical findings>
high <number of high findings>
date <YYYY-MM-DD HH:MM>
```

After a fix, the files change, so the next review writes a new record.
