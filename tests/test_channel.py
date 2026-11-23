"""Release channels, upgrades and the project manifest (rule 6).

The uv tests at the bottom replay what `nexus update` / `nexus channel` do against a local,
offline package index of hand-built wheels — the real uv, no network, no PyPI."""

import base64
import hashlib
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from tools import channel

# ── versions ─────────────────────────────────────────────────────────────────

def test_version_order():
    order = ["3.2.0", "4.0.0a1", "4.0.0a2", "4.0.0b1", "4.0.0rc1", "4.0.0", "4.0.1", "4.1.0a1", "4.1.0"]
    assert sorted(reversed(order), key=channel.version_key) == order
    assert channel.version_key("not-a-version") is None
    assert channel.is_prerelease("4.0.0rc1") and not channel.is_prerelease("4.0.0")


@pytest.mark.parametrize("current,releases,expected", [
    ("3.2.0", ["3.2.0", "3.2.1", "4.0.0a1"], "3.2.1"),            # stable ignores pre-releases
    ("3.2.0", ["3.2.0", "4.0.0a1"], None),
    ("4.0.0a1", ["3.2.0", "4.0.0a1", "4.0.0a2"], "4.0.0a2"),       # pre follows pre
    ("4.0.0a2", ["3.2.0", "4.0.0a1", "4.0.0a2", "4.0.0b1"], "4.0.0b1"),
    ("4.0.0b1", ["3.2.0", "4.0.0b1", "4.0.0rc1", "4.0.0"], "4.0.0"),  # graduates to stable
    ("4.0.0rc1", ["4.0.0rc1", "4.0.0", "4.0.1"], "4.0.1"),
    ("4.0.0a1", ["3.2.0", "3.2.1", "4.0.0a1"], None),               # a 3.x fix is not an upgrade for v4
    ("4.0.0a1", ["4.0.0a1", "5.0.0a1"], None),                      # never jumps to the next major's pre
])
def test_pick_update(current, releases, expected):
    assert channel.pick_update(current, releases) == expected


def test_specs_never_pin():
    assert channel.install_spec("4.0.0a2") == "nexus-dev-toolkit>=4.0.0a0"
    assert channel.install_spec("4.0.0") == "nexus-dev-toolkit"
    assert channel.mcp_from("3.2.0") == "nexus-dev-toolkit"
    assert "==" not in channel.install_spec("4.0.0b1")
    assert channel.install_command("nexus-dev-toolkit", True) == ["uv", "tool", "install", "--reinstall", "nexus-dev-toolkit"]
    assert "--pre" in channel.install_command("nexus-dev-toolkit>=4.0.0a0", False)


def test_fetch_releases_skips_yanked(monkeypatch):
    import io, json
    payload = {"releases": {"3.2.0": [{"yanked": False}], "4.0.0a1": [{"yanked": True}], "4.0.0a2": [{}], "9.9": []}}
    monkeypatch.setattr(channel.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
    assert sorted(channel.fetch_releases()) == ["3.2.0", "4.0.0a2"]
    monkeypatch.setattr(channel.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    assert channel.fetch_releases() is None


# ── manifest ─────────────────────────────────────────────────────────────────

def test_manifest_round_trip_and_gitignore(tmp_path):
    channel.save_manifest(tmp_path, "4.0.0a1", {"a/b.md": channel.sha("x")})
    m = channel.load_manifest(tmp_path)
    assert (m.nexus_version, m.channel, m.files) == ("4.0.0a1", "pre", {"a/b.md": channel.sha("x")})
    assert (tmp_path / ".nexus" / ".gitignore").read_text().splitlines()[-1] == "*"   # per checkout, never committed


def test_broken_manifest_never_stops_sync(tmp_path):
    (tmp_path / ".nexus").mkdir()
    (tmp_path / ".nexus" / "manifest.json").write_text("{nope")
    m = channel.load_manifest(tmp_path)
    assert m.files == {} and "unreadable" in m.problems[0]


def test_prune_removes_only_unedited(tmp_path):
    for rel, text in {"x/old.md": "shipped", "x/edited.md": "shipped", "x/kept.md": "shipped"}.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    (tmp_path / "x/edited.md").write_text("shipped + my notes")
    old = channel.Manifest(files={r: channel.sha("shipped") for r in ("x/old.md", "x/edited.md", "x/kept.md")})
    removed, kept = channel.prune(tmp_path, old, current={"x/kept.md"})
    assert removed == ["x/old.md"] and kept == ["x/edited.md"]
    assert not (tmp_path / "x/old.md").exists() and (tmp_path / "x/edited.md").exists()


def test_backup_keeps_a_copy(tmp_path):
    (tmp_path / "f.md").write_text("mine")
    saved = channel.backup(tmp_path, "f.md", "stamp")
    assert saved.read_text() == "mine" and saved == tmp_path / ".nexus" / "backup" / "stamp" / "f.md"


# ── real uv against an offline local index ───────────────────────────────────

DUMMY = "nexus-uvtest-dummy"


def _wheel(index: Path, version: str) -> None:
    """A minimal valid wheel with one console script that prints its version."""
    dist = f"nexus_uvtest_dummy-{version}.dist-info"
    files = {
        "nexus_uvtest_dummy/__init__.py": f'def main():\n    print("dummy {version}")\n',
        f"{dist}/METADATA": f"Metadata-Version: 2.1\nName: {DUMMY}\nVersion: {version}\n",
        f"{dist}/WHEEL": "Wheel-Version: 1.0\nGenerator: nexus-tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{dist}/entry_points.txt": "[console_scripts]\nnexusdummy = nexus_uvtest_dummy:main\n",
    }
    record = []
    for name, text in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(text.encode()).digest()).rstrip(b"=").decode()
        record.append(f"{name},sha256={digest},{len(text.encode())}")
    record.append(f"{dist}/RECORD,,")
    files[f"{dist}/RECORD"] = "\n".join(record) + "\n"
    with zipfile.ZipFile(index / f"nexus_uvtest_dummy-{version}-py3-none-any.whl", "w") as z:
        for name, text in files.items():
            z.writestr(name, text)


@pytest.fixture
def uvenv(tmp_path):
    if not shutil.which("uv"):
        pytest.skip("uv not installed")
    index = tmp_path / "index"
    index.mkdir()
    env = dict(os.environ, UV_TOOL_DIR=str(tmp_path / "tools"), UV_TOOL_BIN_DIR=str(tmp_path / "bin"),
               UV_CACHE_DIR=str(tmp_path / "cache"), UV_NO_INDEX="1", UV_FIND_LINKS=str(index),
               UV_PYTHON_DOWNLOADS="never")

    def uv(*args) -> str:
        r = subprocess.run(["uv", *args], env=env, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
        return r.stdout

    def installed() -> str:
        return subprocess.run([str(tmp_path / "bin" / "nexusdummy")], capture_output=True, text=True).stdout.strip()

    def spec_for(version: str) -> str:
        return channel.install_spec(version).replace(channel.PACKAGE, DUMMY).replace(">=4.", ">=2.")

    return index, uv, installed, spec_for


def test_uv_upgrade_path_end_to_end(uvenv):
    index, uv, installed, spec_for = uvenv
    for v in ("1.0.0", "2.0.0a1"):
        _wheel(index, v)

    uv("tool", "install", "--reinstall", spec_for("2.0.0a1"))          # NEXUS_CHANNEL=v4 install
    assert installed() == "dummy 2.0.0a1"

    _wheel(index, "2.0.0a2")                                              # next pre-release published
    target = channel.pick_update("2.0.0a1", ["1.0.0", "2.0.0a1", "2.0.0a2"])
    uv("tool", "install", "--reinstall", spec_for(target))
    assert installed() == "dummy 2.0.0a2"

    _wheel(index, "2.0.0")                                                # final published → graduate
    target = channel.pick_update("2.0.0a2", ["1.0.0", "2.0.0a1", "2.0.0a2", "2.0.0"])
    assert target == "2.0.0"
    uv("tool", "install", "--reinstall", spec_for(target))
    assert installed() == "dummy 2.0.0"

    _wheel(index, "2.1.0a1")                                              # stable users never get pre-releases
    uv("tool", "install", "--reinstall", spec_for("2.0.0"))
    assert installed() == "dummy 2.0.0"


def test_uv_back_to_stable_from_a_pre_release(uvenv):
    index, uv, installed, spec_for = uvenv
    for v in ("1.0.0", "2.0.0a2"):
        _wheel(index, v)
    uv("tool", "install", "--reinstall", spec_for("2.0.0a2"))
    assert installed() == "dummy 2.0.0a2"
    uv("tool", "install", "--reinstall", DUMMY)                            # `nexus channel stable`
    assert installed() == "dummy 1.0.0"


def test_uvx_needs_the_pre_release_spec(uvenv):
    """Why the MCP config names `>=4.0.0a0` on the pre channel: plain --from picks stable."""
    index, uv, _, spec_for = uvenv
    for v in ("1.0.0", "2.0.0a1"):
        _wheel(index, v)
    assert uv("tool", "run", "--from", DUMMY, "nexusdummy").strip() == "dummy 1.0.0"
    assert uv("tool", "run", "--from", spec_for("2.0.0a1"), "nexusdummy").strip() == "dummy 2.0.0a1"
