import json
import logging
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from tools.epav import stack_catalog
from tools.epav.formats import guides
from tools.epav.formats.ids import extract_ids, kind_of

logger = logging.getLogger(__name__)

# Fallback for docs that don't follow the project's guide: headings containing these words.
_ARCH_SECTIONS = [
    "stack", "tech stack", "technology stack", "technology choices",
    "data model", "schema", "database",
    "auth", "authentication", "authorization",
    "error", "error handling", "error format",
    "security", "cors", "headers",
    "adr", "architecture decision",
    "api", "conventions", "standards",
    "middleware", "infrastructure", "deployment",
]

GUIDE_PATH = Path("docs/arch-docs/ARCHITECTURE-GUIDE.md")
_SKIP_DIRS = {"node_modules", ".next", "dist", "build", "graphify-out", ".git"}
# Requirements documents sometimes sit in arch-docs/; they are not architecture.
_REQUIREMENT_FILE = re.compile(r"(?i)(\bbrd\b|\bprd\b|requirement|_brd|_prd|-brd|-prd|\bepic\s*\d+\b|\bepic\b.*\.docx)")
_ARCH_FILE = re.compile(r"(?i)^(arch|adr)[-_ ]|architecture|\badr\b")
MAX_FILE_BYTES = 2_000_000


def _extract_sections(text: str) -> dict:
    """Pull labelled sections from markdown text by heading keywords (fallback when a doc
    doesn't follow the guide's section names)."""
    sections: dict[str, list[str]] = {}
    current_key = "preamble"
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.lstrip("#").strip().lower()
        matched = next((k for k in _ARCH_SECTIONS if k in stripped), None)
        if line.startswith("#") and matched:
            if current_lines:
                sections[current_key] = current_lines
            current_key = stripped
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_key] = current_lines

    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def split_sections(text: str, level: int = 2) -> dict[str, str]:
    """Top-level sections by heading (`## …` by default), keyed by guides.heading_key()."""
    out: dict[str, list[str]] = {}
    key = None
    marker = "#" * level + " "
    for line in text.splitlines():
        if line.startswith(marker) and not line.startswith(marker + "#"):
            key = guides.heading_key(line)
            out.setdefault(key, [])
            out[key].append(line)
        elif key is not None:
            out[key].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def match_required(sections: dict[str, str], required: list[str]) -> tuple[dict[str, str], list[str]]:
    """Map each required section name to the doc's heading key. Exact key first, then a heading
    that contains the name (or the name contains the heading). Returns (found, missing)."""
    found, missing = {}, []
    for name in required:
        want = guides.heading_key(name)
        hit = want if want in sections else next(
            (k for k in sections if want in k or (len(k) > 3 and k in want)), None)
        if hit:
            found[name] = hit
        else:
            missing.append(name)
    return found, missing


# An epic is declared by its ADR file: an "Epic: E005 — Invoicing" line, or the
# file name ADR-<PROJECT>-E005-Product-Management-v1.0.md. Its stories are the requirement IDs it cites.
_EPIC_LINE = re.compile(r"(?im)^[\s>*_-]*epic\**\s*:\**\s*(E\d{3})\s*[—–:-]+\s*(.+?)\s*$")
_COVERS_LINE = re.compile(r"(?im)^[\s>*_-]*covers\**\s*:\**\s*(.+)$")
_EPIC_FILE = re.compile(r"(?i)-(E\d{3})-([A-Za-z][A-Za-z0-9-]*?)(?:-v\d+(?:\.\d+)*)?\.md$")


def epic_of(path: Path, text: str) -> tuple[str, str] | None:
    """(id, name) of the epic an ADR file declares, or None."""
    m = _EPIC_LINE.search(text[:3000])
    if m:
        return m.group(1).upper(), m.group(2).strip("*_ ")
    m = _EPIC_FILE.search(path.name)
    if m:
        return m.group(1).upper(), m.group(2).replace("-", " ").strip()
    return None


def _version(name: str) -> tuple[int, ...]:
    m = re.search(r"-v(\d+(?:\.\d+)*)\.md$", name, re.I)
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)


def classify(path: Path) -> str:
    """'architecture' | 'requirements' | 'guide' | 'other' — by file name."""
    name = path.name
    if name.upper().startswith("ARCHITECTURE-GUIDE"):
        return "guide"
    if _REQUIREMENT_FILE.search(name):
        return "requirements"
    if _ARCH_FILE.search(name):
        return "architecture"
    return "other"


def analyse_doc(text: str, guide: guides.Guide) -> dict:
    """Everything nexus reads from one architecture doc, following the guide."""
    sections = split_sections(text)
    found, missing = match_required(sections, guide.required_sections)
    stack_key = found.get(guide.stack_section) if guide.stack_section else None
    stack_text = sections.get(stack_key, "") if stack_key else ""
    stack = stack_catalog.detect_from_choices(stack_text or text)
    source = "choices" if stack else ""
    if not stack:
        stack = stack_catalog.detect_used(text)
        source = "mentions" if stack else "none"
    adr_ids = [i for i in extract_ids(text, guide.id_patterns) if kind_of(i, guide.id_patterns) == "adr"]
    req_ids = [i for i in extract_ids(text, guide.id_patterns) if kind_of(i, guide.id_patterns) not in ("adr", "epic", "change", "design")]
    return {
        "sections": sections, "required_found": found, "required_missing": missing,
        "stack": stack, "stack_source": source, "adr_ids": adr_ids, "requirement_ids": req_ids,
    }


def _collect(source: Path) -> tuple[list[Path], list[dict]]:
    if source.is_file():
        return [source], []
    files, skipped = [], []
    for f in sorted(source.rglob("*")):
        if not f.is_file() or _SKIP_DIRS & set(f.relative_to(source).parts):
            continue
        if f.suffix.lower() not in (".md", ".txt"):
            if f.suffix.lower() in (".docx", ".pdf"):
                skipped.append({"file": str(f), "reason": "not Markdown — add a .md copy (requirements belong in docs/requirements/)"})
            continue
        kind = classify(f)
        if kind == "requirements":
            skipped.append({"file": str(f), "reason": "requirements document — move it to docs/requirements/"})
        elif kind == "guide":
            continue
        elif f.stat().st_size > MAX_FILE_BYTES:
            skipped.append({"file": str(f), "reason": f"larger than {MAX_FILE_BYTES // 1_000_000} MB"})
        else:
            files.append(f)
    named = [f for f in files if classify(f) == "architecture"]
    return (named or files), skipped


def register_arch_ingest_tool(mcp: FastMCP) -> None:

    @mcp.tool()
    async def ingest_architecture_doc(
        doc_path: str = "",
        module: str = "",
        save_summary: bool = True,
    ) -> str:
        """
        Ingest architecture documents and extract key decisions for the EPAV workflow.

        Follows the project's docs/arch-docs/ARCHITECTURE-GUIDE.md (section names, where the stack
        is stated, ID patterns); nexus defaults when there is none. The stack comes from the
        doc's explicit **Choice** lines / Choice tables, not from every technology mentioned.
        Only ARCH-/ADR-/architecture files are read; BRD/PRD/requirements files found in
        arch-docs/ are skipped and reported.

        Args:
            doc_path: A doc (.md) or a folder. Default: docs/arch-docs/ (or docs/arch-docs/<module>/).
            module:   The app folder: docs/arch-docs/<module>/ (e.g. core, inventory). Its epics are
                      the ADR files inside it.
            save_summary: Write knowledge/rules/arch-summary.md.

        Returns:
            JSON with "status": ok | partial (required sections missing) | no_docs | not_found |
            error; per-file required sections found/missing, stack and where it came from,
            ADR and requirement IDs, the epics (one per ADR file: id, name, slug, `covers` — the
            IDs on its Covers: line, else every ID it cites — dev tasks get one CSV per epic), skipped files with the reason,
            guide problems.
        """
        try:
            source = Path(doc_path) if doc_path else Path("docs/arch-docs") / module if module else Path("docs/arch-docs")
            if not source.exists():
                return json.dumps({
                    "status": "not_found",
                    "error": f"Path not found: {source}. Provide doc_path or create docs/arch-docs/<module>/ "
                             "with your architecture doc.",
                })
            guide = guides.load_guide(GUIDE_PATH, "architecture")
            files, skipped = _collect(source)
            if not files:
                return json.dumps({"status": "no_docs", "error": f"No architecture docs in {source}",
                                   "skipped": skipped}, indent=2)

            per_file, all_sections, files_read, epics = [], {}, [], []
            chosen, mentioned = [], []
            for f in files:
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except Exception as e:
                    skipped.append({"file": str(f), "reason": f"unreadable: {e}"})
                    continue
                files_read.append(str(f))
                is_adr = f.name.upper().startswith("ADR")
                a = analyse_doc(text, guide)
                epic = epic_of(f, text) if is_adr else None
                if epic:
                    covers_line = _COVERS_LINE.search(text[:3000])
                    covers = ([i for i in extract_ids(covers_line.group(1), guide.id_patterns)
                               if kind_of(i, guide.id_patterns) not in ("adr", "epic", "change", "design")] if covers_line else [])
                    new = {"id": epic[0], "name": epic[1], "file": str(f), "slug": re.sub(r"[^a-z0-9]+", "-", epic[1].lower()).strip("-"),
                           "covers": covers or a["requirement_ids"][:500], "covers_source": "covers_line" if covers else "cited",
                           "requirement_ids": a["requirement_ids"][:500]}
                    old = next((e for e in epics if e["id"] == new["id"]), None)
                    if old is None:
                        epics.append(new)
                    elif _version(f.name) >= _version(Path(old["file"]).name):   # v2 of an epic's ADR file replaces v1
                        epics[epics.index(old)] = new
                if not a["required_found"]:                 # doc doesn't follow the guide — keyword fallback
                    a["sections"] = _extract_sections(text)
                entry = {"file": str(f), "stack": a["stack"], "stack_source": a["stack_source"],
                         "adr_ids": a["adr_ids"][:200], "requirement_ids": a["requirement_ids"][:500]}
                if not is_adr:
                    entry["required_sections_found"] = list(a["required_found"])
                    entry["required_sections_missing"] = a["required_missing"]
                per_file.append(entry)
                for k, v in a["sections"].items():
                    all_sections[f"{f.stem} — {k}"] = v
                bucket = chosen if a["stack_source"] == "choices" else mentioned
                for tech in a["stack"]:
                    if tech not in bucket:
                        bucket.append(tech)

            # Explicit decisions win; prose mentions are only a fallback and are labelled as such.
            stack, stack_source = (chosen, "choices") if chosen else (mentioned, "mentions" if mentioned else "none")
            arch_docs = [e for e in per_file if "required_sections_missing" in e]
            status = "partial" if any(e["required_sections_missing"] for e in arch_docs) else "ok"

            files_written = []
            if save_summary:
                summary_path = Path("knowledge/rules/arch-summary.md")
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                if stack_source == "choices":
                    stack_md = "\n## Stack (from the docs' Choice lines)\n\n" + "\n".join(f"- **Choice**: {s}" for s in stack) + "\n"
                else:
                    stack_md = ("\n## Stack (NOT confirmed — only mentioned in the docs; record decisions on **Choice** lines)\n\n"
                                + "\n".join(f"- {s}" for s in stack) + "\n")
                lines = ["# Architecture Summary\n", "_Auto-generated by ingest_architecture_doc_\n", stack_md]
                for section, content in all_sections.items():
                    lines.append(f"\n## {section}\n\n{content}\n")
                tmp = summary_path.with_suffix(".md.tmp")
                tmp.write_text("\n".join(lines), encoding="utf-8")
                tmp.replace(summary_path)
                files_written.append(str(summary_path))

            return json.dumps({
                "status": status,
                "guide": {"source": guide.source, "problems": guide.problems},
                "files_read": files_read,
                "files_skipped": skipped,
                "files_written": files_written,
                "stack": stack,
                "stack_source": stack_source,
                "documents": per_file,
                "epics": epics,
                "sections_extracted": list(all_sections.keys()),
                "summary": {k: v[:300] + "…" if len(v) > 300 else v for k, v in all_sections.items()},
            }, indent=2)

        except Exception as e:
            logger.exception("Unexpected error in ingest_architecture_doc")
            return json.dumps({"status": "error", "error": f"Unexpected error: {e}"})
