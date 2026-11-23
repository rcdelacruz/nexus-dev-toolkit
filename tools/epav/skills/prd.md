# /prd

**PRD** — write or update the product's Product Requirements Document (`docs/requirements/PRD.md`) from the BRD: personas, user stories with acceptance criteria, functional and non-functional requirements, flows and release scope — every story and requirement tracing to a business rule. One PRD for the whole product; `/architect` later groups its stories into epics. For product owners and business analysts. Runs EVALUATE → INTERVIEW → PLAN → stop for approval → APPLY → VALIDATE.

## Usage

`/prd [sources | "notes"]` — needs `docs/requirements/BRD.md` (write it first with `/brd`). Sources add product detail: interviews, a product-requirements file, workshop notes.

## Rules for the whole command

- Start from `docs/requirements/templates/PRD-TEMPLATE.md` (nexus's own if the project has none) and follow `docs/requirements/REQUIREMENTS-GUIDE.md` — PRD sections, ID patterns (US-, FR-<AREA>-, NFR-, AC-), rules.
- **Every user story and functional requirement cites the BR- rule it serves**; every BR is served by at least one story or requirement. A BR nothing serves is either out of scope (say so) or a gap (ask).
- Acceptance criteria are testable (`AC-012 A booked slot disappears from the calendar for other patients within 5 s`). Non-functional requirements carry a number.
- **Never invent** behaviour, numbers or personas the sources don't support — ask, or record an Open Question.
- Existing IDs are never renumbered; a changed requirement keeps its ID.
- Group functional requirements by **area** (`FR-<AREA>-`), not by module or epic — epics are the architect's call.
- Write only `docs/requirements/PRD.md`. Never touch code or other docs folders.
- **Never commit, push or open a pull request.** Write the files, check them, then stop: the user reviews the changes (`git diff`) and runs `/commit` (it makes a branch when they're on `main`) and then `/create-pr`.
- **Start from the team's latest docs.** First `git fetch -q origin` (skip it when `git remote` prints nothing). If `git rev-list --count HEAD..origin/main` is above 0, say how many commits behind they are and that they should pull `main` first (`git switch main && git pull`) — then wait for them.

## EVALUATE

1. Read the guide, the template, the BRD (business rules, goals, scope) and any existing PRD.
2. List the BR IDs and which are already served; list existing US/FR/NFR/AC IDs and the highest number of each.

```
PRD — EVALUATE
──────────────
Product:       <name>
BRD:           <version> — BR-001 … BR-0nn
Existing PRD:  <version, counts by kind> | none
Unserved BRs:  <BR ids no story/requirement covers yet>
Gaps:          <personas, flows, NFR numbers, acceptance criteria missing>
```

## INTERVIEW

One round of short, numbered questions for the gaps (personas and their devices, edge cases, numbers for NFRs, what's out of this release). Wait for answers; unanswered items become Open Questions.

## PLAN

Show, then **stop**:

```
PRD — PLAN
──────────
Write:        docs/requirements/PRD.md  (new | v<N+1>)
Personas:     <name — role — device>
Stories:      <US-id — title — serves BR-…>  with AC-ids
Functional:   <FR-<AREA>-id — requirement — serves BR-… — stories>
Non-func:     <NFR-id — measurable target — serves BR-…>
Coverage:     <every BR → stories/requirements>   — none left unserved
Release:      in: <ids>   out: <…>
Questions:    <open items>
```

> Plan ready. Reply **go** to write the PRD, or correct anything above.

## APPLY

1. Stay on the current branch — don't create one (`/commit` does, when the user commits).
2. Write `PRD.md` with every template section, in order; stories as `### US-001 — <title>` with `(serves BR-…)` and their `AC-` list; requirements in the tables.
3. Flows as numbered steps or Mermaid.

## VALIDATE

Check the guide's rules and report each as BLOCKER / FIX NOW / BACKLOG — at least:
- every PRD section present (R8); IDs match the patterns and are unique (R1);
- every story/requirement has acceptance criteria (R2) and cites a BR (R6);
- every BR is served (R7); every NFR has a measurable target (R3).

Fix what you can; ask for the rest. Then stop — don't commit. Suggested commit message: `docs: PRD v<N>` (pull request title `PRD`).

```
PRD — VALIDATE COMPLETE
───────────────────────
Stories / FR / NFR / AC:  <counts>
BR coverage:              <n>/<n> business rules served
Checks:                   <rule → PASS / FIXED / BACKLOG>
Next:           review the changes (`git diff`), then `/commit` and `/create-pr`
```

Next: the architect runs `/architect <app>` — it splits the product into epics. Then designs (optional `/design <app>`, or copy a Claude Design / Figma Make export into `docs/designs/<app>/`), then the tech lead's `/scaffold` (Day 0, once) and `/dev-tasks-planner` against that code.

## FOLLOW-UP — the open questions, one by one

When the user asks to go through the open questions ("ask me the open questions one by one"):

1. Ask **one** question at a time: the question, who owns it, and the likely options where you can. Wait for the answer before asking the next.
2. The user answers, says **skip** (it stays open), or names who will answer (update its owner).
3. After the last question, update `docs/requirements/PRD.md`: each answer goes into its section with its source ("<who answered>, <date>"), answered items leave Open Questions, and the metadata date changes (the version too, if the PRD was already merged). Never fill in what the user didn't say.
4. Run VALIDATE again and stop — don't commit. Suggested commit message: `docs: PRD — open questions answered`. The user runs `/commit`, then `/create-pr` (it updates the pull request if one is already open).

```
PRD — OPEN QUESTIONS
────────────────────
Answered: <n>   Skipped: <n>   Still open: <n> (owners)
Next: review the changes (`git diff`), then `/commit` and `/create-pr`
```
