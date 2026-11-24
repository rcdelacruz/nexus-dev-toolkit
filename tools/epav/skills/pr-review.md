---
name: pr-review
description: Rigorously verify a specific commit or PR against its own claims — read every changed line, cross-reference project specs, and actually build/test the code in an isolated worktree instead of trusting the commit message or a green CI badge.
---

**pr-review** — deep-verify a pull request (every commit in it) or one commit, by number, URL or SHA, and report a narrative review with a clear verdict. Posting it to GitHub happens only after the user's yes.

## When to use

Invoke when the user asks to review a specific commit, PR, or "the dev's latest work" and gives a PR number or URL, or a commit SHA (`/pr-review 12`, `/pr-review <url>`, `/pr-review <sha>`). This is not the same as `/code-review` — that reviews the *current* branch's uncommitted/ahead-of-base changes; this reviews an already-made pull request or commit, often not on the branch currently checked out, and holds it to a higher bar: every claim in the commit message gets checked against the actual diff, and the build/tests actually get run, not assumed from a green CI badge.

## Steps

### 1 — Resolve what to review

- **A pull request** (number or URL): `gh pr view <n> --json number,title,body,url,baseRefName,headRefName,headRefOid,commits,author`. Fetch it without switching branches: `git fetch origin pull/<n>/head` (and the base branch). The range is **every commit in the PR**: base = `git merge-base origin/<baseRefName> <headRefOid>`, head = `<headRefOid>`. The PR's title and description are claims to check, like a commit message.
- **One commit** (SHA or commit URL): base = `<sha>^`, head = `<sha>`.
- Confirm both exist locally (`git cat-file -e <sha>`); if not, `git fetch origin` and retry. No `gh` (or not signed in) and only a PR number → say so and ask for the head SHA.

### 2 — Gather the project's context

As `/code-review` step 2 does: the task the branch is for (`load_task` — acceptance criteria, `trace_ids`), the requirement files with those IDs, the epic's ADRs, the design files for UI changes, `AGENTS.md` and `knowledge/rules/`, and — if `graphify-out/graph.json` exists — tell the agent to use `graphify query` / `path` / `explain` (the graph holds the docs as well as the code). Pass paths and IDs, not file contents.

### 3 — Delegate to the pr-verifier agent

Launch the `pr-verifier` agent (Agent tool, `subagent_type: "pr-verifier"`) with: the range (base SHA, head SHA, the list of commits), the PR's title and description (or the commit message) as the claims, the context from step 2, and anything the user said the change should do. Don't do the review yourself in the main thread.

### 4 — Output

Lead in chat with the verdict — **approve / send back / needs a human decision** — and, if it's "send back" or there's a high-severity finding, say so first. Then:

- **With the Artifact tool** (Claude Code with Artifacts): load the `artifact-design` skill and publish the review as an artifact — a masthead naming the repo, the PR and the range, the verdict as a plain badge; the agent's full narrative (what's done well, gaps by severity with failure scenarios, minor items); a findings ledger across rounds if this PR was reviewed before in this session; and a verification-method section (commands run, the worktree, real test counts). A specific title naming the feature, never "PR Review Report". Give the link in chat; don't re-paste the narrative.
- **Without it** (OpenCode, Codex, or no Artifact tool): print the same review as Markdown in chat, and save it to `.nexus/reviews/pr-<n>-<head-short-sha>.md` (`.nexus/` is git-ignored — nothing to commit). Say where it is.

### 5 — Post it to GitHub — only after a yes

Offer it; never post on your own. Show exactly what would be posted — the verdict and a summary of the findings (file:line, what, why), under 60 lines — and the command:
- approve → `gh pr review <n> --approve --body-file <file>`
- send back → `gh pr review <n> --request-changes --body-file <file>`
- needs a human decision → `gh pr review <n> --comment --body-file <file>`

Post only after an explicit yes to that text. GitHub refuses approving or requesting changes on your own pull request — then use `--comment`. Report the URL `gh` prints. One commit (no PR) → nothing to post; say so.
