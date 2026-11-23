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

1. Branch: `git switch -c docs/prd` (or the user's docs branch).
2. Write `PRD.md` with every template section, in order; stories as `### US-001 — <title>` with `(serves BR-…)` and their `AC-` list; requirements in the tables.
3. Flows as numbered steps or Mermaid.

## VALIDATE

Check the guide's rules and report each as BLOCKER / FIX NOW / BACKLOG — at least:
- every PRD section present (R8); IDs match the patterns and are unique (R1);
- every story/requirement has acceptance criteria (R2) and cites a BR (R6);
- every BR is served (R7); every NFR has a measurable target (R3).

Fix what you can; ask for the rest. Then `git add docs/requirements` — **only** that folder — and commit (`docs: PRD v<N>`). If the repo has a remote (`git remote` prints one), open a pull request (`gh pr create`, title `PRD`); with no remote (e.g. a repo that isn't on GitHub yet) stop at the commit and say so.

```
PRD — VALIDATE COMPLETE
───────────────────────
Stories / FR / NFR / AC:  <counts>
BR coverage:              <n>/<n> business rules served
Checks:                   <rule → PASS / FIXED / BACKLOG>
Pull request:             <url | none — no remote>
```

Next: the architect runs `/architect <app>` — it splits the product into epics. Then designs (optional `/design <app>`, or copy a Claude Design / Figma Make export into `docs/designs/<app>/`), then the tech lead's `/scaffold` (Day 0, once) and `/dev-tasks-planner` against that code.

## FOLLOW-UP — the open questions, one by one

When the user asks to go through the open questions ("ask me the open questions one by one"):

1. Ask **one** question at a time: the question, who owns it, and the likely options where you can. Wait for the answer before asking the next.
2. The user answers, says **skip** (it stays open), or names who will answer (update its owner).
3. After the last question, update `docs/requirements/PRD.md`: each answer goes into its section with its source ("<who answered>, <date>"), answered items leave Open Questions, and the metadata date changes (the version too, if the PRD was already merged). Never fill in what the user didn't say.
4. Run VALIDATE again, commit on the same branch (`docs: PRD — open questions answered`) and push, so the open pull request updates. If it was already merged, use a new branch and pull request.

```
PRD — OPEN QUESTIONS
────────────────────
Answered: <n>   Skipped: <n>   Still open: <n> (owners)
Pull request: <url, updated | new | none — no remote>
```
