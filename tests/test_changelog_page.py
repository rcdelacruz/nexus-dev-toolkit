"""public/changelog.html and the docs "What's new" blocks must match CHANGELOG.md.

Fix a failure with: python3 scripts/build_changelog.py
"""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_changelog", ROOT / "scripts" / "build_changelog.py")
bc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bc)

PAGE = (ROOT / "public" / "changelog.html").read_text(encoding="utf-8")
DOCS = (ROOT / "public" / "docs.html").read_text(encoding="utf-8")
NEXUS = bc.parse((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
_HINT = "out of date: run python3 scripts/build_changelog.py"


def test_changelog_page_matches_changelog_md():
    assert bc._between(PAGE, "changelog:nexus") == bc.render_releases(NEXUS, "nexus"), _HINT


def test_every_release_has_an_anchor():
    for r in NEXUS:
        assert f'id="nexus-{r["version"]}"' in PAGE, r["version"]


def test_changelog_page_nav_and_version():
    assert bc.render_nav(NEXUS, "nexus") in PAGE, _HINT
    version = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M).group(1)
    assert f'<div class="nav-version">v{version}</div>' in PAGE, _HINT
    assert NEXUS[0]["version"] == version, "CHANGELOG.md's newest entry is not the pyproject version"


def test_docs_whats_new_is_latest_release():
    assert bc._between(DOCS, "whats-new:nexus") == bc.render_whats_new(NEXUS[0], "nexus"), _HINT


def test_jev_blocks_present():
    # the jev changelog lives on the experimental-jev branch, which CI does not check out,
    # so only check the jev blocks exist and are filled
    jev = bc._between(PAGE, "changelog:jev")
    assert jev and 'id="jev-' in jev
    assert "whats-new-title" in (bc._between(DOCS, "whats-new:jev") or "")


def test_parse_splits_products():
    text = "# Changelog\n\n## [Unreleased]\n- x\n\n## [jev 2.0.0] - 2026-01-02\n- jev thing\n\n## [1.0.0] - 2026-01-01\n- stable thing\n"
    assert [r["version"] for r in bc.parse(text)] == ["1.0.0"]
    jev = bc.parse(text, prefix="jev ")
    assert [(r["version"], r["date"]) for r in jev] == [("2.0.0", "2026-01-02")]


def test_render_escapes_and_nests():
    out = bc._render_body([
        "### Added",
        "- `<div>` & **bold** [link](https://example.com)",
        "  - sub one",
        "  - sub two",
        "- second",
        "  continued line",
        "",
        "Plain <paragraph>.",
    ])
    assert "<h3>Added</h3>" in out
    assert "<code>&lt;div&gt;</code> &amp; <strong>bold</strong>" in out
    assert '<a href="https://example.com" target="_blank">link</a>' in out
    assert "<ul><li>sub one</li><li>sub two</li></ul>" in out
    assert "<li>second continued line</li>" in out
    assert "<p>Plain &lt;paragraph&gt;.</p>" in out


def test_highlight_shortens():
    assert bc._highlight("Stack detection for most of the world's stacks: long detail here") == \
        "Stack detection for most of the world's stacks"
    assert bc._highlight("Short: x. More.") == "Short: x."
    assert len(bc._highlight("word " * 100)) <= 180
