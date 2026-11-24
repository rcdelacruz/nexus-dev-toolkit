# /create-pr

**create-pr** — commit what's left (if anything), review the code (unless that review already happened), push, and open a pull request with a well-structured description — all after one yes from the user.

## When to use

Invoke when the user wants to open a PR for the current branch's changes (e.g. "create a PR", "open a pull request", "/create-pr"). Uncommitted changes are fine: `/create-pr` commits them the way `/commit` does, in the same yes.

**A person reviews before anything leaves this machine.** Typing `/create-pr` asks you to prepare the pull request, not to open it: you show the commit (if any), the review result, the branch, the title and the description and wait for their yes (step 4). Nothing is committed, pushed or opened before that yes.

## Steps

### 1 — Gather context

Run in parallel:
- `git status` — uncommitted and untracked changes.
- `git branch --show-current`, and the base branch (usually `main`; check whether the branch tracks a remote and whether it's up to date).
- `git log <base>..HEAD` — every commit on this branch, not just the latest.
- `git diff <base>...HEAD` and `git diff` — everything the PR will include, committed and not.

Read every commit and the full diff before drafting anything.

### 2 — Plan the commit, if there's anything uncommitted

Draft it exactly as `/commit` step 2 does — the branch (a new `<type>/<short-slug>` one if on `main`), the files by name, no secrets, a Conventional Commits message — but don't run anything yet. Nothing uncommitted → skip this step.

### 3 — Code review, unless it already happened

Skip the review — and say why — when:
- the branch changes only `docs/` (`git diff --name-only <base>` lists nothing outside it): the docs commands already checked those files against the project's guides;
- `/code-review` isn't installed (product, architect and designer roles).

Otherwise check whether these exact files were already reviewed. Read `$(git rev-parse --git-path nexus-code-review)` (written by `/code-review`). Take the fingerprint of what the PR will hold:
- step 2 commits every uncommitted file, or there's nothing uncommitted → the fingerprint of the files as they are now:

  ```bash
  t=$(mktemp -u); cp "$(git rev-parse --git-path index)" "$t" 2>/dev/null; GIT_INDEX_FILE="$t" git add -A && GIT_INDEX_FILE="$t" git write-tree; rm -f "$t"
  ```
- step 2 leaves some files out → there's no matching fingerprint; review.

Then:
- **Same fingerprint as the record** → don't review again. Use the record: "Review: done earlier (`/code-review`, <date>), nothing changed since." If the record's `blocking` is above 0, say so and ask whether those findings were fixed or accepted before going on.
- **No record, or a different fingerprint** → run `/code-review` (it delegates to the `code-reviewer` agent and writes a new record). If it reports a blocking finding — severity `important`, or `critical` / `high` in a numbered list — stop and show them; ask whether to fix them now or go on anyway. Never open the PR while a blocking finding stands unless the user explicitly says to go on.

### 4 — Show it all and wait for one yes

Draft the PR (see "PR description" below), then show the user, and stop:

```
READY — nothing is committed or pushed yet
Commit:  feat/BOOK-004-free-slots (new, from main)    ← only when step 2 has a commit
         src/booking/slots.ts (modified), src/booking/slots.test.ts (new)
         feat(booking): show free slots for a day
Review:  done earlier (/code-review, 2026-11-24 09:12), nothing changed since
         ← or: passed / skipped (docs only) / the findings you showed
PR:      feat/BOOK-004-free-slots → main   (2 commits)
Title:   feat(booking): show free slots for a day
<the full description>

Commit, push and open this pull request? Reply yes, or tell me what to change.
```

- When the branch already has an open pull request (`gh pr view --json url,state` shows `OPEN`), say "Pushing updates pull request #12 (<url>)." instead of the Title/description — and still wait.
- Go on only after an explicit yes to what you showed. A question or an edit request is not a yes: answer, revise, and show the block again. If files change after the yes, show it again.

### 5 — Commit, push and open (after the yes)

- If step 2 planned a commit: `git switch -c <name>` when it's a new branch, `git add <file> <file>` (never `-A` or `.`), and `git commit -m "$(cat <<'EOF' ... EOF)"`. If the commit check (commitizen) or another hook refuses it, show its message, fix the cause, and show the block again — never `--no-verify`.
- Push: `git push -u origin <branch>`.
- An open pull request already existed → the push updated it; report its URL and stop.
- Otherwise `gh pr create --title "..." --body "$(cat <<'EOF' ... EOF)"`.
- With no remote (`git remote` prints nothing), say so and stop — there's nothing to push to.
- Do not use `--no-verify` or bypass any configured PR checks.

### 6 — Output

Report the commit (if one was made) and the PR URL. Do not merge or request reviewers unless explicitly asked — the team's review on GitHub decides the merge. Then: "After it's merged: `git switch main && git pull`, and delete the branch (`git branch -d <branch>`)."

### PR description

```markdown
## Summary
1-3 bullet points on *why* this change exists and what it does, not a line-by-line diff recap.

## Changes
- Bulleted list of notable changes, grouped logically if the diff spans multiple concerns.

## Test plan
- [ ] Checklist of how this was/should be verified (tests run, manual QA steps, screenshots for UI).

## Breaking changes
Only include if applicable — what breaks and the migration path.

## Related issues
Link tickets/issues if referenced in commits or branch name (e.g. `Closes #123`).
```

Omit sections that don't apply. Rules:
- Title: a Conventional Commits line, like the commit messages — `<type>(<scope>): <imperative summary>`, under 70 characters (e.g. `feat(booking): show free slots for a day`, `docs: BRD v2`). A squash merge makes the title the commit on `main`, so it must pass the same check: run `uvx --from commitizen==4.20.0 cz check --message "<title>"` before showing it (exit 0 = fine). If it fails, fix the title.
- Body focuses on *why*, not a restatement of the diff.
- Do not fabricate a test plan — only list verification that was actually described or run in this conversation; otherwise leave the checklist unchecked with concrete steps the reviewer should take.
- Never commit files that look like secrets (`.env`, credentials, keys).
