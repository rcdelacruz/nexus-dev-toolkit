# Shared formats, lenient readers, strict writers

## The rule

Every file format two parts of nexus exchange (task files, traceability IDs, guides,
`design.json`, change-request records) is defined **once**, in `tools/epav/formats/`. Writers and
readers import it from there; nothing hand-rolls its own column names or parsing.

- **Read leniently.** Accept every shape real projects produce: `TASK_ID` / `Task ID` /
  `task_id`, an Excel BOM, `BE Estimate` vs `BE ESTIMATE`, the project's own ID scheme, its own
  section headings. Unknown columns are kept, not dropped.
- **Write strictly.** One documented layout (uppercase task headers, every canonical column,
  atomic write via a temp file + rename).
- **Version the format, not just the package.** Each format carries `FORMAT_VERSION`; a reader
  that meets a newer version says "upgrade nexus" instead of misreading.
- **Never fail silently.** A missing required column or blank required field is a reported
  status (`invalid_file`, `empty_fields`), never a blank value passed on.
- **Prove it with a round trip.** `tests/test_formats.py` writes each format and reads it back.

## Why

v3.0 `load_task` read `task_id`; v3.1.8 `/dev-tasks-planner` wrote `TASK_ID`. No test read a real
task file, so for months `load_task` returned blank tasks with no error — on the reference
project, 40 of its 49 task files. Two parts of the same tool disagreed about one format.

## Test against real shapes, not stand-ins

`tests/fixtures/projects/ams-shaped/` reproduces the *shapes* of a real project (three header
styles, module folders with clashing names, the 9-section architecture template, a superseded
choice, an "e.g." mention, a quoted remark) with made-up content — this repo is public, client
documents never go in it. `tests/test_real_project.py` runs the same checks against a real
project on your machine when `NEXUS_REAL_PROJECT` is set.
