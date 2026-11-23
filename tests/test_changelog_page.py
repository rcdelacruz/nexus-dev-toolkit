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
    version = bc._current_version()   # pyproject's version, or the newest stable on the pre-release branch
    assert f'<div class="nav-version">v{version}</div>' in PAGE, _HINT
    assert NEXUS[0]["version"] == version, "CHANGELOG.md's newest stable entry is not the site version"


def test_prerelease_entries_stay_off_the_stable_tab():
    text = "## [4.0.0a1] - 2026-11-23\n- pre\n\n## [3.2.0] - 2026-11-22\n- stable\n"
    assert [r["version"] for r in bc.parse(text)] == ["3.2.0"]
    assert [r["version"] for r in bc.parse(text, include_pre=True)] == ["4.0.0a1", "3.2.0"]


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


def test_every_page_shows_the_current_version():
    version = bc._current_version()   # the site shows stable, also while pyproject is a pre-release
    for page in sorted((ROOT / "public").glob("*.html")):
        for shown in re.findall(r'<div class="nav-version">v([^<]+)</div>', page.read_text(encoding="utf-8")):
            assert shown == version, f"{page.name} shows v{shown}, pyproject is {version}"


def test_v4_preview_tab_lists_only_pre_releases():
    block = bc._between(PAGE, "changelog:v4") or ""
    assert 'class="tab"' not in block
    versions = re.findall(r'<h2 id="v4-([^"]+)">', block)
    assert versions, "v4 tab is empty — run python3 scripts/build_changelog.py"
    assert all(bc._PRE.search(v) for v in versions)
    assert not re.search(r'<h2 id="nexus-[^"]*(a|b|rc)\d+"', PAGE)      # never on the stable tab
