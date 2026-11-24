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


STATUSES = ["To Do", "In Progress", "Blocked", "Done"]     # the values /dev-tasks-planner writes


def set_cells(path: Path, task_id: str, values: dict[str, str]) -> dict[str, str] | None:
    """Change cells of one row (canonical field → new value) and nothing else in the file: only that
    row's own lines are rewritten, every other byte — other rows' quoting, the header, a BOM, CRLF line
    ends — stays as it was, so the git diff is exactly the change. Returns the row's old values for the
    fields changed, or None when the task isn't in the file. Raises ValueError for a field the file has
    no column for."""
    raw = Path(path).read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if header is None:
        return None
    col = {}
    for i, h in enumerate(header):
        canon = _canonical(h)
        if canon and canon not in col:
            col[canon] = i
    missing = [f for f in values if f not in col]
    if missing:
        raise ValueError(f"{path} has no column for: {', '.join(missing)}")
    want = task_id.strip().lower()
    start = reader.line_num
    for row in reader:
        end = reader.line_num
        if "task_id" in col and len(row) > col["task_id"] and row[col["task_id"]].strip().lower() == want:
            old = {f: (row[col[f]] if col[f] < len(row) else "") for f in values}
            row += [""] * (len(header) - len(row))
            for f, v in values.items():
                row[col[f]] = v
            out = io.StringIO()
            csv.writer(out, lineterminator=newline).writerow(row)
            trailing = lines[end - 1][len(lines[end - 1].rstrip("\r\n")):]   # keep a missing final newline missing
            new_line = out.getvalue() if trailing else out.getvalue().rstrip("\r\n")
            new_text = "".join(lines[:start]) + new_line + "".join(lines[end:])
            tmp = Path(path).with_suffix(Path(path).suffix + ".tmp")
            tmp.write_bytes((b"\xef\xbb\xbf" if bom else b"") + new_text.encode("utf-8"))
            tmp.replace(path)   # all-or-nothing
            return old
        start = end
    return None


def _csv_cell(value: str) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow([value])
    return out.getvalue()


def add_column(path: Path, header: str, values: dict[str, str]) -> None:
    """Append a column (header + one value per row, by task ID; blank for others) without touching
    anything else: each row's existing text stays byte-for-byte, the cell goes on its last line."""
    raw = Path(path).read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    lines = text.splitlines(keepends=True)
    reader = csv.reader(io.StringIO(text))
    hdr = next(reader, None)
    if hdr is None:
        return
    id_col = next((i for i, h in enumerate(hdr) if _canonical(h) == "task_id"), None)
    want = {k.strip().lower(): v for k, v in values.items()}
    ends = {reader.line_num - 1: header}           # 0-based index of the last physical line → cell to add
    for row in reader:
        tid = row[id_col].strip().lower() if id_col is not None and len(row) > id_col else ""
        ends[reader.line_num - 1] = want.get(tid, "")
    out = []
    for i, line in enumerate(lines):
        if i in ends:
            body = line.rstrip("\r\n")
            out.append(body + "," + _csv_cell(ends[i]) + line[len(body):])
        else:
            out.append(line)
    tmp = Path(path).with_suffix(Path(path).suffix + ".tmp")
    tmp.write_bytes((b"\xef\xbb\xbf" if bom else b"") + "".join(out).encode("utf-8"))
    tmp.replace(path)
