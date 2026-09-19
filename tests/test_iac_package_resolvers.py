"""Tests for the terraform/helm/ansible resolution mechanics in
tools/epav/package_resolver.py.

These never shell out to the real `terraform`/`helm`/`ansible-galaxy`
binaries -- CI doesn't have them installed. `subprocess.run` is monkeypatched
per test; the lock-file/output-parsing functions are tested directly against
real-world-shaped text captured from actual tool runs.
"""

from pathlib import Path

from tools.epav import package_resolver as pr


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ── terraform ────────────────────────────────────────────────────────────────

_TF_LOCK = """\
# This file is maintained automatically by "terraform init".
# Manual edits may be lost in future updates.

provider "registry.terraform.io/hashicorp/aws" {
  version     = "5.100.0"
  constraints = "~> 5.0"
  hashes = [
    "h1:abc=",
  ]
}

provider "registry.terraform.io/hashicorp/random" {
  version     = "3.9.1"
  constraints = "~> 3.6"
  hashes = [
    "h1:def=",
  ]
}
"""

# OpenTofu writes the same file with a different registry host --
# registry.opentofu.org instead of registry.terraform.io.
_OPENTOFU_LOCK = """\
# This file is maintained automatically by "tofu init".
# Manual edits may be lost in future updates.

provider "registry.opentofu.org/hashicorp/aws" {
  version     = "5.100.0"
  constraints = "~> 5.0"
  hashes = [
    "h1:abc=",
  ]
}
"""


def test_parse_terraform_source_splits_constraint():
    assert pr._parse_terraform_source("hashicorp/aws@~>5.0") == ("hashicorp/aws", "~>5.0")
    assert pr._parse_terraform_source("hashicorp/random") == ("hashicorp/random", None)


def test_read_terraform_lock_handles_opentofu_registry_host(tmp_path):
    # Regression: a host-specific regex silently parsed to zero versions
    # against a real OpenTofu-generated lock file (confirmed empirically).
    lock_path = tmp_path / ".terraform.lock.hcl"
    lock_path.write_text(_OPENTOFU_LOCK)
    assert pr._read_terraform_lock(lock_path, ["hashicorp/aws"]) == {"hashicorp/aws": "5.100.0"}


def test_terraform_binary_prefers_terraform_then_falls_back_to_tofu(monkeypatch):
    monkeypatch.setattr(pr.shutil, "which", lambda name: f"/usr/bin/{name}" if name in ("terraform", "tofu") else None)
    assert pr._terraform_binary() == "terraform"

    monkeypatch.setattr(pr.shutil, "which", lambda name: "/usr/bin/tofu" if name == "tofu" else None)
    assert pr._terraform_binary() == "tofu"

    monkeypatch.setattr(pr.shutil, "which", lambda name: None)
    assert pr._terraform_binary() == "terraform"  # neither installed -- fails loudly downstream, like every other tool here


def test_read_terraform_lock_extracts_exact_versions(tmp_path):
    lock_path = tmp_path / ".terraform.lock.hcl"
    lock_path.write_text(_TF_LOCK)
    versions = pr._read_terraform_lock(lock_path, ["hashicorp/aws", "hashicorp/random"])
    assert versions == {"hashicorp/aws": "5.100.0", "hashicorp/random": "3.9.1"}


def test_resolve_terraform_writes_required_providers_and_dedupes_local_names(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, cwd, capture_output, text, timeout):
        captured["cmd"] = cmd
        (Path(cwd) / ".terraform.lock.hcl").write_text(_TF_LOCK)
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(pr, "_terraform_binary", lambda: "terraform")
    monkeypatch.setattr(pr.subprocess, "run", fake_run)
    versions, errors = pr._resolve_terraform(tmp_path, ["hashicorp/aws@~>5.0", "hashicorp/random"])

    assert errors == []
    assert versions == {"hashicorp/aws": "5.100.0", "hashicorp/random": "3.9.1"}
    tf_content = (tmp_path / "versions.tf").read_text()
    assert 'source  = "hashicorp/aws"' in tf_content
    assert 'version = "~>5.0"' in tf_content
    assert captured["cmd"] == ["terraform", "init", "-backend=false", "-input=false"]


def test_resolve_terraform_reports_init_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pr.subprocess, "run",
        lambda *a, **k: _FakeCompletedProcess(returncode=1, stderr="init failed: bad provider"),
    )
    versions, errors = pr._resolve_terraform(tmp_path, ["hashicorp/aws"])
    assert versions == {}
    assert "init failed" in errors[0]


# ── helm ────────────────────────────────────────────────────────────────────

_HELM_LOCK = """\
dependencies:
- name: nginx
  repository: https://charts.bitnami.com/bitnami
  version: 15.0.2
digest: sha256:abc
generated: "2026-01-01T00:00:00Z"
"""


def test_parse_helm_package_all_three_forms():
    assert pr._parse_helm_package("nginx@~15.0.0@https://charts.bitnami.com/bitnami") == (
        "nginx", "~15.0.0", "https://charts.bitnami.com/bitnami",
    )
    assert pr._parse_helm_package("nginx@~15.0.0") == ("nginx", "~15.0.0", None)
    assert pr._parse_helm_package("nginx") == ("nginx", None, None)


def test_read_helm_lock_extracts_exact_versions(tmp_path):
    lock_path = tmp_path / "Chart.lock"
    lock_path.write_text(_HELM_LOCK)
    assert pr._read_helm_lock(lock_path, ["nginx"]) == {"nginx": "15.0.2"}


def test_resolve_helm_errors_on_missing_repository_without_failing_the_rest(tmp_path, monkeypatch):
    def fake_run(cmd, cwd, capture_output, text, timeout):
        (Path(cwd) / "Chart.lock").write_text(_HELM_LOCK)
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(pr.subprocess, "run", fake_run)
    versions, errors = pr._resolve_helm(
        tmp_path, ["nginx@~15.0.0@https://charts.bitnami.com/bitnami", "redis@~19.0.0"]
    )
    assert versions == {"nginx": "15.0.2"}
    assert any("redis" in e for e in errors)


def test_resolve_helm_skips_subprocess_when_no_deps_have_a_repo(tmp_path, monkeypatch):
    def fail_if_called(*a, **k):
        raise AssertionError("should not shell out to helm with zero resolvable deps")

    monkeypatch.setattr(pr.subprocess, "run", fail_if_called)
    versions, errors = pr._resolve_helm(tmp_path, ["redis@~19.0.0"])
    assert versions == {}
    assert len(errors) == 1


# ── ansible ─────────────────────────────────────────────────────────────────

_ANSIBLE_LIST_OUTPUT = """
# /Users/x/.local/share/uv/tools/ansible-core/lib/python3.11/site-packages/ansible/_internal/ansible_collections
Collection           Version
-------------------- -------
ansible._protomatter 2.19.13

# /tmp/nexus-resolve-xyz/collections/ansible_collections
Collection                               Version
---------------------------------------- -------
community.general                        13.4.0
community.library_inventory_filtering_v1 1.1.5
"""


def test_parse_ansible_package_splits_constraint():
    assert pr._parse_ansible_package("community.general:>=8.0.0") == ("community.general", ">=8.0.0")
    assert pr._parse_ansible_package("community.general") == ("community.general", None)


def test_parse_ansible_collection_list_only_reads_our_own_section():
    versions = pr._parse_ansible_collection_list(
        _ANSIBLE_LIST_OUTPUT,
        "/tmp/nexus-resolve-xyz/collections",
        ["community.general", "ansible._protomatter"],
    )
    # Only the collection installed under OUR temp dir counts, not ansible's
    # own bundled collection listed under a different path's section.
    assert versions == {"community.general": "13.4.0"}


def test_resolve_ansible_writes_requirements_yml_and_reads_versions(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["ansible-galaxy", "collection"] and "install" in cmd:
            return _FakeCompletedProcess(returncode=0)
        if cmd[:3] == ["ansible-galaxy", "collection", "list"]:
            collections_dir = cmd[-1]
            output = _ANSIBLE_LIST_OUTPUT.replace("/tmp/nexus-resolve-xyz/collections", collections_dir)
            return _FakeCompletedProcess(returncode=0, stdout=output)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(pr.subprocess, "run", fake_run)
    versions, errors = pr._resolve_ansible(tmp_path, ["community.general:>=8.0.0"])

    assert errors == []
    assert versions == {"community.general": "13.4.0"}
    req_content = (tmp_path / "requirements.yml").read_text()
    assert "name: community.general" in req_content
    assert 'version: ">=8.0.0"' in req_content
