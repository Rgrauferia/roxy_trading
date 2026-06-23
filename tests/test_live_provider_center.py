from streamlit_app import (
    external_confirmation_plan,
    live_provider_effective_summary,
    live_provider_quality_summary,
    live_provider_rows,
    market_realtime_dashboard_rows,
    market_realtime_route_summary,
    render_external_confirmation_plan,
    render_market_realtime_route,
)


def row_for(rows, provider):
    return next(row for row in rows if row["provider"] == provider)


def test_live_provider_rows_flags_partial_alpaca_credentials_without_values():
    rows = live_provider_rows(env={"ALPACA_API_KEY": "key-only"})
    alpaca = row_for(rows, "Alpaca")

    assert alpaca["configured"] is False
    assert alpaca["status"] == "Faltan credenciales"
    assert alpaca["tone"] == "avoid"
    assert alpaca["present"] == 1
    assert alpaca["present_keys"] == "ALPACA_API_KEY"
    assert alpaca["missing"] == "ALPACA_API_SECRET or ALPACA_SECRET_KEY"
    assert "key-only" not in str(alpaca)


def test_live_provider_rows_marks_alpaca_ready_for_paper_when_key_and_secret_exist():
    rows = live_provider_rows(env={"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret"})
    alpaca = row_for(rows, "Alpaca")

    assert alpaca["configured"] is True
    assert alpaca["status"] == "Listo paper/preview"
    assert alpaca["tone"] == "buy"
    assert alpaca["missing"] == "-"
    assert alpaca["present_keys"] == "ALPACA_API_KEY, ALPACA_API_SECRET"


def test_live_provider_rows_accepts_alpaca_secret_key_alias_without_values():
    rows = live_provider_rows(env={"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "top-secret-value"})
    alpaca = row_for(rows, "Alpaca")

    assert alpaca["configured"] is True
    assert alpaca["status"] == "Listo paper/preview"
    assert alpaca["tone"] == "buy"
    assert alpaca["missing"] == "-"
    assert alpaca["present_keys"] == "ALPACA_API_KEY, ALPACA_SECRET_KEY"
    assert "top-secret-value" not in str(alpaca)


def test_live_provider_rows_keeps_finviz_and_tc2000_as_reference_only():
    rows = live_provider_rows(env={})

    assert row_for(rows, "Finviz")["status"] == "Referencia"
    assert row_for(rows, "TC2000")["mode"] == "MANUAL_LINK"


def test_live_provider_rows_marks_polygon_as_stock_data_provider():
    rows = live_provider_rows(env={"POLYGON_API_KEY": "polygon-key-value"})
    polygon = row_for(rows, "Polygon")

    assert polygon["configured"] is True
    assert polygon["status"] == "Listo data"
    assert polygon["tone"] == "buy"
    assert polygon["present_keys"] == "POLYGON_API_KEY"
    assert "polygon-key-value" not in str(polygon)


def test_live_provider_quality_summary_marks_default_as_fallback_only():
    summary = live_provider_quality_summary(live_provider_rows(env={}))

    assert summary["mode"] == "FALLBACK_ONLY"
    assert summary["status"] == "Fallback activo"
    assert summary["tone"] == "watch"
    assert "yfinance" in summary["detail"]
    assert "premium realtime" in summary["detail"]


def test_market_realtime_dashboard_rows_normalizes_market_cards():
    rows = market_realtime_dashboard_rows(
        {
            "market_realtime": {
                "rows": [
                    {
                        "market": "stock",
                        "label": "Acciones bloqueadas",
                        "tone": "avoid",
                        "detail": "1/1 fuentes con auth/permisos premium.",
                        "action": "Configurar POLYGON_API_KEY.",
                        "alerts_allowed": False,
                    },
                    {
                        "market": "crypto",
                        "label": "Cripto realtime",
                        "tone": "buy",
                        "detail": "1 fuente exchange/API valida.",
                        "alerts_allowed": True,
                    },
                ]
            }
        }
    )

    assert rows[0]["market"] == "STOCK"
    assert rows[0]["tone"] == "avoid"
    assert rows[0]["alerts_allowed"] is False
    assert rows[1]["market"] == "CRYPTO"
    assert rows[1]["tone"] == "buy"


def test_market_realtime_route_summary_prioritizes_operable_crypto_when_stock_blocked():
    summary = market_realtime_route_summary(
        {
            "provider_recovery": {
                "action": "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN.",
                "safe_mode": "NO_STOCK_OR_OPTIONS_ALERTS",
                "confirmation_gate": "NO_TRADE_FROM_FALLBACK",
                "alpaca_account_auth_ok": False,
                "alpaca_account_probe_status": "WARN",
                "alpaca_account_probe_diagnosis": "alpaca_account_auth_failed",
            },
            "market_realtime": {
                "rows": [
                    {"market": "stock", "label": "Acciones bloqueadas", "tone": "avoid", "alerts_allowed": False},
                    {"market": "crypto", "label": "Cripto realtime", "tone": "buy", "alerts_allowed": True},
                    {"market": "options", "label": "Opciones bloqueadas", "tone": "avoid", "alerts_allowed": False},
                ]
            },
        }
    )

    assert summary["label"] == "Operar solo CRYPTO"
    assert summary["tone"] == "watch"
    assert summary["allowed_markets"] == ["CRYPTO"]
    assert summary["blocked_markets"] == ["STOCK", "OPTIONS"]
    assert "Alpaca auth falla" in summary["detail"]
    assert "NO_TRADE_FROM_FALLBACK" in summary["detail"]


def test_render_market_realtime_route_outputs_sanitized_html():
    html = render_market_realtime_route(
        {
            "label": "Operar solo CRYPTO",
            "tone": "watch",
            "detail": "Accion: Configurar ALPACA_API_SECRET, no value",
            "allowed_markets": ["CRYPTO"],
            "blocked_markets": ["STOCK"],
        }
    )

    assert "Ruta realtime" in html
    assert "Operar solo CRYPTO" in html
    assert "route-chip-buy" in html
    assert "route-chip-avoid" in html
    assert "<script" not in html


def test_external_confirmation_plan_blocks_stock_fallback_and_links_finviz():
    plan = external_confirmation_plan(
        "AMD",
        "stock",
        {
            "provider_recovery": {"premium_blocked": True},
            "market_realtime": {
                "rows": [
                    {
                        "market": "stock",
                        "tone": "avoid",
                        "alerts_allowed": False,
                        "label": "Acciones bloqueadas",
                    }
                ]
            },
        },
    )

    assert plan["tone"] == "avoid"
    assert plan["gate"] == "NO_TRADE_FROM_FALLBACK"
    assert plan["alerts_allowed"] is False
    assert [link["label"] for link in plan["links"]] == ["Finviz", "TradingView", "Nasdaq"]
    assert "finviz.com/quote.ashx?t=AMD" in plan["links"][0]["url"]
    assert "no usar fallback" in plan["detail"]


def test_external_confirmation_plan_allows_crypto_exchange_confirmation():
    plan = external_confirmation_plan(
        "ETH/USD",
        "crypto",
        {"market_realtime": {"rows": [{"market": "crypto", "tone": "buy", "alerts_allowed": True}]}},
    )

    assert plan["tone"] == "buy"
    assert plan["gate"] == "EXCHANGE_API_CONFIRMED"
    assert plan["alerts_allowed"] is True
    assert [link["label"] for link in plan["links"]] == ["TradingView", "Yahoo", "CoinMarketCap"]


def test_render_external_confirmation_plan_outputs_safe_external_links():
    html = render_external_confirmation_plan(
        {
            "label": "Confirmacion externa obligatoria",
            "tone": "avoid",
            "gate": "NO_TRADE_FROM_FALLBACK",
            "symbol": "AMD",
            "market": "STOCK",
            "detail": "No usar fallback como gatillo.",
            "links": [
                {
                    "label": "Finviz",
                    "kind": "Company + screener",
                    "url": "https://finviz.com/quote.ashx?t=AMD",
                    "why": "Snapshot visual.",
                }
            ],
        }
    )

    assert "provider-confirmation-avoid" in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "NO_TRADE_FROM_FALLBACK" in html


def test_live_provider_quality_summary_marks_alpaca_as_paper_live_ready():
    rows = live_provider_rows(env={"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret"})
    summary = live_provider_quality_summary(rows)

    assert summary["mode"] == "PAPER_LIVE_READY"
    assert summary["status"] == "Credenciales presentes"
    assert summary["tone"] == "buy"
    assert summary["ready_providers"] == "Alpaca"
    assert "credenciales presentes" in summary["detail"]
    assert "Cada grafica valida" in summary["detail"]


def test_live_provider_quality_summary_marks_polygon_as_stock_premium_ready():
    rows = live_provider_rows(env={"POLYGON_API_TOKEN": "token"})
    summary = live_provider_quality_summary(rows)

    assert summary["mode"] == "STOCK_PREMIUM_READY"
    assert summary["status"] == "Credenciales presentes"
    assert summary["tone"] == "buy"
    assert summary["ready_providers"] == "Polygon"
    assert "Polygon puede alimentar velas premium" in summary["detail"]


def test_live_provider_effective_summary_downgrades_alpaca_auth_fallback():
    summary = live_provider_quality_summary(live_provider_rows(env={"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret"}))

    effective = live_provider_effective_summary(
        summary,
        {
            "provider": "yfinance",
            "source": "yfinance",
            "mode": "FALLBACK",
            "label": "yfinance fallback",
            "fallback_reason": "alpaca_auth",
            "fallback_detail": "Alpaca rechazo las credenciales o el token.",
            "fallback_action": "Revisar credenciales Alpaca.",
        },
    )

    assert effective["mode"] == "PROVIDER_FALLBACK"
    assert effective["status"] == "Proveedor en fallback"
    assert effective["tone"] == "avoid"
    assert effective["fallback_reason"] == "alpaca_auth"
    assert "credenciales" in effective["detail"]
    assert effective["next"] == "Revisar credenciales Alpaca."


def test_live_provider_quality_summary_surfaces_incomplete_credentials_first():
    rows = live_provider_rows(env={"ALPACA_API_KEY": "key-only"})
    summary = live_provider_quality_summary(rows)

    assert summary["mode"] == "CREDENTIALS_INCOMPLETE"
    assert summary["tone"] == "avoid"
    assert "ALPACA_API_SECRET or ALPACA_SECRET_KEY" in summary["detail"]
