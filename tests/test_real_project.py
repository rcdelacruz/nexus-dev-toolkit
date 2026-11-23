"""Opt-in checks against a real nexus project on this machine (rule 3).

    NEXUS_REAL_PROJECT=/path/to/project uv run --extra dev pytest -m real_project -v

Skipped unless NEXUS_REAL_PROJECT is set — never runs in CI. Assertions are generic on
purpose: this repository is public, so no client file names, IDs or content may appear here.
The project is only read; the last test proves nothing in it was modified.
"""

import os
from pathlib import Path

import pytest

from tools.epav import stack_catalog
from tools.epav.formats import tasks
from tools.epav.formats.ids import extract_ids

ROOT = Path(os.environ.get("NEXUS_REAL_PROJECT", "")).expanduser()
pytestmark = [
    pytest.mark.real_project,
    pytest.mark.skipif(not os.environ.get("NEXUS_REAL_PROJECT"), reason="set NEXUS_REAL_PROJECT to run"),
]
_SKIP_DIRS = {"node_modules", ".next", "dist", "build", "graphify-out", ".git"}


def _files(pattern: str) -> list[Path]:
    docs = ROOT / "docs"
    return sorted(p for p in docs.rglob(pattern) if not (_SKIP_DIRS & set(p.relative_to(docs).parts)))


@pytest.fixture(scope="module")
def snapshot():
    return {p: p.stat().st_mtime_ns for p in _files("*") if p.is_file()}


def test_every_task_file_loads(snapshot):
    files = _files("*.csv")
    assert files, "no task files found under docs/"
    problems = []
    for f in files:
        tf = tasks.read_tasks(f)
        if tf.missing_required:
            problems.append(f"{f.relative_to(ROOT)}: no column for {tf.missing_required}")
        elif not tf.rows or not all(r.get("task_id") for r in tf.rows):
            problems.append(f"{f.relative_to(ROOT)}: rows without task_id")
    assert not problems, "\n".join(problems)


def test_tasks_trace_to_requirements(snapshot):
    rows = [r for f in _files("*.csv") for r in tasks.read_tasks(f).rows]
    traced = [r for r in rows if extract_ids(" ".join(r.values()))]
    assert rows and len(traced) / len(rows) > 0.5, f"only {len(traced)} of {len(rows)} rows mention a requirement ID"


def test_architecture_docs_give_a_stack_from_their_choices(snapshot):
    docs = [d for d in _files("ARCH-*.md")]
    with_choices = [d for d in docs if "**Choice**" in d.read_text(errors="ignore") or "| Choice" in d.read_text(errors="ignore")]
    assert with_choices, "no architecture doc records its choices"
    for d in with_choices:
        assert stack_catalog.detect_from_choices(d.read_text(errors="ignore")), f"{d.relative_to(ROOT)}: no stack found"


def test_every_module_ingests_and_requirements_stay_out(snapshot, monkeypatch):
    import asyncio, json
    from mcp.server.fastmcp import FastMCP
    from tools.epav import arch_ingest
    monkeypatch.chdir(ROOT)
    m = FastMCP("t")
    arch_ingest.register_arch_ingest_tool(m)
    fn = m._tool_manager._tools["ingest_architecture_doc"].fn
    modules = [d.name for d in (ROOT / "docs" / "arch-docs").iterdir() if d.is_dir() and d.name not in _SKIP_DIRS]
    assert modules
    for mod in modules:
        r = json.loads(asyncio.run(fn(module=mod, save_summary=False)))
        assert r["status"] in ("ok", "partial"), (mod, r.get("error"))
        assert not [f for f in r["files_read"] if arch_ingest.classify(Path(f)) == "requirements"], mod


def test_every_design_export_imports_within_limits(snapshot, monkeypatch):
    import asyncio, json
    from mcp.server.fastmcp import FastMCP
    from tools.epav import design_ingest
    monkeypatch.chdir(ROOT)
    m = FastMCP("t")
    design_ingest.register_design_ingest_tool(m)
    fn = m._tool_manager._tools["ingest_design_export"].fn
    folders = [d for base in ("designs", "figma") if (ROOT / "docs" / base).is_dir()
               for d in (ROOT / "docs" / base).iterdir() if d.is_dir() and d.name not in _SKIP_DIRS]
    if not folders:
        pytest.skip("no design exports in docs/designs or docs/figma")
    for d in folders:
        r = json.loads(asyncio.run(fn(path=str(d), module=d.name)))      # preview: never writes
        assert r["status"] in ("ok", "needs_fixes", "blocked"), (d.name, r.get("error"))
        assert r["files_written"] == []


def test_project_was_not_modified(snapshot):
    after = {p: p.stat().st_mtime_ns for p in _files("*") if p.is_file()}
    assert after == snapshot
