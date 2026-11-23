# AGENTS.md — CareSlot

Clinic appointment booking (example project for nexus v4 — made up).

## Stack (from the architecture's Choice lines)
Stack: Django, Python, htmx, Tailwind CSS, PostgreSQL, Celery, Redis, Docker, AWS

## Where things are
- `docs/` — requirements (BRD/PRD), architecture + ADRs, designs (`design.json`), dev tasks, change requests
- `careslot/` settings, Celery app · apps: `accounts`, `scheduling`, `booking`, `frontdesk`, `notifications`
  (one per component in architecture §3)
- `templates/` — one template per screen, named after its DES id in the first line
- `static/src/app.css` — the theme; colours come only from the design tokens

## Rules
- Build every screen from its HTML frame in `docs/designs/careslot/` and the tokens. The React export there
  is a reference only (ADR-CARESLOT-E001-001).
- No hard-coded colours in templates — use the theme classes (`bg-primary`, `text-muted-foreground`, …).
- Double bookings are prevented by the database, not by a check in Python (ADR-CARESLOT-E001-002).
- Secrets only from the environment (`.env`, see `.env.example`); never committed.
- Every change: `uv run ruff check .`, `uv run python manage.py check`, `uv run pytest` must pass.
- One task at a time, from `docs/dev-tasks/careslot/`, through /evaluate → /plan → /apply → /validate.
