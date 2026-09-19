"""
resolve_package_versions — MCP tool for Day 0 APPLY.

Given a package manager type and a list of packages with optional major-version
constraints (derived from the arch doc), spins up a temp directory, runs the
package manager's resolution command, reads the lock file, and returns exact
pinned versions. Never hardcodes versions or stack-specific logic beyond what
is needed to dispatch the right CLI.

Also covers three IaC tools (terraform, helm, ansible) whose resolution
mechanics genuinely differ from an application package manager's "install
then read a lockfile" shape:
  - terraform has no separate manifest step of its own -- required_providers
    is written directly, and .terraform.lock.hcl pins exact provider versions
    (not module versions, which Terraform pins by source ref, not a resolver).
  - helm has no single central registry, so each chart dependency needs an
    explicit repository URL alongside name/version.
  - ansible-galaxy has no resolve-to-lockfile step at all: installing just
    installs whatever satisfies the constraint, so getting the exact version
    means installing then introspecting with `ansible-galaxy collection list`.
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from tools.epav import judgment

_WORD_RE = re.compile(r"[a-z0-9]+")

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
    "terraform": {
        "detect": ["*.tf", ".terraform.lock.hcl"],
        "init": None,
        "resolve": ["terraform", "init", "-backend=false", "-input=false"],
        "lock_file": ".terraform.lock.hcl",
    },
    "ansible": {
        "detect": ["requirements.yml", "ansible.cfg"],
        "init": None,
        "resolve": ["ansible-galaxy", "collection", "install", "-r", "requirements.yml"],
        "lock_file": None,  # no resolve-to-lockfile mechanism -- see _resolve_ansible
    },
    "helm": {
        "detect": ["Chart.yaml"],
        "init": None,
        "resolve": ["helm", "dependency", "update", "."],
        "lock_file": "Chart.lock",
    },
}


_PM_CRITERIA = {
    "npm": "Node.js/JavaScript or TypeScript projects (React, Next.js, Vite, Express, plain Node) using package.json, when no more specific JS package manager is named",
    "pnpm": "Node.js/JavaScript projects that explicitly name pnpm as their package manager",
    "yarn": "Node.js/JavaScript projects that explicitly name Yarn as their package manager",
    "maven": "Java or Kotlin projects built with Maven (pom.xml)",
    "gradle": "Java, Kotlin, or Android projects built with Gradle",
    "pub": "Dart or Flutter projects (pubspec.yaml)",
    "go": "Go projects (go.mod)",
    "cargo": "Rust projects (Cargo.toml)",
    "pip": "Python projects (requirements.txt, pyproject.toml) not using a Python tool with its own distinct lockfile format",
    "terraform": "Terraform projects (.tf files) with no separate application-language package manager -- dependencies are cloud providers/modules pinned via terraform init and .terraform.lock.hcl",
    "ansible": "Ansible playbooks or roles for provisioning or configuring infrastructure, with dependencies (collections) pinned via ansible-galaxy",
    "helm": "Helm charts for deploying to Kubernetes, with chart dependencies pinned via helm dependency update and Chart.lock",
}

# Below this, the Choice's own probability distribution was too flat to trust
# (observed empirically on an out-of-registry stack: confidence sat at 0.50).
_PM_CONFIDENCE_THRESHOLD = 0.6


def _detect_package_manager(hint: str | None) -> str:
    if not hint:
        return "npm"
    hint_lower = hint.lower()
    # Word-boundary match, not raw substring: "go" is a substring of "django"
    # and "npm" is a substring of "pnpm", so a naive `pm in hint_lower` check
    # misfires on those before TypeSafe or the keyword fallback ever run.
    hint_tokens = set(_WORD_RE.findall(hint_lower))
    for pm in _PM_REGISTRY:
        if pm in hint_tokens:
            return pm

    if judgment.Choice is None:
        return _detect_package_manager_fallback(hint_lower)

    result = judgment.system_one(
        state={},
        questions={
            "package_manager": judgment.Choice(
                instructions=(
                    f'Given the project description "{hint}", which package manager '
                    "should be used to resolve and pin its dependency versions?"
                ),
                criteria=_PM_CRITERIA,
            )
        },
    )
    if result is not None:
        choice = result.choices["package_manager"]
        if choice.confidence >= _PM_CONFIDENCE_THRESHOLD:
            return choice.choice

    return _detect_package_manager_fallback(hint_lower)


def _detect_package_manager_fallback(hint_lower: str) -> str:
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
    if "terraform" in hint_lower:
        return "terraform"
    if "ansible" in hint_lower:
        return "ansible"
    if "helm" in hint_lower:
        return "helm"
    return "npm"


# ── application package managers (npm/pnpm/yarn/maven/gradle/pub/go/cargo/pip) ─

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


def _resolve_generic(pm: str, tmpdir: Path, packages: list[str]) -> tuple[dict[str, str], list[str]]:
    """init (if any) -> install command -> read lockfile. Every package
    manager except the three IaC tools, which don't fit this shape."""
    pm_config = _PM_REGISTRY[pm]
    errors: list[str] = []

    if pm_config["init"]:
        subprocess.run(pm_config["init"], cwd=tmpdir, capture_output=True, timeout=30)

    if pm == "npm":
        (tmpdir / "package.json").write_text(
            json.dumps({"name": "resolve-temp", "version": "0.0.1", "private": True})
        )

    cmd = _build_install_args(pm, packages)
    result = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        errors.append(result.stderr[:500])

    versions: dict[str, str] = {}
    lock_file = pm_config.get("lock_file")
    if lock_file:
        lock_path = tmpdir / lock_file
        if lock_path.exists():
            pkg_names = [
                p.split("@")[0] if "@" in p and not p.startswith("@")
                else p.rsplit("@", 1)[0] if p.count("@") > 1
                else p
                for p in packages
            ]
            versions = _read_lock_file(pm, lock_path, pkg_names)

    return versions, errors


# ── terraform ───────────────────────────────────────────────────────────────
# Packages are providers only, format "source@constraint" (e.g.
# "hashicorp/aws@~>5.0"), matching how a required_providers block identifies
# a provider. Terraform modules aren't covered -- they're pinned by source
# ref/tag directly in the module block, not resolved via a lockfile.

_TF_LOCK_PROVIDER_RE = re.compile(r'^provider\s+"registry\.terraform\.io/(?P<source>[^"]+)"\s*\{')
_TF_LOCK_VERSION_RE = re.compile(r'^\s*version\s*=\s*"(?P<version>[^"]+)"')


def _parse_terraform_source(pkg: str) -> tuple[str, str | None]:
    if "@" in pkg:
        source, constraint = pkg.split("@", 1)
        return source.strip(), constraint.strip()
    return pkg.strip(), None


def _read_terraform_lock(lock_path: Path, sources: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    try:
        current_source = None
        for line in lock_path.read_text().splitlines():
            provider_match = _TF_LOCK_PROVIDER_RE.match(line)
            if provider_match:
                current_source = provider_match.group("source")
                continue
            if current_source:
                version_match = _TF_LOCK_VERSION_RE.match(line)
                if version_match and current_source in sources:
                    versions[current_source] = version_match.group("version")
                current_source = None  # only the first "version =" line per block is the pin
    except Exception:
        pass
    return versions


def _resolve_terraform(tmpdir: Path, packages: list[str]) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    parsed = [_parse_terraform_source(p) for p in packages]

    seen_names: dict[str, int] = {}
    blocks = []
    for source, constraint in parsed:
        name = source.rsplit("/", 1)[-1]
        if name in seen_names:
            seen_names[name] += 1
            name = f"{name}_{seen_names[name]}"
        else:
            seen_names[name] = 0
        block = f'    {name} = {{\n      source  = "{source}"'
        if constraint:
            block += f'\n      version = "{constraint}"'
        block += "\n    }"
        blocks.append(block)

    (tmpdir / "versions.tf").write_text(
        "terraform {\n  required_providers {\n" + "\n".join(blocks) + "\n  }\n}\n"
    )

    result = subprocess.run(
        _PM_REGISTRY["terraform"]["resolve"], cwd=tmpdir, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        errors.append(result.stderr[:500])

    versions: dict[str, str] = {}
    lock_path = tmpdir / _PM_REGISTRY["terraform"]["lock_file"]
    if lock_path.exists():
        sources = [source for source, _ in parsed]
        versions = _read_terraform_lock(lock_path, sources)

    return versions, errors


# ── helm ────────────────────────────────────────────────────────────────────
# Helm has no single central registry, so each dependency needs its own
# repository URL. Format: "name@version@repo_url". A chart with no repo URL
# can't be resolved -- it's reported as an error rather than silently skipped
# or guessed at.

def _parse_helm_package(pkg: str) -> tuple[str, str | None, str | None]:
    parts = pkg.split("@")
    if len(parts) == 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip(), None
    return pkg.strip(), None, None


def _read_helm_lock(lock_path: Path, names: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    try:
        current_name = None
        for line in lock_path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("- name:"):
                current_name = stripped.split(":", 1)[1].strip()
            elif current_name and stripped.startswith("version:"):
                ver = stripped.split(":", 1)[1].strip().strip('"')
                if current_name in names:
                    versions[current_name] = ver
                current_name = None
    except Exception:
        pass
    return versions


def _resolve_helm(tmpdir: Path, packages: list[str]) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    parsed = [_parse_helm_package(p) for p in packages]

    missing_repo = [name for name, _, repo in parsed if repo is None]
    if missing_repo:
        errors.append(
            'Helm chart dependencies need a repository URL: pass packages as '
            f'"name@version@repo_url". Missing repository for: {", ".join(missing_repo)}'
        )

    deps = [p for p in parsed if p[2] is not None]
    if not deps:
        return {}, errors

    dep_yaml = "\n".join(
        f'  - name: {name}\n    version: "{version}"\n    repository: "{repo}"'
        for name, version, repo in deps
    )
    (tmpdir / "Chart.yaml").write_text(
        f"apiVersion: v2\nname: resolve-temp\nversion: 0.0.1\ndependencies:\n{dep_yaml}\n"
    )

    result = subprocess.run(
        _PM_REGISTRY["helm"]["resolve"], cwd=tmpdir, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        errors.append(result.stderr[:500])

    versions: dict[str, str] = {}
    lock_path = tmpdir / _PM_REGISTRY["helm"]["lock_file"]
    if lock_path.exists():
        names = [name for name, _, _ in deps]
        versions = _read_helm_lock(lock_path, names)

    return versions, errors


# ── ansible ─────────────────────────────────────────────────────────────────
# ansible-galaxy has no resolve-to-lockfile step: installing a constraint just
# installs whatever satisfies it, it doesn't write back a discovered exact
# version. Getting exact versions means installing, then introspecting with
# `ansible-galaxy collection list`. Format: "namespace.name:constraint"
# (ansible-galaxy's own CLI convention), collections only -- roles aren't
# covered.

def _parse_ansible_package(pkg: str) -> tuple[str, str | None]:
    if ":" in pkg:
        name, constraint = pkg.split(":", 1)
        return name.strip(), constraint.strip()
    return pkg.strip(), None


def _parse_ansible_collection_list(stdout: str, collections_dir: str, names: list[str]) -> dict[str, str]:
    """Parse `ansible-galaxy collection list` output.

    The command lists every collections path ansible knows about (its own
    built-ins, the user's global path, etc.), each under its own "# <path>"
    header -- only the section for our own temp `collections_dir` is ours.
    """
    versions: dict[str, str] = {}
    in_target = False
    for line in stdout.splitlines():
        line = line.rstrip()
        if line.startswith("#"):
            in_target = collections_dir in line
            continue
        if not in_target or not line.strip() or line.startswith("Collection"):
            continue
        if not line.strip("- "):  # the header/value separator row
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in names:
            versions[parts[0]] = parts[1]
    return versions


def _read_ansible_versions(collections_dir: Path, names: list[str]) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["ansible-galaxy", "collection", "list", "-p", str(collections_dir)],
            capture_output=True, text=True, timeout=30,
        )
        return _parse_ansible_collection_list(result.stdout, str(collections_dir), names)
    except Exception:
        return {}


def _resolve_ansible(tmpdir: Path, packages: list[str]) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    parsed = [_parse_ansible_package(p) for p in packages]

    entries = "\n".join(
        f"  - name: {name}" + (f'\n    version: "{constraint}"' if constraint else "")
        for name, constraint in parsed
    )
    (tmpdir / "requirements.yml").write_text(f"collections:\n{entries}\n")

    collections_dir = tmpdir / "collections"
    result = subprocess.run(
        ["ansible-galaxy", "collection", "install", "-r", "requirements.yml", "-p", str(collections_dir)],
        cwd=tmpdir, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        errors.append(result.stderr[:500])

    names = [name for name, _ in parsed]
    versions = _read_ansible_versions(collections_dir, names)
    return versions, errors


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
            packages: Format depends on package_manager:
                      - npm/pnpm/yarn/pub/go/cargo/maven/gradle/pip: "name@version",
                        e.g. ["next@16", "react", "@supabase/supabase-js@2"]
                      - terraform: "source@constraint" (providers only),
                        e.g. ["hashicorp/aws@~>5.0", "hashicorp/random"]
                      - helm: "name@version@repo_url" (repository required — Helm
                        has no central registry),
                        e.g. ["nginx@~15.0.0@https://charts.bitnami.com/bitnami"]
                      - ansible: "namespace.name:constraint" (collections only),
                        e.g. ["community.general:>=8.0.0"]
            package_manager: npm | pnpm | yarn | pub | maven | gradle | go | cargo | pip
                             | terraform | ansible | helm. Auto-detected from stack_hint
                             if omitted.
            stack_hint: Free-text hint from arch doc, e.g. "Next.js 16 + TypeScript" or
                        "Terraform modules for an AWS VPC".

        Returns:
            JSON: { "versions": {"next": "16.3.2", ...}, "package_manager": "npm",
                    "lock_file": "package-lock.json", "errors": [...] }
        """
        pm = package_manager.strip().lower() if package_manager.strip() else _detect_package_manager(stack_hint)

        if pm not in _PM_REGISTRY:
            return json.dumps({
                "error": f"Unknown package manager: {pm}. Supported: {list(_PM_REGISTRY.keys())}"
            })

        tmpdir = Path(tempfile.mkdtemp(prefix="nexus-resolve-"))

        try:
            if pm == "terraform":
                versions, errors = _resolve_terraform(tmpdir, packages)
            elif pm == "helm":
                versions, errors = _resolve_helm(tmpdir, packages)
            elif pm == "ansible":
                versions, errors = _resolve_ansible(tmpdir, packages)
            else:
                versions, errors = _resolve_generic(pm, tmpdir, packages)

            return json.dumps({
                "versions": versions,
                "package_manager": pm,
                "lock_file": _PM_REGISTRY[pm].get("lock_file"),
                "errors": errors,
            })

        except subprocess.TimeoutExpired:
            return json.dumps({"error": "Resolution timed out after 120s", "package_manager": pm})
        except Exception as e:
            return json.dumps({"error": str(e), "package_manager": pm})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
