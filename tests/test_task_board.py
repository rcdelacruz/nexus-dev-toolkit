"""Task board (next_task), status updates that touch one row only (set_task_status), and the
batch-2 rules in the developer skills."""
import asyncio
import json
import re
import shutil
from pathlib import Path

import pytest

from tools.epav import task_loader
from tools.epav.formats import tasks as task_format

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "clinic-appointments"
SKILLS = ROOT / "tools" / "epav" / "skills"
AGENTS = ROOT / "tools" / "agents"

HEADER = "TASK_ID,ISSUE_TYPE,SUMMARY,USER_STORY,DESCRIPTION,ACCEPTANCE_CRITERIA,PRIORITY,ASSIGNEE,STATUS,EPIC_LINK,DEPENDENCIES"


def _write(tmp_path, rows, name="a-tasks.csv", newline="\n", bom=False):
    d = tmp_path / "docs" / "dev-tasks" / "app"
    d.mkdir(parents=True, exist_ok=True)
    text = newline.join([HEADER] + rows) + newline
    (d / name).write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode())
    return d / name


def test_board_on_the_example(monkeypatch):
    monkeypatch.chdir(EXAMPLE)
    b = task_loader.board("careslot", "BOOK-004")
    assert [t["task_id"] for t in b["ready"]] == ["BOOK-001", "SCHED-003"]          # High before Medium, file order
    assert b["task"]["ready"] is False and b["task"]["dependencies"] == [{"id": "BOOK-003", "status": "To Do"}]
    assert not any(t["task_id"].startswith("EPIC-") for t in b["ready"] + b["waiting"])


def test_epic_dependency_waits_for_every_task_of_the_epic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, [
        "EPIC-A,Epic,A,s,d,ac,High,,To Do,,None",
        "A-1,Task,x,s,d,ac,High,,Done,EPIC-A,None",
        "A-2,Task,y,s,d,ac,High,,To Do,EPIC-A,A-1",
        "B-1,Task,z,s,d,ac,Low,,To Do,EPIC-B,EPIC-A",
    ])
    b = task_loader.board()
    assert [t["task_id"] for t in b["ready"]] == ["A-2"]
    assert b["waiting"][0]["task_id"] == "B-1" and b["waiting"][0]["waiting_on"][0]["id"] == "EPIC-A"


@pytest.mark.parametrize("newline,bom", [("\n", False), ("\r\n", True)])
def test_set_cells_changes_one_row_and_nothing_else(tmp_path, newline, bom):
    f = _write(tmp_path, [
        'A-1,Task,x,s,"multi\nline, quoted",ac,High,,To Do,EPIC-A,None',
        'A-2,Task,y,s,"d",ac,High,,To Do,EPIC-A,A-1',
        'A-3,Task,z,s,d,ac,High,,To Do,EPIC-A,None',
    ], newline=newline, bom=bom)
    before = f.read_bytes()
    assert task_format.set_cells(f, "a-2", {"status": "In Progress", "assignee": "Dana"}) == {"status": "To Do", "assignee": ""}
    after = f.read_bytes()
    assert after.startswith(b"\xef\xbb\xbf") == bom
    changed = [(a, b) for a, b in zip(before.split(newline.encode()), after.split(newline.encode())) if a != b]
    assert len(changed) == 1 and b"A-2" in changed[0][1] and b"In Progress" in changed[0][1] and b"Dana" in changed[0][1]
    assert task_format.read_tasks(f).find("A-1")["description"] == "multi\nline, quoted"
    assert task_format.set_cells(f, "NOPE-1", {"status": "Done"}) is None


def test_set_task_status_tool(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, ["A-1,Task,x,s,d,ac,High,,To Do,EPIC-A,None"])
    tools = {}

    class FakeMCP:
        def tool(self):
            def deco(fn):
                tools[fn.__name__] = fn
                return fn
            return deco
    task_loader.register_task_loader_tool(FakeMCP())
    run = lambda **kw: json.loads(asyncio.run(tools["set_task_status"](**kw)))
    assert run(task_id="A-1", status="finished")["status"] == "invalid_status"
    assert run(task_id="Z-9", status="Done")["status"] == "not_found"
    r = run(task_id="A-1", status="in progress", assignee="Dana")
    assert r["status"] == "updated" and r["new"] == {"status": "In Progress", "assignee": "Dana"}
    assert run(task_id="A-1", status="In Progress", assignee="Dana")["status"] == "unchanged"
    nt = json.loads(asyncio.run(tools["next_task"]()))
    assert nt["in_progress"][0]["task_id"] == "A-1" and nt["in_progress"][0]["assignee"] == "Dana"


def test_every_example_task_names_a_file_it_changes():
    path = re.compile(r"[\w.-]+(?:/[\w.\-]+)+/?")
    for f in (EXAMPLE / "docs" / "dev-tasks").rglob("*.csv"):
        for r in task_format.read_tasks(f).rows:
            if task_loader._is_epic(r):
                continue
            found = [p for p in path.findall(r["description"]) if (EXAMPLE / p.rstrip("/.")).exists()
                     or (EXAMPLE / p.rstrip("/.")).parent.is_dir()]
            assert found, f"{r['task_id']} names no file or folder"


def test_developer_skills_use_the_board_and_the_checks():
    ev, ap, va = [(SKILLS / n).read_text() for n in ("evaluate.md", "apply.md", "validate.md")]
    assert "next_task" in ev and "Never pick for the user" in ev
    assert 'status="In Progress"' in ap
    assert "## Commands" in va and "not run" in va and 'status="Done"' in va
    assert va.index("Run the project's checks") < va.index("Check against acceptance criteria")
    assert "files" in (SKILLS / "dev-tasks-planner.md").read_text() and "names at least one file or folder" in (SKILLS / "dev-tasks-planner.md").read_text()


def test_scaffold_has_docker_safe_ci_and_unique_check_numbers():
    s = (SKILLS / "scaffold.md").read_text()
    assert "`Dockerfile`" in s and "`docker-compose.yml`" in s and "`.dockerignore`" in s
    assert "lint, typecheck, test, db push" not in s and "never runs migrations or `db push` against a real database" in s
    assert "## Commands" in s
    v = s[s.index("## VALIDATE"):]
    nums = [int(n) for n in re.findall(r"^(\d+)\. ", v, re.M)]
    assert nums == list(range(1, len(nums) + 1)), nums


def test_reviewers_get_context_and_graphify_and_are_read_only():
    for skill, agent_name in (("code-review", "code-reviewer"), ("database-review", "database-reviewer"), ("deployment-review", "deployment-reviewer"),
                              ("performance-review", "performance-reviewer"), ("monitoring-review", "monitoring-reviewer")):
        text = (SKILLS / f"{skill}.md").read_text()
        assert "Gather the project's context" in text and "graphify query" in text, skill
        assert f'subagent_type: "{agent_name}"' in text, skill
    names = {}
    for f in AGENTS.glob("*.md"):
        front = f.read_text().split("---")[1]
        names[re.search(r"^name: (.+)$", front, re.M).group(1)] = f
        assert "Write" not in re.search(r"^tools: (.+)$", front, re.M).group(1), f.name
        if "reviewer" in f.name:
            assert "graphify" in f.read_text(), f.name
    assert all(names[n].stem == n for n in names), "agent name must equal its file name — OpenCode names agents by file"
    cr = (AGENTS / "code-reviewer.md").read_text()
    assert "Design tokens" in cr and "Accessibility" in cr and "Acceptance criteria" in cr
