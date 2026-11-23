# /brd

**BRD** — write or update the product's Business Requirements Document (`docs/requirements/BRD.md`): the problem, business goals, stakeholders, scope, business rules (BR-001…) and success metrics. One BRD for the whole product — the epics (modules) come later, from `/architect`. For product owners and business analysts. Runs EVALUATE → INTERVIEW → PLAN → stop for approval → APPLY → VALIDATE.

## Usage

`/brd [sources | "problem description"]`

- **sources** — files with the product's requirements and problems: meeting notes, client emails, an older BRD, a brief, a product-requirements `.md`/`.txt`/`.pdf` (a Google Doc: export it or paste its text);
- **a problem description** — a sentence or a paragraph, quoted: `/brd "Clinics lose 18% of slots to no-shows and booking is phone-only"`;
- **nothing** — the interview does the work.

## Rules for the whole command

- Start from `docs/requirements/templates/BRD-TEMPLATE.md` (nexus's own template if the project has none) and follow `docs/requirements/REQUIREMENTS-GUIDE.md` — its BRD sections, ID patterns and rules.
- **Never invent business facts** — no made-up numbers, deadlines, stakeholders or rules. Anything the sources don't say becomes an interview question or an Open Question in the document.
- Business rules are testable statements ("A patient can hold at most 2 future appointments"), not features. Each gets a `BR-` ID; existing IDs are never renumbered — a changed rule keeps its ID.
- Don't split the product into modules or epics — that's the architect's call (`/architect`).
- Write only `docs/requirements/BRD.md` (and the templates folder if it's missing). Never touch code or other docs folders.
- **Never commit, push or open a pull request.** Write the files, check them, then stop: the user reviews the changes (`git diff`) and runs `/commit` (it makes a branch when they're on `main`) and then `/create-pr`.
- **Start from the team's latest docs.** First `git fetch -q origin` (skip it when `git remote` prints nothing). If `git rev-list --count HEAD..origin/main` is above 0, say how many commits behind they are and that they should pull `main` first (`git switch main && git pull`) — then wait for them.

## EVALUATE

1. Read the guide and the template. Read every source given (or the description) and any existing `docs/requirements/BRD.md`.
2. Map what the sources already answer onto the BRD sections; list what's missing or vague.

```
BRD — EVALUATE
──────────────
Product:       <name>
Sources:       <files / description / none>
Existing BRD:  <version, BR count> | none
Answered:      <sections the sources cover>
Gaps:          <sections with nothing or only vague text>
```

## INTERVIEW

Ask **one round** of short, numbered questions — only for the gaps, grouped by section, at most ~10. Offer the likely options where you can ("Which matters more: fewer no-shows or shorter phone queues?"). Wait for the answers. Whatever stays unanswered goes into **Open Questions** with an owner — never filled in by guessing.

## PLAN

Show, then **stop**:

```
BRD — PLAN
──────────
Write:          docs/requirements/BRD.md  (new | v<N+1>)
Goals:          <goal → success metric (baseline → target)>
Business rules: <BR-id — rule — source>        (new, changed, unchanged)
Scope:          in: <…>   out: <…>
Open questions: <what's still unknown, owner>
```

> Plan ready. Reply **go** to write the BRD, or correct anything above.

## APPLY

1. Stay on the current branch — don't create one (`/commit` does, when the user commits).
2. Write `BRD.md` with every template section, in order. Fill the metadata table (version, date, owner, status, sources).
3. Business rules go in the Business Rules table with their source; success metrics name the BR they serve.

## VALIDATE

Check the guide's rules and report each as BLOCKER / FIX NOW / BACKLOG — at least:
- every BRD section from the guide is present (R8);
- every BR ID matches the pattern and is used once (R1);
- every business goal has a success metric with a baseline and a target (R7);
- nothing stated as fact lacks a source; unknowns are in Open Questions.

Fix what you can; ask for the rest. Then stop — don't commit. Suggested commit message: `docs: BRD v<N>` (pull request title `BRD`).

```
BRD — VALIDATE COMPLETE
───────────────────────
Business rules: <count> (BR-001 … BR-0nn)
Goals/metrics:  <n>/<n>
Open questions: <n>
Checks:         <rule → PASS / FIXED / BACKLOG>
Next:           review the changes (`git diff`), then `/commit` and `/create-pr`
```

Next: `/prd` turns these business rules into user stories and requirements.

## FOLLOW-UP — the open questions, one by one

When the user asks to go through the open questions ("ask me the open questions one by one"):

1. Ask **one** question at a time: the question, who owns it, and the likely options where you can. Wait for the answer before asking the next.
2. The user answers, says **skip** (it stays open), or names who will answer (update its owner).
3. After the last question, update `docs/requirements/BRD.md`: each answer goes into its section with its source ("<who answered>, <date>"), answered items leave Open Questions, and the metadata date changes (the version too, if the BRD was already merged). Never fill in what the user didn't say.
4. Run VALIDATE again and stop — don't commit. Suggested commit message: `docs: BRD — open questions answered`. The user runs `/commit`, then `/create-pr` (it updates the pull request if one is already open).

```
BRD — OPEN QUESTIONS
────────────────────
Answered: <n>   Skipped: <n>   Still open: <n> (owners)
Next: review the changes (`git diff`), then `/commit` and `/create-pr`
```
