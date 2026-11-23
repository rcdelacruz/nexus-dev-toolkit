"""
Change-request records: docs/change-requests/CR-004.json.

Written by /change-request, read by /dev-tasks-planner to re-plan only the task rows linked
to the IDs a change request touched.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tools.epav.formats import FORMAT_VERSION


@dataclass
class ChangeRequest:
    id: str                                            # CR-004
    title: str
    date: str                                          # YYYY-MM-DD
    format_version: int = FORMAT_VERSION
    changed_ids: list[str] = field(default_factory=list)
    added_ids: list[str] = field(default_factory=list)
    removed_ids: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)     # docs/ files the CR edited
    reason: str = ""

    @property
    def touched_ids(self) -> list[str]:
        seen, out = set(), []
        for i in self.changed_ids + self.added_ids + self.removed_ids:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "ChangeRequest":
        return cls(**json.loads(text))


def affected_rows(rows: list[dict[str, str]], cr: ChangeRequest, patterns: dict[str, str] | None = None) -> list[dict[str, str]]:
    """Task rows whose trace_ids (or, if empty, text) mention any ID the CR touched."""
    from tools.epav.formats.ids import extract_ids
    touched = set(cr.touched_ids)
    hit = []
    for r in rows:
        ids = extract_ids(r.get("trace_ids", ""), patterns) or extract_ids(
            " ".join(v for k, v in r.items() if k != "trace_ids"), patterns)
        if touched & set(ids):
            hit.append(r)
    return hit


def read_cr(path: Path) -> ChangeRequest:
    return ChangeRequest.from_json(Path(path).read_text(encoding="utf-8"))


def write_cr(path: Path, cr: ChangeRequest) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(cr.to_json(), encoding="utf-8")
    tmp.replace(p)
