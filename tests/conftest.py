import pytest


@pytest.fixture(autouse=True)
def _never_call_typesafe(monkeypatch):
    """No test may reach the real TypeSafe API: without TYPESAFE_API_KEY every judgment is off.
    Tests of the TypeSafe path set a fake key and replace the client calls themselves."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
