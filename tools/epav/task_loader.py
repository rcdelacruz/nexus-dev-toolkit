import csv
import json
import logging
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

_TASK_FIELDS = ["task_id", "user_story", "description", "acceptance_criteria", "dependencies"]


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


def _run_graphify_query(description: str) -> str | None:
    """Run graphify query if a graph exists. Returns output or None."""
    if not Path("graphify-out/graph.json").exists():
        return None
    try:
        result = subprocess.run(
            ["graphify", "query", description[:200]],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception as e:
        logger.warning("graphify query failed: %s", e)
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

        Reads a task CSV (one row per task with fields: task_id, user_story,
        description, acceptance_criteria, dependencies). Optionally runs a
        graphify query on the task description to surface blast radius context.

        Args:
            csv_path: Path to the CSV file, or a name fragment to search in
                      docs/dev-tasks/. If empty, uses the first CSV found there.
            task_id:  Match a specific task_id value in the CSV. Takes priority
                      over row_index.
            row_index: Zero-based row index to load if task_id is not provided.

        Returns:
            JSON with structured task context ready for /evaluate, including
            graphify blast radius if a graph exists.
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

            if not rows:
                return json.dumps({"error": f"CSV is empty: {csv_file}"})

            # Find the target row
            task: dict | None = None
            if task_id:
                task = next(
                    (r for r in rows if r.get("task_id", "").strip() == task_id.strip()),
                    None,
                )
                if not task:
                    return json.dumps({
                        "error": f"task_id '{task_id}' not found in {csv_file}",
                        "available_ids": [r.get("task_id", "") for r in rows[:20]],
                    })
            else:
                if row_index >= len(rows):
                    return json.dumps({
                        "error": f"row_index {row_index} out of range (CSV has {len(rows)} rows)"
                    })
                task = rows[row_index]

            # Extract standard EPAV fields (graceful if columns differ)
            context = {f: task.get(f, "").strip() for f in _TASK_FIELDS}
            context["_csv_file"] = str(csv_file)
            context["_all_fields"] = dict(task)

            # Graphify blast radius
            description = context.get("description") or context.get("user_story", "")
            blast_radius = _run_graphify_query(description)
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
