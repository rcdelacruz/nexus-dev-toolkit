import json
import shutil
from pathlib import Path


_SETTINGS = {
    "hooks": {
        "PostToolUse": [
            {
                "matcher": ".*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "graphify update . --force 2>/dev/null || true"
                    }
                ]
            }
        ]
    }
}


def sync_claude(project_dir: str = ".") -> list[str]:
    """Sync .nexus/ to .claude/commands/ and .claude/settings.json."""
    root = Path(project_dir)
    nexus = root / ".nexus"
    commands = root / ".claude" / "commands"
    commands.mkdir(parents=True, exist_ok=True)

    written = []

    # Copy all skills
    skills_dir = nexus / "skills"
    if skills_dir.exists():
        for skill in skills_dir.glob("*.md"):
            dest = commands / skill.name
            shutil.copy2(skill, dest)
            written.append(str(dest))

    # Copy all rules as a combined RULES.md for reference
    rules_dir = nexus / "rules"
    if rules_dir.exists():
        rule_files = list(rules_dir.glob("*.md"))
        if rule_files:
            rules_dest = commands / "RULES.md"
            combined = "\n\n---\n\n".join(f.read_text(encoding="utf-8") for f in sorted(rule_files))
            rules_dest.write_text(combined, encoding="utf-8")
            written.append(str(rules_dest))

    # Write settings.json
    settings_path = root / ".claude" / "settings.json"
    existing = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except Exception:
            pass
    existing.update(_SETTINGS)
    settings_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    written.append(str(settings_path))

    return written
