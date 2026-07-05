# Making EPAV an Autonomous Loop — Implementation Guide

> **Status: guide only — none of these changes are applied yet.**
> This document explains how to evolve the existing EPAV cycle
> (`/evaluate → /plan → /apply → /validate`) into a self-correcting
> autonomous loop, so anyone on the team can implement or review the change.

---

## 1. The idea in one picture

**Today** — every arrow is a human action. If `/validate` fails, a human
reads the failures and manually restarts:

```
/evaluate → /plan → [human approves] → /apply → /validate → done
                                                    │
                                                  fail → human reads, human re-runs
```

**Target** — the human still approves the plan, but the *inner* loop
(apply ↔ validate) closes itself and retries until it passes or runs out
of budget:

```
/evaluate → /plan → [human approves plan] ──► INNER LOOP (autonomous)
                                              ┌──────────────────────┐
                                              │ /apply               │
                                              │    ↓                 │
                                              │ /validate            │
                                              │    ├─ PASS → done ───┼──► report to human
                                              │    └─ FAIL           │
                                              │        ↓             │
                                              │ retry budget left?   │
                                              │    ├─ yes → /apply   │
                                              │    │   (failures as  │
                                              │    │    new context) │
                                              │    └─ no → escalate ─┼──► human decides
                                              └──────────────────────┘
```

The human moves from *cranking every phase* to *approving scope and
reviewing outcomes*. This matches the nested-loops model: the agent owns
the seconds-to-minutes coding loop; the human owns the steering loop.

**Why this is safe with EPAV specifically:** the existing "one task, no
scope creep" rule means the autonomous retries can only iterate *within*
the approved plan — they can never expand scope on their own. The plan
approval gate is the contract; the loop just fulfills it.

---

## 2. What changes, file by file

All changes live in three skill files under `tools/epav/skills/`.
No Python code changes are required — the loop is prompt-orchestrated.

| File | Change | Effort |
|---|---|---|
| `epav.md` | Add the retry loop between APPLY and VALIDATE, retry budget, escalation | ~20 lines |
| `validate.md` | Harden the verifier (tests + review mandatory); emit a machine-readable failure block | ~15 lines |
| `apply.md` | Accept a "retry context" input (validation failures from the previous iteration) | ~10 lines |

### 2.1 `epav.md` — close the loop

Replace **Step 3/Step 4** of the current orchestrator with an iterating
inner loop. Concretely, after the existing approval gate, add:

```markdown
### Step 3+4 — APPLY ↔ VALIDATE inner loop (autonomous after approval)

Set `iteration = 1`, `MAX_ITERATIONS = 3`.

1. Run `/apply`. On iteration > 1, pass the previous VALIDATION FAILURES
   block as the apply context — fix exactly those failures, nothing else.
2. Run `/validate` in full (build, tests, criteria, review).
3. If VALIDATE reports zero BLOCKERs and zero FIX NOWs → exit the loop,
   output the final VALIDATE COMPLETE summary, and stop.
4. If failures remain and `iteration < MAX_ITERATIONS`:
   - increment `iteration`
   - announce: "Iteration N of MAX: re-entering APPLY with M failures."
   - go to 1. Do NOT ask the user anything between iterations.
5. If failures remain and `iteration == MAX_ITERATIONS` → ESCALATE:
   stop, and output:

       LOOP ESCALATION
       ───────────────
       Iterations used:   3/3
       Still failing:     <the remaining VALIDATION FAILURES block>
       What was tried:    <one line per iteration>
       Recommendation:    <revise plan | needs human decision | blocked on X>

   Then wait for the user. Never exceed the retry budget.

### Loop rules (non-negotiable)

- The loop may only fix failures listed by VALIDATE. Any new work
  discovered mid-loop goes to knowledge/retros/, exactly as today.
- If the same criterion fails twice with the same root cause, do not
  burn the third iteration — escalate early with that analysis.
- "stop"/"abort"/"cancel" from the user interrupts the loop immediately.
```

### 2.2 `validate.md` — harden the verifier

The loop is only as trustworthy as its exit condition. Two changes:

**(a) Make verification mechanical, not optional.** Extend Step 2 so the
checklist always includes, in order:

```markdown
### 2 — Run the verifier stack (all mandatory, in order)

1. Build:        `npm run build` (or project equivalent) — must exit 0
2. Tests:        `npm test` (or project equivalent) — must exit 0;
                 if the plan added behavior, at least one new/updated test
                 must cover it
3. Type check:   `tsc --noEmit` / `mypy` / project equivalent, if present
4. Review:       run the `/code-review` skill on the diff; treat every
                 finding it classifies as a blocker as [BLOCKER]
5. Criteria:     check each acceptance criterion — PASS / FAIL / PARTIAL
```

**(b) Emit failures in a fixed, machine-readable block** so `/apply`
can consume them on the next iteration. Add to Step 3:

```markdown
When any check fails, output this block verbatim before classification:

    VALIDATION FAILURES (iteration N)
    ─────────────────────────────────
    - [BLOCKER|FIX NOW] <check that failed>: <exact error / failing criterion>
      evidence: <test name, build output line, or review finding id>
      suspected cause: <one line>
```

This block is the loop's feedback signal — it is what makes the retry
targeted instead of a blind re-attempt.

### 2.3 `apply.md` — accept retry context

Add one section after the Prerequisite:

```markdown
## Retry mode (loop iterations 2+)

If a VALIDATION FAILURES block is provided as context:
- Scope for this iteration is fixing exactly those failures. The approved
  plan still bounds all work; the failures narrow it further.
- Do not re-implement steps that already passed validation.
- If a failure cannot be fixed within the approved plan's scope, stop and
  report it — that is a plan problem, not an apply problem.
```

---

## 3. Choosing the retry budget

| Budget | Behavior | When to use |
|---|---|---|
| 1 (no loop) | Today's behavior | High-risk changes, migrations |
| **3 (default)** | Fixes the common "test failed on first pass" cases | Normal feature work |
| 5 | For flaky/integration-heavy suites | Only with fast, reliable verifiers |

Two failures of the *same* criterion with the same root cause should
escalate immediately regardless of remaining budget — a loop that isn't
converging by iteration 2 almost never converges by iteration 5.

Optionally expose the budget as an argument: `/epav <task> --max-loops 5`.

---

## 4. Loop telemetry (recommended, 5 lines of effort)

Append one line per completed cycle to `knowledge/retros/loop-log.md`:

```
| date | task | iterations | exit (pass/escalated) | failing stage(s) |
```

After a few sprints this answers the questions that let you tune the
loop: How often does iteration 1 pass? Where do failures cluster —
tests, review, or criteria? Is the budget too small or wasted?

---

## 5. Closing the outer (learning) loop — optional phase 2

Today `/validate` writes discovered patterns to `knowledge/`, but nothing
forces the next cycle to read them. One-line fix in `evaluate.md` Step 2:
make `knowledge/patterns/` + `knowledge/retros/loop-log.md` a **mandatory**
context load (it is currently a "check if present"). That turns EPAV from
a loop that self-corrects within a task into one that improves across
tasks.

---

## 6. Rollout

1. Edit the three skill files in this repo (`tools/epav/skills/`).
2. Bump the version (full checklist in `CLAUDE.md`) and publish.
3. Consuming projects pick it up with `nexus update` + `nexus sync`.
4. Dogfood on one low-risk task with `MAX_ITERATIONS = 3` and watch the
   first escalation report before trusting it on real work.

Rollback is trivial: the loop is entirely prompt-defined, so reverting
the three files restores today's human-cranked behavior.

---

## 7. What deliberately does NOT change

- **The plan approval gate stays.** Autonomy applies only *after* a human
  approves scope. Never auto-approve plans.
- **Scope discipline stays.** The loop fixes validation failures; it never
  adds features, refactors opportunistically, or expands the plan.
- **Abort stays.** "stop" interrupts the loop at any point.
- **The knowledge contribution step stays** — it runs on the final
  (passing) iteration.

---

## Appendix — what a loop run looks like

```
> /epav "Add CSV export to the reports page"

EVALUATE SUMMARY ...
PLAN ... blast radius ...
Plan ready. Reply go to implement.

> go

[iteration 1/3] APPLY ... APPLY COMPLETE
[iteration 1/3] VALIDATE ... 2 failures:
  - [BLOCKER] tests: exports_csv_handles_empty_rows FAILED
  - [FIX NOW] review: unhandled null in formatRow()
Iteration 2 of 3: re-entering APPLY with 2 failures.

[iteration 2/3] APPLY (retry mode: fixing 2 listed failures) ... COMPLETE
[iteration 2/3] VALIDATE ... all checks pass.

VALIDATE COMPLETE
─────────────────
Criteria passed:  4/4
Iterations used:  2/3
Issues fixed:     empty-rows test, null guard in formatRow
Backlog items:    (none)

Task complete. Ready for the next /evaluate.
```
