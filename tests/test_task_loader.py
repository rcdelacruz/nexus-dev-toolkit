"""load_task reads the CSVs /dev-tasks-planner writes (upper-case headers) as well as lower-case ones."""
import asyncio
import json

import pytest
from mcp.server.fastmcp import FastMCP

from tools.epav.task_loader import register_task_loader_tool

UPPER = ("TASK_ID,ISSUE_TYPE,SUMMARY,USER_STORY,DESCRIPTION,ACCEPTANCE_CRITERIA,DEPENDENCIES,BE - ACTUAL EFFORT\n"
         "TASK-001,Task,Login,US-001,Build login,Can log in,,\n"
         "TASK-002,Task,Logout,US-002,Build logout,Can log out,TASK-001,2h\n")
LOWER = ("task_id,user_story,description,acceptance_criteria,dependencies\n"
         "T1,US-1,Do it,It is done,\n")
SPACED = "﻿Task ID,User Story,Description,Acceptance Criteria,Dependencies\nT9,US-9,Spaced,Works,T1\n"


def _load(**kw) -> dict:
    m = FastMCP("t")
    register_task_loader_tool(m)
    return json.loads(asyncio.run(m._tool_manager._tools["load_task"].fn(**kw)))


@pytest.fixture
def csv_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "docs" / "dev-tasks" / "m"
    d.mkdir(parents=True)
    return d


def test_upper_case_headers_from_dev_tasks_planner(csv_dir):
    (csv_dir / "a-tasks.csv").write_text(UPPER, encoding="utf-8")
    r = _load(task_id="TASK-002")
    assert (r["task_id"], r["description"], r["acceptance_criteria"], r["dependencies"]) == \
        ("TASK-002", "Build logout", "Can log out", "TASK-001")
    assert r["_all_fields"]["BE - ACTUAL EFFORT"] == "2h"     # the CSV's own column names are kept
    assert "Build logout" in r["evaluate_block"]


def test_first_row_and_case_insensitive_id(csv_dir):
    (csv_dir / "a-tasks.csv").write_text(UPPER, encoding="utf-8")
    assert _load()["description"] == "Build login"
    assert _load(task_id="task-002")["task_id"] == "TASK-002"


def test_lower_case_headers_still_work(csv_dir):
    (csv_dir / "b-tasks.csv").write_text(LOWER, encoding="utf-8")
    r = _load(csv_path="b-tasks", task_id="T1")
    assert (r["description"], r["acceptance_criteria"]) == ("Do it", "It is done")


def test_spaced_headers_with_bom(csv_dir):
    (csv_dir / "c-tasks.csv").write_bytes(SPACED.encode("utf-8"))
    r = _load(csv_path="c-tasks")
    assert (r["task_id"], r["user_story"], r["dependencies"]) == ("T9", "US-9", "T1")


def test_unknown_id_lists_the_real_ids(csv_dir):
    (csv_dir / "a-tasks.csv").write_text(UPPER, encoding="utf-8")
    r = _load(task_id="TASK-404")
    assert "not found" in r["error"] and r["available_ids"] == ["TASK-001", "TASK-002"]
