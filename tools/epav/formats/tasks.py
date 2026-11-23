"""
Dev-task files: docs/dev-tasks/<module>/<epic>-tasks.csv.

Reading accepts any header style seen in real projects — `TASK_ID`, `Task ID`, `task_id`,
a leading Excel BOM, `BE Estimate` vs `BE ESTIMATE` — by normalising every header before
matching. Writing always uses the uppercase layout /dev-tasks-planner documents.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from tools.epav.formats import FORMAT_VERSION

# Canonical fields, in the order they are written.
COLUMNS = [
    "task_id", "issue_type", "summary", "user_story", "description", "acceptance_criteria",
    "priority", "estimate", "story_points", "role", "assignee", "status", "labels",
    "epic_link", "dependencies", "trace_ids",
]
# What /evaluate needs from a row. A file without these columns is an error, not a blank task.
REQUIRED = ["task_id", "user_story", "description", "acceptance_criteria"]

# Other header spellings real files use, after normalisation.
_ALIASES = {
    "task_id": {"id", "task", "key", "issue_key", "issue_id", "ticket"},
    "issue_type": {"type"},
    "user_story": {"story"},
    "acceptance_criteria": {"acceptance", "ac", "criteria"},
    "dependencies": {"depends_on", "dependency", "blocked_by"},
    "epic_link": {"epic"},
    "trace_ids": {"trace", "traceability", "requirements", "requirement_ids", "req_ids"},
}


def normalize_header(header: str) -> str:
    """`\\ufeffTASK_ID` / `Task ID` / `task-id` → `task_id`; `BE - Actual Effort` → `be_actual_effort`."""
    h = header.replace("﻿", "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", h).strip("_")


def _canonical(header: str) -> str | None:
    n = normalize_header(header)
    if n in COLUMNS:
        return n
    for canon, aliases in _ALIASES.items():
        if n in aliases:
            return canon
    return None


@dataclass
class TaskFile:
    path: Path
    header_map: dict[str, str]            # canonical field → the file's own header
    rows: list[dict[str, str]]            # canonical field → value (unknown columns kept under their own header)
    extra_columns: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)

    @property
    def ids(self) -> list[str]:
        return [r.get("task_id", "") for r in self.rows]

    def find(self, task_id: str) -> dict[str, str] | None:
        want = task_id.strip().lower()
        return next((r for r in self.rows if r.get("task_id", "").strip().lower() == want), None)


def read_tasks(path: Path) -> TaskFile:
    """Read a task file in any header style. Never raises on odd headers; reports them."""
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    header_map: dict[str, str] = {}
    extra: list[str] = []
    for h in headers:
        canon = _canonical(h)
        if canon and canon not in header_map:
            header_map[canon] = h
        elif h.strip():
            extra.append(h)
    rows = []
    for raw in reader:
        row = {canon: (raw.get(h) or "").strip() for canon, h in header_map.items()}
        for h in extra:
            row[h] = (raw.get(h) or "").strip()
        if any(v for v in row.values()):
            rows.append(row)
    missing = [f for f in REQUIRED if f not in header_map]
    return TaskFile(Path(path), header_map, rows, extra, missing)


def empty_required(row: dict[str, str]) -> list[str]:
    return [f for f in REQUIRED if not row.get(f, "").strip()]


def write_tasks(path: Path, rows: list[dict[str, str]], extra_columns: list[str] | None = None) -> None:
    """Write the documented layout: uppercase canonical headers (+ any extra columns), UTF-8."""
    extra_columns = extra_columns or []
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow([c.upper() for c in COLUMNS] + extra_columns)
    for r in rows:
        w.writerow([r.get(c, "") for c in COLUMNS] + [r.get(c, "") for c in extra_columns])
    tmp = Path(path).with_suffix(Path(path).suffix + ".tmp")
    tmp.write_text(out.getvalue(), encoding="utf-8")
    tmp.replace(path)  # all-or-nothing


__all__ = ["COLUMNS", "REQUIRED", "FORMAT_VERSION", "TaskFile", "normalize_header", "read_tasks",
           "write_tasks", "empty_required"]
