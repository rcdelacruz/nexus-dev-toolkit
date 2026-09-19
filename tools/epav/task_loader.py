import csv
import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from tools.epav import graph_backend, judgment

logger = logging.getLogger(__name__)

_TASK_FIELDS = ["task_id", "user_story", "description", "acceptance_criteria", "dependencies"]

_TASK_FIELD_CRITERIA = {
    "task_id": "A short unique identifier for this task/ticket (ID, ticket number, key)",
    "user_story": "A user story or one-line summary of the task, often phrased 'As a ... I want ... so that ...'",
    "description": "A longer description of the work to be done",
    "acceptance_criteria": "Acceptance criteria, definition of done, or test conditions",
    "dependencies": "Other tasks or tickets this one depends on or blocks",
    "other": "Doesn't map to any of the standard task fields (e.g. status, assignee, priority, sprint, labels)",
}

# Keyword fallback, used only when TypeSafe is unavailable.
_TASK_FIELD_KEYWORDS: dict[str, list[str]] = {
    "task_id": ["id", "ticket", "key"],
    "user_story": ["story", "summary", "title"],
    "description": ["description", "detail", "requirement"],
    "acceptance_criteria": ["acceptance", "criteria", " ac", "ac ", "definition of done", "dod"],
    "dependencies": ["depend", "block"],
}


def _normalize_header(h: str) -> str:
    return h.strip().lower().replace(" ", "_").replace("-", "_")


def _map_csv_headers_fallback(headers: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used_fields: set[str] = set()
    for header in headers:
        header_lower = f" {header.strip().lower()} "
        for field, keywords in _TASK_FIELD_KEYWORDS.items():
            if field in used_fields:
                continue
            if any(k in header_lower for k in keywords):
                mapping[header] = field
                used_fields.add(field)
                break
    return mapping


async def _map_csv_headers(headers: list[str]) -> dict[str, str]:
    """Map each CSV column header to a canonical EPAV task field.

    Returns {original_header: canonical_field} -- only for headers that map
    to something; headers matching nothing (status, assignee, ...) are
    omitted. Exact-name headers (any casing/spacing) are matched directly,
    without an API call; only genuinely different names go through TypeSafe.

    A CSV exported from Jira/Linear/Notion/etc. rarely uses this project's
    exact literal field names -- confirmed empirically: a CSV with headers
    "Ticket, Story, Requirement, Depends On, AC" produced entirely empty
    fields under a plain `task.get("task_id", ...)`-style lookup, even
    though every field is present under a differently-spelled header.
    """
    normalized_fields = {_normalize_header(f): f for f in _TASK_FIELDS}
    mapping: dict[str, str] = {}
    unmapped: list[str] = []
    for header in headers:
        canonical = normalized_fields.get(_normalize_header(header))
        if canonical:
            mapping[header] = canonical
        else:
            unmapped.append(header)

    if not unmapped:
        return mapping

    if judgment.Choice is None:
        mapping.update(_map_csv_headers_fallback(unmapped))
        return mapping

    result = await judgment.system_one_async(
        state={},
        questions={
            f"h{i}": judgment.Choice(
                instructions=f'Which standard task field does the CSV column header "{header}" correspond to?',
                criteria=_TASK_FIELD_CRITERIA,
            )
            for i, header in enumerate(unmapped)
        },
    )
    if result is not None:
        for i, header in enumerate(unmapped):
            choice = result.choices[f"h{i}"].choice
            if choice != "other":
                mapping[header] = choice
        return mapping

    mapping.update(_map_csv_headers_fallback(unmapped))
    return mapping


def _find_csv(hint: str) -> Path | None:
    """Locate a CSV task file from a path hint or by scanning docs/dev-tasks/."""
    p = Path(hint)
    if p.exists() and p.suffix == ".csv":
        return p
    dev_tasks = Path("docs/dev-tasks")
    if dev_tasks.exists():
        candidates = sorted(dev_tasks.rglob("*.csv"))
        if hint:
            matched = [c for c in candidates if hint.lower() in c.name.lower()]
            if matched:
                return matched[0]
        if candidates:
            return candidates[0]
    return None


def register_task_loader_tool(mcp: FastMCP) -> None:

    @mcp.tool()
    async def load_task(
        csv_path: str = "",
        task_id: str = "",
        row_index: int = 0,
    ) -> str:
        """
        Load a dev task from a CSV file and structure it for the EVALUATE step.

        Reads a task CSV (one row per task) and maps its columns onto the standard
        EPAV fields (task_id, user_story, description, acceptance_criteria,
        dependencies) -- column names don't need to match exactly; a real-world
        export's headers (Ticket/Story/AC/Depends On, etc.) are mapped
        automatically. Optionally runs a knowledge-graph query (graphify or
        codegraph, whichever is active) on the task description to surface
        blast radius context.

        Args:
            csv_path: Path to the CSV file, or a name fragment to search in
                      docs/dev-tasks/. If empty, uses the first CSV found there.
            task_id:  Match a specific task_id value in the CSV. Takes priority
                      over row_index.
            row_index: Zero-based row index to load if task_id is not provided.

        Returns:
            JSON with structured task context ready for /evaluate, including
            knowledge-graph blast radius if a graph exists.
        """
        try:
            csv_file = _find_csv(csv_path)
            if not csv_file:
                return json.dumps({
                    "error": "No CSV task file found. Provide csv_path or create docs/dev-tasks/ "
                             "with your task CSVs."
                })

            rows: list[dict] = []
            with csv_file.open(encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                headers = reader.fieldnames or []

            if not rows:
                return json.dumps({"error": f"CSV is empty: {csv_file}"})

            # Map this CSV's actual headers to the standard EPAV fields --
            # most task exports (Jira/Linear/Notion/etc.) don't use this
            # project's exact field names, so a plain lookup by literal name
            # silently returns nothing even when the data is right there.
            header_map = await _map_csv_headers(headers)
            canonical_to_header = {v: k for k, v in header_map.items()}
            task_id_header = canonical_to_header.get("task_id", "task_id")

            # Find the target row
            task: dict | None = None
            if task_id:
                task = next(
                    (r for r in rows if r.get(task_id_header, "").strip() == task_id.strip()),
                    None,
                )
                if not task:
                    return json.dumps({
                        "error": f"task_id '{task_id}' not found in {csv_file}",
                        "available_ids": [r.get(task_id_header, "") for r in rows[:20]],
                    })
            else:
                if row_index >= len(rows):
                    return json.dumps({
                        "error": f"row_index {row_index} out of range (CSV has {len(rows)} rows)"
                    })
                task = rows[row_index]

            # Extract standard EPAV fields via the header map
            context = {f: task.get(canonical_to_header.get(f, f), "").strip() for f in _TASK_FIELDS}
            context["_csv_file"] = str(csv_file)
            context["_all_fields"] = dict(task)

            # Knowledge-graph blast radius (graphify or codegraph, whichever is active)
            description = context.get("description") or context.get("user_story", "")
            blast_radius = graph_backend.run_query(description[:200])
            if blast_radius:
                context["blast_radius"] = blast_radius

            # Human-readable EVALUATE block
            evaluate_block = [
                "TASK CONTEXT (ready for /evaluate)",
                "─" * 40,
                f"Task ID:     {context.get('task_id', '(none)')}",
                f"User story:  {context.get('user_story', '(none)')}",
                "",
                f"Description:\n{context.get('description', '(none)')}",
                "",
                f"Acceptance criteria:\n{context.get('acceptance_criteria', '(none)')}",
                "",
                f"Dependencies: {context.get('dependencies', 'none')}",
            ]
            if blast_radius:
                evaluate_block += ["", "Graphify blast radius:", blast_radius[:800]]

            context["evaluate_block"] = "\n".join(evaluate_block)

            return json.dumps(context, indent=2)

        except Exception as e:
            logger.exception("Unexpected error in load_task")
            return json.dumps({"error": f"Unexpected error: {e}"})
