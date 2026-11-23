# /architect

**ARCHITECT** — write or update an app's architecture document and ADRs in `docs/arch-docs/<app>/`, following the team's architecture guide and covering every requirement. **This is where the product is split into epics** — one ADR file per epic, each citing the stories and requirements it delivers; designs, dev tasks (one CSV per epic) and change requests all follow those epics. For architects and solution designers. Runs EVALUATE → PLAN → stop for approval → APPLY → VALIDATE.

## Usage

`/architect <app>` — `<app>` is the folder for one application of the product (`careslot`, or `core` / `inventory` / `security` when a product has several). Reads the product's `docs/requirements/BRD.md` and `PRD.md`.

## Rules for the whole command

- Follow `docs/arch-docs/ARCHITECTURE-GUIDE.md`: its section names, ADR template, team patterns, rules and severities. If it doesn't exist, nexus's defaults apply (same 9-section template and rules); say so once.
- Every decision goes on a `- **Choice**: …` line (or a Choice column) inside the stack section. A dropped option is written as `- **Prior choice (superseded)**: …`, never as a Choice — nexus reads Choice lines as the project's stack.
- Every section cites the requirement IDs it covers. Never invent requirements; gaps are questions.
- **Epics:** each epic is one ADR file `ADR-<PROJECT>-E<NNN>-<Epic-Name>-v<N>.md` starting with an `Epic: E<NNN> — <name>` line and a `Covers:` line listing its user stories and functional requirements. Every user story and functional requirement belongs to exactly one epic (shared rules such as NFRs may be cited by several). Epic IDs are never renumbered.
- Write only under `docs/arch-docs/`. Never touch code, `docs/requirements/` or `docs/designs/`.
- **Never commit, push or open a pull request.** Write the files, check them, then stop: the user reviews the changes (`git diff`) and runs `/commit` (it makes a branch when they're on `main`) and then `/create-pr`.
- **Start from the team's latest docs.** First `git fetch -q origin` (skip it when `git remote` prints nothing). If `git rev-list --count HEAD..origin/main` is above 0, say how many commits behind they are and that they should pull `main` first (`git switch main && git pull`) — then wait for them.

## EVALUATE

1. Read the guide. Read `docs/requirements/` (BRD, PRD, any imported requirements) and list every requirement ID with its kind.
2. Run `ingest_architecture_doc` with `module=<app>`, `save_summary=false`: current sections found/missing, the stack and `stack_source`, ADR IDs, the current `epics`, skipped (misplaced) files.
3. If designs already exist in `docs/designs/<app>/` (with or without `design.json`), note their screens and the export's framework — the design must be buildable on the chosen stack (the stack decides; the export's framework doesn't).

```
ARCHITECT — EVALUATE
────────────────────
App:                <app>
Guide:              <project guide | nexus defaults>
Requirements:       <count by kind>
Current doc:        <file, sections missing>  |  none yet
Stack:              <from Choice lines> | "mentions only — no recorded decisions"
ADRs / epics:       <count> / <E001 name, E002 name …>
Uncovered IDs:      <requirement IDs no section or ADR covers>
Pattern conflicts:  <team patterns the current design breaks>
```

## PLAN

Show, then **stop**:

```
ARCHITECT — PLAN
────────────────
Write:        docs/arch-docs/<app>/ARCH-<PROJECT>-v<N>.md  (new | new version | edit)
Sections:     <each required section → what goes in it, with the IDs it covers>
Choices:      <each decision: area — choice — rationale (IDs) — ADR id>
Epics:        <E001 — name — Covers: US-…, FR-…>   (one ADR file per epic)
New ADRs:     <ADR-…-E001-NNN: decision> (in its epic's file, guide's template)
Coverage:     <every requirement ID → section or ADR; every story / FR → its epic>   — nothing left uncovered
Per client:   <web / mobile / API → stack>
Questions:    <anything only the user can decide>
```

> Plan ready. Reply **go** to write these files, or give feedback.

Do not write anything before the user approves.

## APPLY

1. Stay on the current branch — don't create one (`/commit` does, when the user commits).
2. Write the document with exactly the guide's section names; diagrams in Mermaid.
3. Write one ADR file per epic: the `Epic:` and `Covers:` lines first, then the guide's template, one `## ADR-…-E<NNN>-NNN` heading per decision; cite each ADR on its Choice line. An epic with no decision of its own still gets its file (Covers line, and a short note on which ADRs it follows).
4. On a substantial revision, write a new version file and keep the old one until the change request is closed.

## VALIDATE

1. Run `ingest_architecture_doc` again (`module=<app>`, `save_summary=false`): `required_sections_missing` must be empty, `stack_source` must be `choices`, and `epics` lists every epic.
2. Check every guide rule and report BLOCKER / FIX NOW / BACKLOG — at least: every functional requirement covered (list any ID not cited), every required section present, decisions on Choice lines, an ADR per major decision, pattern breaks justified by an ADR, each client's stack stated and consistent with the design, every NFR ID in NFR Fulfillment, every user story and functional requirement in exactly one epic (A9).
3. Fix every BLOCKER and FIX NOW, then:
   - Stop — don't commit. Suggested commit message: `docs(<app>): architecture …`.
   - For the pull request (`/create-pr`): title `Architecture: <app>`, listing the Choices, the epics and new ADRs.

```
ARCHITECT — VALIDATE COMPLETE
─────────────────────────────
Sections:      <9/9 or the guide's count>
Stack:         <Choice lines>
Coverage:      <n/n requirement IDs>
Epics:         <E001 … E0nn, each with its story count>
ADRs:          <new / total>
Checks:        <rule → PASS / FIXED / BACKLOG>
Next:           review the changes (`git diff`), then `/commit` and `/create-pr`
```

Next: designs — `/design <app> --system <design system>`, or a Claude Design / Figma Make export copied into `docs/designs/<app>/` (no command needed). Then the tech lead runs `/scaffold` (Day 0, once) and `/dev-tasks-planner <app>` against that code — one task CSV per epic.
