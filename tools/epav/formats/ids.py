"""
Traceability IDs: business rules, requirements, epics, ADRs, design screens, change requests.

Projects keep their own ID schemes; a project's guide can replace or extend these defaults:
BRD business rules BR-003, plus the scheme measured in a real nexus project — user stories
US-001, FR-AUTH-003, NFR-012 / NFR-SEC-004, AC-184, epics E001, ADR-ACME-CORE-E001-001.
"""

import re

DEFAULT_PATTERNS: dict[str, str] = {
    "business": r"BR-\d+",
    "user_story": r"US-\d+",
    "functional": r"FR-[A-Z]+-\d+",
    "non_functional": r"NFR-(?:[A-Z]+-)?\d+",
    "acceptance": r"AC-\d+",
    "epic": r"E\d{3}",
    "adr": r"ADR(?:-[A-Z0-9]+)+-\d{3}",
    "design": r"DES-\d+",
    "change": r"CR-\d+",
}

_EDGE_L = r"(?<![A-Za-z0-9_-])"
_EDGE_R = r"(?![A-Za-z0-9_])"


def compile_patterns(patterns: dict[str, str] | None = None) -> list[tuple[str, re.Pattern]]:
    """Longest patterns first, so ADR-…-E001-001 is one ID, not also an epic E001."""
    pats = dict(DEFAULT_PATTERNS)
    if patterns:
        pats.update(patterns)
    ordered = sorted(pats.items(), key=lambda kv: -len(kv[1]))
    return [(kind, re.compile(_EDGE_L + p + _EDGE_R)) for kind, p in ordered]


def extract_ids(text: str, patterns: dict[str, str] | None = None) -> list[str]:
    """Every ID in `text`, in order of first appearance, each once. IDs inside a longer ID are skipped."""
    found: list[tuple[int, int, str]] = []
    for _, rx in compile_patterns(patterns):
        for m in rx.finditer(text or ""):
            s, e = m.span()
            if any(s >= fs and e <= fe for fs, fe, _ in found):
                continue
            found.append((s, e, m.group(0)))
    seen, out = set(), []
    for _, _, ident in sorted(found):
        if ident not in seen:
            seen.add(ident)
            out.append(ident)
    return out


def kind_of(ident: str, patterns: dict[str, str] | None = None) -> str | None:
    for kind, rx in compile_patterns(patterns):
        if rx.fullmatch(ident):
            return kind
    return None


def parse_id_list(value: str, patterns: dict[str, str] | None = None) -> list[str]:
    """A trace_ids cell ("US-001, FR-AUTH-003") → ["US-001", "FR-AUTH-003"]."""
    return extract_ids(value, patterns)


def format_id_list(ids: list[str]) -> str:
    return ", ".join(ids)
