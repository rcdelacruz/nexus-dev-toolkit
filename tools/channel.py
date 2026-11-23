"""
Release channels, upgrades and the per-project file manifest.

Channels
  stable  — normal releases (3.2.0, 4.0.0, 4.1.0 …). Installers never pick pre-releases.
  pre     — pre-releases of the next major (4.0.0a1 → a2 → b1 → rc1). `nexus update` follows
            them and, once that major's final release exists, moves the user onto stable.

Measured uv behaviour this module relies on (local test index, 2026-11-22):
  - `uvx --from nexus-dev-toolkit …` resolves the newest STABLE release, even when a newer
    pre-release exists. So the MCP config must name `>=4.0.0a0` on the pre channel.
  - `uv tool install 'pkg>=4.0.0a0'` installs the newest pre-release and later upgrades follow it.
  - A pinned `pkg==4.0.0a1` never upgrades. Never pin.
  - `uv tool install --reinstall` is used instead of `uv tool upgrade`, which can no-op.

Manifest
  .nexus/manifest.json lists every file nexus copied into the project with the hash of the
  text nexus shipped. That makes two things safe:
  - removing a file nexus no longer ships, ONLY if the file on disk still matches (unedited);
  - overwriting a built-in the user edited: the edited copy is backed up first.
Standard library only.
"""

import hashlib
import json
import re
import shutil
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE = "nexus-dev-toolkit"
MANIFEST = Path(".nexus") / "manifest.json"
BACKUP_DIR = Path(".nexus") / "backup"
MANIFEST_VERSION = 1

_VER = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:(a|b|rc)(\d+))?$")
_RANK = {"a": 0, "b": 1, "rc": 2, None: 3}


# ── versions ─────────────────────────────────────────────────────────────────

def version_key(v: str) -> tuple[int, int, int, int, int] | None:
    """PEP 440 subset: 4, 4.0, 4.0.0, 4.0.0a1, 4.0.0b2, 4.0.0rc1. None if unparseable."""
    m = _VER.match(v.strip())
    if not m:
        return None
    major, minor, patch, tag, num = m.groups()
    return int(major), int(minor or 0), int(patch or 0), _RANK[tag], int(num or 0)


def is_prerelease(v: str) -> bool:
    k = version_key(v)
    return bool(k) and k[3] < 3


def is_newer(candidate: str, current: str) -> bool:
    a, b = version_key(candidate), version_key(current)
    return bool(a and b and a > b)


def channel_of(v: str) -> str:
    return "pre" if is_prerelease(v) else "stable"


def major_of(v: str) -> int:
    k = version_key(v)
    return k[0] if k else 0


def fetch_releases(timeout: float = 5.0) -> list[str] | None:
    """Every non-yanked version on PyPI. None on any failure (offline, timeout, bad JSON)."""
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{PACKAGE}/json", timeout=timeout) as r:
            data = json.loads(r.read())
        out = []
        for v, files in data.get("releases", {}).items():
            if files and not all(f.get("yanked") for f in files) and version_key(v):
                out.append(v)
        return out
    except Exception:
        return None


def pick_update(current: str, releases: list[str]) -> str | None:
    """The version `nexus update` should move to, or None if already current.

    stable channel: newest stable newer than current (pre-releases ignored).
    pre channel:    if a final release of this major (or later) exists → newest stable
                    (graduation); otherwise newest pre-release of this major newer than current.
    """
    stable = [v for v in releases if not is_prerelease(v)]
    if not is_prerelease(current):
        newer = [v for v in stable if is_newer(v, current)]
        return max(newer, key=version_key) if newer else None
    major = major_of(current)
    finals = [v for v in stable if major_of(v) >= major]
    if finals:
        return max(finals, key=version_key)
    pres = [v for v in releases if is_prerelease(v) and major_of(v) == major and is_newer(v, current)]
    return max(pres, key=version_key) if pres else None


def install_spec(version: str) -> str:
    """Requirement to install/upgrade to `version` without pinning (pins never upgrade)."""
    if is_prerelease(version):
        return f"{PACKAGE}>={major_of(version)}.0.0a0"
    return PACKAGE


def mcp_from(version: str) -> str:
    """The `--from` value for project MCP configs, so the MCP server runs the same channel as
    the CLI that wrote the config."""
    return install_spec(version)


def install_command(spec: str, have_uv: bool) -> list[str]:
    if have_uv:
        return ["uv", "tool", "install", "--reinstall", spec]
    cmd = ["pip", "install", "--upgrade", spec]
    return cmd + ["--pre"] if ">=" in spec and "a0" in spec else cmd


# ── manifest ─────────────────────────────────────────────────────────────────

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Manifest:
    nexus_version: str = ""
    channel: str = ""
    files: dict[str, str] = field(default_factory=dict)      # relpath → sha256 of the text nexus shipped
    role: str = ""                                            # developer | architect | designer
    manifest_version: int = MANIFEST_VERSION
    problems: list[str] = field(default_factory=list)


def load_manifest(root: Path) -> Manifest:
    p = root / MANIFEST
    if not p.is_file():
        return Manifest()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return Manifest(
            nexus_version=str(data.get("nexus_version", "")),
            channel=str(data.get("channel", "")),
            files={str(k): str(v) for k, v in dict(data.get("files", {})).items()},
            role=str(data.get("role", "")),
            manifest_version=int(data.get("manifest_version", MANIFEST_VERSION)),
        )
    except Exception as e:  # a broken manifest must never stop sync — treat as absent
        m = Manifest()
        m.problems.append(f"{MANIFEST} unreadable ({e}); rebuilding it")
        return m


def save_manifest(root: Path, version: str, files: dict[str, str], role: str = "") -> None:
    p = root / MANIFEST
    p.parent.mkdir(parents=True, exist_ok=True)
    role = role or load_manifest(root).role or "developer"
    data = {"manifest_version": MANIFEST_VERSION, "nexus_version": version, "channel": channel_of(version),
            "role": role, "files": dict(sorted(files.items()))}
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)
    # .nexus/ is per checkout: each person's manifest records their own role and the files nexus
    # wrote for it, so teammates with different roles never overwrite each other's. It stays out of git.
    ignore = p.parent / ".gitignore"
    if not ignore.exists() or ignore.read_text(encoding="utf-8").strip() == "backup/":
        ignore.write_text("# nexus bookkeeping for this checkout (its role and files) — not shared\n*\n", encoding="utf-8")


def is_edited(root: Path, rel: str, manifest: Manifest) -> bool:
    """True if the file on disk differs from what nexus last shipped for it."""
    p = root / rel
    if not p.is_file() or rel not in manifest.files:
        return False
    try:
        return sha(p.read_text(encoding="utf-8")) != manifest.files[rel]
    except Exception:
        return True


def backup(root: Path, rel: str, stamp: str | None = None) -> Path:
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    dst = root / BACKUP_DIR / stamp / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / rel, dst)
    return dst


def prune(root: Path, old: Manifest, current: set[str]) -> tuple[list[str], list[str]]:
    """Remove files nexus wrote before but no longer ships. Returns (removed, kept_because_edited).
    Only files listed in the old manifest and still identical to what nexus shipped are removed."""
    removed, kept = [], []
    for rel in sorted(set(old.files) - current):
        p = root / rel
        if not p.is_file():
            continue
        if is_edited(root, rel, old):
            kept.append(rel)
            continue
        p.unlink()
        removed.append(rel)
        parent = p.parent
        while parent != root and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return removed, kept
