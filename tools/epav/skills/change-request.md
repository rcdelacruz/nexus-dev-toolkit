# /change-request

**CHANGE REQUEST** — apply a client change to the requirements, architecture and designs first, record exactly which IDs changed, and hand developers the precise list of dev tasks to re-plan. For whoever owns the change (product, architect or designer). Runs EVALUATE → PLAN → stop for approval → APPLY → VALIDATE.

## Usage

`/change-request <CR-id> "<one-line title>"` — e.g. `/change-request CR-004 "Sessions expire after 10 minutes; add sign-out"`.

## Rules for the whole command

- Change requests flow upstream → downstream: requirements, then architecture, then designs, then dev tasks. This command edits only `docs/requirements/`, `docs/arch-docs/`, `docs/designs/` and `docs/change-requests/` — never code, never task files (that's `/dev-tasks-planner`'s job, using this command's record).
- A changed requirement keeps its ID. New requirements get new IDs. Removed ones are deleted from the docs, not renumbered.
- Follow each folder's guide (requirements / architecture / design) for whatever you edit.
- **Never commit, push or open a pull request.** Write the files, check them, then stop: the user reviews the changes (`git diff`) and runs `/commit` (it makes a branch when they're on `main`) and then `/create-pr`.
- **Start from the team's latest docs.** First `git fetch -q origin` (skip it when `git remote` prints nothing). If `git rev-list --count HEAD..origin/main` is above 0, say how many commits behind they are and that they should pull `main` first (`git switch main && git pull`) — then wait for them.

## EVALUATE

1. Read the request. Find every requirement it touches (by ID) in `docs/requirements/`, every architecture section/ADR citing those IDs, and every design screen whose `trace_ids` include them (`docs/designs/*/design.json`, or the frames that cite them when designs were copied in without `/design`). Note the epic each touched story belongs to (`ingest_architecture_doc` → `epics`) — a new story needs an epic.
2. Check the branch: `git status` — start from a clean `docs/` (commit or stash unrelated edits first).

```
CHANGE REQUEST — EVALUATE
─────────────────────────
CR:            <CR-id> — <title>
Requirements:  <IDs to change / add / remove>
Architecture:  <sections / ADRs that cite them>
Designs:       <screens (DES-ids) that cover them>
```

## PLAN

Show, then **stop**:

```
CHANGE REQUEST — PLAN
─────────────────────
Requirements:  <ID: old → new wording>; <new IDs>; <removed IDs>
Architecture:  <section/ADR edits; new ADR if a decision changes>
Designs:       <screens the designer must update (re-export or /design after)>
Record:        docs/change-requests/<CR-id>.json
```

> Plan ready. Reply **go** to edit the docs, or give feedback.

## APPLY

1. Stay on the current branch — don't create one (`/commit` does, when the user commits).
2. Edit the requirement files, then the architecture doc/ADRs (new version file for substantial changes). For design changes, list them for the designer — they update the screens (in Claude Design / Figma Make, or with `/design`) and commit the new files.
3. Run `record_change_request` with `cr_id`, `title`, `reason`, `base` = `main` (it reads your uncommitted edits too), **write=false**: it reads the git diff of `docs/` and returns the changed / added / removed IDs and the dev-task rows that trace to them. Show it.
4. If it matches the plan, run it again with **write=true** to write `docs/change-requests/<CR-id>.json`.

## VALIDATE

1. The record's IDs match the plan — nothing missing, nothing extra. `no_changes` means the edits didn't touch any ID: stop and check.
2. The edited docs still pass their guides (`ingest_architecture_doc` for architecture; requirement IDs unique; designs re-checked when re-imported).
3. Stop — don't commit. Suggested commit message: `docs: <CR-id> <title>`; for the pull request (`/create-pr`), the record and the affected task list.

```
CHANGE REQUEST — VALIDATE COMPLETE
──────────────────────────────────
Changed:   <IDs>    Added: <IDs>    Removed: <IDs>
Affected dev tasks: <file — task ids>   (only these get re-planned)
Next:      review the changes (`git diff`), then `/commit` and `/create-pr`
```

**A later part of the same change request** — typically the designer's screens, in their own branch after the requirements were merged: the designer runs `/change-request <CR-id>` again. `record_change_request` sees the record exists and adds the new IDs to it as an `updates` entry (`new_ids`, `newly_affected_tasks`) instead of writing a second record. Show what this part adds; `no_new_changes` means the record already holds every ID changed since `main`.

Next, for the tech lead, once the change request's pull request is merged and they've pulled `main`: `/dev-tasks-planner cr <CR-id>` re-plans only the affected rows; developers then build them with `/evaluate`, `/plan`, `/apply`, `/validate`. (The Day 0 scaffold isn't re-run for a change request.)
