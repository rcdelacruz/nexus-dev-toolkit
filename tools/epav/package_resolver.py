"""
resolve_package_versions — MCP tool for Day 0 APPLY.

Given a package manager and a list of packages with optional constraints
(derived from the arch doc), resolves exact pinned versions from the real
source of truth — never from AI memory:

  - Most ecosystems: write a minimal manifest in a temp directory, run the
    real package manager's lock step, read the lock file it produced.
  - JVM (maven / gradle / sbt) and CocoaPods: those tools can't resolve in an
    empty directory (they need a real build or an Xcode project), so the
    official registry metadata is queried directly instead (Maven Central,
    CocoaPods trunk).

Never hardcodes versions. Unknown package managers and missing binaries get a
structured "unsupported" / "tool_missing" answer with instructions, instead of
a silent wrong guess.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from mcp.server.fastmcp import FastMCP

from tools.epav import stack_catalog

_TIMEOUT = 120
_HTTP_TIMEOUT = 20
_UNSTABLE = re.compile(
    r"(?:^|[.\-_+\d])(alpha|beta|a|b|rc|cr|snapshot|preview|pre|dev|canary|nightly|milestone|ea|m)(?:\d|[.\-_+]|$)",
    re.I,
)


# ── spec parsing ────────────────────────────────────────────────────────────

def _split_spec(pkg: str) -> tuple[str, str]:
    """"next@^16" -> ("next", "^16"); "@scope/x@2" -> ("@scope/x", "2");
    "django>=5,<6" -> ("django", ">=5,<6"); "g:a:3" (JVM) -> ("g:a", "3")."""
    pkg = pkg.strip()
    if pkg.startswith("@"):
        name, sep, ver = pkg[1:].partition("@")
        return ("@" + name, ver) if sep else (pkg, "")
    if "@" in pkg:
        name, _, ver = pkg.rpartition("@")
        return name, ver
    m = re.match(r"^([A-Za-z0-9_.\-\[\]/]+)\s*((?:[<>=!~^]).*)$", pkg)
    if m:
        return m.group(1), m.group(2).strip()
    return pkg, ""


def _bounds(constraint: str) -> tuple[str, int] | None:
    """"16" / "^16" / "^16.2" / "16.x" -> ("16" or "16.2", 16); None if not a simple major constraint."""
    c = constraint.strip()
    m = re.fullmatch(r"(\^?)(\d+)((?:\.\d+)*)(?:\.[x*])?", c)
    if not m:
        return None
    if not m.group(1) and m.group(3).count(".") >= 2:
        return None  # a full version like "5.2.3" is an exact pin, not a major range
    return m.group(2) + m.group(3), int(m.group(2))


def _norm_py(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.split("[")[0]).lower()


def _py_req(pkg: str) -> str:
    name, c = _split_spec(pkg)
    if not c:
        return name
    if re.fullmatch(r"~\d+\.\d+.*", c):
        major, minor = c[1:].split(".")[:2]
        return f"{name}>={major}.{minor},<{major}.{int(minor) + 1}"
    if c[0] in "<>=!~":
        return f"{name}{c}"
    b = _bounds(c)
    if b:
        return f"{name}>={b[0]},<{b[1] + 1}"
    return f"{name}=={c}"


def _version_key(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:4])


def _pick(versions: list[str], constraint: str) -> str | None:
    """Highest stable version matching a simple constraint (major / ^ / ~ / exact)."""
    stable = [v for v in versions if not _UNSTABLE.search(v)]
    c = constraint.strip()
    if c and re.fullmatch(r"\d+\.\d+\.\d+.*", c) and c in versions:
        return c
    if c.startswith("~") and re.fullmatch(r"~\d+\.\d+", c):
        prefix = tuple(int(x) for x in c[1:].split("."))
        stable = [v for v in stable if _version_key(v)[:2] == prefix]
    elif c:
        b = _bounds(c)
        if not b:
            return None
        stable = [v for v in stable if _version_key(v)[:1] == (b[1],) and _version_key(v) >= _version_key(b[0])]
    return max(stable, key=_version_key) if stable else None


# ── lock readers ────────────────────────────────────────────────────────────

def _read_npm_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    try:
        deps = json.loads(lock_path.read_text()).get("packages", {})
    except Exception:
        return {}
    return {n: deps[f"node_modules/{n}"]["version"] for n in names if "version" in deps.get(f"node_modules/{n}", {})}


def _read_pnpm_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    text = lock_path.read_text()
    for n in names:
        m = re.search(rf"^\s+'?{re.escape(n)}'?:\n\s+specifier: .*\n\s+version: '?([0-9][^\s('\n]*)", text, re.M)
        if m:
            out[n] = m.group(1)
    return out


def _read_yarn_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    text = lock_path.read_text()
    for n in names:
        m = re.search(rf'^"?{re.escape(n)}@[^\n]*:\n(?:\s+[^\n]*\n)*?\s+version:? "?([0-9][^"\s]*)', text, re.M)
        if m:
            out[n] = m.group(1)
    return out


def _read_bun_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    text = lock_path.read_text()
    out: dict[str, str] = {}
    for n in names:
        m = re.search(rf'"{re.escape(n)}":\s*\[\s*"{re.escape(n)}@([^"]+)"', text)
        if m:
            out[n] = m.group(1)
    return out


def _read_toml_packages(lock_path: Path, names: list[str]) -> dict[str, str]:
    """uv.lock / poetry.lock: [[package]] blocks with name = / version =."""
    wanted = {_norm_py(n): n for n in names}
    out: dict[str, str] = {}
    for block in lock_path.read_text().split("[[package]]")[1:]:
        name = re.search(r'^name = "([^"]+)"', block, re.M)
        ver = re.search(r'^version = "([^"]+)"', block, re.M)
        if name and ver and _norm_py(name.group(1)) in wanted:
            out[wanted[_norm_py(name.group(1))]] = ver.group(1)
    return out


def _read_pipfile_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    try:
        default = {_norm_py(k): v for k, v in json.loads(lock_path.read_text()).get("default", {}).items()}
    except Exception:
        return {}
    return {n: default[_norm_py(n)]["version"].lstrip("=") for n in names if "version" in default.get(_norm_py(n), {})}


def _read_pip_report(stdout: str, names: list[str]) -> dict[str, str]:
    try:
        installs = json.loads(stdout).get("install", [])
    except Exception:
        return {}
    found = {_norm_py(i["metadata"]["name"]): i["metadata"]["version"] for i in installs if "metadata" in i}
    return {n: found[_norm_py(n)] for n in names if _norm_py(n) in found}


def _read_composer_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    try:
        pkgs = {p["name"].lower(): p["version"] for p in json.loads(lock_path.read_text()).get("packages", [])}
    except Exception:
        return {}
    return {n: pkgs[n.lower()].lstrip("v") for n in names if n.lower() in pkgs}


def _read_gemfile_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    specs = dict(re.findall(r"^    ([A-Za-z0-9_.\-]+) \(([^)\s]+)\)$", lock_path.read_text(), re.M))
    return {n: specs[n].split("-")[0] for n in names if n in specs}


def _read_nuget_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    try:
        frameworks = json.loads(lock_path.read_text()).get("dependencies", {})
    except Exception:
        return {}
    found: dict[str, str] = {}
    for deps in frameworks.values():
        for k, v in deps.items():
            found.setdefault(k.lower(), v.get("resolved", ""))
    return {n: found[n.lower()] for n in names if found.get(n.lower())}


def _swift_identity(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git").lower()


def _read_package_resolved(lock_path: Path, names: list[str]) -> dict[str, str]:
    try:
        data = json.loads(lock_path.read_text())
    except Exception:
        return {}
    pins = data.get("pins") or data.get("object", {}).get("pins", [])
    found = {}
    for p in pins:
        ident = (p.get("identity") or p.get("package") or "").lower()
        ver = (p.get("state") or {}).get("version")
        if ident and ver:
            found[ident] = ver
    return {n: found[_swift_identity(n)] for n in names if _swift_identity(n) in found}


def _read_mix_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    found = dict(re.findall(r'"([a-z0-9_]+)": \{:hex, :[a-z0-9_]+, "([^"]+)"', lock_path.read_text()))
    return {n: found[n] for n in names if n in found}


def _read_cabal_freeze(lock_path: Path, names: list[str]) -> dict[str, str]:
    found = dict(re.findall(r"any\.([A-Za-z0-9\-]+) ==([0-9.]+)", lock_path.read_text()))
    return {n: found[n] for n in names if n in found}


def _read_conan_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    try:
        requires = json.loads(lock_path.read_text()).get("requires", [])
    except Exception:
        return {}
    found = {}
    for ref in requires:
        name, _, rest = ref.partition("/")
        found.setdefault(name, re.split(r"[#%@]", rest)[0])
    return {n: found[n] for n in names if n in found}


def _read_pubspec_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    current = None
    for line in lock_path.read_text().splitlines():
        m = re.match(r"^  ([A-Za-z0-9_]+):\s*$", line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r'^    version: "?([^"\s]+)"?', line)
        if current and m and current in names:
            out[current] = m.group(1)
    return out


def _read_go_mod(lock_path: Path, names: list[str]) -> dict[str, str]:
    found = dict(re.findall(r"^\s*(?:require\s+)?([^\s()]+)\s+v([^\s]+)", lock_path.read_text(), re.M))
    return {n: found[n] for n in names if n in found}


def _read_cargo_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for block in lock_path.read_text().split("[[package]]")[1:]:
        name = re.search(r'^name = "([^"]+)"', block, re.M)
        ver = re.search(r'^version = "([^"]+)"', block, re.M)
        if name and ver and name.group(1) in names and name.group(1) not in out:
            out[name.group(1)] = ver.group(1)
    return out


# ── manifest writers (temp dir setup) ───────────────────────────────────────

def _write(tmp: Path, name: str, text: str) -> None:
    (tmp / name).write_text(text, encoding="utf-8")


def _setup_node(tmp: Path, pkgs: list[str]) -> None:
    _write(tmp, "package.json", json.dumps({"name": "resolve-temp", "version": "0.0.1", "private": True}))


def _setup_composer(tmp: Path, pkgs: list[str]) -> None:
    require = {}
    for p in pkgs:
        name, c = _split_spec(p.replace(":", "@", 1) if ":" in p and "@" not in p else p)
        b = _bounds(c) if c else None
        require[name] = f"^{b[0]}" if b else (c or "*")
    _write(tmp, "composer.json", json.dumps({"name": "nexus/resolve-temp", "require": require, "minimum-stability": "stable"}))


def _setup_bundler(tmp: Path, pkgs: list[str]) -> None:
    lines = ['source "https://rubygems.org"']
    for p in pkgs:
        name, c = _split_spec(p)
        b = _bounds(c) if c else None
        ver = f'"~> {b[0]}"' if b else (f'"{c}"' if c else "")
        lines.append(f'gem "{name}"' + (f", {ver}" if ver else ""))
    _write(tmp, "Gemfile", "\n".join(lines) + "\n")


def _setup_dotnet(tmp: Path, pkgs: list[str]) -> None:
    sdk = subprocess.run(["dotnet", "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    tfm = f"net{sdk.split('.')[0]}.0" if sdk[:1].isdigit() else "net8.0"
    refs = []
    for p in pkgs:
        name, c = _split_spec(p)
        b = _bounds(c) if c else None
        ver = f"{b[1]}.*" if b else (c or "*")
        refs.append(f'    <PackageReference Include="{name}" Version="{ver}" />')
    _write(tmp, "resolve.csproj", (
        '<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n'
        f"    <TargetFramework>{tfm}</TargetFramework>\n"
        "    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>\n"
        "  </PropertyGroup>\n  <ItemGroup>\n" + "\n".join(refs) + "\n  </ItemGroup>\n</Project>\n"
    ))


def _setup_swiftpm(tmp: Path, pkgs: list[str]) -> None:
    deps = []
    for p in pkgs:
        url, c = _split_spec(p)
        b = _bounds(c) if c else None
        if b:
            lo = ".".join((b[0].split(".") + ["0", "0"])[:3])
            deps.append(f'        .package(url: "{url}", from: "{lo}"),')
        elif c:
            deps.append(f'        .package(url: "{url}", exact: "{c}"),')
        else:
            deps.append(f'        .package(url: "{url}", "0.0.0"..<"100000.0.0"),')
    _write(tmp, "Package.swift", (
        "// swift-tools-version:5.9\nimport PackageDescription\n\n"
        'let package = Package(\n    name: "ResolveTemp",\n    dependencies: [\n'
        + "\n".join(deps) + "\n    ],\n    targets: []\n)\n"
    ))


def _setup_mix(tmp: Path, pkgs: list[str]) -> None:
    deps = []
    for p in pkgs:
        name, c = _split_spec(p)
        b = _bounds(c) if c else None
        req = f"~> {'.'.join((b[0].split('.') + ['0'])[:2])}" if b else (c or ">= 0.0.0")
        deps.append(f'      {{:{name}, "{req}"}}')
    _write(tmp, "mix.exs", (
        "defmodule ResolveTemp.MixProject do\n  use Mix.Project\n\n"
        '  def project, do: [app: :resolve_temp, version: "0.0.1", deps: deps()]\n\n'
        "  defp deps do\n    [\n" + ",\n".join(deps) + "\n    ]\n  end\nend\n"
    ))


def _setup_cabal(tmp: Path, pkgs: list[str]) -> None:
    deps = []
    for p in pkgs:
        name, c = _split_spec(p)
        b = _bounds(c) if c else None
        deps.append(f"{name} >={b[0]} && <{b[1] + 1}" if b else (f"{name} {'==' + c if c[:1].isdigit() else c}" if c else name))
    _write(tmp, "cabal.project", "packages: .\n")
    _write(tmp, "resolve-temp.cabal", (
        "cabal-version: 2.4\nname: resolve-temp\nversion: 0.0.1\nbuild-type: Simple\n\n"
        "library\n  default-language: Haskell2010\n  build-depends: base, " + ", ".join(deps) + "\n"
    ))


def _setup_conan(tmp: Path, pkgs: list[str]) -> None:
    reqs = []
    for p in pkgs:
        name, c = _split_spec(p.replace("/", "@", 1) if "/" in p and "@" not in p else p)
        b = _bounds(c) if c else None
        reqs.append(f"{name}/[>={b[0]} <{b[1] + 1}]" if b else (f"{name}/{c}" if c else f"{name}/[>=0.0.0]"))
    _write(tmp, "conanfile.txt", "[requires]\n" + "\n".join(reqs) + "\n")


def _setup_pub(tmp: Path, pkgs: list[str]) -> None:
    flutter = shutil.which("flutter") is not None
    deps = "dependencies:\n  flutter:\n    sdk: flutter\n" if flutter else "dependencies: {}\n"
    _write(tmp, "pubspec.yaml", f"name: resolve_temp\nenvironment:\n  sdk: ^3.0.0\n{deps}")


def _setup_uv(tmp: Path, pkgs: list[str]) -> None:
    _write(tmp, "pyproject.toml", '[project]\nname = "resolve-temp"\nversion = "0.0.1"\nrequires-python = ">=3.10"\ndependencies = []\n')


def _pub_arg(p: str) -> str:
    name, c = _split_spec(p)
    b = _bounds(c) if c else None
    if b:
        return f"{name}:^{'.'.join((b[0].split('.') + ['0', '0'])[:3])}"
    return f"{name}:{c}" if c else name


def _go_arg(p: str) -> str:
    name, c = _split_spec(p)
    b = _bounds(c) if c else None
    if b:
        return f"{name}@v{b[0]}"
    return f"{name}@{c if c.startswith('v') else 'v' + c}" if c else f"{name}@latest"


# ── registry-backed resolvers (no local build possible) ─────────────────────

def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "nexus-dev-toolkit"})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as r:
        return r.read().decode("utf-8")


def _resolve_maven_central(pkgs: list[str]) -> tuple[dict[str, str], list[str]]:
    versions, errors = {}, []
    for p in pkgs:
        coords, c = _split_spec(p)
        parts = coords.split(":")
        if len(parts) == 3 and not c:
            coords, c = ":".join(parts[:2]), parts[2]
            parts = parts[:2]
        if len(parts) != 2:
            errors.append(f"{p}: expected 'group:artifact[@version]'")
            continue
        group, artifact = parts
        url = f"https://repo1.maven.org/maven2/{group.replace('.', '/')}/{artifact}/maven-metadata.xml"
        try:
            found = re.findall(r"<version>([^<]+)</version>", _http_get(url))
        except Exception as e:
            errors.append(f"{coords}: Maven Central lookup failed ({e})")
            continue
        picked = _pick(found, c)
        if picked:
            versions[coords] = picked
        else:
            errors.append(f"{coords}: no stable version matches '{c}'")
    return versions, errors


def _resolve_cocoapods(pkgs: list[str]) -> tuple[dict[str, str], list[str]]:
    versions, errors = {}, []
    for p in pkgs:
        name, c = _split_spec(p)
        try:
            data = json.loads(_http_get(f"https://trunk.cocoapods.org/api/v1/pods/{urllib.parse.quote(name)}"))
        except Exception as e:
            errors.append(f"{name}: CocoaPods trunk lookup failed ({e})")
            continue
        picked = _pick([v["name"] for v in data.get("versions", [])], c)
        if picked:
            versions[name] = picked
        else:
            errors.append(f"{name}: no stable version matches '{c}'")
    return versions, errors


# ── registry ────────────────────────────────────────────────────────────────
# Each entry:
#   aliases     words in a stack hint that name this package manager directly
#   binary      CLI that must be on PATH (None for registry-backed entries)
#   setup       writes the minimal manifest into the temp dir
#   commands    list of commands to run, built from the package specs
#   lock_file   file the reader parses ("<stdout>" = command output)
#   reader      parses versions out of the lock file
#   registry    registry-backed resolver used instead of a local CLI

def _names(pkgs: list[str]) -> list[str]:
    return [_split_spec(p)[0] for p in pkgs]


def _jvm_names(pkgs: list[str]) -> list[str]:
    return [":".join(_split_spec(p)[0].split(":")[:2]) for p in pkgs]


_PM_REGISTRY: dict[str, dict] = {
    "npm": {
        "aliases": ["npm"], "binary": "npm", "setup": _setup_node,
        "commands": lambda p: [["npm", "install", "--package-lock-only", "--legacy-peer-deps", *p]],
        "lock_file": "package-lock.json", "reader": _read_npm_lock,
    },
    "pnpm": {
        "aliases": ["pnpm"], "binary": "pnpm", "setup": _setup_node,
        "commands": lambda p: [["pnpm", "add", "--lockfile-only", *p]],
        "lock_file": "pnpm-lock.yaml", "reader": _read_pnpm_lock,
    },
    "yarn": {
        "aliases": ["yarn"], "binary": "yarn", "setup": _setup_node,
        "commands": lambda p: [["yarn", "add", "--ignore-scripts", *p]],
        "lock_file": "yarn.lock", "reader": _read_yarn_lock,
    },
    "bun": {
        "aliases": ["bun"], "binary": "bun", "setup": _setup_node,
        "commands": lambda p: [["bun", "add", "--ignore-scripts", *p]],
        "lock_file": "bun.lock", "reader": _read_bun_lock,
    },
    "pip": {
        "aliases": ["pip"], "binary": "pip", "setup": None,
        "commands": lambda p: [["pip", "install", "--dry-run", "--quiet", "--ignore-installed", "--report", "-", *map(_py_req, p)]],
        "lock_file": "<stdout>", "reader": None,
    },
    "uv": {
        "aliases": ["uv"], "binary": "uv", "setup": _setup_uv,
        "commands": lambda p: [["uv", "add", "--no-sync", *map(_py_req, p)]],
        "lock_file": "uv.lock", "reader": _read_toml_packages,
    },
    "poetry": {
        "aliases": ["poetry"], "binary": "poetry", "setup": None,
        "commands": lambda p: [["poetry", "init", "-n", "--name", "resolve-temp"], ["poetry", "add", "--lock", *map(_py_req, p)]],
        "lock_file": "poetry.lock", "reader": _read_toml_packages,
    },
    "pipenv": {
        "aliases": ["pipenv"], "binary": "pipenv", "setup": None,
        "commands": lambda p: [["pipenv", "install", *map(_py_req, p)]],
        "lock_file": "Pipfile.lock", "reader": _read_pipfile_lock,
        "env": {"PIPENV_VENV_IN_PROJECT": "1", "PIPENV_IGNORE_VIRTUALENVS": "1"},
    },
    "composer": {
        "aliases": ["composer", "packagist"], "binary": "composer", "setup": _setup_composer,
        "commands": lambda p: [["composer", "update", "--no-install", "--no-interaction", "--no-scripts", "--no-plugins"]],
        "lock_file": "composer.lock", "reader": _read_composer_lock,
        "names": lambda p: [_split_spec(x.replace(":", "@", 1) if ":" in x and "@" not in x else x)[0] for x in p],
    },
    "bundler": {
        "aliases": ["bundler", "rubygems", "gemfile"], "binary": "bundle", "setup": _setup_bundler,
        "commands": lambda p: [["bundle", "lock"]],
        "lock_file": "Gemfile.lock", "reader": _read_gemfile_lock,
    },
    "dotnet": {
        "aliases": ["nuget", "dotnet"], "binary": "dotnet", "setup": _setup_dotnet,
        "commands": lambda p: [["dotnet", "restore", "--use-lock-file"]],
        "lock_file": "packages.lock.json", "reader": _read_nuget_lock,
    },
    "swiftpm": {
        "aliases": ["swiftpm", "swift package manager", "spm"], "binary": "swift", "setup": _setup_swiftpm,
        "commands": lambda p: [["swift", "package", "resolve"]],
        "lock_file": "Package.resolved", "reader": _read_package_resolved,
    },
    "cocoapods": {
        "aliases": ["cocoapods", "podfile"], "binary": None, "registry": _resolve_cocoapods,
        "lock_file": None,
    },
    "mix": {
        "aliases": ["mix.exs", "hex.pm"], "binary": "mix", "setup": _setup_mix,
        "commands": lambda p: [["mix", "local.hex", "--force", "--if-missing"], ["mix", "deps.get"]],
        "lock_file": "mix.lock", "reader": _read_mix_lock,
    },
    "cabal": {
        "aliases": ["cabal", "hackage"], "binary": "cabal", "setup": _setup_cabal,
        "commands": lambda p: [["cabal", "update"], ["cabal", "freeze"]],
        "lock_file": "cabal.project.freeze", "reader": _read_cabal_freeze,
    },
    "conan": {
        "aliases": ["conan", "conanfile"], "binary": "conan", "setup": _setup_conan,
        "commands": lambda p: [["conan", "profile", "detect", "--exist-ok"], ["conan", "lock", "create", "."]],
        "lock_file": "conan.lock", "reader": _read_conan_lock,
        "names": lambda p: [_split_spec(x.replace("/", "@", 1) if "/" in x and "@" not in x else x)[0] for x in p],
    },
    "maven": {
        "aliases": ["maven", "mvn", "pom.xml"], "binary": None, "registry": _resolve_maven_central,
        "lock_file": None, "names": _jvm_names,
    },
    "gradle": {
        "aliases": ["gradle"], "binary": None, "registry": _resolve_maven_central,
        "lock_file": None, "names": _jvm_names,
    },
    "sbt": {
        "aliases": ["sbt"], "binary": None, "registry": _resolve_maven_central,
        "lock_file": None, "names": _jvm_names,
    },
    "pub": {
        "aliases": ["pub.dev", "pubspec"], "binary": "dart", "setup": _setup_pub,
        "commands": lambda p: [[("flutter" if shutil.which("flutter") else "dart"), "pub", "add", *map(_pub_arg, p)]],
        "lock_file": "pubspec.lock", "reader": _read_pubspec_lock,
    },
    "go": {
        "aliases": ["go modules", "go.mod"], "binary": "go", "setup": None,
        "commands": lambda p: [["go", "mod", "init", "resolvetemp"], ["go", "get", *map(_go_arg, p)]],
        "lock_file": "go.mod", "reader": _read_go_mod,
    },
    "cargo": {
        "aliases": ["cargo", "crates.io"], "binary": "cargo", "setup": None,
        "commands": lambda p: [["cargo", "init", "--lib", "--vcs", "none", "--name", "resolve_temp"], ["cargo", "add", *p], ["cargo", "generate-lockfile"]],
        "lock_file": "Cargo.lock", "reader": _read_cargo_lock,
    },
}

_MANUAL_INSTRUCTIONS = (
    "Pin exact versions yourself from that ecosystem's official registry or its own CLI "
    "(look them up now — never from memory), write them into the manifest without ranges, "
    "then run the package manager to produce the lock file."
)


def _detect_package_manager(hint: str | None) -> str:
    """Package manager named in the hint, else the first catalog tech that has one, else ""."""
    if not hint:
        return ""
    for pm, cfg in _PM_REGISTRY.items():
        for alias in cfg["aliases"]:
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(alias)}(?![A-Za-z0-9_])", hint, re.I):
                return pm
    return stack_catalog.package_manager_for(hint)


def _status(versions: dict, names: list[str]) -> tuple[str, list[str]]:
    missing = [n for n in names if n not in versions]
    if not missing:
        return "resolved", []
    return ("partial" if versions else "failed"), missing


def resolve(packages: list[str], package_manager: str = "", stack_hint: str = "") -> dict:
    pm = package_manager.strip().lower() or _detect_package_manager(stack_hint)
    if pm not in _PM_REGISTRY:
        return {
            "status": "unsupported",
            "package_manager": pm or "unknown",
            "versions": {},
            "supported": sorted(_PM_REGISTRY),
            "instructions": (
                ("Could not detect a package manager from stack_hint — pass package_manager explicitly. " if not pm else
                 f"'{pm}' is not supported by resolve_package_versions. ") + _MANUAL_INSTRUCTIONS
            ),
        }

    cfg = _PM_REGISTRY[pm]
    names = cfg.get("names", _names)(packages)

    if cfg.get("registry"):
        versions, errors = cfg["registry"](packages)
        status, missing = _status(versions, names)
        return {"status": status, "package_manager": pm, "versions": versions, "missing": missing,
                "lock_file": None, "source": "registry", "errors": errors}

    binary = cfg["binary"]
    if binary and shutil.which(binary) is None:
        return {
            "status": "tool_missing",
            "package_manager": pm,
            "versions": {},
            "instructions": f"`{binary}` is not installed on this machine. Install it and call again, or: {_MANUAL_INSTRUCTIONS}",
        }

    tmp = Path(tempfile.mkdtemp(prefix="nexus-resolve-"))
    errors: list[str] = []
    stdout = ""
    try:
        if cfg.get("setup"):
            cfg["setup"](tmp, packages)
        env = {**os.environ, **cfg["env"]} if cfg.get("env") else None
        for cmd in cfg["commands"](packages):
            result = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=_TIMEOUT, env=env)
            stdout = result.stdout
            if result.returncode != 0:
                errors.append(f"{' '.join(cmd[:3])}: {(result.stderr or result.stdout)[:500]}")
                break

        lock_file = cfg["lock_file"]
        if lock_file == "<stdout>":
            versions = _read_pip_report(stdout, names)
        else:
            lock_path = tmp / lock_file
            versions = cfg["reader"](lock_path, names) if lock_path.exists() else {}
        status, missing = _status(versions, names)
        return {"status": status, "package_manager": pm, "versions": versions, "missing": missing,
                "lock_file": None if lock_file == "<stdout>" else lock_file, "errors": errors}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "package_manager": pm, "versions": {}, "errors": [f"Resolution timed out after {_TIMEOUT}s"]}
    except Exception as e:
        return {"status": "failed", "package_manager": pm, "versions": {}, "errors": [str(e)]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def register_package_resolver_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    async def resolve_package_versions(
        packages: list[str],
        package_manager: str = "",
        stack_hint: str = "",
    ) -> str:
        """
        Resolve exact pinned package versions from the real package manager or registry.

        Runs in a temp directory — does not modify the project. Returns exact
        versions so Day 0 APPLY can write deterministic package manifests.

        Args:
            packages: Packages with optional constraints, in the ecosystem's own naming:
                      npm ["next@16", "@supabase/supabase-js@2"], Python ["django@5"],
                      JVM ["org.springframework.boot:spring-boot-starter-web@3"],
                      Go ["github.com/gin-gonic/gin@1"], SwiftPM ["https://github.com/vapor/vapor@4"],
                      Composer ["laravel/framework@11"], Conan ["fmt@10"].
            package_manager: npm | pnpm | yarn | bun | pip | uv | poetry | pipenv | composer |
                             bundler | dotnet | swiftpm | cocoapods | mix | cabal | conan |
                             maven | gradle | sbt | pub | go | cargo.
                             Auto-detected from stack_hint if omitted.
            stack_hint: Free-text hint from arch doc, e.g. "Laravel 11 on PHP 8.3".

        Returns:
            JSON: { "status": "resolved" | "partial" | "failed" | "unsupported" | "tool_missing",
                    "versions": {"next": "16.3.2", ...}, "missing": [...],
                    "package_manager": "npm", "lock_file": "package-lock.json",
                    "errors": [...], "instructions": "..." (when not resolved) }
        """
        # Package managers can run for minutes; run them in a worker thread so the MCP server
        # keeps answering other tool calls meanwhile.
        return json.dumps(await asyncio.to_thread(resolve, packages, package_manager, stack_hint))
