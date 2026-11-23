"""
docs/designs/<module>/design.json — the framework-neutral summary of a design export.

Written by /design (from HTML frames, tokens, an optional react/next export), read by
/architect, /dev-tasks-planner and /scaffold. Holds what every stack needs; framework code
stays in the export folder and is only referenced.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tools.epav.formats import FORMAT_VERSION


@dataclass
class Screen:
    id: str                                   # DES-001
    name: str                                 # "Login"
    frame: str = ""                           # path of the HTML frame, relative to the module folder
    component: str = ""                       # matching component in an export, if any
    states: list[str] = field(default_factory=list)      # empty / loading / error / disabled …
    trace_ids: list[str] = field(default_factory=list)   # requirement IDs this screen covers


@dataclass
class DesignManifest:
    module: str
    format_version: int = FORMAT_VERSION
    sources: list[str] = field(default_factory=list)                 # files/folders imported
    tokens: dict[str, dict[str, str]] = field(default_factory=lambda: {"light": {}, "dark": {}})
    token_sources: list[str] = field(default_factory=list)
    screens: list[Screen] = field(default_factory=list)
    exports: list[dict] = field(default_factory=list)                # {"path", "framework"}
    assets: list[str] = field(default_factory=list)
    unmatched_colours: dict[str, list[str]] = field(default_factory=dict)   # frame → colours not in tokens
    unrecognised: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "DesignManifest":
        data = json.loads(text)
        screens = [Screen(**s) for s in data.pop("screens", [])]
        return cls(screens=screens, **data)

    def problems(self) -> list[str]:
        out = []
        if self.format_version > FORMAT_VERSION:
            out.append(f"design.json format_version {self.format_version} is newer than this nexus understands")
        ids = [s.id for s in self.screens]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            out.append(f"duplicate screen IDs: {dup}")
        if not self.tokens.get("light") and not self.tokens.get("dark"):
            out.append("no design tokens found")
        return out


def read_manifest(path: Path) -> DesignManifest:
    return DesignManifest.from_json(Path(path).read_text(encoding="utf-8"))


def write_manifest(path: Path, manifest: DesignManifest) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(manifest.to_json(), encoding="utf-8")
    tmp.replace(p)
