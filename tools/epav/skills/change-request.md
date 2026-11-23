# /change-request

**CHANGE REQUEST** — apply a client change to the requirements, architecture and designs first, record exactly which IDs changed, and hand developers the precise list of dev tasks to re-plan. For whoever owns the change (product, architect or designer). Runs EVALUATE → PLAN → stop for approval → APPLY → VALIDATE.

## Usage

`/change-request <CR-id> "<one-line title>"` — e.g. `/change-request CR-004 "Sessions expire after 10 minutes; add sign-out"`.

## Rules for the whole command

- Change requests flow upstream → downstream: requirements, then architecture, then designs, then dev tasks. This command edits only `docs/requirements/`, `docs/arch-docs/`, `docs/designs/` and `docs/change-requests/` — never code, never task files (that's `/dev-tasks-planner`'s job, using this command's record).
- A changed requirement keeps its ID. New requirements get new IDs. Removed ones are deleted from the docs, not renumbered.
- Follow each folder's guide (requirements / architecture / design) for whatever you edit.

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

1. Branch: `git switch -c cr/<CR-id>`.
2. Edit the requirement files, then the architecture doc/ADRs (new version file for substantial changes). For design changes, list them for the designer — they update the screens (in Claude Design / Figma Make, or with `/design`) and commit the new files.
3. Run `record_change_request` with `cr_id`, `title`, `reason`, `base` = the branch point (e.g. `main`), **write=false**: it reads the git diff of `docs/` and returns the changed / added / removed IDs and the dev-task rows that trace to them. Show it.
4. If it matches the plan, run it again with **write=true** to write `docs/change-requests/<CR-id>.json`.

## VALIDATE

1. The record's IDs match the plan — nothing missing, nothing extra. `no_changes` means the edits didn't touch any ID: stop and check.
2. The edited docs still pass their guides (`ingest_architecture_doc` for architecture; requirement IDs unique; designs re-checked when re-imported).
3. `git add docs/` — **only** docs/. `git commit -m "docs: <CR-id> <title>"`. If the repo has a remote, `gh pr create` titled `<CR-id>: <title>` with the record and the affected task list; with no remote (e.g. a repo that isn't on GitHub yet) stop at the commit and say so.

```
CHANGE REQUEST — VALIDATE COMPLETE
──────────────────────────────────
Changed:   <IDs>    Added: <IDs>    Removed: <IDs>
Affected dev tasks: <file — task ids>   (only these get re-planned)
Pull request: <url>
```

Next, for the tech lead: `/dev-tasks-planner cr <CR-id>` re-plans only the affected rows; developers then build them with `/evaluate`, `/plan`, `/apply`, `/validate`. (The Day 0 scaffold isn't re-run for a change request.)
