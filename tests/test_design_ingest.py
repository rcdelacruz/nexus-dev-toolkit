"""ingest_design_export: framework-neutral, content-based, bounded, guide-checked."""

import asyncio
import json
import shutil
import zipfile
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from tools.epav import design_ingest as di
from tools.epav.formats import guides

DESIGNS = Path(__file__).parent / "fixtures" / "projects" / "sample-project" / "docs" / "designs"


@pytest.fixture
def project(tmp_path, monkeypatch):
    shutil.copytree(DESIGNS, tmp_path / "exports")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _ingest(**kw) -> dict:
    m = FastMCP("t")
    di.register_design_ingest_tool(m)
    return json.loads(asyncio.run(m._tool_manager._tools["ingest_design_export"].fn(**kw)))


def _zip(folder: Path, dest: Path) -> Path:
    with zipfile.ZipFile(dest, "w") as z:
        for f in folder.rglob("*"):
            if f.is_file():
                z.write(f, Path(folder.name) / f.relative_to(folder))
    return dest


# ── colours and tokens ───────────────────────────────────────────────────────

@pytest.mark.parametrize("value,hexv", [
    ("#1F9D6B", "#1f9d6b"), ("#fff", "#ffffff"), ("#1f9d6b80", "#1f9d6b"),
    ("rgb(31, 157, 107)", "#1f9d6b"), ("hsl(0, 0%, 100%)", "#ffffff"),
    ("oklch(1 0 0)", "#ffffff"), ("oklch(0 0 0)", "#000000"), ("oklch(100% 0 0)", "#ffffff"),
    ("var(--x)", None), ("transparent", None),
])
def test_colour_to_hex(value, hexv):
    assert di.colour_to_hex(value) == hexv


def test_light_and_dark_tokens_and_compiled_css_ignored():
    text = (DESIGNS / "web" / "tokens.css").read_text()
    t = di.parse_css_tokens(text)
    assert t["light"]["--primary"] == "#1F9D6B" and t["dark"]["--foreground"] == "oklch(1 0 0)"
    assert t["dark"]["--primary"] == "#22c38e"                      # prefers-color-scheme: dark
    assert di.is_compiled_css((DESIGNS / "web" / "react-export" / "src" / "index.css").read_text())


@pytest.mark.parametrize("name,role", [
    ("--primary", "primary"), ("--primary-foreground", "foreground"), ("--muted-foreground", "foreground"),
    ("--color-t1", "foreground"), ("--text-2xl", "typography"), ("--color-surface", "background"),
    ("--destructive", "error"), ("--radius", "radius"), ("--color-border-input", "border"),
])
def test_token_roles(name, role):
    assert di.token_role(name) == role


# ── a designer's export (frames + tokens + react-export) ─────────────────────

def test_frames_become_screens_paired_with_components(project):
    r = _ingest(path="exports/web", module="web")
    screens = {s["name"]: s for s in r["manifest"]["screens"]}
    assert set(screens) == {"Login", "Orders"}                     # "Design System" is reference, not a screen
    assert screens["Login"]["component"].endswith("LoginScreen.jsx")
    assert screens["Orders"]["component"].endswith("OrdersPage.jsx")
    assert screens["Login"]["id"] != screens["Orders"]["id"]
    assert "error" in screens["Login"]["states"] and {"empty", "loading"} <= set(screens["Orders"]["states"])
    assert screens["Login"]["trace_ids"] == ["US-001"] and screens["Orders"]["trace_ids"] == ["FR-ORD-001"]
    assert r["reference_frames"] == ["Design System.dc.html"]
    assert r["manifest"]["exports"] == [{"path": "react-export", "framework": "react (vite)"}]


def test_build_output_is_skipped_and_reported(project):
    r = _ingest(path="exports/web", module="web")
    assert {"react-export/node_modules", "react-export/.next"} <= set(r["skipped_build_output"])
    assert "react-export/src/index.css" not in r["manifest"]["token_sources"]    # compiled Tailwind
    assert r["manifest"]["token_sources"] == ["tokens.css"]


def test_off_token_colours_are_reported_per_frame(project):
    r = _ingest(path="exports/web", module="web")
    assert r["manifest"]["unmatched_colours"] == {"Frame - Login.dc.html": ["#1c1f1c", "#6b6f6b"]}
    d4 = [f for f in r["findings"] if f["rule"] == "D4"]
    assert d4 and d4[0]["severity"] == "FIX NOW" and "#6b6f6b" in d4[0]["message"] and d4[0]["fix"]
    assert r["status"] == "needs_fixes"


def test_notes_assets_and_unknown_files_are_listed_not_dropped(project):
    r = _ingest(path="exports/web", module="web")
    assert r["notes"] == ["DEV-NOTES.md"]
    assert r["manifest"]["assets"] == ["assets/logo.svg"]
    assert r["manifest"]["unrecognised"] == ["support.js"]


def test_zip_gives_the_same_result(project):
    folder = _ingest(path="exports/web", module="web")
    z = _zip(project / "exports" / "web", project / "web.zip")
    zipped = _ingest(path=str(z), module="web")
    strip = lambda s: [(x["name"], Path(x["frame"]).name, Path(x["component"]).name) for x in s]  # noqa: E731
    assert strip(zipped["manifest"]["screens"]) == strip(folder["manifest"]["screens"])
    assert any("node_modules" in s for s in zipped["skipped_build_output"])


def test_unsafe_zip_is_refused_before_extracting(project):
    z = project / "evil.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("ok.html", "<html></html>")
        zf.writestr("../../escaped.txt", "x")
    r = _ingest(path=str(z), module="evil")
    assert r["status"] == "unsafe_zip"
    assert not (project.parent / "escaped.txt").exists()


def test_size_limits_say_so(project, monkeypatch):
    monkeypatch.setattr(di, "MAX_FILES", 3)
    r = _ingest(path="exports/web", module="web")
    assert r["status"] == "too_large" and "build output" in r["error"]


def test_screen_ids_stay_stable_across_reimports(project):
    out = project / "docs" / "designs" / "web" / "design.json"
    first = _ingest(path="exports/web", module="web", write=True)
    assert first["files_written"] == ["docs/designs/web/design.json"] and out.is_file()
    ids = {s["name"]: s["id"] for s in first["manifest"]["screens"]}
    (project / "exports" / "web" / "Frame - Checkout.dc.html").write_text("<html><body>Checkout</body></html>")
    again = _ingest(path="exports/web", module="web", write=True)
    ids2 = {s["name"]: s["id"] for s in again["manifest"]["screens"]}
    assert ids2["Login"] == ids["Login"] and ids2["Orders"] == ids["Orders"]
    assert ids2["Checkout"] not in ids.values()


def test_preview_writes_nothing(project):
    _ingest(path="exports/web", module="web")
    assert not (project / "docs").exists()


def test_requirement_coverage(project):
    r = _ingest(path="exports/web", module="web", requirement_ids=["US-001", "US-002"])
    d2 = next(f for f in r["findings"] if f["rule"] == "D2")
    assert d2["severity"] == "BLOCKER" and "US-002" in d2["message"] and "US-001" not in d2["message"]


# ── a Figma-Make-style export (code only) ────────────────────────────────────

def test_code_only_export(project):
    r = _ingest(path="exports/make", module="make")
    man = r["manifest"]
    assert man["exports"] == [{"path": ".", "framework": "react (vite)"}]
    assert man["token_sources"] == ["src/styles/globals.css"]           # compiled src/index.css ignored
    assert [(s["name"], s["component"]) for s in man["screens"]] == [("login", "src/components/login-screen.tsx")]
    assert any(f["rule"] == "D3" for f in r["findings"])                # no HTML frames


# ── guide-driven ─────────────────────────────────────────────────────────────

def test_no_project_guide_still_checks_with_nexus_defaults(project):
    r = _ingest(path="exports/web", module="web")
    assert r["guide"]["source"] == "default" and r["findings"]


def test_a_rule_removed_from_the_guide_is_not_checked(project):
    g = guides.default_guide("design")
    g.rules = [x for x in g.rules if x["id"] != "D4"]
    (project / "docs" / "designs").mkdir(parents=True)
    (project / "docs" / "designs" / "DESIGN-GUIDE.md").write_text(g.to_block())
    r = _ingest(path="exports/web", module="web")
    assert not any(f["rule"] == "D4" for f in r["findings"])


def test_missing_export(project):
    assert _ingest(module="nothing")["status"] == "not_found"


def test_css_comments_never_decide_the_theme():
    # measured on a real export: a header comment mentioning [data-theme="dark"] filed every light token as dark
    css = '/* the [data-theme="dark"] block comes later */\n:root {\n  --color-bg: #f5f6f4;\n  --color-text: #1c1f1c; /* .dark */\n}\n'
    t = di.parse_css_tokens(css)
    assert t["light"] == {"--color-bg": "#f5f6f4", "--color-text": "#1c1f1c"} and t["dark"] == {}


def test_code_export_without_package_json_is_recognised(project):
    r = _ingest(path="exports/bundle", module="bundle")
    man = r["manifest"]
    assert man["exports"] == [{"path": "shop-react-export", "framework": "react (no package.json)"}]
    pairs = {s["name"]: Path(s["component"]).name for s in man["screens"]}
    assert pairs == {"Login": "LoginScreen.jsx", "Mobile Shop": "MobileShopPage.jsx"}
    assert man["unrecognised"] == ["browser-window.jsx"]            # helper next to the frames, not an export


def test_frames_and_tokens_alone_are_enough(project, tmp_path):
    """F3: no code export at all (e.g. the app is Go + htmx) — screens, states and tokens still come through."""
    src = project / "exports" / "frames-only"
    src.mkdir()
    for f in ("Frame - Login.dc.html", "Frame - Orders.dc.html", "tokens.css"):
        shutil.copy(project / "exports" / "web" / f, src / f)
    r = _ingest(path=str(src), module="frames-only")
    man = r["manifest"]
    assert man["exports"] == [] and {s["name"] for s in man["screens"]} == {"Login", "Orders"}
    assert man["tokens"]["light"]["--primary"] == "#1F9D6B"
    assert not any(f["rule"] in ("D3", "D7") for f in r["findings"])     # nothing asks for a React export


def test_next_app_router_pages_in_js_are_screens(tmp_path, monkeypatch):
    """A Next.js export copied in as-is: app/<route>/page.js files are the screens."""
    root = tmp_path / "docs" / "designs" / "core"
    for rel, text in {
        "package.json": '{"dependencies": {"next": "15.0.0", "react": "19.0.0"}}',
        "next.config.js": "module.exports = {}",
        "app/layout.js": "export default function L({children}) { return children }",
        "app/page.js": "export default function Home() { return null }",
        "app/orders/page.js": "export default function Orders() { return null }",
        "app/design-system/page.js": "export default function DS() { return null }",
        "app/globals.css": ":root { --background: #ffffff; --foreground: #111111; --primary: #0f766e; }",
        "components/ui/Button.jsx": "export const Button = () => null",
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    monkeypatch.chdir(tmp_path)
    names = [s["name"] for s in _ingest(module="core")["manifest"]["screens"]]
    assert sorted(names) == ["index", "orders"]      # design-system page, layout, config and ui/ are not screens


def test_a_note_that_a_state_does_not_apply_is_not_the_state(tmp_path, monkeypatch):
    root = tmp_path / "docs" / "designs" / "app"
    root.mkdir(parents=True)
    (root / "tokens.css").write_text(":root { --background: #ffffff; --foreground: #111111; --primary: #0f766e; }")
    (root / "Frame - Book.dc.html").write_text(
        "<!-- empty: not applicable (there are always slots) · no disabled state -->"
        "<!-- state: loading --><p>Loading…</p><!-- state: error --><p class='err'>Slot taken</p>")
    monkeypatch.chdir(tmp_path)
    screen = _ingest(module="app")["manifest"]["screens"][0]
    assert screen["states"] == ["loading", "error"]
