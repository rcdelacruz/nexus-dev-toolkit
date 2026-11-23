"""
Per-project guides: docs/requirements/REQUIREMENTS-GUIDE.md, docs/arch-docs/ARCHITECTURE-GUIDE.md,
docs/designs/DESIGN-GUIDE.md.

A guide is a normal Markdown document people read and edit. Its machine-readable part is one
fenced block tagged `nexus-guide`, holding JSON:

    ```nexus-guide
    {"kind": "architecture", "format_version": 1,
     "id_patterns": {...}, "required_sections": [...], "stack_section": "...",
     "rules": [{"id": "A1", "severity": "BLOCKER", "text": "..."}]}
    ```

Missing or broken blocks never crash a command: `load_guide` returns the defaults for that kind
plus a list of problems, so the caller can report them.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from tools.epav.formats import FORMAT_VERSION
from tools.epav.formats.ids import DEFAULT_PATTERNS

KINDS = ("requirements", "architecture", "design")
SEVERITIES = ("BLOCKER", "FIX NOW", "BACKLOG")
_BLOCK = re.compile(r"```nexus-guide\s*\n(.*?)\n```", re.S)

# Section names a team's architecture doc uses (defaults: the 9-section template measured in a
# real project). Matching ignores numbering ("## 4\\. Technology Choices") and case.
DEFAULT_ARCH_SECTIONS = [
    "Document Metadata", "System Overview", "Component Breakdown", "Technology Choices",
    "Data Model", "Integration and API Design", "Deployment Topology", "NFR Fulfillment",
    "Open Questions and Deferred Decisions",
]


@dataclass
class Guide:
    kind: str
    format_version: int = FORMAT_VERSION
    id_patterns: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_PATTERNS))
    required_sections: list[str] = field(default_factory=list)
    stack_section: str = ""
    documents: dict[str, list[str]] = field(default_factory=dict)   # doc type → its required sections (BRD, PRD)
    rules: list[dict] = field(default_factory=list)
    source: str = "default"
    problems: list[str] = field(default_factory=list)

    def to_block(self) -> str:
        data = {
            "kind": self.kind, "format_version": self.format_version,
            "id_patterns": self.id_patterns, "required_sections": self.required_sections,
            "stack_section": self.stack_section, "documents": self.documents, "rules": self.rules,
        }
        return "```nexus-guide\n" + json.dumps(data, indent=2) + "\n```"


_TEMPLATES = Path(__file__).resolve().parent.parent.parent / "templates"
_TEMPLATE_FILES = {"architecture": "ARCHITECTURE-GUIDE.md", "design": "DESIGN-GUIDE.md",
                   "requirements": "REQUIREMENTS-GUIDE.md"}


def default_guide(kind: str) -> Guide:
    """nexus's own guide for `kind`: the rules of the shipped template, so a project without
    its own guide is still checked (never a silent "ok" with no rules)."""
    g = Guide(kind)
    if kind == "architecture":
        g.required_sections, g.stack_section = list(DEFAULT_ARCH_SECTIONS), "Technology Choices"
    tpl = _TEMPLATES / _TEMPLATE_FILES.get(kind, "")
    m = _BLOCK.search(tpl.read_text(encoding="utf-8")) if tpl.is_file() else None
    if m:
        try:
            data = json.loads(m.group(1))
            g.rules = [r for r in data.get("rules", []) if str(r.get("severity", "")).upper() in SEVERITIES]
            g.required_sections = list(data.get("required_sections") or g.required_sections)
            g.stack_section = data.get("stack_section") or g.stack_section
            if isinstance(data.get("documents"), dict):
                g.documents = {str(k): [str(x) for x in v] for k, v in data["documents"].items() if isinstance(v, list)}
        except json.JSONDecodeError:
            pass
    return g


def parse_guide(text: str, kind: str, source: str = "") -> Guide:
    base = default_guide(kind)
    base.source = source or "default"
    m = _BLOCK.search(text or "")
    if not m:
        base.problems.append("no ```nexus-guide``` block found — using nexus defaults")
        return base
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        base.problems.append(f"nexus-guide block is not valid JSON ({e.msg}, line {e.lineno}) — using nexus defaults")
        return base
    if data.get("kind", kind) != kind:
        base.problems.append(f"guide kind is {data.get('kind')!r}, expected {kind!r}")
    if int(data.get("format_version", FORMAT_VERSION)) > FORMAT_VERSION:
        base.problems.append(f"guide format_version {data.get('format_version')} is newer than this nexus "
                             f"understands ({FORMAT_VERSION}) — upgrade nexus")
    if isinstance(data.get("id_patterns"), dict):
        bad = []
        for k, p in data["id_patterns"].items():
            try:
                re.compile(p)
                base.id_patterns[k] = p
            except re.error:
                bad.append(k)
        if bad:
            base.problems.append(f"invalid ID patterns ignored: {bad}")
    if isinstance(data.get("required_sections"), list):
        base.required_sections = [str(s) for s in data["required_sections"]]
    if data.get("stack_section"):
        base.stack_section = str(data["stack_section"])
    if isinstance(data.get("documents"), dict):
        base.documents = {str(k): [str(x) for x in v] for k, v in data["documents"].items() if isinstance(v, list)}
    rules = []
    for r in data.get("rules", []) if isinstance(data.get("rules"), list) else []:
        sev = str(r.get("severity", "")).upper()
        if sev not in SEVERITIES:
            base.problems.append(f"rule {r.get('id', '?')}: severity {r.get('severity')!r} is not one of {SEVERITIES}")
            continue
        rules.append({"id": str(r.get("id", "")), "severity": sev, "text": str(r.get("text", ""))})
    base.rules = rules
    return base


def load_guide(path: Path, kind: str) -> Guide:
    p = Path(path)
    if not p.is_file():
        g = default_guide(kind)
        g.problems.append(f"{p} not found — using nexus defaults")
        return g
    return parse_guide(p.read_text(encoding="utf-8", errors="replace"), kind, str(p))


def heading_key(heading: str) -> str:
    """'## 4\\. Technology Choices' / '4. technology choices' → 'technology choices'."""
    h = heading.lstrip("#").replace("\\", "").strip().lower()
    h = re.sub(r"^[\d.]+\s*", "", h)
    return re.sub(r"\s+", " ", h)
