# Requirements Guide

This guide is how this team writes and numbers requirements. `/requirements` follows it when it
imports or writes `docs/requirements/`, and every other nexus step uses the same IDs to
trace requirements → architecture → designs → dev tasks → change requests.

**Edit this file to match your team.** Only the block at the bottom is read by nexus.

## Where files go

- One set for the whole product, in `docs/requirements/`: `BRD.md` (business), `PRD.md` (product),
  plus any imported briefs and client notes.
- Write the BRD with `/brd` (from a problem description, files with the product's requirements, or an
  interview) and the PRD with `/prd`; both start from the templates in `docs/requirements/templates/`.
  `/requirements` imports documents you already have.
- Don't split requirements into modules here. The architect splits the product into **epics**
  (`/architect`), and designs and dev tasks follow those epics.
- Keep the original files (`.docx`, `.pdf`) next to a Markdown copy; nexus reads the Markdown.
- Never put requirements in `docs/arch-docs/`.

## IDs

Every requirement gets a stable ID that never changes meaning; a changed requirement keeps its ID
and the change request records what changed. Defaults (change them in the block below):

| What | Pattern | Example |
|---|---|---|
| Business rule (BRD) | `BR-` + number | BR-003 |
| User story | `US-` + number | US-014 |
| Functional requirement | `FR-<AREA>-` + number | FR-AUTH-003 |
| Non-functional requirement | `NFR-` (+ area) + number | NFR-009, NFR-SEC-004 |
| Acceptance criterion | `AC-` + number | AC-184 |
| Epic (decided by the architect) | `E` + 3 digits | E001 |

## Traceability

Every user story and functional requirement in the PRD cites the business rule it serves
(`serves BR-003`). Architecture sections, design screens and dev tasks then cite the PRD IDs, so a
change to one business rule can be followed all the way to the code.

## What every requirement needs

- An ID, a one-line statement, and acceptance criteria someone can test.
- For anything with a screen: which user does it, on which device size.
- For non-functional requirements: a number (≤ 5 s, 15 minutes, 99.5 %), not "fast".

## Rules nexus checks

```nexus-guide
{
  "kind": "requirements",
  "format_version": 1,
  "required_sections": [],
  "documents": {
    "BRD": ["Purpose", "Problem", "Business Goals", "Stakeholders", "Scope", "Business Rules",
            "Success Metrics", "Assumptions", "Constraints", "Open Questions"],
    "PRD": ["Overview", "Personas", "User Stories", "Functional Requirements",
            "Non-Functional Requirements", "Flows", "Release Scope", "Dependencies", "Open Questions"]
  },
  "id_patterns": {},
  "rules": [
    {"id": "R1", "severity": "BLOCKER", "text": "Every requirement has an ID matching the patterns above, used once."},
    {"id": "R2", "severity": "BLOCKER", "text": "Every functional requirement or user story has acceptance criteria."},
    {"id": "R3", "severity": "FIX NOW", "text": "Non-functional requirements state a measurable target."},
    {"id": "R4", "severity": "FIX NOW", "text": "Requirements files live in docs/requirements/, not in docs/arch-docs/."},
    {"id": "R5", "severity": "BACKLOG", "text": "Original .docx/.pdf files have a Markdown copy next to them."},
    {"id": "R6", "severity": "FIX NOW", "text": "Every user story and functional requirement in the PRD cites the business rule (BR-) it serves."},
    {"id": "R7", "severity": "FIX NOW", "text": "Every business rule is served by at least one user story or functional requirement, and every business goal has a success metric."},
    {"id": "R8", "severity": "BLOCKER", "text": "The BRD and PRD contain every section listed for them above."}
  ]
}
```
