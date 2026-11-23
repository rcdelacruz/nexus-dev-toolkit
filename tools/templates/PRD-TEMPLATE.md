# PRD — <Product>

<!-- Product Requirements Document. Written with /prd from the BRD; edit freely. The headings below
     are the ones the requirements guide checks. Every user story and functional requirement cites
     the BR- rule it serves. IDs are never renumbered; a changed requirement keeps its ID. -->

| Field | Value |
|---|---|
| Version | 1.0 |
| Date | YYYY-MM-DD |
| Owner | <product owner> |
| BRD | <link to BRD.md and its version> |
| Status | Draft · In review · Approved |

## 1. Overview

<What we're building in this release, in three sentences, and which business goals it serves.>

## 2. Personas

| Persona | Who | Goal | Device |
|---|---|---|---|
| <name> | <role> | <what they want done> | <desktop / mobile> |

## 3. User Stories

### US-001 — <short title>
As a <persona>, I want <capability>, so that <outcome>. *(serves BR-001)*

Acceptance criteria:
- AC-001 <testable condition>
- AC-002 <testable condition>

## 4. Functional Requirements

| ID | Requirement | Serves | Stories |
|---|---|---|---|
| FR-<AREA>-001 | <what the system does> | BR-001 | US-001 |

## 5. Non-Functional Requirements

| ID | Requirement (measurable) | Serves |
|---|---|---|
| NFR-001 | <e.g. booking page loads in ≤ 2 s at the 95th percentile> | BR-002 |

## 6. Flows

<Main flows as numbered steps or a Mermaid diagram — one per user story group.>

## 7. Release Scope

**In this release:** <US/FR IDs>

**Out of this release:** <capabilities> — <when>

## 8. Dependencies

- <other teams, systems, vendors, data>

## 9. Open Questions

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | <question> | <who answers> | <date> |
