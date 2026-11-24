"""ingest_architecture_doc follows the project's guide (rules 1, 3, 7)."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from tools.epav import arch_ingest, project_rules
from tools.epav.formats import guides

SAMPLE = Path(__file__).parent / "fixtures" / "projects" / "sample-project"


@pytest.fixture
def project(tmp_path, monkeypatch):
    shutil.copytree(SAMPLE / "docs", tmp_path / "docs")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _ingest(**kw) -> dict:
    m = FastMCP("t")
    arch_ingest.register_arch_ingest_tool(m)
    return json.loads(asyncio.run(m._tool_manager._tools["ingest_architecture_doc"].fn(**kw)))


def test_template_doc_gives_all_sections_and_the_chosen_stack(project):
    r = _ingest(module="core", save_summary=False)
    assert r["status"] == "ok"
    arch = next(d for d in r["documents"] if "ARCH-" in d["file"])
    assert arch["required_sections_missing"] == []
    assert len(arch["required_sections_found"]) == 9
    assert r["stack_source"] == "choices"
    assert "Redis" not in r["stack"] and "Nginx" not in r["stack"] and ".NET" not in r["stack"]


def test_requirements_files_in_arch_docs_are_skipped_with_a_reason(project):
    r = _ingest(module="core", save_summary=False)
    skipped = {Path(s["file"]).name: s["reason"] for s in r["files_skipped"]}
    assert "docs/requirements" in skipped["Widget_Epic_Login_BRD.md"]
    assert not any("node_modules" in f for f in r["files_read"])


def test_adr_ids_are_collected(project):
    r = _ingest(module="core", save_summary=False)
    adr = next(d for d in r["documents"] if Path(d["file"]).name.startswith("ADR"))
    assert adr["adr_ids"] == ["ADR-ACME-WIDGET-E001-001"]
    assert "US-001" in adr["requirement_ids"]


def test_doc_without_the_template_is_partial_and_says_what_is_missing(project):
    r = _ingest(module="legacy", save_summary=False)
    assert r["status"] == "partial"
    assert r["stack_source"] == "mentions" and r["stack"] == ["Django", "PostgreSQL"]
    assert "Technology Choices" in r["documents"][0]["required_sections_missing"]


def test_project_guide_overrides_section_names(project):
    g = guides.default_guide("architecture")
    g.required_sections = ["Tech Stack", "Authentication"]
    g.stack_section = "Tech Stack"
    (project / "docs" / "arch-docs" / "ARCHITECTURE-GUIDE.md").write_text("# Our guide\n\n" + g.to_block())
    r = _ingest(module="legacy", save_summary=False)
    assert r["status"] == "ok" and r["guide"]["problems"] == []
    assert r["documents"][0]["required_sections_found"] == {"Tech Stack": "tech stack", "Authentication": "authentication"} \
        or set(r["documents"][0]["required_sections_found"]) == {"Tech Stack", "Authentication"}


def test_broken_guide_is_reported_not_fatal(project):
    (project / "docs" / "arch-docs" / "ARCHITECTURE-GUIDE.md").write_text("```nexus-guide\n{oops\n```")
    r = _ingest(module="core", save_summary=False)
    assert r["status"] == "ok"
    assert "not valid JSON" in r["guide"]["problems"][0]


def test_summary_labels_only_real_choices_as_choices(project):
    _ingest(module="core")
    text = (project / "knowledge" / "rules" / "arch-summary.md").read_text()
    assert "- **Choice**: Next.js" in text
    assert project_rules._infer_stack(text).startswith("Next.js")
    _ingest(module="legacy")
    text = (project / "knowledge" / "rules" / "arch-summary.md").read_text()
    stack_part = text.split("## Stack")[1].split("\n## ")[0]
    assert "NOT confirmed" in stack_part and "- **Choice**:" not in stack_part
    from tools.epav import stack_catalog
    assert stack_catalog.detect_from_choices(text) == []          # nothing in it reads as a decision


def test_missing_path_and_empty_folder(project):
    assert _ingest(module="nope")["status"] == "not_found"
    (project / "docs" / "arch-docs" / "empty").mkdir()
    assert _ingest(module="empty")["status"] == "no_docs"


def test_epics_come_from_the_adr_files(tmp_path, monkeypatch):
    d = tmp_path / "docs" / "arch-docs" / "shop"
    d.mkdir(parents=True)
    (d / "ADR-ACME-E001-Checkout-v1.0.md").write_text(
        "Epic: E001 — Checkout\nCovers: US-001, US-002, FR-PAY-001\n\n## ADR-ACME-E001-001: Use Stripe\nSee US-009 for context.\n")
    (d / "ADR-ACME-E002-Catalogue-v1.0.md").write_text("## ADR-ACME-E002-001: Search with Postgres FTS\nUS-003, FR-CAT-001\n")
    (d / "ADR-ACME-E002-Catalogue-v2.0.md").write_text("## ADR-ACME-E002-001: Search with OpenSearch\nUS-003, US-004\n")
    monkeypatch.chdir(tmp_path)
    epics = {e["id"]: e for e in _ingest(module="shop", save_summary=False)["epics"]}
    assert list(epics) == ["E001", "E002"]
    assert epics["E001"]["name"] == "Checkout" and epics["E001"]["slug"] == "checkout"
    assert epics["E001"]["covers"] == ["US-001", "US-002", "FR-PAY-001"]       # the Covers: line, not US-009
    assert epics["E002"]["file"].endswith("-v2.0.md")                           # the newest version wins
    assert epics["E002"]["covers_source"] == "cited" and "US-004" in epics["E002"]["covers"]


def test_only_the_newest_version_of_a_doc_is_read(tmp_path, monkeypatch):
    """v1 and v2 of the same ARCH doc used to be merged: the stack held both React (v1) and Vue (v2)."""
    d = tmp_path / "docs" / "arch-docs" / "shop"
    d.mkdir(parents=True)
    (d / "ARCH-SHOP-v1.0.md").write_text("# Architecture\n## Tech Stack\n- **Choice**: React\n")
    (d / "ARCH-SHOP-v2.0.md").write_text("# Architecture\n## Tech Stack\n- **Choice**: Vue\n")
    (d / "ARCH-SHOP-v1.10.md").write_text("# Architecture\n## Tech Stack\n- **Choice**: Svelte\n")   # 1.10 < 2.0
    monkeypatch.chdir(tmp_path)
    r = _ingest(module="shop", save_summary=False)
    assert [Path(f).name for f in r["files_read"]] == ["ARCH-SHOP-v2.0.md"], r
    stack = " ".join(r["stack"]).lower()
    assert "vue" in stack and "react" not in stack and "svelte" not in stack
    assert sorted(Path(s["file"]).name for s in r["files_skipped"] if "older version" in s["reason"]) == ["ARCH-SHOP-v1.0.md", "ARCH-SHOP-v1.10.md"]
