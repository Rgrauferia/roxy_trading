from streamlit_app import alpaca_operations_gate, render_alpaca_operations_gate


def test_alpaca_operations_gate_defaults_configured_credentials_to_paper_only():
    gate = alpaca_operations_gate(
        {
            "ALPACA_API_KEY": "paper-key-value",
            "ALPACA_API_SECRET": "paper-secret-value",
        }
    )

    assert gate["mode"] == "PAPER_ONLY"
    assert gate["status"] == "Paper listo"
    assert gate["paper_orders_allowed"] is True
    assert gate["live_orders_allowed"] is False
    assert gate["endpoint_mode"] == "paper"
    assert "paper-key-value" not in str(gate)
    assert "paper-secret-value" not in str(gate)


def test_alpaca_operations_gate_blocks_live_endpoint_even_with_credentials():
    gate = alpaca_operations_gate(
        {
            "ALPACA_API_KEY": "live-key-value",
            "ALPACA_API_SECRET": "live-secret-value",
            "ALPACA_PAPER": "false",
            "ALPACA_BASE_URL": "https://api.alpaca.markets",
        }
    )

    assert gate["mode"] == "LIVE_LOCKED"
    assert gate["status"] == "Live bloqueado"
    assert gate["tone"] == "avoid"
    assert gate["paper_orders_allowed"] is False
    assert gate["live_orders_allowed"] is False
    assert gate["live_detected"] is True
    assert "live-key-value" not in str(gate)
    assert "live-secret-value" not in str(gate)


def test_alpaca_operations_gate_blocks_paper_when_endpoint_points_to_live():
    gate = alpaca_operations_gate(
        {
            "ALPACA_API_KEY": "paper-key-value",
            "ALPACA_API_SECRET": "paper-secret-value",
            "ALPACA_PAPER": "true",
            "ALPACA_BASE_URL": "https://api.alpaca.markets",
        }
    )

    assert gate["mode"] == "ENDPOINT_MISMATCH"
    assert gate["status"] == "Endpoint desalineado"
    assert gate["paper_orders_allowed"] is False
    assert gate["live_orders_allowed"] is False
    assert gate["endpoint_mismatch"] is True
    assert "paper-key-value" not in str(gate)
    assert "paper-secret-value" not in str(gate)


def test_alpaca_operations_gate_reports_missing_secret_without_values():
    gate = alpaca_operations_gate({"ALPACA_API_KEY": "key-only"})

    assert gate["mode"] == "NOT_CONFIGURED"
    assert gate["missing"] == "ALPACA_API_SECRET or ALPACA_SECRET_KEY"
    assert gate["present_keys"] == "ALPACA_API_KEY"
    assert "key-only" not in str(gate)


def test_render_alpaca_operations_gate_hides_values_and_labels_live_as_locked():
    html = render_alpaca_operations_gate(
        {
            "ALPACA_API_KEY": "live-key-value",
            "ALPACA_SECRET_KEY": "live-secret-value",
            "ALPACA_PAPER": "false",
            "ALPACA_ENDPOINT": "https://api.alpaca.markets",
        }
    )

    assert "Live orders: LOCKED" in html
    assert "ALPACA_API_KEY" in html
    assert "ALPACA_SECRET_KEY" in html
    assert "live-key-value" not in html
    assert "live-secret-value" not in html


def test_alpaca_operations_gate_blocks_paper_when_runtime_auth_is_invalid():
    report = {
        "checks": [
            {
                "name": "alpaca_account_probe",
                "status": "WARN",
                "auth_ok": False,
                "error_category": "AUTH_INVALID",
                "detail": "account authentication failed",
            }
        ]
    }

    gate = alpaca_operations_gate(
        {
            "ALPACA_API_KEY": "rejected-key-value",
            "ALPACA_API_SECRET": "rejected-secret-value",
            "ALPACA_PAPER": "true",
        },
        realtime_report=report,
    )

    assert gate["configured"] is True
    assert gate["paper_ready"] is False
    assert gate["paper_orders_allowed"] is False
    assert gate["live_orders_allowed"] is False
    assert gate["mode"] == "AUTH_INVALID"
    assert gate["status"] == "Autenticacion invalida"
    assert gate["runtime_checked"] is True
    assert gate["runtime_auth_ok"] is False
    assert "rejected-key-value" not in str(gate)
    assert "rejected-secret-value" not in str(gate)
