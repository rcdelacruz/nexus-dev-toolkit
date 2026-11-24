import json
import logging
import re
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


_PRIORITY_RANK = {"highest": 0, "critical": 0, "blocker": 0, "high": 1, "medium": 2, "normal": 2, "low": 3, "lowest": 4}
_NO_DEPS = {"", "none", "n/a", "-", "—"}


def _task_files(module: str) -> list[Path]:
    root = Path("docs/dev-tasks") / module if module else Path("docs/dev-tasks")
    return sorted(c for c in root.rglob("*.csv") if "graphify-out" not in c.parts) if root.is_dir() else []


def _is_epic(row: dict) -> bool:
    return row.get("issue_type", "").strip().lower() == "epic" or row.get("task_id", "").upper().startswith("EPIC-")


def board(module: str = "", task_id: str = "") -> dict:
    """Every task in docs/dev-tasks/[<module>/]: which are ready (To Do, every dependency Done),
    which wait on what, which are in progress. A dependency is a task ID (any file of the module —
    IDs are unique) or EPIC-<NAME>, done when every task linked to that epic is Done."""
    rows = []
    for f in _task_files(module):
        try:
            tf = task_format.read_tasks(f)
        except Exception:
            continue
        rows += [dict(r, _file=str(f), _order=i) for i, r in enumerate(tf.rows) if r.get("task_id")]
    status = {r["task_id"].upper(): r.get("status", "").strip() for r in rows}
    epic_members: dict[str, list[str]] = {}
    for r in rows:
        if r.get("epic_link") and not _is_epic(r):
            epic_members.setdefault(r["epic_link"].strip().upper(), []).append(r["task_id"].upper())

    def dep_status(dep: str) -> str:
        d = dep.strip().upper()
        if d in epic_members:
            return "Done" if all(status.get(m, "").lower() == "done" for m in epic_members[d]) else "not done"
        return status.get(d, "unknown ID")

    def deps(r: dict) -> list[dict]:
        out = []
        for d in re.split(r"[,;\n]", r.get("dependencies", "")):
            if d.strip().lower() in _NO_DEPS:
                continue
            out.append({"id": d.strip(), "status": dep_status(d)})
        return out

    ready, waiting, in_progress = [], [], []
    for r in rows:
        if _is_epic(r):
            continue
        s = r.get("status", "").strip().lower()
        item = {"task_id": r["task_id"], "summary": r.get("summary", ""), "priority": r.get("priority", ""),
                "status": r.get("status", ""), "assignee": r.get("assignee", ""), "file": r["_file"]}
        open_deps = [d for d in deps(r) if d["status"].lower() != "done"]
        if s == "in progress":
            in_progress.append(item)
        elif s in ("to do", "todo", "") and not open_deps:
            ready.append((_PRIORITY_RANK.get(r.get("priority", "").strip().lower(), 9), r["_file"], r["_order"], item))
        elif s != "done":
            waiting.append(dict(item, waiting_on=open_deps))
    out = {"status": "ok" if rows else "no_tasks",
           "ready": [x[-1] for x in sorted(ready, key=lambda x: x[:3])],
           "waiting": waiting, "in_progress": in_progress,
           "done": sum(1 for r in rows if not _is_epic(r) and r.get("status", "").strip().lower() == "done"),
           "total": sum(1 for r in rows if not _is_epic(r))}
    if task_id:
        r = next((x for x in rows if x["task_id"].lower() == task_id.strip().lower()), None)
        if r is None:
            out["task"] = {"task_id": task_id, "status": "not_found"}
        else:
            d = deps(r)
            out["task"] = {"task_id": r["task_id"], "status": r.get("status", ""), "assignee": r.get("assignee", ""),
                           "dependencies": d, "ready": all(x["status"].lower() == "done" for x in d), "file": r["_file"]}
    return out


def register_task_loader_tool(mcp: FastMCP) -> None:

    @mcp.tool()
    async def next_task(module: str = "", task_id: str = "") -> str:
        """
        The task board, for /evaluate: which tasks are ready to start (STATUS To Do and every
        dependency Done), in priority order; which wait on unfinished dependencies (and on what);
        which are In Progress and by whom. With task_id, also that task's own dependencies and
        whether it can start.

        Args:
            module: limit to docs/dev-tasks/<module>/ (e.g. "careslot"); empty = every module.
            task_id: a task to check (e.g. "BOOK-004").

        Returns:
            JSON: status (ok | no_tasks), ready[], waiting[] (with waiting_on), in_progress[],
            done, total, and task{} when task_id is given.
        """
        try:
            return json.dumps(board(module, task_id), indent=2)
        except Exception as e:
            logger.exception("Unexpected error in next_task")
            return json.dumps({"status": "error", "error": f"Unexpected error: {e}"})

    @mcp.tool()
    async def set_task_status(task_id: str, status: str, assignee: str = "") -> str:
        """
        Set one task's STATUS (and optionally ASSIGNEE) in its task file. Only that row's line
        changes — the rest of the file stays byte-for-byte as it was. It never commits: the change
        goes into the task's branch with the code, so main shows it when the pull request merges.

        Args:
            task_id: e.g. "BOOK-004" (looked up across docs/dev-tasks/; IDs are unique).
            status: one of To Do, In Progress, Blocked, Done.
            assignee: optional — e.g. the developer's git user.name.

        Returns:
            JSON: status (updated | unchanged | not_found | ambiguous | invalid_status | error),
            file, old and new values.
        """
        try:
            want = next((s for s in task_format.STATUSES if s.lower() == status.strip().lower()), None)
            if not want:
                return json.dumps({"status": "invalid_status", "error": f"status must be one of: {', '.join(task_format.STATUSES)}"})
            having = [f for f in _task_files("") if _has_id(f, task_id)]
            if not having:
                return json.dumps({"status": "not_found", "error": f"task_id {task_id!r} is in no task file under docs/dev-tasks/"})
            if len(having) > 1:
                return json.dumps({"status": "ambiguous", "error": f"task_id {task_id!r} is in {len(having)} files",
                                   "candidates": [str(f) for f in having]})
            values = {"status": want}
            if assignee.strip():
                values["assignee"] = assignee.strip()
            current = task_format.read_tasks(having[0]).find(task_id) or {}
            if all(current.get(k, "") == v for k, v in values.items()):
                return json.dumps({"status": "unchanged", "file": str(having[0]), "values": values})
            old = task_format.set_cells(having[0], task_id, values)
            return json.dumps({"status": "updated", "file": str(having[0]), "old": old, "new": values}, indent=2)
        except ValueError as e:
            return json.dumps({"status": "error", "error": str(e)})
        except Exception as e:
            logger.exception("Unexpected error in set_task_status")
            return json.dumps({"status": "error", "error": f"Unexpected error: {e}"})

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
