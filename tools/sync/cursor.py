import shutil
from pathlib import Path


def sync_cursor(project_dir: str = ".") -> list[str]:
    """Sync .nexus/ to .cursor/rules/ as .mdc files."""
    root = Path(project_dir)
    nexus = root / ".nexus"
    rules_dir = root / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    written = []

    def _write_mdc(dest: Path, title: str, content: str) -> None:
        mdc = f"---\ndescription: {title}\nalwaysApply: false\n---\n\n{content}"
        dest.write_text(mdc, encoding="utf-8")

    # Skills → .cursor/rules/skill-*.mdc
    skills_dir = nexus / "skills"
    if skills_dir.exists():
        for skill in skills_dir.glob("*.md"):
            dest = rules_dir / f"skill-{skill.stem}.mdc"
            _write_mdc(dest, skill.stem, skill.read_text(encoding="utf-8"))
            written.append(str(dest))

    # Rules → .cursor/rules/rule-*.mdc
    project_rules = nexus / "rules"
    if project_rules.exists():
        for rule in project_rules.glob("*.md"):
            dest = rules_dir / f"rule-{rule.stem}.mdc"
            _write_mdc(dest, rule.stem, rule.read_text(encoding="utf-8"))
            written.append(str(dest))

    return written
