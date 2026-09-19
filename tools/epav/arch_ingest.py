import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from tools.epav import judgment

logger = logging.getLogger(__name__)

_ARCH_CATEGORIES = {
    "stack": "Technology stack, frameworks, languages, or runtime/platform choices",
    "data_model": "Data model, database schema, or entity/table design",
    "auth": "Authentication or authorization strategy (login, sessions, tokens, permissions)",
    "error_handling": "Error handling conventions or the error response format",
    "security": "Security rules, CORS policy, headers, or other security constraints not specific to login/auth",
    "adr": "An architecture decision record or a specific named architecture decision",
    "api_conventions": "API design conventions, naming standards, or request/response contracts",
    "middleware_infra": "Middleware stack or infrastructure/deployment setup",
    "other": "Does not clearly belong to any of the other categories (e.g. table of contents, changelog, project timeline, unrelated notes)",
}

# Keyword fallback, used only when TypeSafe is unavailable (no API key,
# network error, SDK not installed). Same literal substrings the old
# heuristic used for all of these categories.
_ARCH_KEYWORDS = [
    "stack", "tech stack", "technology stack",
    "data model", "schema", "database",
    "auth", "authentication", "authorization",
    "error", "error handling", "error format",
    "security", "cors", "headers",
    "adr", "architecture decision",
    "api", "conventions", "standards",
    "middleware", "infrastructure",
]


def _split_by_heading(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Structural split only: every '#' heading line starts a new block.

    Deciding what each heading is *about* is a semantic judgment made by
    `_classify_headings`; this just recovers the document's actual structure,
    so no heading's content silently gets absorbed into an unrelated section.
    """
    preamble_lines: list[str] = []
    blocks: list[list[str]] = []
    headings: list[str] = []

    for line in text.splitlines():
        if line.startswith("#"):
            headings.append(line.lstrip("#").strip())
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
        else:
            preamble_lines.append(line)

    bodies = ["\n".join(b).strip() for b in blocks]
    return "\n".join(preamble_lines).strip(), list(zip(headings, bodies))


def _classify_headings_fallback(headings: list[str]) -> list[str]:
    return [
        "relevant" if any(k in heading.lower() for k in _ARCH_KEYWORDS) else "other"
        for heading in headings
    ]


async def _classify_headings(headings: list[str]) -> list[str]:
    """Classify each heading into an architecture category, or "other".

    Each question embeds its own heading text directly in `instructions`
    rather than referencing a shared `headings` list by index: batching many
    structurally identical questions over an indexed array risks the model
    binding an answer to the wrong index (observed empirically — two adjacent
    headings' classifications shifted by one position when done that way).
    """
    if judgment.Choice is None:
        return _classify_headings_fallback(headings)

    result = await judgment.system_one_async(
        state={},
        questions={
            f"h{i}": judgment.Choice(
                instructions=f'Which architecture-document category does the heading "{heading}" belong to?',
                criteria=_ARCH_CATEGORIES,
            )
            for i, heading in enumerate(headings)
        },
    )
    if result is not None:
        return [result.choices[f"h{i}"].choice for i in range(len(headings))]

    return _classify_headings_fallback(headings)


async def _extract_sections(text: str) -> dict:
    """Pull architecturally-relevant sections from markdown text, keyed by heading."""
    preamble, blocks = _split_by_heading(text)
    sections: dict[str, str] = {}
    if preamble:
        sections["preamble"] = preamble

    if blocks:
        headings = [heading for heading, _ in blocks]
        categories = await _classify_headings(headings)
        for (heading, body), category in zip(blocks, categories):
            if category != "other":
                sections[heading.lower()] = body

    return sections


def register_arch_ingest_tool(mcp: FastMCP) -> None:

    @mcp.tool()
    async def ingest_architecture_doc(
        doc_path: str = "",
        save_summary: bool = True,
    ) -> str:
        """
        Ingest an architecture document and extract key decisions for the EPAV workflow.

        Reads a markdown architecture doc (or scans docs/arch-docs/ if no path given),
        extracts stack decisions, data model, auth strategy, error format, security rules,
        and ADR list. Optionally writes a summary to knowledge/rules/arch-summary.md.

        Args:
            doc_path: Path to the architecture doc (.md) or a directory containing
                      arch docs. If empty, looks for docs/arch-docs/ in the project root.
            save_summary: If True, writes extracted summary to
                          knowledge/rules/arch-summary.md (creates dirs if needed).

        Returns:
            JSON with extracted architecture sections and file paths written.
        """
        try:
            # Resolve the source path
            source = Path(doc_path) if doc_path else Path("docs/arch-docs")

            if not source.exists():
                return json.dumps({
                    "error": f"Path not found: {source}. "
                             "Provide doc_path or create docs/arch-docs/ with your architecture doc."
                })

            # Collect markdown files
            if source.is_file():
                md_files = [source]
            else:
                md_files = sorted(source.rglob("*.md")) + sorted(source.rglob("*.txt"))

            if not md_files:
                return json.dumps({"error": f"No markdown files found in {source}"})

            # Extract sections from all files
            all_sections: dict[str, str] = {}
            files_read = []
            for f in md_files:
                try:
                    text = f.read_text(encoding="utf-8")
                    sections = await _extract_sections(text)
                    all_sections.update(sections)
                    files_read.append(str(f))
                except Exception as e:
                    logger.warning("Could not read %s: %s", f, e)

            if not all_sections:
                return json.dumps({
                    "error": "No recognisable architecture sections found. "
                             "Check that headings use standard terms (stack, auth, data model, etc.)."
                })

            files_written = []
            if save_summary:
                summary_path = Path("knowledge/rules/arch-summary.md")
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                lines = ["# Architecture Summary\n", "_Auto-generated by ingest_architecture_doc_\n"]
                for section, content in all_sections.items():
                    lines.append(f"\n## {section.title()}\n\n{content}\n")
                summary_path.write_text("\n".join(lines), encoding="utf-8")
                files_written.append(str(summary_path))

            return json.dumps({
                "files_read": files_read,
                "files_written": files_written,
                "sections_extracted": list(all_sections.keys()),
                "summary": {k: v[:300] + "…" if len(v) > 300 else v
                            for k, v in all_sections.items()},
            }, indent=2)

        except Exception as e:
            logger.exception("Unexpected error in ingest_architecture_doc")
            return json.dumps({"error": f"Unexpected error: {e}"})
