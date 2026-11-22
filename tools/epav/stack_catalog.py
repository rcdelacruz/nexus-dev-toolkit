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
    """Every catalog entry found in `text`, as (first position, entry), ordered by position."""
    hits = []
    for tech in load():
        positions = [m.start() for p in tech["_patterns"] if (m := p.search(text))]
        if positions:
            hits.append((min(positions), tech))
    hits.sort(key=lambda h: h[0])
    return hits


def detect(text: str) -> list[str]:
    """Names of every catalog technology mentioned in `text`, in order of first mention."""
    return [tech["name"] for _, tech in find(text)]


def package_manager_for(text: str) -> str:
    """Package manager of the first-mentioned technology that has one, or ""."""
    for _, tech in find(text):
        if tech.get("package_manager"):
            return tech["package_manager"]
    return ""
