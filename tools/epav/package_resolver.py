"""
resolve_package_versions — MCP tool for Day 0 APPLY.

Given a package manager type and a list of packages with optional major-version
constraints (derived from the arch doc), spins up a temp directory, runs the
package manager's resolution command, reads the lock file, and returns exact
pinned versions. Never hardcodes versions or stack-specific logic beyond what
is needed to dispatch the right CLI.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from mcp.server.fastmcp import FastMCP

_PM_REGISTRY: dict[str, dict] = {
    "npm": {
        "detect": ["package.json", "package-lock.json", ".npmrc"],
        "init": ["npm", "init", "-y"],
        "resolve": ["npm", "install", "--package-lock-only", "--legacy-peer-deps"],
        "lock_file": "package-lock.json",
    },
    "pnpm": {
        "detect": ["pnpm-lock.yaml", "pnpm-workspace.yaml"],
        "init": ["pnpm", "init"],
        "resolve": ["pnpm", "install", "--lockfile-only"],
        "lock_file": "pnpm-lock.yaml",
    },
    "yarn": {
        "detect": ["yarn.lock", ".yarnrc.yml"],
        "init": ["yarn", "init", "-y"],
        "resolve": ["yarn", "install", "--frozen-lockfile"],
        "lock_file": "yarn.lock",
    },
    "maven": {
        "detect": ["pom.xml"],
        "init": None,
        "resolve": ["mvn", "dependency:resolve", "-q"],
        "lock_file": None,
    },
    "gradle": {
        "detect": ["build.gradle", "build.gradle.kts"],
        "init": None,
        "resolve": ["gradle", "dependencies", "--configuration", "runtimeClasspath"],
        "lock_file": "gradle.lockfile",
    },
    "pub": {
        "detect": ["pubspec.yaml"],
        "init": None,
        "resolve": ["flutter", "pub", "get"],
        "lock_file": "pubspec.lock",
    },
    "go": {
        "detect": ["go.mod"],
        "init": None,
        "resolve": ["go", "mod", "tidy"],
        "lock_file": "go.sum",
    },
    "cargo": {
        "detect": ["Cargo.toml"],
        "init": None,
        "resolve": ["cargo", "update"],
        "lock_file": "Cargo.lock",
    },
    "pip": {
        "detect": ["requirements.txt", "pyproject.toml"],
        "init": None,
        "resolve": ["pip", "install", "--dry-run", "--report", "-"],
        "lock_file": None,
    },
}


def _detect_package_manager(hint: str | None) -> str:
    if not hint:
        return "npm"
    hint_lower = hint.lower()
    for pm in _PM_REGISTRY:
        if pm in hint_lower:
            return pm
    if any(k in hint_lower for k in ["node", "next", "react", "vite", "typescript"]):
        return "npm"
    if any(k in hint_lower for k in ["flutter", "dart"]):
        return "pub"
    if any(k in hint_lower for k in ["java", "spring", "kotlin"]):
        return "maven"
    if "python" in hint_lower:
        return "pip"
    if "rust" in hint_lower:
        return "cargo"
    return "npm"


def _strip_version_spec(pkg: str) -> str:
    if pkg.startswith("@"):
        rest = pkg[1:]
        if "@" in rest:
            return f"@{rest[:rest.index('@')]}"
        return pkg
    return pkg.split("@")[0] if "@" in pkg else pkg


def _read_npm_lock(lock_path: Path, packages: list[str]) -> dict[str, str]:
    try:
        lock = json.loads(lock_path.read_text())
        deps = lock.get("packages", {})
        return {
            _strip_version_spec(pkg): deps.get(f"node_modules/{_strip_version_spec(pkg)}", {}).get("version", "unknown")
            for pkg in packages
            if f"node_modules/{_strip_version_spec(pkg)}" in deps
        }
    except Exception:
        return {}


def _read_pubspec_lock(lock_path: Path, packages: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    try:
        current_pkg = None
        for line in lock_path.read_text().splitlines():
            stripped = line.strip()
            if stripped.endswith(":") and not stripped.startswith(" "):
                current_pkg = stripped[:-1]
            elif current_pkg and stripped.startswith("version:"):
                ver = stripped.split(":", 1)[1].strip().strip('"')
                if current_pkg in packages:
                    versions[current_pkg] = ver
    except Exception:
        pass
    return versions


def _read_go_sum(lock_path: Path, packages: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    try:
        for line in lock_path.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                mod, ver = parts[0], parts[1].split("/")[0]
                for pkg in packages:
                    if pkg in mod and pkg not in versions:
                        versions[pkg] = ver.lstrip("v")
    except Exception:
        pass
    return versions


def _read_cargo_lock(lock_path: Path, packages: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    try:
        current_name = None
        for line in lock_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("name ="):
                current_name = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("version =") and current_name:
                ver = line.split("=", 1)[1].strip().strip('"')
                if current_name in packages and current_name not in versions:
                    versions[current_name] = ver
    except Exception:
        pass
    return versions


def _read_lock_file(pm: str, lock_path: Path, packages: list[str]) -> dict[str, str]:
    if pm in ("npm", "pnpm", "yarn"):
        return _read_npm_lock(lock_path, packages)
    if pm == "pub":
        return _read_pubspec_lock(lock_path, packages)
    if pm == "go":
        return _read_go_sum(lock_path, packages)
    if pm == "cargo":
        return _read_cargo_lock(lock_path, packages)
    return {}


def _build_install_args(pm: str, packages: list[str]) -> list[str]:
    if pm == "npm":
        return ["npm", "install", "--package-lock-only", "--legacy-peer-deps"] + packages
    if pm == "pnpm":
        return ["pnpm", "add", "--lockfile-only"] + packages
    if pm == "yarn":
        return ["yarn", "add"] + packages
    if pm == "pub":
        return ["flutter", "pub", "add"] + packages
    if pm == "go":
        return ["go", "get"] + packages
    if pm == "cargo":
        return ["cargo", "add"] + packages
    return _PM_REGISTRY[pm]["resolve"]


def register_package_resolver_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    def resolve_package_versions(
        packages: list[str],
        package_manager: str = "",
        stack_hint: str = "",
    ) -> str:
        """
        Resolve exact pinned package versions using the real package manager.

        Runs in a temp directory — does not modify the project. Returns exact
        versions so Day 0 APPLY can write deterministic package manifests.

        Args:
            packages: List of packages with optional constraints,
                      e.g. ["next@16", "react", "@supabase/supabase-js@2"]
            package_manager: npm | pnpm | yarn | pub | maven | gradle | go | cargo | pip.
                             Auto-detected from stack_hint if omitted.
            stack_hint: Free-text hint from arch doc, e.g. "Next.js 16 + TypeScript".

        Returns:
            JSON: { "versions": {"next": "16.3.2", ...}, "package_manager": "npm",
                    "lock_file": "package-lock.json", "errors": [...] }
        """
        pm = package_manager.strip().lower() if package_manager.strip() else _detect_package_manager(stack_hint)

        if pm not in _PM_REGISTRY:
            return json.dumps({
                "error": f"Unknown package manager: {pm}. Supported: {list(_PM_REGISTRY.keys())}"
            })

        pm_config = _PM_REGISTRY[pm]
        tmpdir = tempfile.mkdtemp(prefix="nexus-resolve-")
        errors: list[str] = []

        try:
            if pm_config["init"]:
                subprocess.run(pm_config["init"], cwd=tmpdir, capture_output=True, timeout=30)

            if pm == "npm":
                (Path(tmpdir) / "package.json").write_text(
                    json.dumps({"name": "resolve-temp", "version": "0.0.1", "private": True})
                )

            cmd = _build_install_args(pm, packages)
            result = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                errors.append(result.stderr[:500])

            lock_file = pm_config.get("lock_file")
            versions: dict[str, str] = {}
            if lock_file:
                lock_path = Path(tmpdir) / lock_file
                if lock_path.exists():
                    pkg_names = [
                        p.split("@")[0] if "@" in p and not p.startswith("@")
                        else p.rsplit("@", 1)[0] if p.count("@") > 1
                        else p
                        for p in packages
                    ]
                    versions = _read_lock_file(pm, lock_path, pkg_names)

            return json.dumps({
                "versions": versions,
                "package_manager": pm,
                "lock_file": lock_file,
                "errors": errors,
            })

        except subprocess.TimeoutExpired:
            return json.dumps({"error": "Resolution timed out after 120s", "package_manager": pm})
        except Exception as e:
            return json.dumps({"error": str(e), "package_manager": pm})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
