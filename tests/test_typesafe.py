"""TypeSafe judgments: on only with TYPESAFE_API_KEY, only where nexus would otherwise guess,
never replacing an explicit source, and every failure falls back to the built-in rules.
The client is always mocked here — no test reaches the real API (see conftest.py)."""

import asyncio
import json
from types import SimpleNamespace as NS

import pytest
from mcp.server.fastmcp import FastMCP

from tools.epav import arch_ingest, design_ingest, judgment, package_resolver, project_rules

UNGUIDED = """# Booking service

## About
Patients book 20-minute slots online; a Django app on PostgreSQL behind nginx.

## Release history
v0.1 in March, v0.2 in May.

## Where it runs
Docker containers on a single VM, nightly backups to object storage.
"""


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key-not-real")


def _never(*a, **k):
    pytest.fail("TypeSafe must not be called here")


def _choices(**picks):
    return NS(choices={k: NS(choice=v[0], confidence=v[1]) if isinstance(v, tuple) else NS(choice=v, confidence=0.9)
                       for k, v in picks.items()}, nouls={})


def _ingest(tmp_path, monkeypatch) -> dict:
    d = tmp_path / "docs" / "arch-docs" / "app"
    d.mkdir(parents=True)
    (d / "ARCH-APP-v1.md").write_text(UNGUIDED)
    monkeypatch.chdir(tmp_path)
    m = FastMCP("t")
    arch_ingest.register_arch_ingest_tool(m)
    return json.loads(asyncio.run(m._tool_manager._tools["ingest_architecture_doc"].fn(save_summary=False)))


def test_the_key_is_the_switch(monkeypatch):
    assert not judgment.enabled()
    monkeypatch.setenv("TYPESAFE_API_KEY", "   ")
    assert not judgment.enabled()
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    assert judgment.enabled()


def test_no_key_means_no_call_and_the_built_in_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(judgment, "system_one_async", _never)
    monkeypatch.setattr(judgment, "system_one", _never)
    doc = _ingest(tmp_path, monkeypatch)["documents"][0]
    assert doc["sections_from"] == "built-in"
    assert package_resolver._pick_package_manager("a Laravel shop") == ("composer", "catalog")


def test_an_unguided_doc_is_judged_from_heading_and_body(tmp_path, monkeypatch, key):
    seen = {}

    async def fake(state, questions):
        seen.update({k: q.instructions for k, q in questions.items()})
        return _choices(h0="components", h1="components", h2="other", h3="infrastructure")
    monkeypatch.setattr(judgment, "system_one_async", fake)
    r = _ingest(tmp_path, monkeypatch)
    doc = r["documents"][0]
    assert doc["sections_from"] == "typesafe"
    assert "release history" not in " ".join(r["sections_extracted"]) and "where it runs" in " ".join(r["sections_extracted"])
    assert 'Heading: "Where it runs"' in seen["h3"] and "Docker containers" in seen["h3"]   # body, not just the title


def test_a_failed_judgment_falls_back(tmp_path, monkeypatch, key):
    async def down(state, questions):
        return None                                   # what judgment returns on any SDK/network error
    monkeypatch.setattr(judgment, "system_one_async", down)
    assert _ingest(tmp_path, monkeypatch)["documents"][0]["sections_from"] == "built-in"

    async def half(state, questions):
        return _choices(h0="stack")                   # answers missing — trust none of it
    monkeypatch.setattr(judgment, "system_one_async", half)
    assert _ingest(tmp_path / "b", monkeypatch)["documents"][0]["sections_from"] == "built-in"


def test_a_guided_doc_never_asks(monkeypatch, key):
    from pathlib import Path
    import shutil
    monkeypatch.setattr(judgment, "system_one_async", _never)
    sample = Path(__file__).parent / "fixtures" / "projects" / "sample-project"
    tmp = Path(__import__("tempfile").mkdtemp())
    shutil.copytree(sample / "docs", tmp / "docs")
    monkeypatch.chdir(tmp)
    m = FastMCP("t")
    arch_ingest.register_arch_ingest_tool(m)
    r = json.loads(asyncio.run(m._tool_manager._tools["ingest_architecture_doc"].fn(module="core", save_summary=False)))
    arch = next(d for d in r["documents"] if "ARCH-" in d["file"])
    assert arch["sections_from"] == "guide"


def test_tokens_the_rules_cant_place_are_judged_and_the_rest_kept(monkeypatch, key):
    asked = []

    async def fake(state, questions):
        asked.extend(q.instructions for q in questions.values())
        return _choices(t0="primary", t1="other")
    monkeypatch.setattr(judgment, "system_one_async", fake)
    roles = {"--background": "background", "--c-sea-500": "other", "--z-modal": "other"}
    out, src = asyncio.run(design_ingest.judge_unplaced_tokens(roles, {"--c-sea-500": "#0E7C86"}))
    assert src == "typesafe" and out["--c-sea-500"] == "primary" and out["--z-modal"] == "other"
    assert out["--background"] == "background" and len(asked) == 2 and "#0E7C86" in asked[0]


def test_tokens_without_a_key_stay_as_the_rules_said(monkeypatch):
    monkeypatch.setattr(judgment, "system_one_async", _never)
    roles = {"--c-sea-500": "other"}
    assert asyncio.run(design_ingest.judge_unplaced_tokens(roles, {})) == (roles, "built-in")


def test_package_manager_named_in_the_hint_never_asks(monkeypatch, key):
    monkeypatch.setattr(judgment, "system_one", _never)
    assert package_resolver._pick_package_manager("Next.js with pnpm") == ("pnpm", "hint")


def test_package_manager_judgment_needs_confidence(monkeypatch, key):
    monkeypatch.setattr(judgment, "system_one", lambda state, questions: _choices(package_manager=("composer", 0.92)))
    assert package_resolver._pick_package_manager("a PHP shop built on Symfony") == ("composer", "typesafe")
    monkeypatch.setattr(judgment, "system_one", lambda state, questions: _choices(package_manager=("composer", 0.5)))
    pm, src = package_resolver._pick_package_manager("a PHP shop built on Symfony")
    assert src in ("catalog", "none")                 # too flat to trust — the catalog decides
    assert package_resolver.resolve([], stack_hint="")["package_manager_from"] == "none"


def test_stack_from_choice_lines_never_asks(monkeypatch, key):
    monkeypatch.setattr(judgment, "system_one_async", _never)
    stack, src = asyncio.run(project_rules._infer_stack_judged("- **Choice**: Django 5.2 on PostgreSQL 17\n"))
    assert src == "choices" and "Django" in stack


def test_stack_without_choice_lines_keeps_what_the_doc_uses(monkeypatch, key):
    async def fake(state, questions):
        return NS(choices={}, nouls={k: NS(noul=0.9 if "Django" in q.instructions or "PostgreSQL" in q.instructions else 0.1)
                                     for k, q in questions.items()})
    monkeypatch.setattr(judgment, "system_one_async", fake)
    doc = "We build on Django with PostgreSQL. Ruby on Rails was evaluated and rejected."
    stack, src = asyncio.run(project_rules._infer_stack_judged(doc))
    assert src == "typesafe" and "Django" in stack and "PostgreSQL" in stack and "Rails" not in stack
