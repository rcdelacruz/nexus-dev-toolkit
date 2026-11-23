# Coding standards — CareSlot

- Django apps own their models; cross-app access goes through the owning app's functions, not raw queries.
- Views stay thin; business rules (2-appointment limit, cancel cut-off) live in `services.py` per app.
- htmx endpoints return template fragments named `_<name>.html` next to the page template.
- Tests: pytest + pytest-django; one test per acceptance criterion, named after it (`test_ac_007_…`).
