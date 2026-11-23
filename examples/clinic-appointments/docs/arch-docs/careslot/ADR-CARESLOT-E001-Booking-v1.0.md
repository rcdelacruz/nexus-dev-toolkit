<!-- Example project for nexus v4. CareSlot and everything in it is made up. -->

Epic: E001 — Booking
Covers: US-002, US-003, US-004, US-005, FR-BOOK-001, FR-BOOK-002, FR-BOOK-003, FR-BOOK-004

Patients find a free slot, book it, see their appointments and cancel them (BR-001, BR-002, BR-003, BR-005).
ADR-CARESLOT-E001-001 (server-rendered Django + htmx) applies to every epic.


## ADR-CARESLOT-E001-001: Build a server-rendered Django app with htmx, not a single-page app
### Status
Accepted
### Type
Decision
### Context
Two developers, a fixed launch date (BRD §9), and screens that need live updates in only a few places (US-002, US-007). The designer also exported a React version of the screens.
### Options Considered
1. Django + htmx, server-rendered. 2. Django REST API + React SPA (reusing the design export). 3. Next.js full-stack.
### Decision
Option 1.
### Rationale
One codebase and one deployable unit; the React export would save some UI time but double the stack the team has to run and secure. The HTML frames and tokens give everything needed to build the screens.
### Consequences
The React export is used as a behaviour reference only. Partial updates are written as htmx fragments.
### Affected Epics
E001, E002, E003
### Architecture Document Reference
§4 Web framework, §4 Interactivity

## ADR-CARESLOT-E001-002: Prevent double bookings with a database constraint
### Status
Accepted
### Type
Decision
### Context
BR-003 says a double booking must be impossible, not unlikely; today it happens twice a week.
### Options Considered
1. Application-level check before insert. 2. Unique partial index on (doctor_id, starts_at) where status = booked.
### Decision
Option 2; the application turns the constraint error into "This slot was just taken" (AC-007).
### Rationale
An application check can't stop two simultaneous requests; the database can.
### Consequences
Moving an appointment is cancel + book inside one transaction.
### Affected Epics
E001
### Architecture Document Reference
§5 Data Model
