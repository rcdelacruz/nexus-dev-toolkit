# /requirements

**REQUIREMENTS** — import or write the product's requirements, with stable IDs, into `docs/requirements/` (use `/brd` and `/prd` to write new ones from scratch). For product owners and business analysts. Runs EVALUATE → PLAN → stop for approval → APPLY → VALIDATE.

## Usage

`/requirements [source]` — source can be a .md/.docx/.pdf file, a pasted brief, or files already in the repo (e.g. an epic BRD sitting under `docs/arch-docs/`).

## Rules for the whole command

- Follow `docs/requirements/REQUIREMENTS-GUIDE.md` — its ID patterns, its rules and their severities. If the file doesn't exist, nexus's defaults apply (same rules); say so once.
- Use the project's **existing** ID scheme. Never renumber an existing requirement: a changed requirement keeps its ID (that's what `/change-request` records).
- Never invent requirements, numbers or acceptance criteria. Anything missing from the source is a question for the user, listed in the plan.
- Write only under `docs/requirements/`. Never touch code, `docs/arch-docs/` or `docs/designs/`.
- **Never commit, push or open a pull request.** Write the files, check them, then stop: the user reviews the changes (`git diff`) and runs `/commit` (it makes a branch when they're on `main`) and then `/create-pr`.
- **Start from the team's latest docs.** First `git fetch -q origin` (skip it when `git remote` prints nothing). If `git rev-list --count HEAD..origin/main` is above 0, say how many commits behind they are and that they should pull `main` first (`git switch main && git pull`) — then wait for them.

## EVALUATE

1. Read the guide (or note the defaults). Read the source and everything already in `docs/requirements/`.
2. List the IDs already in use (`US-`, `FR-<AREA>-`, `NFR-`, `AC-`, epics — whatever the guide's patterns say) and the highest number of each kind.
3. Look for requirements files in the wrong place: `docs/arch-docs/**` files named like BRD/PRD/epic briefs (`ingest_architecture_doc` reports them under `files_skipped`).

```
REQUIREMENTS — EVALUATE
───────────────────────
Product:           <name>
Source:            <files / brief>
Existing IDs:      <counts per kind, highest number>
New in source:     <count, by kind>
Misplaced files:   <BRD/PRD files under docs/arch-docs/, or none>
Gaps:              <requirements without acceptance criteria, NFRs without a number, ambiguities>
```

## PLAN

Show, then **stop**:

```
REQUIREMENTS — PLAN
───────────────────
Write:     docs/requirements/<file>.md   (new | updated)
IDs:       <new IDs to assign, one line each: ID — statement>
Kept:      <existing IDs unchanged>
Move:      <misplaced file → docs/requirements/ (git mv), or none>
Questions: <every gap the user must answer before APPLY>
```

> Plan ready. Reply **go** to write these files, or answer the questions first.

Do not write anything before the user approves.

## APPLY

1. Stay on the current branch — don't create one (`/commit` does, when the user commits).
2. Write the Markdown files. One requirement per line or table row: `ID — statement`, then its acceptance criteria (`AC-…` or a bullet list). Keep original `.docx`/`.pdf` next to the Markdown copy.
3. `git mv` misplaced requirement files out of `docs/arch-docs/`.

## VALIDATE

Check every rule in the guide; report each as BLOCKER / FIX NOW / BACKLOG:

- Every requirement has an ID matching the patterns, and no ID is used twice.
- Every functional requirement / user story has acceptance criteria.
- Non-functional requirements state a measurable target.
- Nothing under `docs/arch-docs/` is a requirements document any more.

Fix every BLOCKER and FIX NOW (asking the user where only they can answer), then:

1. Stop — don't commit. Suggested commit message: `docs: requirements …` (pull request title `Requirements`).
2. For the pull request (`/create-pr`): list the new IDs in it; the repo's CODEOWNERS decides who approves.

```
REQUIREMENTS — VALIDATE COMPLETE
────────────────────────────────
IDs written:   <count, by kind>
Checks:        <rule → PASS / FIXED / BACKLOG>
Next:           review the changes (`git diff`), then `/commit` and `/create-pr`
```

Next step for the architect: `/architect <app>` — it splits the product into epics.
