"""Tests for tools/epav/design_ingest.py.

The format detector and CSS-property extractor are pure deterministic code
(no TypeSafe involved -- see the module docstring for why format detection
isn't a judgment call). The token-role mapping's TypeSafe path is tested in
test_typesafe_judgments.py, alongside the other judgment calls.
"""

import asyncio
import json
import zipfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from tools.epav import design_ingest, judgment
from tools.epav.design_ingest import register_design_ingest_tool

_HTML = """
<html><head><style>
:root {
  --brand-500: #4f46e5;
  --btn-danger-bg: #dc2626;
  --space-4: 16px;
}
</style></head><body></body></html>
"""


# ── deterministic parsing ────────────────────────────────────────────────────

def test_extract_css_custom_properties_pulls_root_block_vars():
    tokens = design_ingest._extract_css_custom_properties(_HTML)
    assert tokens == {
        "brand-500": "#4f46e5",
        "btn-danger-bg": "#dc2626",
        "space-4": "16px",
    }


def test_extract_css_custom_properties_ignores_non_custom_props():
    css = ":root { color: red; --ok: 1px; margin: 0; }"
    assert design_ingest._extract_css_custom_properties(css) == {"ok": "1px"}


def test_detect_design_format_zip(tmp_path):
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("tokens.css", ":root { --a: 1; }")
    assert design_ingest._detect_design_format(zip_path) == "figma_export_zip"


def test_detect_design_format_html_file(tmp_path):
    p = tmp_path / "mockup.html"
    p.write_text(_HTML)
    assert design_ingest._detect_design_format(p) == "html_mockup"


def test_detect_design_format_figma_dev_mode_dir(tmp_path):
    (tmp_path / "Design System.dc.html").write_text(_HTML)
    assert design_ingest._detect_design_format(tmp_path) == "figma_dev_mode_export"


def test_detect_design_format_plain_html_dir(tmp_path):
    (tmp_path / "mockup.html").write_text(_HTML)
    assert design_ingest._detect_design_format(tmp_path) == "html_mockup"


def test_detect_design_format_unknown(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("not a design export")
    assert design_ingest._detect_design_format(p) == "unknown"


def test_map_token_roles_fallback_recognizes_keywords():
    mapping = design_ingest._map_token_roles_fallback(
        ["brand-500", "btn-danger-bg", "space-4", "z-index-modal"]
    )
    assert mapping == {
        "brand-500": "primary",
        "btn-danger-bg": "error",
        "space-4": "spacing",
    }
    assert "z-index-modal" not in mapping  # nothing to map it to -- correctly omitted


# ── full tool, TypeSafe mocked ───────────────────────────────────────────────

class _FakeChoiceAnswer:
    def __init__(self, choice):
        self.choice = choice


class _FakeResponse:
    def __init__(self, choices):
        self.choices = choices


def test_ingest_design_export_html_mockup_end_to_end(tmp_path, monkeypatch):
    async def fake_system_one_async(state, questions):
        return _FakeResponse(choices={
            "t0": _FakeChoiceAnswer("primary"),
            "t1": _FakeChoiceAnswer("error"),
            "t2": _FakeChoiceAnswer("spacing"),
        })

    monkeypatch.setattr(judgment, "system_one_async", fake_system_one_async)

    mockup = tmp_path / "mockup.html"
    mockup.write_text(_HTML)

    mcp = FastMCP("test")
    register_design_ingest_tool(mcp)
    tool = mcp._tool_manager.get_tool("ingest_design_export")

    result = asyncio.run(tool.run({"doc_path": str(mockup)}))
    data = json.loads(result[0].text if isinstance(result, tuple) else result)

    assert data["format"] == "html_mockup"
    assert data["tokens"]["brand-500"] == {"value": "#4f46e5", "role": "primary"}
    assert data["tokens"]["btn-danger-bg"] == {"value": "#dc2626", "role": "error"}
    assert str(mockup) in data["files_read"]


def test_ingest_design_export_missing_source_returns_error():
    mcp = FastMCP("test")
    register_design_ingest_tool(mcp)
    tool = mcp._tool_manager.get_tool("ingest_design_export")

    result = asyncio.run(tool.run({"doc_path": "/nonexistent/path/xyz"}))
    data = json.loads(result[0].text if isinstance(result, tuple) else result)
    assert "error" in data
