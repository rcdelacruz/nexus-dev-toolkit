# /commit

**commit** — stage the relevant changes and create a well-formed, team-readable git commit.

## When to use

Invoke when the user asks to commit changes (`/commit`, "commit this", "create a commit"). Only commit when explicitly asked — never commit proactively as a side effect of other work.

## Steps

### 1 — Inspect changes

Run in parallel:
- `git status` — see all changed/untracked files (never `-uall`).
- `git diff` and `git diff --staged` — review both unstaged and already-staged changes.
- `git log --oneline -10` — match this repo's existing commit message style and conventions.

### 2 — Never on `main`

If the current branch is `main` (or `master`, or the repo's default branch), create a branch for this work first — `main` is protected and is only changed through pull requests:
- name it from the change: `<type>/<short-slug>` — e.g. `docs/brd-v2`, `feat/BOOK-004-free-slots`, `docs/CR-004-reminders`;
- if that name exists, add `-2`, `-3`…;
- `git switch -c <name>` (uncommitted changes come along), and tell the user the branch name.

### 3 — Stage deliberately

- Stage specific files by name (`git add <file> <file>`). Never use `git add -A` or `git add .` — it can sweep in unrelated work-in-progress or files that shouldn't be committed.
- If a change touches multiple unrelated concerns, prefer separate commits over one mixed commit — ask the user if it's unclear whether to split.
- Check staged content for anything that looks like a secret (`.env`, credentials, API keys, tokens) before committing. Warn the user and stop if found; never commit it silently.

### 4 — Write the commit message

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
- Always pass the message via a heredoc (`git commit -m "$(cat <<'EOF' ... EOF)"`) so multi-line formatting survives.
- Never use `--no-verify`, `--no-gpg-sign`, or `-c commit.gpgsign=false` unless the user explicitly asks. If a pre-commit hook fails, fix the underlying issue and create a new commit — don't bypass it.
- Never use `--amend` unless the user explicitly asks for it.

### 5 — Confirm

Run `git status` after committing to confirm it succeeded, and report the commit hash and subject line back to the user. Do not push unless separately asked.
