# /commit

**commit** — stage the relevant changes and create a well-formed, team-readable git commit.

## When to use

Invoke when the user asks to commit changes (`/commit`, "commit this", "create a commit"). Only commit when explicitly asked — never commit proactively as a side effect of other work.

**A person reviews before anything goes into git.** Typing `/commit` asks you to prepare a commit, not to make it: you show exactly what you'll commit and wait for their yes (step 3). Nothing that changes git — a branch, `git add`, `git commit` — runs before that yes.

## Steps

### 1 — Inspect changes

Run in parallel:
- `git status` — see all changed/untracked files (never `-uall`).
- `git diff` and `git diff --staged` — review both unstaged and already-staged changes.
- `git log --oneline -10` — match this repo's existing commit message style and conventions.

### 2 — Draft (change nothing yet)

Work out, without running any command that changes git:

- **The branch.** If the current branch is `main` (or `master`, or the repo's default branch), the work needs a new branch — `main` is protected and is only changed through pull requests. Name it from the change: `<type>/<short-slug>` — e.g. `docs/brd-v2`, `feat/BOOK-004-free-slots`, `docs/CR-004-reminders`; if that name exists, add `-2`, `-3`…. Otherwise stay on the current branch.
- **The files.** Pick the files that belong to this change, by name. If the changes touch several unrelated concerns, plan separate commits and say so.
- **Secrets.** If any of those files looks like a secret (`.env`, credentials, API keys, tokens), leave it out and warn the user.
- **The message**, written as in "Commit message format" below.

### 3 — Show it and wait for a yes

Show the user, and stop:

```
READY TO COMMIT — nothing is committed yet
Branch:   docs/brd-v1 (new, from main)        ← or: feat/BOOK-004 (current)
Files:    docs/requirements/brd.md            (modified)
          docs/requirements/brd-open-questions.md (new)
Left out: notes.txt (unrelated)               ← only when something is left out
Message:  docs: add BRD v1

Look at the changes with `git diff` (and open any new file). Commit these? Reply yes, or tell me what to change.
```

- Commit only after an explicit yes to this list and this message. A question, an edit request or "wait" is not a yes: answer, revise, and show the block again.
- If the files change after the yes (the user edits something, you fix something), show the block again and wait again.

### 4 — Branch, stage and commit (after the yes)

- New branch: `git switch -c <name>` (uncommitted changes come along); tell the user its name.
- Stage the agreed files by name (`git add <file> <file>`). Never use `git add -A` or `git add .` — it can sweep in unrelated work-in-progress or files that shouldn't be committed.
- Commit with the agreed message, through a heredoc (`git commit -m "$(cat <<'EOF' ... EOF)"`) so multi-line formatting survives.
- If the commit check (commitizen) or another hook refuses the commit, show its message, fix the cause, and show the block again — never bypass it.

### 5 — Confirm

Run `git status` after committing to confirm it succeeded, and report the commit hash and subject line back to the user. Don't push — that's `/create-pr`, which also waits for the user's yes.

### Commit message format

Format (Conventional Commits, since this is a team repo — consistent history matters for changelogs and skimming `git log`):

```
<type>(<scope>): <short imperative summary, under 72 chars>

<optional body — the *why*, not a line-by-line diff recap, wrap at ~72 chars>

<optional footer — Closes #123, BREAKING CHANGE: ..., etc.>
```

Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`. Pick the one that matches the actual change; don't default to `chore`/`fix` if another fits better.

Rules:
- Subject line: imperative mood ("add", "fix", "remove" — not "added"/"fixes").
- Body explains *why*, only when the *why* isn't obvious from the diff or subject alone — skip it for small, self-explanatory changes.
- Never fabricate a footer reference (`Closes #123`) unless an issue number was actually given or is evident from the branch name/conversation.
- Never use `--no-verify`, `--no-gpg-sign`, or `-c commit.gpgsign=false` unless the user explicitly asks. If a pre-commit hook fails, fix the underlying issue and create a new commit — don't bypass it.
- Never use `--amend` unless the user explicitly asks for it.
