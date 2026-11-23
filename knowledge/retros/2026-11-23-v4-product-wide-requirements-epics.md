# v4: product-wide BRD/PRD, epics from the architecture, optional /design — validate notes

- [VERIFIED] Two real headless Claude sessions (`claude -p`, plan pre-approved in the prompt) ran the new skills in lab folders, graded by `nexus lab check`:
  - `/architect careslot` → 9/9 sections, 4 epics (its own split: Access and Platform, Patient Booking, Clinic Schedule, Appointment Reminders), every story/FR in exactly one epic; 5/5 checks.
  - `/design careslot --system lab/inputs/design-system` → 8 screens by epic, tokens unchanged from the system, every frame names its epic; 3/3 checks.
  - Pattern: a headless run with "the plan is approved in advance — go straight on after PLAN; don't ask, record questions" exercises a stop-for-approval skill end to end. Allow only the tools the skill needs (`--allowedTools`, `--strict-mcp-config --mcp-config .mcp.json`).
- [FIXED] Found by those runs:
  - `detect_from_choices` read a technology a Choice line rejects ("not a React SPA", "instead of the React export", "the React export is a reference only"). Negated clauses are now dropped. On the real reference project (checked locally) this removed two false stack entries, both from lines that rejected the technology, and changed nothing else.
  - The design reader counted a state as shown when a frame said it does NOT have it ("empty: not applicable"). Notes of absence are now removed before the state patterns run.
  - Lab modules started from the PRD *after* CR-001 (dangling `CR-001.json` reference, and the team module's exercise given away). `tools/lab/careslot/upstream/` now holds the docs as they were before CR-001 (generated, drift-checked).
- [FIXED] Both runs flagged the same product contradiction in the answer key: after CR-001 the reminder arrives exactly when online cancelling closes (BR-005). Recorded as Open Question 2 in PRD v1.1 (the CR-001 record is unchanged).
- [BACKLOG] State detection is still keyword-based for exports without `<!-- state: … -->` markers; a frame mentioning "error" in prose counts as an error state. The guide asks for the markers; a stricter mode (markers only) could be a guide option.
- [BACKLOG] Not yet run with a real agent: `/brd "description"`, `/prd`, `/scaffold` reading a copied export without `design.json`, `/dev-tasks-planner` one CSV per epic. Unit/lab tests cover their inputs and outputs; the agents' behaviour on these skills is not measured.
- [BACKLOG] The architect run noted gaps the CareSlot PRD leaves open (visit reason has no story; no account creation / password reset story; receptionist bookings vs the 2-appointment limit). Fine for an example; worth a line in the walkthrough's exercise ideas.
