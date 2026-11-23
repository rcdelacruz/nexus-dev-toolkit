"""Shared docs/ formats: every writer's output reads back through its reader (rule 2), and the
readers accept the shapes real projects use (rule 3)."""

from pathlib import Path

import pytest

from tools.epav.formats import FORMAT_VERSION
from tools.epav.formats import cr as cr_format
from tools.epav.formats import design as design_format
from tools.epav.formats import guides, ids, tasks

SAMPLE = Path(__file__).parent / "fixtures" / "projects" / "sample-project" / "docs"


# ── tasks ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("header,canonical", [
    ("TASK_ID", "task_id"), ("Task ID", "task_id"), ("task_id", "task_id"), ("﻿TASK_ID", "task_id"),
    ("task-id", "task_id"), ("ACCEPTANCE_CRITERIA", "acceptance_criteria"), ("Issue key", "task_id"),
    ("Acceptance Criteria", "acceptance_criteria"), ("EPIC_LINK", "epic_link"), ("Trace IDs", "trace_ids"),
])
def test_header_variants_map_to_one_field(header, canonical):
    assert tasks._canonical(header) == canonical


@pytest.mark.parametrize("rel", ["core/login-tasks.csv", "security/login-tasks.csv", "exempt/registration-tasks.csv"])
def test_every_header_style_reads(rel):
    tf = tasks.read_tasks(SAMPLE / "dev-tasks" / rel)
    assert tf.missing_required == []
    assert all(r["task_id"] for r in tf.rows)
    assert tf.find("task-001")["task_id"] == "TASK-001"     # case-insensitive lookup


def test_unknown_columns_are_kept_not_dropped():
    tf = tasks.read_tasks(SAMPLE / "dev-tasks" / "exempt" / "registration-tasks.csv")
    assert "QA - Actual Effort" in tf.extra_columns
    assert "BE Estimate" in tf.extra_columns


def test_missing_required_column_is_reported(tmp_path):
    f = tmp_path / "t.csv"
    f.write_text("TASK_ID,SUMMARY\nTASK-1,x\n")
    assert tasks.read_tasks(f).missing_required == ["user_story", "description", "acceptance_criteria"]


def test_blank_required_fields_are_reported():
    tf = tasks.read_tasks(SAMPLE / "dev-tasks" / "exempt" / "registration-tasks.csv")
    assert tasks.empty_required(tf.rows[0]) == ["acceptance_criteria"]


def test_tasks_round_trip(tmp_path):
    src = tasks.read_tasks(SAMPLE / "dev-tasks" / "core" / "login-tasks.csv")
    out = tmp_path / "out.csv"
    tasks.write_tasks(out, src.rows, src.extra_columns)
    back = tasks.read_tasks(out)
    # the writer always emits every documented column (e.g. TRACE_IDS); nothing else may change
    assert back.rows == [{c: r.get(c, "") for c in tasks.COLUMNS} | {c: r[c] for c in src.extra_columns} for r in src.rows]
    assert out.read_text().splitlines()[0].startswith("TASK_ID,ISSUE_TYPE,SUMMARY")
    assert not list(tmp_path.glob("*.tmp"))


# ── IDs ──────────────────────────────────────────────────────────────────────

def test_ids_follow_the_reference_scheme():
    text = ("US-001 and US-014 per ADR-ACME-CORE-E001-009 (epic E001); NFR-SEC-004, NFR-009, "
            "FR-AUTH-003, AC-184, DES-002, CR-004; not XUS-1, US-12a or FOO-E0011")
    assert ids.extract_ids(text) == ["US-001", "US-014", "ADR-ACME-CORE-E001-009", "E001", "NFR-SEC-004",
                                     "NFR-009", "FR-AUTH-003", "AC-184", "DES-002", "CR-004"]
    assert ids.kind_of("NFR-SEC-004") == "non_functional"
    assert ids.kind_of("ADR-ACME-CORE-E001-009") == "adr"


def test_project_patterns_extend_the_defaults():
    assert ids.extract_ids("see REQ-12 and US-1", {"requirement": r"REQ-\d+"}) == ["REQ-12", "US-1"]


def test_id_list_round_trip():
    lst = ["US-001", "FR-AUTH-002"]
    assert ids.parse_id_list(ids.format_id_list(lst)) == lst


# ── guides ───────────────────────────────────────────────────────────────────

def test_guide_round_trip():
    g = guides.default_guide("architecture")
    g.rules = [{"id": "A1", "severity": "BLOCKER", "text": "Every FR has a section"}]
    back = guides.parse_guide("# Guide\n\n" + g.to_block() + "\n", "architecture")
    assert back.problems == []
    assert back.rules == g.rules and back.required_sections == g.required_sections
    assert back.stack_section == "Technology Choices"


@pytest.mark.parametrize("text,problem", [
    ("no block here", "no ```nexus-guide``` block"),
    ("```nexus-guide\n{not json\n```", "not valid JSON"),
    ('```nexus-guide\n{"kind": "architecture", "format_version": 99}\n```', "newer than this nexus"),
    ('```nexus-guide\n{"kind": "architecture", "rules": [{"id": "X", "severity": "MAYBE"}]}\n```', "severity"),
    ('```nexus-guide\n{"kind": "architecture", "id_patterns": {"bad": "("}}\n```', "invalid ID patterns"),
])
def test_broken_guides_fall_back_and_say_why(text, problem):
    g = guides.parse_guide(text, "architecture")
    assert any(problem in p for p in g.problems), g.problems
    assert g.required_sections  # defaults still usable


def test_missing_guide_file_uses_defaults(tmp_path):
    g = guides.load_guide(tmp_path / "nope.md", "design")
    assert g.source == "default" and "not found" in g.problems[0]


def test_heading_key_ignores_numbering():
    assert guides.heading_key("## 4\\. Technology Choices") == "technology choices"
    assert guides.heading_key("## 10. NFR Fulfillment") == "nfr fulfillment"


# ── design.json ──────────────────────────────────────────────────────────────

def test_design_manifest_round_trip(tmp_path):
    m = design_format.DesignManifest(
        module="core", sources=["figma/core"], tokens={"light": {"--primary": "#1F9D6B"}, "dark": {}},
        screens=[design_format.Screen("DES-001", "Login", "Login.dc.html", "LoginScreen.jsx", ["error"], ["US-001"])],
        unmatched_colours={"Login.dc.html": ["#6b6f6b"]})
    p = tmp_path / "designs" / "core" / "design.json"
    design_format.write_manifest(p, m)
    assert design_format.read_manifest(p) == m
    assert m.problems() == []


def test_design_manifest_problems():
    m = design_format.DesignManifest(module="x", format_version=FORMAT_VERSION + 1,
                                     screens=[design_format.Screen("DES-1", "A"), design_format.Screen("DES-1", "B")])
    probs = " ".join(m.problems())
    assert "newer" in probs and "duplicate screen IDs" in probs and "no design tokens" in probs


# ── change requests ──────────────────────────────────────────────────────────

def test_cr_round_trip_and_affected_rows(tmp_path):
    c = cr_format.ChangeRequest("CR-004", "Shorter session", "2026-11-23",
                                changed_ids=["NFR-SEC-003"], files=["docs/requirements/core/PRD.md"])
    p = tmp_path / "CR-004.json"
    cr_format.write_cr(p, c)
    assert cr_format.read_cr(p) == c
    rows = tasks.read_tasks(SAMPLE / "dev-tasks" / "core" / "login-tasks.csv").rows
    hit = cr_format.affected_rows(rows, c)
    assert [r["task_id"] for r in hit] == ["TASK-001"]   # only the row that mentions NFR-SEC-003
