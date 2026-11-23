"""
Change requests and traceability — the deterministic half of /change-request and
/dev-tasks-planner's CR mode.

Git is the change log: a change request is a commit/PR that touches docs/. This module reads the
diff of docs/requirements, docs/arch-docs and docs/designs, works out which IDs were changed,
added or removed, writes the CR record (formats.cr), and lists exactly which dev-task rows trace
to those IDs — so re-planning touches those rows and nothing else.
"""

import json
import logging
import re
import subprocess
from datetime import date
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from tools.epav.formats import cr as cr_format
from tools.epav.formats import guides, tasks
from tools.epav.formats.ids import extract_ids, format_id_list, kind_of

logger = logging.getLogger(__name__)

DOC_DIRS = ["docs/requirements", "docs/arch-docs", "docs/designs"]
CR_DIR = Path("docs/change-requests")
_CR_ID = re.compile(r"^CR-\d+$")


class GitError(Exception):
    pass


def _git(args: list[str]) -> str:
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise GitError("git is not installed")
    except subprocess.TimeoutExpired:
        raise GitError(f"git {' '.join(args)} timed out")
    if r.returncode != 0:
        raise GitError((r.stderr or r.stdout).strip()[:500])
    return r.stdout


_LEAD = re.compile(r"^[\s|>*#+\-`]*(?:\*\*)?")


def _subject(line: str, patterns: dict | None) -> str | None:
    """The ID a line is about: the ID it starts with (a table row, bullet, heading or AC line).
    IDs further along a line are references ("serves BR-005", a release-scope list)."""
    rest = line[_LEAD.match(line).end():]
    found = extract_ids(rest[:40], patterns)
    return found[0] if found and rest.find(found[0]) <= 3 else None


def _heading_ids(text: str, patterns: dict | None) -> list[str | None]:
    """For every line (1-based index), the ID of the nearest heading above it that has one."""
    current, out = None, [None]
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            subj = _subject(line, patterns)
            if subj:
                current = subj                         # "### US-005 — Cancel" → lines below belong to US-005
            elif stripped.startswith(("# ", "## ")):
                current = None                         # a new top-level section without an ID
        out.append(current)
    return out


def _diff_path(raw: str) -> str | None:
    """Path from a '+++ b/…' / '--- a/…' line. Git appends a tab to paths with spaces and
    C-quotes unusual ones ("b/caf\\303\\251.md")."""
    raw = raw.rstrip("\t\r\n")
    if raw == "/dev/null":
        return None
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1].encode("latin-1", "backslashreplace").decode("unicode_escape").encode("latin-1").decode("utf-8", "replace")
    return raw[2:] if raw[:2] in ("a/", "b/") else raw


def _file_at(base: str, path: str) -> str:
    try:
        return _git(["show", f"{base}:{path}"])
    except GitError:
        return ""


def diff_ids(base: str, patterns: dict | None = None, include_untracked: bool = True) -> dict:
    """Requirement IDs changed in docs/ since `base` (working tree included).

    Each changed line is classified by what it is ABOUT: the ID it starts with, or else the ID of
    the heading it sits under (a new AC bullet under "### US-005" changes US-005). IDs merely
    mentioned further along a line are references and don't count.
      changed = about an ID on both sides, or an ID that existed before
      added   = about an ID that's new to the docs
      removed = about an ID that's gone from the docs
    Design-screen, ADR and epic IDs touched are reported separately as "other".
    """
    dirs = [d for d in DOC_DIRS if Path(d).exists()]
    if not dirs:
        return {"files": [], "changed": [], "added": [], "removed": [], "other": []}
    diff = _git(["diff", "-U0", "--no-color", base, "--", *dirs])
    plus_ids, minus_ids, parents, files, other = set(), set(), set(), [], set()
    cur_new = cur_old = None
    new_heads = old_heads = []
    new_no = old_no = 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            cur_new = _diff_path(line[4:])
            if cur_new:
                files.append(cur_new)
                p = Path(cur_new)
                new_heads = _heading_ids(p.read_text(encoding="utf-8", errors="replace"), patterns) if p.is_file() else []
        elif line.startswith("--- "):
            cur_old = _diff_path(line[4:])
            old_heads = _heading_ids(_file_at(base, cur_old), patterns) if cur_old else []
        elif line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", line)
            old_no, new_no = int(m.group(1)), int(m.group(2))
        elif line.startswith("+"):
            other |= {i for i in extract_ids(line, patterns) if kind_of(i, patterns) in ("adr", "design", "epic")}
            head = new_heads[new_no] if new_no < len(new_heads) else None
            subj = _subject(line[1:], patterns) or head
            if subj:
                plus_ids.add(subj)
            if head and head != subj:
                parents.add(head)          # an AC added under "### US-005" changes US-005 too
            new_no += 1
        elif line.startswith("-"):
            other |= {i for i in extract_ids(line, patterns) if kind_of(i, patterns) in ("adr", "design", "epic")}
            head = old_heads[old_no] if old_no < len(old_heads) else None
            subj = _subject(line[1:], patterns) or head
            if subj:
                minus_ids.add(subj)
            if head and head != subj:
                parents.add(head)
            old_no += 1
    if include_untracked:
        for f in _git(["ls-files", "--others", "--exclude-standard", "--", *dirs]).split():
            p = Path(f)
            if p.suffix.lower() in (".md", ".txt", ".html", ".csv") and p.stat().st_size < 5_000_000:
                files.append(f)
                for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    if (s := _subject(l, patterns)):
                        plus_ids.add(s)
    current = set()
    for d in dirs:
        for p in Path(d).rglob("*"):
            if p.is_file() and p.suffix.lower() in (".md", ".txt", ".json", ".html") and p.stat().st_size < 5_000_000:
                current |= set(extract_ids(p.read_text(encoding="utf-8", errors="replace"), patterns))
    changed = (plus_ids & minus_ids) | {i for i in plus_ids - minus_ids if _seen_before(i, base, dirs)} \
        | {i for i in minus_ids - plus_ids if i in current} \
        | {i for i in parents if i in current and (i in minus_ids or _seen_before(i, base, dirs))}  # a new heading is added, not changed
    added = {i for i in plus_ids - minus_ids if i not in changed}
    removed = {i for i in minus_ids - plus_ids if i not in current}
    req = lambda ids: sorted(i for i in ids if kind_of(i, patterns) not in ("adr", "design", "change", "epic"))  # noqa: E731
    other |= {i for i in plus_ids | minus_ids | parents if kind_of(i, patterns) in ("adr", "design", "epic")}
    return {"files": sorted(set(files)), "changed": req(changed), "added": req(added), "removed": req(removed),
            "other": sorted(other)}


def _seen_before(ident: str, base: str, dirs: list[str]) -> bool:
    try:
        return bool(_git(["grep", "-l", "-F", ident, base, "--", *dirs]).strip())
    except GitError:
        return False


def task_files() -> list[Path]:
    root = Path("docs/dev-tasks")
    return sorted(p for p in root.rglob("*.csv") if "graphify-out" not in p.parts) if root.is_dir() else []


def affected(cr: cr_format.ChangeRequest, patterns: dict | None = None) -> list[dict]:
    out = []
    for f in task_files():
        tf = tasks.read_tasks(f)
        for row in cr_format.affected_rows(tf.rows, cr, patterns):
            hit = sorted(set(cr.touched_ids) & set(extract_ids(" ".join(row.values()), patterns)))
            out.append({"file": str(f), "task_id": row.get("task_id", ""), "summary": row.get("summary", ""),
                        "status": row.get("status", ""), "ids": hit})
    return out


def propose_trace_ids(path: Path, patterns: dict | None = None) -> list[dict]:
    """For each row: the IDs its text already cites (requirements, design screens, ADRs)."""
    tf = tasks.read_tasks(path)
    out = []
    for r in tf.rows:
        text = " ".join(v for k, v in r.items() if k != "trace_ids")
        found = [i for i in extract_ids(text, patterns) if kind_of(i, patterns) not in ("change", "epic")]
        current = extract_ids(r.get("trace_ids", ""), patterns)
        merged = list(dict.fromkeys(current + found))
        out.append({"task_id": r.get("task_id", ""), "current": current, "proposed": merged,
                    "changed": merged != current})
    return out


def _patterns() -> dict:
    return guides.load_guide(Path("docs/requirements/REQUIREMENTS-GUIDE.md"), "requirements").id_patterns


def register_change_request_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def record_change_request(
        cr_id: str,
        title: str,
        base: str = "HEAD",
        reason: str = "",
        write: bool = False,
    ) -> str:
        """
        Work out what a change request changed in docs/ and which dev tasks it affects.

        Reads the git diff of docs/requirements, docs/arch-docs and docs/designs since `base`
        (uncommitted edits and new files included), extracts the requirement IDs that were
        changed / added / removed (the project's own ID scheme), and lists every dev-task row
        that traces to them. With write=True, writes docs/change-requests/<cr_id>.json.

        Args:
            cr_id: e.g. "CR-004".
            title: one line.
            base: git revision the change request starts from (default HEAD = only uncommitted edits;
                  use the branch point, e.g. "main", when the edits are already committed).
            reason: why the change was requested.
            write: write the record (do it after the user approves).

        Returns:
            JSON with "status": ok | no_changes | invalid | git_error | error, the record, the
            affected task rows (file, task_id, summary, status, ids), files written.
        """
        try:
            if not _CR_ID.match(cr_id):
                return json.dumps({"status": "invalid", "error": f"cr_id must look like CR-004, got {cr_id!r}"})
            patterns = _patterns()
            d = diff_ids(base, patterns)
            record = cr_format.ChangeRequest(cr_id, title, date.today().isoformat(), changed_ids=d["changed"],
                                             added_ids=d["added"], removed_ids=d["removed"], files=d["files"], reason=reason)
            rows = affected(record, patterns)
            status = "ok" if record.touched_ids else "no_changes"
            written = []
            if write and status == "ok":
                path = CR_DIR / f"{cr_id}.json"
                cr_format.write_cr(path, record)
                written.append(str(path))
            return json.dumps({"status": status, "record": json.loads(record.to_json()),
                               "other_ids_touched": d["other"], "affected_tasks": rows,
                               "files_written": written,
                               **({"hint": f"No requirement IDs changed in docs/ since {base}."} if status == "no_changes" else {})},
                              indent=2)
        except GitError as e:
            return json.dumps({"status": "git_error", "error": str(e)})
        except Exception as e:
            logger.exception("record_change_request failed")
            return json.dumps({"status": "error", "error": f"Unexpected error: {e}"})

    @mcp.tool()
    async def trace_tasks(csv_path: str = "", cr_id: str = "", write: bool = False) -> str:
        """
        Traceability for dev tasks.

        Without cr_id: for each row of a task file, the requirement/design/ADR IDs its text already
        cites, proposed for the TRACE_IDS column (write=True fills them in, keeping existing ones).
        With cr_id: the rows across docs/dev-tasks/ that trace to that change request's IDs — the
        only rows /dev-tasks-planner should re-plan.

        Returns:
            JSON with "status": ok | not_found | invalid | error and the rows.
        """
        try:
            patterns = _patterns()
            if cr_id:
                p = CR_DIR / f"{cr_id}.json"
                if not p.is_file():
                    return json.dumps({"status": "not_found", "error": f"{p} not found — run record_change_request first"})
                record = cr_format.read_cr(p)
                return json.dumps({"status": "ok", "cr": cr_id, "touched_ids": record.touched_ids,
                                   "affected_tasks": affected(record, patterns)}, indent=2)
            if not csv_path or not Path(csv_path).is_file():
                return json.dumps({"status": "not_found", "error": f"task file not found: {csv_path!r}"})
            tf = tasks.read_tasks(Path(csv_path))
            if tf.missing_required:
                return json.dumps({"status": "invalid", "error": f"missing columns: {tf.missing_required}"})
            proposal = propose_trace_ids(Path(csv_path), patterns)
            written = []
            if write:
                by_id = {p["task_id"]: p["proposed"] for p in proposal}
                for r in tf.rows:
                    r["trace_ids"] = format_id_list(by_id.get(r.get("task_id", ""), []))
                tasks.write_tasks(Path(csv_path), tf.rows, tf.extra_columns)
                written.append(csv_path)
            return json.dumps({"status": "ok", "rows": proposal,
                               "rows_with_ids": sum(1 for p in proposal if p["proposed"]),
                               "files_written": written}, indent=2)
        except Exception as e:
            logger.exception("trace_tasks failed")
            return json.dumps({"status": "error", "error": f"Unexpected error: {e}"})
