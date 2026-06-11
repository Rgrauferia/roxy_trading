from streamlit_app import live_provider_rows


def row_for(rows, provider):
    return next(row for row in rows if row["provider"] == provider)


def test_live_provider_rows_flags_partial_alpaca_credentials_without_values():
    rows = live_provider_rows(env={"ALPACA_API_KEY": "key-only"})
    alpaca = row_for(rows, "Alpaca")

    assert alpaca["configured"] is False
    assert alpaca["status"] == "Faltan credenciales"
    assert alpaca["tone"] == "avoid"
    assert alpaca["present"] == 1
    assert alpaca["missing"] == "ALPACA_API_SECRET"
    assert "key-only" not in str(alpaca)


def test_live_provider_rows_marks_alpaca_ready_for_paper_when_key_and_secret_exist():
    rows = live_provider_rows(env={"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret"})
    alpaca = row_for(rows, "Alpaca")

    assert alpaca["configured"] is True
    assert alpaca["status"] == "Listo paper/preview"
    assert alpaca["tone"] == "buy"
    assert alpaca["missing"] == "-"


def test_live_provider_rows_keeps_finviz_and_tc2000_as_reference_only():
    rows = live_provider_rows(env={})

    assert row_for(rows, "Finviz")["status"] == "Referencia"
    assert row_for(rows, "TC2000")["mode"] == "MANUAL_LINK"
