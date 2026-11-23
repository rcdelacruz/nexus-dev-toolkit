"""
Release check for nexus-dev-toolkit — run before every push that changes the version.

    python3 scripts/release.py            # check everything; prints the publish steps if all pass

Checks, in order, and stops at the first failure (nothing is published by this script):
  1. version is the same in pyproject.toml and nexus_cli.py
  2. branch fits the version: stable → main, pre-release (aN/bN/rcN) → v4
  3. CHANGELOG.md's newest entry is this version
  4. stable only: every site page shows this version, and the changelog page is up to date
  5. git working tree is clean (what gets tested is exactly what gets released)
  6. a clean checkout of HEAD builds, the wheel carries the package data, and the tests pass

Then prints the remaining CLAUDE.md steps (push, deploy, GitHub release) for this version.
Standard library only.
"""

import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRE = re.compile(r"(a|b|rc|dev)\d+$")
PAGES = ["public/docs.html", "public/cursor.html", "public/loop-guide.html"]
PACKAGE_DATA = ["tools/epav/stack_catalog.json", "tools/epav/skills/epav.md", "tools/agents/code-reviewer.md",
                "tools/epav/skills/design.md", "tools/epav/skills/change-request.md",
                "tools/templates/ARCHITECTURE-GUIDE.md", "tools/templates/DESIGN-GUIDE.md",
                "tools/templates/REQUIREMENTS-GUIDE.md", "tools/templates/CODEOWNERS",
                "tools/channel.py", "tools/epav/formats/tasks.py", "tools/epav/design_ingest.py"]


class Fail(Exception):
    pass


def _run(cmd: list[str], cwd: Path = ROOT, timeout: int = 900) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise Fail(f"`{' '.join(cmd)}` failed:\n{(r.stdout + r.stderr)[-3000:]}")
    return r.stdout


def version() -> str:
    m = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)
    if not m:
        raise Fail("no version in pyproject.toml")
    return m.group(1)


def check_versions(v: str) -> None:
    m = re.search(r'^_VERSION = "([^"]+)"', (ROOT / "nexus_cli.py").read_text(), re.M)
    if not m or m.group(1) != v:
        raise Fail(f"nexus_cli.py _VERSION is {m.group(1) if m else 'missing'}, pyproject is {v}")


def check_branch(v: str) -> str:
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    want = "v4" if PRE.search(v) else "main"
    if branch != want:
        raise Fail(f"{v} is {'a pre-release' if want == 'v4' else 'stable'}: release it from `{want}`, not `{branch}`")
    return branch


def check_changelog(v: str) -> None:
    m = re.search(r"^## \[([^\]]+)\]", (ROOT / "CHANGELOG.md").read_text(), re.M)
    if not m or m.group(1) != v:
        raise Fail(f"CHANGELOG.md newest entry is {m.group(1) if m else 'missing'}, expected [{v}]")


def check_site(v: str) -> None:
    if PRE.search(v):
        return  # the site is deployed from main and shows the stable release
    shown = re.search(r'id="site-version">v([^<]+)<', (ROOT / "public/index.html").read_text())
    if not shown or shown.group(1) != v:
        raise Fail(f"public/index.html shows v{shown.group(1) if shown else '?'}, expected v{v}")
    for page in PAGES:
        for label in re.findall(r'<div class="nav-version">v([^<]+)</div>', (ROOT / page).read_text()):
            if label != v:
                raise Fail(f"{page} shows v{label}, expected v{v}")
    before = (ROOT / "public/changelog.html").read_text()
    _run([sys.executable, "scripts/build_changelog.py"])
    if (ROOT / "public/changelog.html").read_text() != before:
        raise Fail("public/changelog.html was out of date — rebuilt it; review and commit, then re-run")


def check_clean() -> None:
    dirty = _run(["git", "status", "--porcelain"]).strip()
    if dirty:
        raise Fail(f"working tree not clean — commit first:\n{dirty}")


def check_clean_build_and_tests(v: str) -> None:
    with tempfile.TemporaryDirectory(prefix="nexus-release-") as tmp:
        wt = Path(tmp) / "wt"
        _run(["git", "worktree", "add", "--detach", str(wt), "HEAD"])
        try:
            _run(["uv", "build", "--out-dir", str(wt / "dist")], cwd=wt)
            wheels = list((wt / "dist").glob(f"*-{v}-*.whl"))
            if not wheels:
                raise Fail(f"no wheel for {v} was built")
            names = set(zipfile.ZipFile(wheels[0]).namelist())
            missing = [p for p in PACKAGE_DATA if p not in names]
            if missing:
                raise Fail(f"wheel is missing package data: {missing}")
            _run(["uv", "run", "--extra", "dev", "pytest", "tests/", "-q"], cwd=wt)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT, capture_output=True)


def next_steps(v: str, branch: str) -> str:
    pre = bool(PRE.search(v))
    steps = [
        f"git push origin {branch}        # CI: Tests (3.10–3.13) must pass before Publish runs",
        f"gh run list --branch {branch} --limit 3   # confirm Tests and Publish are green",
    ]
    if not pre:
        steps.append("wrangler pages deploy public/ --project-name nexus-coderstudio --branch main --commit-dirty=true")
    steps.append(
        f'gh release create v{v} --target {branch} --title "v{v}"'
        + (" --prerelease" if pre else "") + " --notes-file <CHANGELOG section>"
    )
    return "\n".join(f"  {i}. {s}" for i, s in enumerate(steps, 1))


def main() -> int:
    try:
        v = version()
        checks = [
            ("version in pyproject + nexus_cli", lambda: check_versions(v)),
            ("branch fits the version", lambda: check_branch(v)),
            ("CHANGELOG newest entry", lambda: check_changelog(v)),
            ("site pages + changelog page (stable only)", lambda: check_site(v)),
            ("working tree clean", check_clean),
            ("clean checkout builds + tests pass", lambda: check_clean_build_and_tests(v)),
        ]
        branch = ""
        for name, fn in checks:
            result = fn()
            if name.startswith("branch"):
                branch = result
            print(f"  ✓ {name}")
    except Fail as e:
        print(f"  ✗ {e}", file=sys.stderr)
        print("Release stopped — nothing was published.", file=sys.stderr)
        return 1
    print(f"\nAll checks passed for {v}. Remaining steps:\n{next_steps(v, branch)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
