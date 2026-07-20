from tools.auto_exec import _execution_enabled


def test_auto_execution_fails_closed_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("EXECUTION_ENABLED", raising=False)
    assert _execution_enabled() is False


def test_auto_execution_accepts_only_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("EXECUTION_ENABLED", "paper")
    assert _execution_enabled() is True
    monkeypatch.setenv("EXECUTION_ENABLED", "unexpected")
    assert _execution_enabled() is False
