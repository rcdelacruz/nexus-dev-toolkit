<!-- Example project for nexus v4. CareSlot and everything in it is made up. -->

Epic: E003 — Notifications
Covers: US-006, FR-NOTIF-001

SMS reminders before each appointment, delivered on time and never lost (BR-004, NFR-003); access to patient
data is logged (NFR-SEC-001).

## ADR-CARESLOT-E003-001: Send reminders from a Celery worker scheduled by Celery beat
### Status
Accepted (updated by CR-001: reminder moved from 24 h to 2 h before the appointment)
### Type
Decision
### Context
Reminders must go out within 5 minutes of their time (NFR-003) and survive SMS-provider hiccups.
### Options Considered
1. Cron + management command. 2. Celery worker + beat with retries.
### Decision
Option 2.
### Rationale
Retries and visibility of failed sends; independent of web traffic.
### Consequences
Redis runs as the broker; beat must run as exactly one instance.
### Affected Epics
E003
### Architecture Document Reference
§4 Background jobs, §8 NFR-003
