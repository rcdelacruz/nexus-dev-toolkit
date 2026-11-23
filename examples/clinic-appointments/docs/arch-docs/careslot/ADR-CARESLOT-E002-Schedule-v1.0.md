<!-- Example project for nexus v4. CareSlot and everything in it is made up. -->

Epic: E002 — Schedule
Covers: US-001, US-007, US-008, FR-AUTH-001, FR-SCHED-001, FR-SCHED-002

Staff sign in; receptionists manage the daily schedule for every doctor; doctors see their own day (BR-003, BR-006).
No decision of its own: it follows ADR-CARESLOT-E001-001 (server-rendered Django + htmx, htmx fragments for
the live schedule) and ADR-CARESLOT-E001-002 (moving an appointment is cancel + book in one transaction, so the
double-booking constraint holds for receptionists too). Sign-in lockout and the 30-minute idle timeout
(NFR-SEC-002) use Django's session settings — `accounts` in §3 and §8 of ARCH-CARESLOT-v1.0.
