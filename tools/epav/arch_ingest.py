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


_BODY_SNIPPET_LEN = 500


def _classify_headings_fallback(blocks: list[tuple[str, str]]) -> list[str]:
    return [
        "relevant" if any(k in (heading + " " + body).lower() for k in _ARCH_KEYWORDS) else "other"
        for heading, body in blocks
    ]


async def _classify_headings(blocks: list[tuple[str, str]]) -> list[str]:
    """Classify each section into an architecture category, or "other".

    Classifying on heading text alone fails for a generic top-level heading
    like "Architecture" or "Overview" whose title carries no signal even
    though its body clearly does (observed empirically: a heading titled
    just "Architecture" containing real Terraform/Helm/Ansible content
    scored 0.80 confidence for "other" on title alone, and 0.83 for the
    correct category once a body snippet was included) — so each question
    gets a snippet of the section's actual content, not just its heading.

    Each question embeds its own heading+snippet directly in `instructions`
    rather than referencing a shared list by index: batching many
    structurally identical questions over an indexed array risks the model
    binding an answer to the wrong index (observed empirically — two adjacent
    headings' classifications shifted by one position when done that way).
    """
    if judgment.Choice is None:
        return _classify_headings_fallback(blocks)

    result = await judgment.system_one_async(
        state={},
        questions={
            f"h{i}": judgment.Choice(
                instructions=(
                    f'Which architecture-document category does this document section belong to? '
                    f'Heading: "{heading}". Content: """{body[:_BODY_SNIPPET_LEN]}"""'
                ),
                criteria=_ARCH_CATEGORIES,
            )
            for i, (heading, body) in enumerate(blocks)
        },
    )
    if result is not None:
        return [result.choices[f"h{i}"].choice for i in range(len(blocks))]

    return _classify_headings_fallback(blocks)


async def _extract_sections(text: str) -> dict:
    """Pull architecturally-relevant sections from markdown text, keyed by heading."""
    preamble, blocks = _split_by_heading(text)
    sections: dict[str, str] = {}
    if preamble:
        sections["preamble"] = preamble

    if blocks:
        categories = await _classify_headings(blocks)
        for (heading, body), category in zip(blocks, categories):
            if category != "other":
                sections[heading.lower()] = body

    return sections


_PROJECT_SHAPES = {
    "web_app": "A web application with a user-facing UI (frontend + backend)",
    "mobile_app": "A mobile application with a user-facing UI (Flutter, React Native, native)",
    "backend_api": "A backend/API service with no user-facing UI of its own",
    "infrastructure": "Infrastructure-as-code: provisioning cloud resources, networking, clusters, or platform config, not application code",
    "data_pipeline": "A data pipeline, ETL job, or analytics workflow",
    "cli_or_library": "A command-line tool, SDK, or library with no server or UI",
}

# Keyword fallback, used only when TypeSafe is unavailable. Deliberately
# defaults to "web_app" on no match -- that's the shape /scaffold has always
# assumed, so a missing judgment call degrades to today's existing behavior
# rather than silently switching everyone's default.
_PROJECT_SHAPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("infrastructure", ["terraform", ".tf files", "ansible", "helm chart", "kubernetes manifest", "cloudformation", "pulumi", "provisioning"]),
    ("data_pipeline", ["etl", "airflow", "data pipeline", "spark", "data warehouse"]),
    ("cli_or_library", ["cli tool", "command-line", "command line tool", "sdk", "library with no server"]),
    ("mobile_app", ["flutter", "react native", "ios app", "android app"]),
]


def _classify_project_shape_fallback(text: str) -> str:
    text_lower = text.lower()
    for shape, keywords in _PROJECT_SHAPE_KEYWORDS:
        if any(k in text_lower for k in keywords):
            return shape
    return "web_app"


async def _classify_project_shape(text: str) -> str:
    """What kind of project is this overall -- so /scaffold can skip the
    Figma/UI-shell/mock-auth steps for a project that has no UI at all."""
    if judgment.Choice is None:
        return _classify_project_shape_fallback(text)

    result = await judgment.system_one_async(
        state={"architecture_document": text},
        questions={
            "shape": judgment.Choice(
                instructions="What is the overall shape of the project described in `architecture_document`?",
                criteria=_PROJECT_SHAPES,
            )
        },
    )
    if result is not None:
        return result.choices["shape"].choice

    return _classify_project_shape_fallback(text)


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
        and ADR list. Also classifies the overall project_shape (web_app, mobile_app,
        backend_api, infrastructure, data_pipeline, cli_or_library) so /scaffold can
        skip UI-specific steps (Figma, UI shell, mock auth) for non-UI projects.
        Optionally writes a summary to knowledge/rules/arch-summary.md.

        Args:
            doc_path: Path to the architecture doc (.md) or a directory containing
                      arch docs. If empty, looks for docs/arch-docs/ in the project root.
            save_summary: If True, writes extracted summary to
                          knowledge/rules/arch-summary.md (creates dirs if needed).

        Returns:
            JSON with extracted architecture sections, project_shape, and file paths written.
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
            all_text_parts: list[str] = []
            files_read = []
            for f in md_files:
                try:
                    text = f.read_text(encoding="utf-8")
                    sections = await _extract_sections(text)
                    all_sections.update(sections)
                    all_text_parts.append(text)
                    files_read.append(str(f))
                except Exception as e:
                    logger.warning("Could not read %s: %s", f, e)

            if not all_sections:
                return json.dumps({
                    "error": "No recognisable architecture sections found. "
                             "Check that headings use standard terms (stack, auth, data model, etc.)."
                })

            project_shape = await _classify_project_shape("\n\n".join(all_text_parts))

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
                "project_shape": project_shape,
                "sections_extracted": list(all_sections.keys()),
                "summary": {k: v[:300] + "…" if len(v) > 300 else v
                            for k, v in all_sections.items()},
            }, indent=2)

        except Exception as e:
            logger.exception("Unexpected error in ingest_architecture_doc")
            return json.dumps({"error": f"Unexpected error: {e}"})
