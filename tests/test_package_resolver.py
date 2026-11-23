import json
import shutil
from pathlib import Path

import pytest

from tools.epav import package_resolver as pr

LOCKS = Path(__file__).parent / "fixtures" / "locks"


# ── lock readers ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("reader,lock,names,expected", [
    (pr._read_npm_lock, "package-lock.json", ["react", "@supabase/supabase-js", "absent"],
     {"react": "19.3.1", "@supabase/supabase-js": "2.119.2"}),
    (pr._read_pnpm_lock, "pnpm-lock.yaml", ["react", "@scope/pkg"], {"react": "19.3.1", "@scope/pkg": "2.0.4"}),
    (pr._read_yarn_lock, "yarn.lock", ["react", "@scope/pkg"], {"react": "19.3.1", "@scope/pkg": "2.0.4"}),
    (pr._read_bun_lock, "bun.lock", ["react", "@scope/pkg"], {"react": "19.3.1", "@scope/pkg": "2.0.4"}),
    (pr._read_toml_packages, "uv.lock", ["Django", "typing_extensions"], {"Django": "5.2.19", "typing_extensions": "4.15.0"}),
    (pr._read_toml_packages, "poetry.lock", ["django"], {"django": "5.2.19"}),
    (pr._read_pipfile_lock, "Pipfile.lock", ["django", "typing_extensions"], {"django": "5.2.19", "typing_extensions": "4.15.0"}),
    (pr._read_composer_lock, "composer.lock", ["laravel/framework"], {"laravel/framework": "11.45.1"}),
    (pr._read_gemfile_lock, "Gemfile.lock", ["rails", "nokogiri", "rack"], {"rails": "7.2.4", "nokogiri": "1.18.9"}),
    (pr._read_nuget_lock, "packages.lock.json", ["newtonsoft.json"], {"newtonsoft.json": "13.0.4"}),
    (pr._read_package_resolved, "Package.resolved", ["https://github.com/apple/swift-argument-parser.git"],
     {"https://github.com/apple/swift-argument-parser.git": "1.8.2"}),
    (pr._read_mix_lock, "mix.lock", ["phoenix"], {"phoenix": "1.7.21"}),
    (pr._read_cabal_freeze, "cabal.project.freeze", ["aeson", "text"], {"aeson": "2.2.3.0", "text": "2.1.2"}),
    (pr._read_conan_lock, "conan.lock", ["fmt", "zlib"], {"fmt": "10.2.1", "zlib": "1.3.1"}),
    (pr._read_pubspec_lock, "pubspec.lock", ["http"], {"http": "1.6.0"}),
    (pr._read_go_mod, "go.mod", ["github.com/gin-gonic/gin", "github.com/gin-gonic"], {"github.com/gin-gonic/gin": "1.12.0"}),
    (pr._read_cargo_lock, "Cargo.lock", ["serde"], {"serde": "1.0.228"}),
])
def test_lock_readers(reader, lock, names, expected):
    assert reader(LOCKS / lock, names) == expected


def test_pip_report_reader():
    report = (LOCKS / "pip-report.json").read_text()
    assert pr._read_pip_report(report, ["requests", "typing-extensions"]) == {"requests": "2.33.1", "typing-extensions": "4.15.0"}


# ── spec parsing / version picking ──────────────────────────────────────────

@pytest.mark.parametrize("spec,expected", [
    ("next@^16", ("next", "^16")),
    ("@supabase/supabase-js@2", ("@supabase/supabase-js", "2")),
    ("@scope/pkg", ("@scope/pkg", "")),
    ("django>=5,<6", ("django", ">=5,<6")),
    ("github.com/gin-gonic/gin@1", ("github.com/gin-gonic/gin", "1")),
    ("https://github.com/vapor/vapor@4", ("https://github.com/vapor/vapor", "4")),
    ("react", ("react", "")),
])
def test_split_spec(spec, expected):
    assert pr._split_spec(spec) == expected


@pytest.mark.parametrize("spec,expected", [
    ("django@5", "django>=5,<6"), ("django@^5.1", "django>=5.1,<6"), ("django>=5", "django>=5"),
    ("django@~5.1", "django>=5.1,<5.2"), ("django@5.2.3", "django==5.2.3"), ("django", "django"),
])
def test_py_req(spec, expected):
    assert pr._py_req(spec) == expected


def test_pick_skips_unstable_and_respects_major():
    versions = ["3.4.0", "3.5.16", "4.0.0-M1", "4.0.0-RC1", "2.7.18", "5.3.0.RELEASE"]
    assert pr._pick(versions, "3") == "3.5.16"
    assert pr._pick(versions, "") == "5.3.0.RELEASE"
    assert pr._pick(versions, "~3.4") == "3.4.0"
    assert pr._pick(versions, "3.4.0") == "3.4.0"
    assert pr._pick(versions, "9") is None


# ── detection / fallbacks ───────────────────────────────────────────────────

@pytest.mark.parametrize("hint,pm", [
    ("Next.js 16 TypeScript", "npm"),
    ("Next.js with pnpm", "pnpm"),
    ("Django 5 managed with uv", "uv"),
    ("Django 5 with Poetry", "poetry"),
    ("Laravel 11", "composer"),
    ("Rails 7", "bundler"),
    ("ASP.NET Core 8", "dotnet"),
    ("Spring Boot 3 with Gradle", "gradle"),
    ("Spring Boot 3", "maven"),
    ("Phoenix on Elixir", "mix"),
    ("Flutter 3", "pub"),
    ("Go 1.23 with Gin framework", "go"),
    ("Rust Axum", "cargo"),
    ("Vapor (Swift)", "swiftpm"),
    ("iOS app, deps via CocoaPods", "cocoapods"),
    ("Play Framework in Scala", "sbt"),
    ("Haskell servant", "cabal"),
    ("C++ with Qt", "conan"),
    ("something nobody has heard of", ""),
    ("", ""),
])
def test_detect_package_manager(hint, pm):
    assert pr._detect_package_manager(hint) == pm


def test_unknown_package_manager_is_unsupported_not_error():
    r = pr.resolve(["x"], "weirdpm")
    assert r["status"] == "unsupported" and r["package_manager"] == "weirdpm"
    assert "never from memory" in r["instructions"]
    assert "npm" in r["supported"]


def test_undetectable_hint_does_not_guess_npm():
    r = pr.resolve(["x"], "", "a proprietary in-house stack")
    assert r["status"] == "unsupported" and r["package_manager"] == "unknown"
    assert "pass package_manager explicitly" in r["instructions"]


def test_missing_binary_reports_tool_missing(monkeypatch):
    monkeypatch.setattr(pr.shutil, "which", lambda _: None)
    r = pr.resolve(["serde@1"], "cargo")
    assert r["status"] == "tool_missing" and "`cargo` is not installed" in r["instructions"]


def test_registry_backed_resolution_uses_registry(monkeypatch):
    xml = "<metadata><versioning><versions><version>3.4.0</version><version>3.5.16</version><version>4.0.0-M1</version></versions></versioning></metadata>"
    monkeypatch.setattr(pr, "_http_get", lambda url: xml)
    r = pr.resolve(["org.springframework.boot:spring-boot-starter-web:3"], "gradle")
    assert r["status"] == "resolved"
    assert r["versions"] == {"org.springframework.boot:spring-boot-starter-web": "3.5.16"}


def test_tool_output_is_json():
    from mcp.server.fastmcp import FastMCP
    m = FastMCP("t")
    pr.register_package_resolver_tool(m)
    fn = m._tool_manager._tools["resolve_package_versions"].fn
    import asyncio
    assert json.loads(asyncio.run(fn(packages=["x"], package_manager="weirdpm")))["status"] == "unsupported"


# ── real runs (skipped when the tool is not installed) ──────────────────────

_REAL = [
    ("npm", ["react@19"], "react"),
    ("pnpm", ["react@19"], "react"),
    ("yarn", ["react@19"], "react"),
    ("bun", ["react@19"], "react"),
    ("uv", ["django@5"], "django"),
    ("poetry", ["django@5"], "django"),
    ("pip", ["requests@2"], "requests"),
    ("bundle", ["rails@7"], "rails"),
    ("composer", ["monolog/monolog@3"], "monolog/monolog"),
    ("swift", ["https://github.com/apple/swift-argument-parser@1"], "https://github.com/apple/swift-argument-parser"),
    ("go", ["github.com/google/uuid@1"], "github.com/google/uuid"),
    ("dart", ["http@1"], "http"),
    ("cargo", ["serde@1"], "serde"),
    ("dotnet", ["Newtonsoft.Json@13"], "Newtonsoft.Json"),
]
_BIN_TO_PM = {"bundle": "bundler", "swift": "swiftpm", "dart": "pub"}


@pytest.mark.network
@pytest.mark.parametrize("binary,pkgs,name", _REAL)
def test_real_resolution(binary, pkgs, name):
    if shutil.which(binary) is None:
        pytest.skip(f"{binary} not installed")
    r = pr.resolve(pkgs, _BIN_TO_PM.get(binary, binary))
    assert r["status"] == "resolved", r
    assert r["versions"][name][0].isdigit()


def test_slow_resolve_does_not_block_other_tools(monkeypatch):
    """Rule 7: a package manager can run for minutes; other MCP tools must keep answering."""
    import asyncio
    import time
    from mcp.server.fastmcp import FastMCP

    def slow_resolve(*a, **k):
        time.sleep(1.0)
        return {"status": "resolved", "versions": {}}
    monkeypatch.setattr(pr, "resolve", slow_resolve)
    m = FastMCP("t")
    pr.register_package_resolver_tool(m)
    tool = m._tool_manager._tools["resolve_package_versions"].fn

    async def scenario():
        done = {}
        async def other_tool():
            await asyncio.sleep(0.05)
            done["other"] = time.monotonic()
        start = time.monotonic()
        await asyncio.gather(tool(packages=["x"], package_manager="npm"), other_tool())
        done["resolve"] = time.monotonic()
        return start, done

    start, done = asyncio.run(scenario())
    assert done["other"] - start < 0.5          # answered while the resolve was still running
    assert done["resolve"] - start >= 1.0
