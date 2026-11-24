import pytest


@pytest.fixture(autouse=True)
def _never_call_typesafe(monkeypatch):
    """No test may reach the real TypeSafe API: without TYPESAFE_API_KEY every judgment is off.
    Tests of the TypeSafe path set a fake key and replace the client calls themselves."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _never_install_commit_hooks(monkeypatch):
    """No test downloads pre-commit through uvx: the commit-msg install is faked (and recorded).
    test_commit_check.py runs the real one, marked network."""
    import nexus_cli
    calls = []

    def fake(root):
        calls.append(root)
        return None
    monkeypatch.setattr(nexus_cli, "_install_commit_hook", fake)
    return calls


@pytest.fixture(autouse=True)
def _no_global_claude_commands(monkeypatch, tmp_path_factory):
    """The owner's own ~/.claude/commands (nexus 3 copies) must not change test results: point nexus at an empty one."""
    import nexus_cli
    monkeypatch.setattr(nexus_cli, "_GLOBAL_CLAUDE_DIR", tmp_path_factory.mktemp("home-claude"))
