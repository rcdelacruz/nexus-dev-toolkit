from pathlib import Path


def detect_tools(project_dir: str = ".") -> list[str]:
    """Detect which LLM tools are configured in the project directory."""
    root = Path(project_dir)
    detected = []

    if (root / ".claude").exists() or (root / ".mcp.json").exists():
        detected.append("claude")
    if (root / ".cursor").exists() or (root / ".cursorrules").exists():
        detected.append("cursor")
    if (root / ".github" / "copilot-instructions.md").exists():
        detected.append("copilot")
    if (root / ".windsurfrules").exists():
        detected.append("windsurf")

    return detected or ["claude"]  # default to claude if nothing detected
