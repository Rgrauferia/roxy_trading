from types import SimpleNamespace

from streamlit_app import alpaca_paper_account_snapshot, render_alpaca_paper_account_panel


def test_alpaca_paper_account_snapshot_reads_account_with_paper_client_only():
    calls = {}

    def factory(api_key, secret_key):
        calls["api_key"] = api_key
        calls["secret_key"] = secret_key

        class FakeClient:
            def get_account(self):
                return SimpleNamespace(
                    buying_power="12500.50",
                    cash="10000.00",
                    portfolio_value="15125.75",
                    equity="15125.75",
                    status="ACTIVE",
                    trading_blocked=False,
                    pattern_day_trader=False,
                )

        return FakeClient()

    snapshot = alpaca_paper_account_snapshot(
        {"ALPACA_API_KEY": "paper-key-value", "ALPACA_API_SECRET": "paper-secret-value"},
        client_factory=factory,
    )

    assert snapshot["connected"] is True
    assert snapshot["status"] == "Paper conectado"
    assert snapshot["mode"] == "PAPER_ACCOUNT_SYNC"
    assert snapshot["buying_power"] == 12500.50
    assert snapshot["account_status"] == "ACTIVE"
    assert calls == {"api_key": "paper-key-value", "secret_key": "paper-secret-value"}
    assert "paper-key-value" not in str(snapshot)
    assert "paper-secret-value" not in str(snapshot)


def test_alpaca_paper_account_snapshot_blocks_live_endpoint_before_client_call():
    called = False

    def factory(api_key, secret_key):
        nonlocal called
        called = True
        raise AssertionError("client should not be created for live endpoint")

    snapshot = alpaca_paper_account_snapshot(
        {
            "ALPACA_API_KEY": "live-key-value",
            "ALPACA_API_SECRET": "live-secret-value",
            "ALPACA_PAPER": "false",
            "ALPACA_BASE_URL": "https://api.alpaca.markets",
        },
        client_factory=factory,
    )

    assert called is False
    assert snapshot["connected"] is False
    assert snapshot["mode"] == "LIVE_LOCKED"
    assert snapshot["paper_ready"] is False
    assert "live-key-value" not in str(snapshot)
    assert "live-secret-value" not in str(snapshot)


def test_render_alpaca_paper_account_panel_hides_values():
    html = render_alpaca_paper_account_panel({"ALPACA_API_KEY": "key-only"})

    assert "Alpaca Paper Account" in html
    assert "key-only" not in html
    assert "Credenciales pendientes" in html
