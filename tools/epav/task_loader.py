import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from tools.epav import graph_backend
from tools.epav.formats import tasks as task_format
from tools.epav.formats.ids import extract_ids

logger = logging.getLogger(__name__)

_TASK_FIELDS = ["task_id", "user_story", "description", "acceptance_criteria", "dependencies"]


def _find_csv(hint: str) -> tuple[Path | None, list[Path]]:
    """Locate a task file from a path or a name/path fragment under docs/dev-tasks/.

    Returns (file, candidates). When the hint matches more than one file — e.g.
    "authentication" in a project with authentication-tasks.csv in four modules — the file is
    None and every candidate is returned, so the caller asks instead of silently picking one.
    """
    p = Path(hint)
    if hint and p.is_file() and p.suffix.lower() == ".csv":
        return p, [p]
    dev_tasks = Path("docs/dev-tasks")
    if not dev_tasks.is_dir():
        return None, []
    candidates = sorted(c for c in dev_tasks.rglob("*.csv") if "graphify-out" not in c.parts)
    if not hint:
        return (candidates[0] if len(candidates) == 1 else None), candidates
    h = hint.lower().replace("\\", "/")
    by_path = [c for c in candidates if h in c.as_posix().lower()]
    exact_name = [c for c in by_path if c.stem.lower() in (h, f"{h}-tasks") or c.name.lower() == h]
    if len(exact_name) == 1:
        return exact_name[0], exact_name
    if len(by_path) == 1:
        return by_path[0], by_path
    return None, by_path or candidates


def _has_id(path: Path, task_id: str) -> bool:
    try:
        return task_format.read_tasks(path).find(task_id) is not None
    except Exception:
        return False


def register_task_loader_tool(mcp: FastMCP) -> None:

    @mcp.tool()
    async def load_task(
        csv_path: str = "",
        task_id: str = "",
        row_index: int = 0,
    ) -> str:
        """
        Load a dev task from a task file and structure it for the EVALUATE step.

        Reads task files in any header style (TASK_ID / Task ID / task_id, Excel BOM).
        Optionally runs a knowledge-graph query (graphify or codegraph, whichever is
        active) on the task description to surface blast radius context.

        Args:
            csv_path: Path to the CSV, or a name/path fragment under docs/dev-tasks/
                      (e.g. "authentication" or "core/authentication"). If several files
                      match, nothing is guessed: status "ambiguous" lists them. With only a
                      task_id, the one file that has that ID is used.
            task_id:  Match a task_id (case-insensitive). Takes priority over row_index.
            row_index: Zero-based row index to load if task_id is not provided.

        Returns:
            JSON with "status": found | empty_fields | not_found | ambiguous | no_file |
            invalid_file | out_of_range | error. found/empty_fields include the task context
            (task_id, user_story, description, acceptance_criteria, dependencies, trace_ids)
            and an evaluate_block; empty_fields lists the required fields that are blank.
        """
        try:
            csv_file, candidates = _find_csv(csv_path)
            if not csv_file and task_id and candidates:
                # `/evaluate BOOK-004` names no file: use the one file that has that ID
                having = [c for c in candidates if _has_id(c, task_id)]
                if len(having) == 1:
                    csv_file = having[0]
                elif having:
                    return json.dumps({
                        "status": "ambiguous",
                        "error": f"task_id {task_id!r} is in {len(having)} task files — pass one of these as csv_path "
                                 "(task IDs should be unique across a module's files)",
                        "candidates": [str(c) for c in having[:50]],
                    }, indent=2)
                else:
                    return json.dumps({
                        "status": "not_found",
                        "error": f"task_id '{task_id}' is in none of the {len(candidates)} task files",
                        "candidates": [str(c) for c in candidates[:50]],
                    }, indent=2)
            if not csv_file:
                if candidates:
                    return json.dumps({
                        "status": "ambiguous",
                        "error": f"{len(candidates)} task files match {csv_path!r} — pass one of these as csv_path",
                        "candidates": [str(c) for c in candidates[:50]],
                    }, indent=2)
                return json.dumps({
                    "status": "no_file",
                    "error": "No task file found. Provide csv_path or create docs/dev-tasks/<module>/<epic>-tasks.csv.",
                })

            tf = task_format.read_tasks(csv_file)
            if tf.missing_required:
                return json.dumps({
                    "status": "invalid_file",
                    "error": f"{csv_file} has no column for: {', '.join(tf.missing_required)}",
                    "headers_found": list(tf.header_map.values()) + tf.extra_columns,
                }, indent=2)
            if not tf.rows:
                return json.dumps({"status": "invalid_file", "error": f"task file has no rows: {csv_file}"})

            if task_id:
                task = tf.find(task_id)
                if not task:
                    return json.dumps({
                        "status": "not_found",
                        "error": f"task_id '{task_id}' not found in {csv_file}",
                        "available_ids": tf.ids[:50],
                    }, indent=2)
            else:
                if not 0 <= row_index < len(tf.rows):
                    return json.dumps({
                        "status": "out_of_range",
                        "error": f"row_index {row_index} out of range ({csv_file} has {len(tf.rows)} rows)",
                    })
                task = tf.rows[row_index]

            context = {f: task.get(f, "") for f in _TASK_FIELDS}
            trace = extract_ids(task.get("trace_ids", "")) or extract_ids(
                " ".join(task.get(f, "") for f in ("summary", "user_story", "description", "acceptance_criteria")))
            context["trace_ids"] = trace
            blank = task_format.empty_required(task)
            context["status"] = "empty_fields" if blank else "found"
            if blank:
                context["empty_fields"] = blank
                context["warning"] = (f"Required fields are blank in {csv_file}: {', '.join(blank)}. "
                                      "Do not invent them — ask the user or fix the task file.")
            context["_csv_file"] = str(csv_file)
            context["_all_fields"] = dict(task)

            description = context.get("description") or context.get("user_story", "")
            blast_radius = graph_backend.run_query(description[:200]) if description else None
            if blast_radius:
                context["blast_radius"] = blast_radius

            evaluate_block = [
                "TASK CONTEXT (ready for /evaluate)",
                "─" * 40,
                f"Task ID:     {context['task_id'] or '(blank)'}",
                f"User story:  {context['user_story'] or '(blank)'}",
                f"Traces to:   {', '.join(trace) if trace else '(none found)'}",
                "",
                f"Description:\n{context['description'] or '(blank)'}",
                "",
                f"Acceptance criteria:\n{context['acceptance_criteria'] or '(blank)'}",
                "",
                f"Dependencies: {context['dependencies'] or 'none'}",
            ]
            if blank:
                evaluate_block += ["", f"WARNING: blank required fields: {', '.join(blank)}"]
            if blast_radius:
                evaluate_block += ["", "Graphify blast radius:", blast_radius[:800]]
            context["evaluate_block"] = "\n".join(evaluate_block)

            return json.dumps(context, indent=2)

        except Exception as e:
            logger.exception("Unexpected error in load_task")
            return json.dumps({"status": "error", "error": f"Unexpected error: {e}"})
