import os
import shutil
import subprocess
from pathlib import Path

ENV_VAR = "NEXUS_GRAPH_BACKEND"

_BACKENDS = {
    "graphify": {
        "bin": "graphify",
        "output": Path("graphify-out/graph.json"),
        "query_cmd": lambda text: ["graphify", "query", text],
    },
    "codegraph": {
        "bin": "codegraph",
        "output": Path(".codegraph/codegraph.db"),
        "query_cmd": lambda text: ["codegraph", "explore", text],
    },
}

BACKEND_NAMES = tuple(_BACKENDS)
_PRIORITY = ("graphify", "codegraph")
_GRAPHIFY_HOOK_MARKER = "graphify update"


def backend_installed(name: str) -> bool:
    return bool(shutil.which(_BACKENDS[name]["bin"]))


def graph_exists(name: str, root: Path = Path(".")) -> bool:
    return (root / _BACKENDS[name]["output"]).exists()


def get_override() -> str | None:
    return os.environ.get(ENV_VAR)


def detect_backend(root: Path = Path(".")) -> str | None:
    """Pick the active knowledge-graph backend.

    NEXUS_GRAPH_BACKEND overrides the default, but only when that backend's graph
    actually exists — an override pointing at an unbuilt graph is ignored here so
    callers fall back to a usable backend instead of silently querying nothing.
    Otherwise, a built graph wins over a merely-installed tool, and graphify wins
    ties when both are built.
    """
    override = get_override()
    if override in _BACKENDS and graph_exists(override, root):
        return override

    for name in _PRIORITY:
        if graph_exists(name, root):
            return name
    for name in _PRIORITY:
        if backend_installed(name):
            return name
    return None


def run_query(text: str, backend: str | None = None, root: Path = Path(".")) -> str | None:
    """Run a blast-radius query against the active (or given) backend.

    Returns None if no backend is available or the query fails — callers should
    treat that as "no graph context available", not an error.
    """
    backend = backend or detect_backend(root)
    if backend is None:
        return None
    try:
        result = subprocess.run(
            _BACKENDS[backend]["query_cmd"](text),
            capture_output=True, text=True, timeout=30, cwd=root,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def has_graphify_hook(root: Path = Path(".")) -> bool:
    """True if this project has graphify's PostToolUse automation wired in."""
    settings_path = root / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            if _GRAPHIFY_HOOK_MARKER in settings_path.read_text():
                return True
        except Exception:
            pass
    return (root / ".opencode" / "plugins" / "graphify.js").exists()
