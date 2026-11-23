"""Change requests: git diff of docs/ → changed/added/removed IDs → only the affected task rows (F4)."""

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from tools.epav import change_request as crm
from tools.epav.formats import tasks

SAMPLE = Path(__file__).parent / "fixtures" / "projects" / "sample-project"
PRD_V1 = """# Login PRD
## Requirements
- US-001 As a clerk I sign in with SSO.
- US-002 As a clerk I see a sign-in page.
- NFR-SEC-003 Sessions expire after 15 minutes of inactivity.
"""
PRD_V2 = """# Login PRD
## Requirements
- US-001 As a clerk I sign in with SSO.
- NFR-SEC-003 Sessions expire after 10 minutes of inactivity.
- US-003 As a clerk I can sign out from every page.
"""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@example.com", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"})


@pytest.fixture
def repo(tmp_path, monkeypatch):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    shutil.copytree(SAMPLE / "docs", tmp_path / "docs")
    (tmp_path / "docs" / "requirements" / "core").mkdir(parents=True)
    (tmp_path / "docs" / "requirements" / "core" / "PRD.md").write_text(PRD_V1)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "baseline")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _tool(name, **kw) -> dict:
    m = FastMCP("t")
    crm.register_change_request_tools(m)
    return json.loads(asyncio.run(m._tool_manager._tools[name].fn(**kw)))


def test_diff_classifies_changed_added_removed(repo):
    (repo / "docs" / "requirements" / "core" / "PRD.md").write_text(PRD_V2)
    d = crm.diff_ids("HEAD")
    assert d["changed"] == ["NFR-SEC-003"]
    assert d["added"] == ["US-003"]
    assert d["removed"] == ["US-002"]
    assert d["files"] == ["docs/requirements/core/PRD.md"]


def test_record_lists_only_affected_rows_and_writes_after_approval(repo):
    (repo / "docs" / "requirements" / "core" / "PRD.md").write_text(PRD_V2)
    preview = _tool("record_change_request", cr_id="CR-004", title="Shorter sessions, sign-out")
    assert preview["status"] == "ok" and preview["files_written"] == []
    assert not (repo / "docs" / "change-requests").exists()
    hit = {(Path(a["file"]).parent.name, a["task_id"]): a["ids"] for a in preview["affected_tasks"]}
    # core TASK-001 cites NFR-SEC-003, core TASK-002 cites US-002; nothing else in any module
    assert hit == {("core", "TASK-001"): ["NFR-SEC-003"], ("core", "TASK-002"): ["US-002"]}
    done = _tool("record_change_request", cr_id="CR-004", title="Shorter sessions, sign-out", write=True)
    assert done["files_written"] == ["docs/change-requests/CR-004.json"]
    again = _tool("trace_tasks", cr_id="CR-004")
    assert {(Path(a["file"]).parent.name, a["task_id"]) for a in again["affected_tasks"]} == set(hit)


def test_no_doc_changes_is_said_plainly(repo):
    r = _tool("record_change_request", cr_id="CR-005", title="nothing", write=True)
    assert r["status"] == "no_changes" and r["files_written"] == []


def test_new_requirement_file_counts(repo):
    (repo / "docs" / "requirements" / "core" / "Addendum.md").write_text("- US-009 Export to Excel\n")
    assert crm.diff_ids("HEAD")["added"] == ["US-009"]


def test_bad_inputs(repo):
    assert _tool("record_change_request", cr_id="4", title="x")["status"] == "invalid"
    assert _tool("record_change_request", cr_id="CR-6", title="x", base="no-such-rev")["status"] == "git_error"
    assert _tool("trace_tasks", cr_id="CR-404")["status"] == "not_found"


def test_trace_tasks_fills_the_column_from_existing_text(repo):
    f = "docs/dev-tasks/core/login-tasks.csv"
    preview = _tool("trace_tasks", csv_path=f)
    rows = {r["task_id"]: r["proposed"] for r in preview["rows"]}
    assert rows["TASK-001"] == ["US-001", "ADR-ACME-WIDGET-E001-001", "FR-AUTH-002", "NFR-SEC-003"]
    assert preview["files_written"] == []
    _tool("trace_tasks", csv_path=f, write=True)
    back = {r["task_id"]: r["trace_ids"] for r in tasks.read_tasks(repo / f).rows}
    assert back["TASK-001"] == "US-001, ADR-ACME-WIDGET-E001-001, FR-AUTH-002, NFR-SEC-003"
    assert back["TASK-002"] == "US-002"


PRD_SECTIONS_V1 = """# PRD
## 3. User Stories
### US-005 — Cancel
- AC-009 Cancel until 2 hours before.

## 4. Functional Requirements
| ID | Requirement | Serves | Stories |
|---|---|---|---|
| FR-NOTIF-001 | SMS reminder 24 hours before. | BR-004 | US-006 |

## 7. Release Scope
**In this release:** US-001 – US-008, FR-BOOK-001 – FR-BOOK-003
"""
PRD_SECTIONS_V2 = """# PRD
## 3. User Stories
### US-005 — Cancel
- AC-009 Cancel until 2 hours before.
- AC-015 A cancellation reason is required.

## 4. Functional Requirements
| ID | Requirement | Serves | Stories |
|---|---|---|---|
| FR-BOOK-004 | Cancellation reason required. | BR-005 | US-005 |
| FR-NOTIF-001 | SMS reminder 2 hours before. | BR-004 | US-006 |

## 7. Release Scope
**In this release:** US-001 – US-008, FR-BOOK-001 – FR-BOOK-004
"""


def test_lines_are_judged_by_what_they_are_about(repo):
    f = repo / "docs" / "requirements" / "core" / "PRD.md"
    f.write_text(PRD_SECTIONS_V1)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v1")
    f.write_text(PRD_SECTIONS_V2)
    d = crm.diff_ids("HEAD")
    assert d["changed"] == ["FR-NOTIF-001", "US-005"]    # row edited; new AC bullet under the US-005 heading
    assert d["added"] == ["AC-015", "FR-BOOK-004"]
    assert d["removed"] == []
    # references only: BR-005 / US-005 in the new row, and the release-scope list, don't count as changes
    assert "BR-005" not in d["changed"] and "US-001" not in d["changed"]


def test_a_new_story_with_its_criteria_is_added_not_changed(repo):
    f = repo / "docs" / "requirements" / "core" / "PRD.md"
    f.write_text(PRD_SECTIONS_V1)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v1")
    f.write_text(PRD_SECTIONS_V1.replace("## 4.", "### US-016 — Monthly count\n- AC-051 A count per reason.\n\n## 4."))
    d = crm.diff_ids("HEAD")
    assert d["added"] == ["AC-051", "US-016"]
    assert d["changed"] == []


def test_paths_with_spaces_and_unicode():
    assert crm._diff_path("b/docs/designs/core/Frame - Login.dc.html\t") == "docs/designs/core/Frame - Login.dc.html"
    assert crm._diff_path('"b/docs/caf\\303\\251.md"') == "docs/café.md"
    assert crm._diff_path("/dev/null") is None


def _example_repo(tmp_path, monkeypatch):
    ex = Path(__file__).parent.parent / "examples" / "clinic-appointments"
    shutil.copytree(ex / "docs", tmp_path / "docs")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "chore: baseline")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_an_architecture_only_change_is_recorded_and_replans_its_epic(tmp_path, monkeypatch):
    """CR "notifications via a queue": only the epic E003 ADR changes, no requirement ID — the
    record still gets written and the notifications epic is re-planned, nothing else."""
    if not shutil.which("git"):
        pytest.skip("git not installed")
    repo = _example_repo(tmp_path, monkeypatch)
    adr = next((repo / "docs" / "arch-docs" / "careslot").glob("ADR-CARESLOT-E003-*.md"))
    adr.write_text(adr.read_text() + "\nReminders now go through a managed queue instead of Celery beat.\n")
    r = _tool("record_change_request", cr_id="CR-010", title="Queue for reminders", write=True)
    assert r["status"] == "ok" and "E003" in r["record"]["changed_ids"], r
    files = {Path(a["file"]).name for a in r["affected_tasks"]}
    assert files == {"notifications-tasks.csv"}
    assert r["files_written"] == ["docs/change-requests/CR-010.json"]


def test_a_design_only_change_replans_the_rows_that_trace_the_screen(tmp_path, monkeypatch):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    repo = _example_repo(tmp_path, monkeypatch)
    dj = repo / "docs" / "designs" / "careslot" / "design.json"
    data = json.loads(dj.read_text())
    screen = next(s for s in data["screens"] if s.get("id") == "DES-003")
    screen["name"] = screen.get("name", "") + " (redesigned)"
    dj.write_text(json.dumps(data, indent=2))
    r = _tool("record_change_request", cr_id="CR-011", title="Redo DES-003")
    assert r["status"] == "ok" and "DES-003" in r["record"]["changed_ids"], r
    assert r["affected_tasks"] and all("DES-003" in a["ids"] for a in r["affected_tasks"])


def test_a_reexported_frame_counts_as_its_screen(tmp_path, monkeypatch):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    repo = _example_repo(tmp_path, monkeypatch)
    frame = repo / "docs" / "designs" / "careslot" / "Frame - My Appointments.dc.html"
    frame.write_text(frame.read_text() + "\n<!-- cancel reason field -->\n")
    screen = next(s["id"] for s in json.loads((frame.parent / "design.json").read_text())["screens"]
                  if s.get("frame") == frame.name)
    assert crm.diff_ids("HEAD")["other"] == [screen]
