"""load_task on the task-file shapes real projects use (rules 1 and 3). 3.2.0 returned blank
fields for uppercase headers without an error; every outcome now has an explicit status."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from tools.epav import task_loader

SAMPLE = Path(__file__).parent / "fixtures" / "projects" / "sample-project"


@pytest.fixture
def project(tmp_path, monkeypatch):
    shutil.copytree(SAMPLE / "docs", tmp_path / "docs")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(task_loader.graph_backend, "run_query", lambda q: None)
    return tmp_path


def _load(**kw) -> dict:
    m = FastMCP("t")
    task_loader.register_task_loader_tool(m)
    fn = m._tool_manager._tools["load_task"].fn
    return json.loads(asyncio.run(fn(**kw)))


@pytest.mark.parametrize("path", ["core/login", "security/login", "exempt/registration"])
def test_every_header_style_loads_with_fields(project, path):
    r = _load(csv_path=path, task_id="TASK-001")
    assert r["status"] in ("found", "empty_fields")
    assert r["task_id"] == "TASK-001"
    assert r["user_story"] and r["description"]


def test_uppercase_file_by_id_is_found_not_blank(project):
    # the exact 3.2.0 failure: TASK_ID headers → "not found" / blank fields
    r = _load(csv_path="core/login", task_id="TASK-001")
    assert r["status"] == "found"
    assert "SSO" in r["user_story"] and r["acceptance_criteria"].startswith("- Redirects")


def test_trace_ids_come_from_the_task_text(project):
    r = _load(csv_path="core/login", task_id="TASK-001")
    assert r["trace_ids"] == ["US-001", "ADR-ACME-WIDGET-E001-001", "FR-AUTH-002", "NFR-SEC-003"]
    assert "Traces to:" in r["evaluate_block"]


def test_same_name_in_several_modules_is_ambiguous_not_guessed(project):
    r = _load(csv_path="login", task_id="TASK-001")
    assert r["status"] == "ambiguous"
    assert sorted(r["candidates"]) == ["docs/dev-tasks/core/login-tasks.csv", "docs/dev-tasks/security/login-tasks.csv"]


def test_blank_required_field_is_flagged(project):
    r = _load(csv_path="exempt/registration", task_id="TASK-001")
    assert r["status"] == "empty_fields"
    assert r["empty_fields"] == ["acceptance_criteria"]
    assert "Do not invent" in r["warning"]


def test_unknown_task_lists_ids(project):
    r = _load(csv_path="core/login", task_id="TASK-999")
    assert r["status"] == "not_found"
    assert "TASK-001" in r["available_ids"]


def test_missing_columns_is_invalid_file(project):
    (project / "docs" / "dev-tasks" / "core" / "bad-tasks.csv").write_text("TASK_ID,SUMMARY\nTASK-1,x\n")
    r = _load(csv_path="core/bad")
    assert r["status"] == "invalid_file"
    assert "user_story" in r["error"]


def test_no_task_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _load()["status"] == "no_file"


def test_row_index_out_of_range(project):
    assert _load(csv_path="security/login", row_index=5)["status"] == "out_of_range"


def test_an_id_alone_finds_the_one_file_that_has_it(project):
    r = _load(task_id="TASK-002")                       # only core/login-tasks.csv has TASK-002
    assert r["status"] == "found" and r["_csv_file"] == "docs/dev-tasks/core/login-tasks.csv"


def test_an_id_in_several_files_is_ambiguous(project):
    r = _load(task_id="TASK-001")                       # in all three files
    assert r["status"] == "ambiguous" and len(r["candidates"]) == 3


def test_an_id_in_no_file_is_not_found(project):
    assert _load(task_id="NOPE-404")["status"] == "not_found"
