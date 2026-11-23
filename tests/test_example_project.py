"""The CareSlot example (examples/clinic-appointments) passes nexus's own checks, and its generated
parts are exactly what nexus produces — so the example can't rot."""

import asyncio
import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from tools.epav import arch_ingest, change_request, design_ingest, task_loader
from tools.epav.formats import guides, tasks
from tools.epav.formats.ids import extract_ids, kind_of

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "clinic-appointments"
DOCS = EXAMPLE / "docs"
PRD = (DOCS / "requirements" / "PRD.md").read_text()
BRD = (DOCS / "requirements" / "BRD.md").read_text()
ARCH = "\n".join(p.read_text() for p in (DOCS / "arch-docs" / "careslot").glob("*.md"))
ROWS = [r for f in sorted((DOCS / "dev-tasks" / "careslot").glob("*.csv")) for r in tasks.read_tasks(f).rows]


def _ids(text, kind):
    return sorted({i for i in extract_ids(text) if kind_of(i) == kind})


def _tool(tool_module, name, cwd, **kw):
    m = FastMCP("t")
    getattr(tool_module, [f for f in dir(tool_module) if f.startswith("register_")][0])(m)
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(cwd)
        mp.setattr(task_loader.graph_backend, "run_query", lambda q: None)
        return json.loads(asyncio.run(m._tool_manager._tools[name].fn(**kw)))


def test_generated_parts_are_up_to_date():
    spec = importlib.util.spec_from_file_location("build_example", ROOT / "scripts" / "build_example.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not shutil.which("git"):
        pytest.skip("git not installed")
    assert mod.main(["--check"]) == 0, "run: python3 scripts/build_example.py"


def test_brd_and_prd_have_the_guides_sections():
    g = guides.load_guide(DOCS / "requirements" / "REQUIREMENTS-GUIDE.md", "requirements")
    assert g.problems == []
    for doc, text in (("BRD", BRD), ("PRD", PRD)):
        heads = {guides.heading_key(h) for h in re.findall(r"(?m)^## .+$", text)}
        missing = [s for s in g.documents[doc] if guides.heading_key(s) not in heads]
        assert missing == [], (doc, missing)


def test_every_business_rule_is_served_and_every_story_cites_one():
    brs = _ids(BRD, "business")
    assert brs == [f"BR-00{i}" for i in range(1, 7)]
    for br in brs:
        assert br in PRD, f"{br} is served by nothing in the PRD"
    stories = re.findall(r"(?ms)^### (US-\d+)[^\n]*\n(.*?)(?=^- AC|^###|^## )", PRD)
    assert len(stories) == 8                      # the check really looked at every story
    for sid, body in stories:
        assert "serves BR-" in body, f"{sid} cites no business rule"


def test_architecture_covers_every_requirement_and_keeps_react_out():
    r = _tool(arch_ingest, "ingest_architecture_doc", EXAMPLE, module="careslot", save_summary=False)
    assert r["status"] == "ok" and r["stack_source"] == "choices"
    assert {"Django", "htmx", "PostgreSQL", "Celery"} <= set(r["stack"]) and "React" not in r["stack"]
    prd_ids = _ids(PRD, "user_story") + _ids(PRD, "functional") + _ids(PRD, "non_functional")
    uncovered = [i for i in prd_ids if i not in ARCH]
    assert uncovered == []


def test_epics_split_the_product_and_match_the_task_files():
    r = _tool(arch_ingest, "ingest_architecture_doc", EXAMPLE, module="careslot", save_summary=False)
    epics = r["epics"]
    assert [(e["id"], e["slug"]) for e in epics] == [("E001", "booking"), ("E002", "schedule"), ("E003", "notifications")]
    need = _ids(PRD, "user_story") + _ids(PRD, "functional")
    assert sorted(i for e in epics for i in e["covers"]) == sorted(need)        # each story / FR in exactly one epic
    assert sorted(f.name for f in (DOCS / "dev-tasks" / "careslot").glob("*.csv")) == sorted(f"{e['slug']}-tasks.csv" for e in epics)


def test_requirements_are_product_wide():
    assert sorted(p.name for p in (DOCS / "requirements").iterdir() if p.is_file()) == ["BRD.md", "PRD.md", "REQUIREMENTS-GUIDE.md"]


def test_design_is_clean_and_covers_every_story():
    stories = _ids(PRD, "user_story")
    r = _tool(design_ingest, "ingest_design_export", EXAMPLE, module="careslot", requirement_ids=stories)
    assert r["status"] == "ok" and r["findings"] == []
    screens = r["manifest"]["screens"]
    assert len(screens) == 4 and all(s["component"] for s in screens)
    assert r["manifest"]["unmatched_colours"] == {}
    assert set(stories) <= {i for s in screens for i in s["trace_ids"]}


def test_every_task_loads_and_every_requirement_has_a_task():
    for f in sorted((DOCS / "dev-tasks" / "careslot").glob("*.csv")):
        for row in tasks.read_tasks(f).rows:
            r = _tool(task_loader, "load_task", EXAMPLE, csv_path=str(f.relative_to(EXAMPLE)), task_id=row["task_id"])
            assert r["status"] == "found", (f.name, row["task_id"], r.get("empty_fields"))
    traced = {i for r in ROWS for i in extract_ids(r["trace_ids"])}
    needed = _ids(PRD, "user_story") + _ids(PRD, "functional")
    assert [i for i in needed if i not in traced] == []


def test_cr_001_records_exactly_its_changes_and_tasks():
    record = json.loads((DOCS / "change-requests" / "CR-001.json").read_text())
    assert record["changed_ids"] == ["FR-NOTIF-001", "US-005"]
    assert record["added_ids"] == ["AC-015", "FR-BOOK-004"]
    assert record["removed_ids"] == []
    r = _tool(change_request, "trace_tasks", EXAMPLE, cr_id="CR-001")
    assert [a["task_id"] for a in r["affected_tasks"]] == ["BOOK-005", "BOOK-006", "NOTIF-002"]


def test_client_pack_zip_is_what_the_team_gets_on_day_one():
    import zipfile
    pack = ROOT / "examples" / "careslot-client-pack"
    names = set(zipfile.ZipFile(ROOT / "public" / "careslot-client-pack.zip").namelist())
    # unzipped in the repository root, the files land where the commands read them
    assert "docs/requirements/sources/kickoff-notes.md" in names and "docs/designs/design-system/tokens.css" in names
    assert all(n.startswith(("docs/requirements/sources/", "docs/designs/design-system/")) for n in names)
    assert not any("later" in n for n in names)                           # the change request arrives later
    assert (pack / "later" / "cr-001-client-email.md").is_file()
    assert (pack / "design-system" / "tokens.css").read_text() == (DOCS / "designs" / "design-system" / "tokens.css").read_text()
