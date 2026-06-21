from tools.sync.detect import detect_tools
from tools.sync.claude import sync_claude
from tools.sync.cursor import sync_cursor
from tools.sync.copilot import sync_copilot
from tools.sync.windsurf import sync_windsurf

_ADAPTERS = {
    "claude": sync_claude,
    "cursor": sync_cursor,
    "copilot": sync_copilot,
    "windsurf": sync_windsurf,
}


def sync_all(project_dir: str = ".", tools: list[str] | None = None) -> dict[str, list[str]]:
    """Sync .nexus/ to all detected (or specified) LLM tools. Returns files written per tool."""
    detected = tools or detect_tools(project_dir)
    results: dict[str, list[str]] = {}
    for tool in detected:
        adapter = _ADAPTERS.get(tool)
        if adapter:
            results[tool] = adapter(project_dir)
    return results
