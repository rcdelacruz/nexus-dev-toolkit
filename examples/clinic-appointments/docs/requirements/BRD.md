# BRD — CareSlot · appointments

<!-- Example project for nexus v4. CareSlot and everything in it is made up. -->

| Field | Value |
|---|---|
| Version | 1.0 |
| Date | 2026-11-23 |
| Owner | Product owner, CareSlot clinics |
| Status | Approved |
| Sources | Kickoff workshop with the clinic manager and front-desk team; last quarter's no-show and phone-queue reports |

## 1. Purpose

Decide what the first release of online appointment booking must achieve for CareSlot's three
outpatient clinics, and which business rules it has to respect.

## 2. Problem

Patients can only book by phone. Front-desk staff spend most of the morning on calls (average
wait 6 minutes at peak), and 18 % of booked appointments are no-shows, so doctors sit idle while
other patients can't get a slot. Double bookings happen about twice a week because two staff
members edit the same paper-backed schedule.

## 3. Business Goals

1. Fewer no-shows — free doctor time is wasted today.
2. Fewer booking phone calls — front-desk time goes to patients at the desk.
3. No double bookings.
4. Patients can see and manage their own appointments.

## 4. Stakeholders

| Stakeholder | Interest | Decides on |
|---|---|---|
| Clinic manager | Utilisation, no-show rate | Business rules, release scope |
| Front-desk team | Fewer calls, a reliable schedule | Daily schedule workflow |
| Doctors | A full, predictable day | Working hours, slot length |
| Patients | Booking without calling | — (represented by the manager) |
| Data protection officer | Patient data handling | Privacy and retention rules |

## 5. Scope

**In scope**
- Patients book, see and cancel their own appointments online.
- Front desk sees and manages the daily schedule of every doctor.
- Reminders before the appointment.

**Out of scope**
- Payments and insurance — later release.
- Video consultations — not planned.
- Integration with the hospital's medical-records system — release 2.

## 6. Business Rules

| ID | Rule | Source |
|---|---|---|
| BR-001 | Patients can book any free slot online, 24 hours a day, up to 30 days ahead. | Clinic manager, kickoff |
| BR-002 | A patient can hold at most 2 future appointments at a time. | Clinic manager, kickoff |
| BR-003 | A slot can be booked by only one patient; a double booking must be impossible, not just unlikely. | Front-desk team, kickoff |
| BR-004 | Every patient is reminded before each appointment. | Clinic manager, no-show report |
| BR-005 | Patients can cancel online until 2 hours before the appointment; later cancellations go through the front desk. | Clinic manager, kickoff |
| BR-006 | Patient data stays in the clinic's region and is visible only to the patient and clinic staff. | Data protection officer |

## 7. Success Metrics

| Metric | Today | Target | Measured by | Serves |
|---|---|---|---|---|
| No-show rate | 18 % | ≤ 8 % three months after launch | Monthly no-show report | BR-004, BR-005 |
| Bookings made online | 0 % | ≥ 60 % three months after launch | Booking channel in the schedule | BR-001 |
| Booking calls per day | ~140 | ≤ 60 | Phone system report | BR-001 |
| Double bookings | ~2 per week | 0 | Front-desk incident log | BR-003 |

## 8. Assumptions

- Most patients have a mobile phone that can receive SMS.
- Doctors' working hours are fixed per week and change rarely.

## 9. Constraints

- Launch before the flu season (target: 1 October).
- Hosting in the clinic's region (BR-006).
- Two developers and one designer for the first release.

## 10. Open Questions

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Should walk-in patients be added to the online schedule by the front desk? | Front-desk lead | Before release 2 |
