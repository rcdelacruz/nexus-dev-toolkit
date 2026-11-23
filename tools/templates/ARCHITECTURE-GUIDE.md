# Architecture Guide

This guide is how this team writes architecture documents. `/architect` follows it when it
writes or updates `docs/arch-docs/<app>/ARCH-*.md` and the epic ADR files, and its VALIDATE step checks the
result against the rules below. nexus tools read architecture docs the same way.

**Edit this file to match your team.** Change section names, add your own patterns, raise or lower
a rule's severity. Only the block at the bottom is read by nexus; the rest is for people.

## Where files go

- One folder per application of the product: `docs/arch-docs/<app>/` (one app → one folder, e.g.
  `careslot`; several → `core`, `inventory`, `security` …).
- Architecture document: `ARCH-<PROJECT>-v<N>.md` (one per app; bump the version on substantial
  changes and keep the old file until the change request is closed).
- **Epics are decided here.** One file per epic: `ADR-<PROJECT>-E<NNN>-<Epic-Name>-v<N>.md`, starting
  with `Epic: E<NNN> — <name>` and `Covers: US-…, FR-…` (the stories and functional requirements it
  delivers), then one `## ADR-…-E<NNN>-NNN` heading per decision. Every story and functional
  requirement belongs to exactly one epic. Designs and dev tasks follow the epics (one task CSV per epic).
- A shared platform document (`ARCH-<PROJECT>-PLATFORM-v<N>.md`) holds choices every app
  inherits; app docs cite it instead of re-arguing.
- Requirements (BRD, PRD, epic briefs) do **not** go here — they live in `docs/requirements/`, one
  set for the whole product.

## Sections of an architecture document

1. Document Metadata — version, date, status, owners, source documents (BRD/PRD versions)
2. System Overview — context, clients, a Mermaid diagram
3. Component Breakdown — each component, its responsibility, what it talks to
4. Technology Choices — one `### <area>` per decision, each with:
   - `- **Choice**: <technology and version>` — the only lines nexus reads as "the stack"
   - `- **Rationale**: …` citing requirement IDs (e.g. NFR-009)
   - `- **ADR**: <ADR id>` when the decision has one
   A dropped option is written as `- **Prior choice (superseded)**: …`, never as a Choice.
   Decision tables work too, as long as they have a `Choice` column.
5. Data Model
6. Integration and API Design
7. Deployment Topology
8. NFR Fulfillment — one line per NFR ID: how it's met, or why not yet
9. Open Questions and Deferred Decisions

## Epic file template

```
Epic: E001 — <name>
Covers: US-001, US-002, FR-BOOK-001 …

## ADR-<PROJECT>-E001-001: <decision in one sentence>
### Status        Proposed | Accepted | Superseded by ADR-…
### Type          Decision | Prescribed (dictated by the client/platform)
### Context
### Options Considered
### Decision
### Rationale
### Consequences
### Affected Epics
### Architecture Document Reference
```

## Team patterns

Write your team's defaults here. A design that breaks one needs an ADR saying why. Examples:

- Authorization is enforced server-side (guards/policies), never only by hiding UI.
- Modular monolith first; split a service out only with an ADR.
- Secrets come from the deployment environment, never from the repository.

## Rules nexus checks

```nexus-guide
{
  "kind": "architecture",
  "format_version": 1,
  "required_sections": [
    "Document Metadata", "System Overview", "Component Breakdown", "Technology Choices",
    "Data Model", "Integration and API Design", "Deployment Topology", "NFR Fulfillment",
    "Open Questions and Deferred Decisions"
  ],
  "stack_section": "Technology Choices",
  "id_patterns": {},
  "rules": [
    {"id": "A1", "severity": "BLOCKER", "text": "Every functional requirement (FR-, US-) of the product that this app delivers is covered by a section or an ADR."},
    {"id": "A2", "severity": "BLOCKER", "text": "Every required section is present."},
    {"id": "A3", "severity": "BLOCKER", "text": "Technology Choices states each decision on a **Choice** line or in a Choice column; dropped options are marked superseded."},
    {"id": "A4", "severity": "FIX NOW", "text": "Every major decision has an ADR, and the Choice line cites it."},
    {"id": "A5", "severity": "FIX NOW", "text": "A design that breaks a team pattern has an ADR explaining why."},
    {"id": "A6", "severity": "FIX NOW", "text": "Each client (web, mobile, API) states its own stack, and it matches what the design export targets."},
    {"id": "A7", "severity": "FIX NOW", "text": "Every NFR ID has a line in NFR Fulfillment."},
    {"id": "A8", "severity": "BACKLOG", "text": "Diagrams are written in Mermaid, not images."},
    {"id": "A9", "severity": "FIX NOW", "text": "The product is split into epics — one ADR file per epic with Epic: and Covers: lines — and every user story and functional requirement belongs to exactly one epic."}
  ]
}
```
