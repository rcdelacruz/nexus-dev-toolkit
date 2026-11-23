"""
Stack catalog — data-driven technology detection.

The technologies live in `stack_catalog.json` next to this file. Supporting a
new stack means adding an entry there, not code. Matching is whole-word:
an alias only matches when the characters on both sides are not letters,
digits or underscores, so "t3" no longer matches inside "ht3x" and "go" never
matches inside "mongo". Aliases in `exact_case` are matched case-sensitively,
for names that are also everyday English words ("Go", "Rails", "Swift").

Known limit: keyword matching cannot tell "we use X" from "we rejected X".
"""

import json
import re
from functools import lru_cache
from pathlib import Path

_CATALOG_PATH = Path(__file__).parent / "stack_catalog.json"
_WORD = r"[A-Za-z0-9_]"


def _alias_pattern(alias: str) -> str:
    parts = [re.escape(p) for p in alias.split()]
    return rf"(?<!{_WORD})" + r"\s+".join(parts) + rf"(?!{_WORD})"


@lru_cache(maxsize=1)
def load() -> tuple[dict, ...]:
    """Return the catalog entries, each with compiled matchers under `_patterns`."""
    data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    entries = []
    for tech in data["technologies"]:
        patterns = [re.compile(_alias_pattern(a), re.IGNORECASE) for a in tech.get("aliases", [])]
        patterns += [re.compile(_alias_pattern(a)) for a in tech.get("exact_case", [])]
        entries.append({**tech, "_patterns": tuple(patterns)})
    return tuple(entries)


def find(text: str) -> list[tuple[int, dict]]:
    """Every catalog entry found in `text`, as (first position, entry), ordered by position.

    A technology can list others it "shadows" in the catalog: a match of a shadowed name that
    sits inside its own match is dropped ("React Native" reports React Native, not also React).
    Everything else that genuinely implies another tech keeps reporting both ("Ruby on Rails"
    → Ruby on Rails + Ruby).
    """
    spans: list[tuple[int, int, str]] = []          # (start, end, tech name)
    techs = {t["name"]: t for t in load()}
    for tech in techs.values():
        for p in tech["_patterns"]:
            spans += [(m.start(), m.end(), tech["name"]) for m in p.finditer(text)]
    spans.sort(key=lambda s: (-(s[1] - s[0]), s[0]))
    kept: list[tuple[int, int, str]] = []
    for s, e, name in spans:
        if any(ks <= s and e <= ke and name in techs[kn].get("shadows", ()) for ks, ke, kn in kept):
            continue
        kept.append((s, e, name))
    first: dict[str, int] = {}
    for s, _, name in kept:
        first[name] = min(s, first.get(name, s))
    return sorted(((pos, techs[name]) for name, pos in first.items()), key=lambda h: h[0])


def detect(text: str) -> list[str]:
    """Names of every catalog technology mentioned in `text`, in order of first mention."""
    return [tech["name"] for _, tech in find(text)]


# A line saying a technology was dropped or is only an example is not part of the stack.
_NOT_USED = re.compile(
    r"(?i)\b(superseded|no longer (?:used|in use)|deprecated|rejected|replaced by|removed|"
    r"not (?:used|chosen|adopted)|considered but|was originally)\b"
)
_QUOTED = re.compile(r'"[^"\n]{3,}"|“[^”\n]{3,}”')   # quotations cite people, they are not decisions
_EXAMPLE = re.compile(r"(?i)\((?:[^()]*?\b(?:e\.g\.|for example|such as)\b[^()]*)\)|\be\.g\.[^.;\n)]*")
# Inside one Choice line, what the decision says it does NOT use: "Django + htmx, not a React SPA",
# "templates instead of the React export", "the React export is a reference only".
_CLAUSE_SPLIT = re.compile(r"\s*(?:[;,—–]|\s-\s)\s*")
_NEGATED_TAIL = re.compile(r"(?i)\b(?:not|no|never|instead of|rather than|without|apart from|except)\b.*$")
_REFERENCE_ONLY = re.compile(r"(?i)\b(?:(?:is|as|stays?|kept as|only) an?\s+(?:behaviou?r\s+)?reference|reference only|for reference)\b")


def _drop_negated(value: str) -> str:
    kept = []
    for clause in _CLAUSE_SPLIT.split(value):
        if _REFERENCE_ONLY.search(clause):
            continue
        kept.append(_NEGATED_TAIL.sub("", clause))
    return "; ".join(c for c in kept if c.strip())


_CHOICE = re.compile(r"(?im)^\s*(?:[-*+]\s*)?\*\*Choice\*\*\s*:?\s*:?\s*(.+)$|^\s*(?:[-*+]\s*)?\*\*Choice:\*\*\s*(.+)$")


def detect_used(text: str) -> list[str]:
    """Like detect(), but ignores lines that mark a technology as dropped/rejected/superseded
    and "e.g." examples. Still keyword matching; prefer detect_from_choices when the doc has
    **Choice** lines."""
    kept = []
    for line in text.splitlines():
        if _NOT_USED.search(line):
            continue
        kept.append(_EXAMPLE.sub(" ", line))
    return detect("\n".join(kept))


def _table_choice_cells(text: str) -> list[str]:
    """Cells of the "Choice" column in Markdown tables (| Category | Choice | Rationale |)."""
    cells, col = [], None
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            col = None
            continue
        parts = [p.strip() for p in s.strip("|").split("|")]
        if col is None:
            low = [p.lower() for p in parts]
            col = low.index("choice") if "choice" in low else -1
            continue
        if col < 0 or set(s) <= set("|-: "):
            continue
        if col < len(parts):
            cells.append(parts[col])
    return cells


def detect_from_choices(text: str) -> list[str]:
    """Technologies the architecture doc explicitly chose: `**Choice**:` lines
    ("- **Choice**: Next.js v16 (TypeScript)") and the "Choice" column of decision tables.
    Choices marked superseded/rejected, "e.g." examples and what a Choice line says it does not use
    ("not a React SPA", "instead of …", "… is a reference only") are ignored. Empty if the doc
    records no choices."""
    values = [m.group(1) or m.group(2) or "" for m in _CHOICE.finditer(text)] + _table_choice_cells(text)
    lines = [_drop_negated(_EXAMPLE.sub(" ", _QUOTED.sub(" ", v))) for v in values if v and not _NOT_USED.search(v)]
    return detect("\n".join(lines)) if lines else []


def package_manager_for(text: str) -> str:
    """Package manager of the first-mentioned technology that has one, or ""."""
    for _, tech in find(text):
        if tech.get("package_manager"):
            return tech["package_manager"]
    return ""
