from datetime import datetime, timezone
import json
from pathlib import Path

from system_diagnostics import (
    api_usage_check,
    authentication_security_check,
    backtest_engine_contract_check,
    binanceus_symbol_coverage_check,
    asset_identity_cache_check,
    cache_policy_check,
    collect_system_diagnostics,
    database_check,
    diagnostic_summary,
    device_sync_configuration_check,
    effective_diagnostic_provider_env,
    elevenlabs_runtime_check,
    frontend_chart_runtime_resource_check,
    frontend_actions_pro_chart_runtime_resource_check,
    frontend_actions_reference_terminal_resource_check,
    frontend_backtest_equity_runtime_resource_check,
    frontend_function_contract_check,
    frontend_stock_live_runtime_resource_check,
    frontend_three_universe_runtime_resource_check,
    frontend_style_resources_check,
    frontend_voice_runtime_resource_check,
    macro_calendar_data_check,
    macro_calendar_service_check,
    macro_calendar_sync_check,
    mobile_gateway_configuration_check,
    operational_state_check,
    operational_asset_identity_requirements,
    price_alert_monitor_check,
    opportunity_sync_check,
    navigation_route_contract_check,
    ui_control_contract_check,
    voice_remote_access_check,
    provider_checks,
    provider_environment_security_check,
    professional_chart_data_contract_check,
    realtime_report_checks,
    responsive_matrix_check,
    runtime_dependency_security_check,
    simulation_check,
    visual_strategy_engine_check,
)


def test_runtime_dependency_security_check_accepts_only_documented_build_exception(tmp_path: Path):
    report = tmp_path / "dependency_audit.json"
    report.write_text(
        '{"dependencies":[{"name":"setuptools","version":"82.0.1",'
        '"vulns":[{"id":"PYSEC-2026-3447"}]}]}',
        encoding="utf-8",
    )

    row = runtime_dependency_security_check(report, runtime_version=(3, 12, 13))

    assert row.status == "WARNING"
    assert "0 vulnerabilidades de runtime" in row.detail
    assert "build-only" in row.detail


def test_runtime_dependency_security_check_rejects_actionable_finding(tmp_path: Path):
    report = tmp_path / "dependency_audit.json"
    report.write_text(
        '{"dependencies":[{"name":"example","version":"1",'
        '"vulns":[{"id":"PYSEC-EXAMPLE"}]}]}',
        encoding="utf-8",
    )

    row = runtime_dependency_security_check(report, runtime_version=(3, 12, 13))

    assert row.status == "ERROR"
    assert "1 vulnerabilidad(es) de runtime" in row.detail


def test_runtime_dependency_security_check_rejects_legacy_python(tmp_path: Path):
    row = runtime_dependency_security_check(tmp_path / "missing.json", runtime_version=(3, 9, 6))

    assert row.status == "ERROR"
    assert "no cumple el piso 3.11" in row.detail


def test_frontend_style_resources_check_accepts_exact_split_contract(tmp_path: Path):
    style_dir = tmp_path / "assets" / "styles"
    style_dir.mkdir(parents=True)
    (style_dir / "roxy_base.css.html").write_text("<style>" + ("a" * 100_000), encoding="utf-8")
    (style_dir / "roxy_academy_auth.css").write_text(
        ".roxy-academy-shell{" + ("b" * 600_000),
        encoding="utf-8",
    )
    (style_dir / "roxy_responsive.css.html").write_text(
        '[data-testid="stTabs"] button{' + ("c" * 10_000) + "</style>",
        encoding="utf-8",
    )

    row = frontend_style_resources_check(tmp_path)

    assert row.status == "CONNECTED"
    assert "3/3 recursos" in row.detail
    assert "Academy/auth" in row.detail


def test_frontend_style_resources_check_reports_missing_chunk(tmp_path: Path):
    (tmp_path / "assets" / "styles").mkdir(parents=True)

    row = frontend_style_resources_check(tmp_path)

    assert row.status == "ERROR"
    assert "base" in row.detail
    assert "academy_auth" in row.detail


def test_frontend_voice_runtime_resource_check_accepts_safe_template_contract(tmp_path: Path):
    runtime_dir = tmp_path / "assets" / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "roxy_elevenlabs_assistant.js.html").write_text(
        "<script>" + "x" * 60_000
        + "__ROXY_VOICE_PAYLOAD_JSON____ROXY_VOICE_PAYLOAD_JSON__"
        + "__ROXY_AVATAR_MARKUP_JSON__Conversation.startSession</script>",
        encoding="utf-8",
    )
    (tmp_path / "streamlit_app.py").write_text(
        'def roxy_json_for_inline_script():\n    value.replace("<", "\\\\u003c")\n'
        "def roxy_elevenlabs_runtime_markup():\n    pass\n",
        encoding="utf-8",
    )

    row = frontend_voice_runtime_resource_check(tmp_path)

    assert row.status == "CONNECTED"
    assert "marcadores 3/3" in row.detail


def test_frontend_voice_runtime_resource_check_reports_missing_template(tmp_path: Path):
    row = frontend_voice_runtime_resource_check(tmp_path)

    assert row.status == "ERROR"
    assert "Falta la plantilla" in row.detail


def test_frontend_chart_runtime_resource_check_accepts_complete_safe_contract(tmp_path: Path):
    runtime_dir = tmp_path / "assets" / "runtime"
    vendor_dir = tmp_path / "assets" / "vendor"
    runtime_dir.mkdir(parents=True)
    vendor_dir.mkdir(parents=True)
    (runtime_dir / "roxy_live_candle_chart.html").write_text(
        '<div id="roxy-live-chart-root">' + "x" * 100_000
        + "__ROXY_PAYLOAD____LIGHTWEIGHT_INLINE__"
        + "LightweightCharts.createChart chart.subscribeCrosshairMove openKlineSocket() "
        + 'sourceCandleByTime mergeStreamKline aggregationSeconds data-fasttf="20m" data-fasttf="30m" '
        + 'data-fasttf="2h" data-fasttf="4h" data-indicator="EMA50" data-indicator="EMA200" '
        + 'data-indicator="VWAP" technicalMetrics id="rlc-rsi-chart" id="rlc-macd-chart" '
        + 'id="rlc-candle-countdown" id="rlc-session-legend" decorateSessionCandle '
        + 'roxy-chart-viewport:v1 restoreViewport priceScaleMode = indicatorSettings.Scale ? "auto-visible" : "manual-axis" '
        + 'renderCandleCountdown subscribeVisibleTimeRangeChange</script>',
        encoding="utf-8",
    )
    (vendor_dir / "lightweight-charts.4.2.3.min.js").write_text(
        "LightweightCharts" + "v" * 100_000,
        encoding="utf-8",
    )
    (tmp_path / "streamlit_app.py").write_text(
        "def roxy_json_for_inline_script(): pass\n"
        "def roxy_live_chart_runtime_markup(): pass\n"
        "def chart_stream_source_interval_seconds(): pass\n"
        'mapping = {"20m": "5m", "30m": "30m"}\n'
        'payload = {"aggregationSeconds": 1200}\n'
        'window = add_central_indicators(window)\n'
        'contract = {"oscillators": {}, "metrics": {}}\n'
        'session_contract = {}; contract = {"session": session_contract}\n'
        'contract = {"sessionVisual": {}}\n'
        "def chart_market_session_contract(): pass\n"
        "def stock_candle_session_phase(): pass\n"
        'viewport = {"viewport": dict()}\n'
        "roxy_live_chart_runtime_markup()\n",
        encoding="utf-8",
    )

    row = frontend_chart_runtime_resource_check(tmp_path)

    assert row.status == "CONNECTED"
    assert "marcadores 2/2" in row.detail
    assert "JSON protegido" in row.detail
    assert "20m derivado de 5m" in row.detail
    assert "paneles RSI/MACD sincronizados" in row.detail
    assert "cuenta regresiva de vela" in row.detail
    assert "bordes PRE/POST" in row.detail
    assert "viewport/escala persistibles" in row.detail


def test_frontend_chart_runtime_resource_check_reports_missing_resources(tmp_path: Path):
    row = frontend_chart_runtime_resource_check(tmp_path)

    assert row.status == "ERROR"
    assert "roxy_live_candle_chart.html" in row.detail
    assert "lightweight-charts.4.2.3.min.js" in row.detail


def test_professional_chart_data_contract_accepts_explicit_central_contract(tmp_path: Path):
    app = tmp_path / "streamlit_app.py"
    app.write_text(
        "def prepare_chart_window(chart_df): return chart_df.replace([float('inf')], None)\n"
        "def explicit_chart_target_rows(setup, confluence, brief):\n"
        "    target_ladder = brief.get('target_ladder', [])\n"
        "    return [{'source': 'brief.target_ladder'} for _ in target_ladder]\n"
        "def chart_trade_direction(setup, confluence, brief, entry=None, stop=None, targets=None):\n"
        "    return 'SHORT' if stop is not None and entry is not None and stop > entry else 'LONG'\n"
        "def build_chart_level_plan(chart_df, setup, confluence, brief):\n"
        "    return explicit_chart_target_rows(setup, confluence, brief)\n"
        "def build_professional_price_chart(chart_df, setup, confluence, brief):\n"
        "    chart_window = prepare_chart_window(chart_df)\n"
        "    return chart_window, explicit_chart_target_rows(setup, confluence, brief)\n"
        "def build_professional_oscillator_chart(chart_df): return chart_df\n",
        encoding="utf-8",
    )

    row = professional_chart_data_contract_check(app)

    assert row.status == "CONNECTED"
    assert "objetivos explícitos con procedencia" in row.detail
    assert "sin rolling/ewm local" in row.detail


def test_professional_chart_data_contract_rejects_inferred_targets(tmp_path: Path):
    app = tmp_path / "streamlit_app.py"
    app.write_text(
        "def prepare_chart_window(chart_df): return chart_df\n"
        "def explicit_chart_target_rows(setup, confluence, brief): return [{'source': 'x', 'target_ladder': []}]\n"
        "def chart_trade_direction(setup, confluence, brief, entry=None, stop=None, targets=None):\n"
        "    return 'SHORT' if stop is not None and entry is not None and stop > entry else 'LONG'\n"
        "def build_chart_level_plan(chart_df, setup, confluence, brief):\n"
        "    explicit_chart_target_rows(setup, confluence, brief)\n"
        "    return entry * 1.02\n"
        "def build_professional_price_chart(chart_df, setup, confluence, brief):\n"
        "    prepare_chart_window(chart_df)\n"
        "    explicit_chart_target_rows(setup, confluence, brief)\n"
        "    return entry * 1.10\n"
        "def build_professional_oscillator_chart(chart_df): return chart_df\n",
        encoding="utf-8",
    )

    row = professional_chart_data_contract_check(app)

    assert row.status == "ERROR"
    assert "objetivos porcentuales implícitos" in row.detail


def test_frontend_actions_pro_chart_runtime_resource_check_accepts_safe_contract(tmp_path: Path):
    runtime_dir = tmp_path / "assets" / "runtime"
    vendor_dir = tmp_path / "assets" / "vendor"
    runtime_dir.mkdir(parents=True)
    vendor_dir.mkdir(parents=True)
    (runtime_dir / "roxy_actions_pro_chart.html").write_text(
        '<div class="roxy-pro-chart">' + "x" * 45_000
        + "__PAYLOAD____LIGHTWEIGHT_INLINE____CHART_ID____CHART_ID__"
        + "LightweightCharts.createChart chart.subscribeCrosshairMove roxy-stock-quote</script>",
        encoding="utf-8",
    )
    (vendor_dir / "lightweight-charts.4.2.3.min.js").write_text(
        "LightweightCharts" + "v" * 100_000,
        encoding="utf-8",
    )
    (tmp_path / "streamlit_app.py").write_text(
        "def roxy_json_for_inline_script(): pass\n"
        "def roxy_actions_pro_chart_runtime_markup():\n"
        '    re.fullmatch(r"[A-Za-z0-9_-]{1,80}", "id")\n'
        "roxy_actions_pro_chart_runtime_markup()\n",
        encoding="utf-8",
    )

    row = frontend_actions_pro_chart_runtime_resource_check(tmp_path)

    assert row.status == "CONNECTED"
    assert "marcadores 4/4" in row.detail
    assert "DOM id protegidos" in row.detail


def test_frontend_actions_pro_chart_runtime_resource_check_reports_missing_resources(tmp_path: Path):
    row = frontend_actions_pro_chart_runtime_resource_check(tmp_path)

    assert row.status == "ERROR"
    assert "roxy_actions_pro_chart.html" in row.detail
    assert "lightweight-charts.4.2.3.min.js" in row.detail


def test_frontend_actions_reference_terminal_resource_check_accepts_complete_contract(tmp_path: Path):
    runtime_dir = tmp_path / "assets" / "runtime"
    runtime_dir.mkdir(parents=True)
    markers = " ".join(f"__ROXY_ACTIONS_SLOT_{index:02d}__" for index in range(33))
    (runtime_dir / "roxy_actions_reference_terminal.html").write_text(
        '<style id="roxy-actions-terminal-v3">' + "x" * 25_000
        + markers
        + '<section class="roxy-actions-terminal"><div class="terminal-top-strip"></div>'
        + '<div class="terminal-chart-row"></div><div class="terminal-grid"></div>'
        + '<div class="strategy-terminal-section">Lightweight Charts local</div></section></style>',
        encoding="utf-8",
    )
    (tmp_path / "streamlit_app.py").write_text(
        "ROXY_ACTIONS_REFERENCE_TERMINAL_MARKERS = ()\n"
        "def roxy_actions_reference_terminal_template(): pass\n"
        "def roxy_actions_reference_terminal_markup(): pass\n"
        "roxy_actions_reference_terminal_markup()\n",
        encoding="utf-8",
    )

    row = frontend_actions_reference_terminal_resource_check(tmp_path)

    assert row.status == "CONNECTED"
    assert "marcadores 33/33" in row.detail
    assert "slots completos" in row.detail


def test_frontend_actions_reference_terminal_resource_check_reports_missing_template(tmp_path: Path):
    row = frontend_actions_reference_terminal_resource_check(tmp_path)

    assert row.status == "ERROR"
    assert "roxy_actions_reference_terminal.html" in row.detail


def test_frontend_backtest_equity_runtime_resource_check_accepts_safe_contract(tmp_path: Path):
    runtime_dir = tmp_path / "assets" / "runtime"
    vendor_dir = tmp_path / "assets" / "vendor"
    runtime_dir.mkdir(parents=True)
    vendor_dir.mkdir(parents=True)
    (runtime_dir / "roxy_backtest_equity_chart.html").write_text(
        '<div id="roxy-backtest-equity-root">' + "x" * 4_000
        + "__ROXY_BACKTEST_EQUITY_PAYLOAD____LIGHTWEIGHT_INLINE__"
        + "LightweightCharts.createChart chart.subscribeCrosshairMove ResizeObserver</script>",
        encoding="utf-8",
    )
    (vendor_dir / "lightweight-charts.4.2.3.min.js").write_text(
        "LightweightCharts" + "v" * 100_000,
        encoding="utf-8",
    )
    (tmp_path / "streamlit_app.py").write_text(
        "def roxy_json_for_inline_script(): pass\n"
        "def roxy_backtest_equity_runtime_markup(): pass\n"
        "def render_backtest_equity_chart(): pass\n",
        encoding="utf-8",
    )

    row = frontend_backtest_equity_runtime_resource_check(tmp_path)

    assert row.status == "CONNECTED"
    assert "marcadores 2/2" in row.detail
    assert "crosshair y JSON seguros" in row.detail


def test_frontend_backtest_equity_runtime_resource_check_reports_missing_resources(tmp_path: Path):
    row = frontend_backtest_equity_runtime_resource_check(tmp_path)

    assert row.status == "ERROR"
    assert "roxy_backtest_equity_chart.html" in row.detail
    assert "lightweight-charts.4.2.3.min.js" in row.detail


def test_frontend_stock_live_runtime_resource_check_accepts_safe_template_contract(tmp_path: Path):
    runtime_dir = tmp_path / "assets" / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "roxy_stock_live_runtime.js.html").write_text(
        "<script>" + "x" * 20_000
        + "__ROXY_STOCK_STREAM_URL____ROXY_STOCK_SNAPSHOT_URL__"
        + "new EventSource fetchBridgeSnapshot roxy-stock-quote</script>",
        encoding="utf-8",
    )
    (runtime_dir / "roxy_stock_server_refresh.js.html").write_text(
        "<script>" + "x" * 10_000
        + "__ROXY_STOCK_QUOTES__ data-roxy-stock-live-price data-roxy-stock-provider-state "
        + "setRefreshMeta setTradeState roxy-stock-quote</script>",
        encoding="utf-8",
    )
    (tmp_path / "streamlit_app.py").write_text(
        "def roxy_json_for_inline_script(): pass\n"
        "def roxy_stock_live_runtime_markup(): pass\n"
        "roxy_stock_live_runtime_markup()\n"
        "def roxy_stock_server_refresh_runtime_markup(): pass\n"
        "roxy_stock_server_refresh_runtime_markup()\n",
        encoding="utf-8",
    )

    row = frontend_stock_live_runtime_resource_check(tmp_path)

    assert row.status == "CONNECTED"
    assert "marcadores 3/3" in row.detail
    assert "URLs y cotizaciones protegidas" in row.detail


def test_frontend_stock_live_runtime_resource_check_reports_missing_template(tmp_path: Path):
    row = frontend_stock_live_runtime_resource_check(tmp_path)

    assert row.status == "ERROR"
    assert "roxy_stock_live_runtime.js.html" in row.detail


def test_frontend_three_universe_runtime_resource_check_accepts_complete_contract(tmp_path: Path):
    runtime_dir = tmp_path / "assets" / "runtime"
    vendor_dir = tmp_path / "assets" / "vendor"
    runtime_dir.mkdir(parents=True)
    vendor_dir.mkdir(parents=True)
    (runtime_dir / "roxy_three_universe_runtime.js.html").write_text(
        "<script>" + "x" * 15_000 + "__ROXY_THREE_INLINE_SOURCE__"
        + "MutationObserver roxy-three-canvas roxy-three-fallback-hidden</script>",
        encoding="utf-8",
    )
    (vendor_dir / "three.r128.min.js").write_text("THREE" + "v" * 100_000, encoding="utf-8")
    (tmp_path / "streamlit_app.py").write_text(
        "def roxy_json_for_inline_script(): pass\n"
        "def roxy_three_universe_runtime_markup(): pass\n"
        "roxy_three_universe_runtime_markup()\n",
        encoding="utf-8",
    )

    row = frontend_three_universe_runtime_resource_check(tmp_path)

    assert row.status == "CONNECTED"
    assert "marcador 1/1" in row.detail
    assert "carga progresiva segura" in row.detail


def test_frontend_three_universe_runtime_resource_check_reports_missing_resources(tmp_path: Path):
    row = frontend_three_universe_runtime_resource_check(tmp_path)

    assert row.status == "ERROR"
    assert "roxy_three_universe_runtime.js.html" in row.detail
    assert "three.r128.min.js" in row.detail


def test_binanceus_symbol_coverage_check_accepts_current_exact_catalog(tmp_path: Path):
    path = tmp_path / "coverage.json"
    path.write_text(
        '{"contract_version":"roxy-binanceus-symbol-coverage/1.0.0",'
        '"status":"CONNECTED","generated_at":"2026-07-19T14:00:00+00:00",'
        '"requested_count":25,"supported_count":25,"unsupported_count":0,'
        '"exact_count":25,"quote_fallback_count":0}',
        encoding="utf-8",
    )

    row = binanceus_symbol_coverage_check(
        path,
        now=datetime(2026, 7, 19, 14, 10, tzinfo=timezone.utc),
    )

    assert row.status == "CONNECTED"
    assert "25/25" in row.detail
    assert "exactos 25" in row.detail


def test_binanceus_symbol_coverage_check_warns_for_stale_or_fallback_catalog(tmp_path: Path):
    path = tmp_path / "coverage.json"
    path.write_text(
        '{"contract_version":"roxy-binanceus-symbol-coverage/1.0.0",'
        '"status":"CONNECTED","generated_at":"2026-07-19T12:00:00+00:00",'
        '"requested_count":2,"supported_count":2,"unsupported_count":0,'
        '"exact_count":1,"quote_fallback_count":1}',
        encoding="utf-8",
    )

    row = binanceus_symbol_coverage_check(
        path,
        now=datetime(2026, 7, 19, 14, 0, tzinfo=timezone.utc),
    )

    assert row.status == "WARNING"
    assert "fallback 1" in row.detail
    assert "120.0 min" in row.detail


def test_binanceus_symbol_coverage_check_warns_when_provider_catalog_is_unavailable(tmp_path: Path):
    path = tmp_path / "coverage.json"
    path.write_text(
        '{"contract_version":"roxy-binanceus-symbol-coverage/1.0.0",'
        '"status":"PROVIDER_UNAVAILABLE","generated_at":"2026-07-19T14:00:00+00:00",'
        '"requested_count":25,"supported_count":0,"unsupported_count":0,'
        '"exact_count":0,"quote_fallback_count":0}',
        encoding="utf-8",
    )

    row = binanceus_symbol_coverage_check(
        path,
        now=datetime(2026, 7, 19, 14, 5, tzinfo=timezone.utc),
    )

    assert row.status == "WARNING"
    assert "PROVIDER_UNAVAILABLE" in row.detail


def test_api_usage_diagnostic_reports_no_data_without_creating_storage(tmp_path: Path):
    row = api_usage_check(tmp_path, {})

    assert row.status == "NO_DATA"
    assert "roxy-api-budget/1.0.0" in row.detail
    assert "14 proveedores" in row.detail
    assert "modo protect" in row.detail
    assert not (tmp_path / "data" / "roxy_api_usage.sqlite").exists()


def test_api_usage_diagnostic_reports_invalid_override_without_value(tmp_path: Path):
    secret_like_value = "invalid-secret-like-value"
    row = api_usage_check(tmp_path, {"ROXY_API_BUDGET_ALPACA_PER_MINUTE": secret_like_value})

    assert row.status == "WARNING"
    assert "ROXY_API_BUDGET_ALPACA_PER_MINUTE" in row.detail
    assert secret_like_value not in row.detail


def test_api_usage_diagnostic_reports_rate_limit_without_secrets(tmp_path: Path):
    from roxy_trader.api_budget import ApiUsageLedger

    secret_like_value = "provider-secret-value"
    ledger = ApiUsageLedger(tmp_path / "data" / "roxy_api_usage.sqlite")
    ledger.record(provider="polygon", operation="candles", status="ERROR", http_status=429)

    row = api_usage_check(tmp_path, {"POLYGON_API_KEY": secret_like_value})

    assert row.status == "WARNING"
    assert "rate limits 1" in row.detail
    assert secret_like_value not in row.detail


def test_api_usage_diagnostic_exposes_provider_error_not_secret(tmp_path: Path):
    from roxy_trader.api_budget import ApiUsageLedger

    secret_like_value = "elevenlabs-secret-value"
    ledger = ApiUsageLedger(tmp_path / "data" / "roxy_api_usage.sqlite")
    ledger.record(provider="elevenlabs", operation="conversation_token", status="ERROR", http_status=401)

    row = api_usage_check(tmp_path, {"ELEVENLABS_API_KEY": secret_like_value})

    assert row.status == "WARNING"
    assert "elevenlabs ERROR x1" in row.detail
    assert "errores 1/1" in row.detail
    assert "Incidentes 24h: elevenlabs errores 1/429 0" in row.detail
    assert "elevenlabs 1 req/24h (presupuesto 10/min)" in row.detail
    assert secret_like_value not in row.detail


def test_elevenlabs_runtime_diagnostic_exposes_auth_failure_without_secret(tmp_path: Path):
    from roxy_trader.api_budget import ApiUsageLedger

    ledger = ApiUsageLedger(tmp_path / "data" / "roxy_api_usage.sqlite")
    ledger.record(
        provider="elevenlabs",
        operation="conversation_token",
        status="ERROR",
        http_status=401,
        occurred_at=datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
    )

    result = elevenlabs_runtime_check(
        tmp_path,
        now=datetime(2026, 7, 19, 13, tzinfo=timezone.utc),
    )

    assert result.status == "ERROR"
    assert "AUTH_INVALID" in result.detail
    assert "HTTP 401" in result.detail
    assert "conversation_token" in result.detail


def test_elevenlabs_runtime_diagnostic_exposes_active_auth_circuit(tmp_path: Path):
    from roxy_trader.api_budget import ApiUsageLedger

    ledger = ApiUsageLedger(tmp_path / "data" / "roxy_api_usage.sqlite")
    ledger.record(
        provider="elevenlabs",
        operation="conversation_token",
        status="ERROR",
        http_status=401,
        occurred_at=datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
    )
    circuit = tmp_path / "alerts" / "elevenlabs_auth_circuit.json"
    circuit.parent.mkdir()
    circuit.write_text(
        json.dumps(
            {
                "state": "AUTH_INVALID",
                "failed_at": "2026-07-19T12:55:00+00:00",
                "retry_seconds": 21_600,
                "fingerprint": "non-secret-digest",
            }
        ),
        encoding="utf-8",
    )

    result = elevenlabs_runtime_check(
        tmp_path,
        now=datetime(2026, 7, 19, 13, tzinfo=timezone.utc),
    )

    assert result.status == "ERROR"
    assert "Circuito protector activo" in result.detail
    assert "21300s" in result.detail
    assert "non-secret-digest" not in result.detail


def test_cache_policy_diagnostic_reports_contract_without_environment_values():
    secret_like_value = "not-a-number-secret"
    row = cache_policy_check({"ROXY_CACHE_TTL_LIVE_PRICE": secret_like_value})

    assert row.status == "WARNING"
    assert "roxy-cache/1.0.0" in row.detail
    assert "ROXY_CACHE_TTL_LIVE_PRICE" in row.detail
    assert secret_like_value not in row.detail


def test_cache_policy_diagnostic_is_connected_with_default_contract():
    row = cache_policy_check({})

    assert row.status == "CONNECTED"
    assert "22 clases" in row.detail
    assert "Todos los TTL dentro de limites" in row.detail


def _create_auth_storage(root: Path, profiles: dict, *, plaintext_db_token: str = "") -> None:
    import json
    import os
    import sqlite3

    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "db").mkdir(parents=True, exist_ok=True)
    users_path = root / "data" / "roxy_users.json"
    users_path.write_text(json.dumps({"users": profiles}))
    os.chmod(users_path, 0o600)
    db_path = root / "db" / "roxy.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE roxy_auth_users (username TEXT, profile_json TEXT, session_token TEXT)"
        )
        connection.execute(
            "CREATE TABLE roxy_auth_attempts (identifier_hash TEXT PRIMARY KEY, failures INTEGER)"
        )
        connection.execute(
            "INSERT INTO roxy_auth_users VALUES (?, ?, ?)",
            ("alice", json.dumps(profiles.get("alice", {})), plaintext_db_token),
        )
    os.chmod(db_path, 0o600)


def test_authentication_security_check_accepts_hardened_storage(tmp_path: Path):
    _create_auth_storage(
        tmp_path,
        {"alice": {"username": "alice", "password_hash": "hash", "password_iterations": 600_000}},
    )

    result = authentication_security_check(tmp_path, env={})

    assert result.status == "CONNECTED"
    assert "throttle=activo" in result.detail
    assert "tokens plaintext 0" in result.detail
    assert "alice" not in result.detail
    assert "hash" not in result.detail


def test_authentication_security_check_detects_plaintext_tokens_and_weak_hashes(tmp_path: Path):
    _create_auth_storage(
        tmp_path,
        {
            "alice": {
                "username": "alice",
                "password_hash": "secret-hash",
                "password_iterations": 160_000,
                "session_token": "plaintext-secret-token",
            }
        },
        plaintext_db_token="another-plaintext-token",
    )

    result = authentication_security_check(tmp_path, env={})

    assert result.status == "ERROR"
    assert "tokens plaintext=" in result.detail
    assert "hashes por actualizar=1" in result.detail
    assert "plaintext-secret-token" not in result.detail
    assert "another-plaintext-token" not in result.detail


def test_authentication_security_check_warns_when_throttle_is_missing(tmp_path: Path):
    _create_auth_storage(tmp_path, {})
    import sqlite3

    with sqlite3.connect(tmp_path / "db" / "roxy.db") as connection:
        connection.execute("DROP TABLE roxy_auth_attempts")

    result = authentication_security_check(tmp_path, env={})

    assert result.status == "WARNING"
    assert "limitador persistente ausente" in result.detail


def test_database_check_reports_valid_read_only_database(tmp_path: Path):
    import sqlite3

    path = tmp_path / "roxy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("create table sample(id integer primary key)")

    result = database_check(path)

    assert result.status == "CONNECTED"
    assert "quick_check=ok" in result.detail
    assert "1 tablas" in result.detail


def test_database_check_supports_fast_ui_probe_without_deep_integrity_scan(tmp_path: Path):
    import sqlite3

    path = tmp_path / "roxy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("create table sample(id integer primary key)")

    result = database_check(path, deep=False)

    assert result.status == "CONNECTED"
    assert "lectura=ok" in result.detail
    assert "quick_check profundo diferido" in result.detail


def test_provider_checks_never_expose_secret_values():
    secret = "super-secret-value"
    rows = provider_checks(
        {
            "ALPACA_API_KEY": secret,
            "ALPACA_API_SECRET": secret,
            "ELEVENLABS_API_KEY": secret,
            "ELEVENLABS_AGENT_ID": "agent-id",
        }
    )

    serialized = str([row.to_dict() for row in rows])
    assert secret not in serialized
    assert next(row for row in rows if row.component == "Alpaca").status == "CONFIGURED"


def test_provider_checks_treat_elevenlabs_agent_id_as_optional():
    rows = provider_checks({"ELEVENLABS_API_KEY": "configured-but-never-rendered"})

    elevenlabs = next(row for row in rows if row.component == "ElevenLabs")
    assert elevenlabs.status == "CONFIGURED"
    assert "configuracion presente" in elevenlabs.detail.lower()
    assert "configured-but-never-rendered" not in str(elevenlabs.to_dict())


def test_provider_checks_merge_allowlisted_launchagent_context_without_exposing_values(tmp_path: Path):
    service_env = tmp_path / ".env"
    service_env.write_text(
        "ALPACA_API_KEY=service-key\n"
        "ALPACA_API_SECRET='service-secret'\n"
        "UNRELATED_PRIVATE_VALUE=must-not-load\n",
        encoding="utf-8",
    )

    values, loaded = effective_diagnostic_provider_env({}, service_env_path=service_env)
    rows = provider_checks({}, service_env_path=service_env)
    serialized = str([row.to_dict() for row in rows])

    assert loaded == ["ALPACA_API_KEY", "ALPACA_API_SECRET"]
    assert "UNRELATED_PRIVATE_VALUE" not in values
    assert next(row for row in rows if row.component == "Alpaca").status == "CONFIGURED"
    assert "service-key" not in serialized
    assert "service-secret" not in serialized


def test_provider_environment_security_requires_owner_only_files(tmp_path: Path):
    project_env = tmp_path / "project.env"
    service_env = tmp_path / "service.env"
    project_env.write_text("SECRET=hidden\n", encoding="utf-8")
    service_env.write_text("SECRET=hidden\n", encoding="utf-8")
    project_env.chmod(0o600)
    service_env.chmod(0o600)

    secure = provider_environment_security_check(project_env, service_env_path=service_env)
    project_env.chmod(0o644)
    insecure = provider_environment_security_check(project_env, service_env_path=service_env)

    assert secure.status == "CONNECTED"
    assert "0600" in secure.detail
    assert insecure.status == "ERROR"
    assert "Aplicar permisos 0600" in insecure.detail
    assert "hidden" not in secure.detail + insecure.detail


def test_provider_environment_security_includes_optional_local_override(tmp_path: Path):
    project_env = tmp_path / ".env"
    local_env = tmp_path / ".env.local"
    service_env = tmp_path / "service.env"
    for path in (project_env, local_env, service_env):
        path.write_text("SECRET=hidden\n", encoding="utf-8")
        path.chmod(0o600)

    secure = provider_environment_security_check(project_env, service_env_path=service_env)
    local_env.chmod(0o644)
    insecure = provider_environment_security_check(project_env, service_env_path=service_env)

    assert secure.status == "CONNECTED"
    assert "local=0600" in secure.detail
    assert insecure.status == "ERROR"
    assert "local" in insecure.detail
    assert "hidden" not in secure.detail + insecure.detail


def test_simulation_check_reports_live_execution_guard():
    result = simulation_check({"ROXY_ENABLE_LIVE_BROKER_EXECUTION": "0", "ALPACA_PAPER": "true"})

    assert result.status == "SIMULATED"
    assert "Ejecucion real bloqueada" in result.detail


def test_asset_identity_cache_check_validates_metadata_and_logo_blob(tmp_path: Path):
    cache = tmp_path / "asset_identity_cache"
    cache.mkdir()
    (cache / "aapl.png").write_bytes(b"png")
    (cache / "aapl.json").write_text(
        '{"logo_file":"aapl.png","logo_source":"simple_icons"}'
    )

    result = asset_identity_cache_check(cache)

    assert result.status == "CONNECTED"
    assert "1 logos cacheados" in result.detail
    assert "simple_icons=1" in result.detail


def test_asset_identity_cache_check_warns_when_an_operational_asset_has_no_cached_logo(tmp_path: Path):
    cache = tmp_path / "asset_identity_cache"
    cache.mkdir()
    (cache / "aapl.png").write_bytes(b"png")
    (cache / "aapl.json").write_text(
        '{"symbol":"AAPL","market":"stock","logo_file":"aapl.png","logo_source":"simple_icons"}',
        encoding="utf-8",
    )

    result = asset_identity_cache_check(cache, {("stock", "AAPL"), ("crypto", "BTC")})

    assert result.status == "WARNING"
    assert "cobertura operativa 1/2" in result.detail
    assert "crypto:BTC" in result.detail


def test_operational_asset_identity_requirements_reads_live_and_durable_symbols(tmp_path: Path):
    output = tmp_path / "output"
    alerts = tmp_path / "alerts"
    data = tmp_path / "data"
    output.mkdir()
    alerts.mkdir()
    data.mkdir()
    (output / "ma_live_strategy_crypto_20260719.csv").write_text(
        "market,symbol,tf\ncrypto,BTC/USD,1h\nstock,AAPL,1h\n",
        encoding="utf-8",
    )
    (alerts / "roxy_ai_brief.json").write_text(
        '{"opportunities":[{"symbol":"ETH-USDT","market":"crypto"}]}',
        encoding="utf-8",
    )
    (data / "roxy_watchlists.json").write_text(
        '{"users":{"u":{"lists":{"Main":{"items":[{"symbol":"MSFT","market":"stock"}]}}}}}',
        encoding="utf-8",
    )

    requirements = operational_asset_identity_requirements(tmp_path)

    assert requirements == {
        ("crypto", "BTC"),
        ("crypto", "ETH"),
        ("stock", "AAPL"),
        ("stock", "MSFT"),
    }


def test_diagnostic_summary_separates_failures_and_configuration_gaps():
    summary = diagnostic_summary(
        [
            {"status": "CONNECTED"},
            {"status": "DISCONNECTED"},
            {"status": "NOT_CONFIGURED"},
            {"status": "SIMULATED"},
        ]
    )

    assert summary == {
        "checked": 4,
        "unhealthy": 1,
        "not_configured": 1,
        "operational": 2,
        "generated_at": summary["generated_at"],
    }


def test_operational_state_check_reports_watchlist_and_alert_counts(tmp_path: Path):
    state = tmp_path / "roxy_watchlists.json"
    state.write_text(
        '{"schema_version":1,"users":{"user":{"lists":{"Principal":{"items":[{"symbol":"AAPL"}]}},'
        '"alerts":[{"status":"Activa"},{"status":"Activada"},{"status":"Archivada"}],'
        '"opportunity_archive":[{"symbol":"MSFT","status":"Expirada"}]}}}'
    )

    result = operational_state_check(state)

    assert result.status == "CONNECTED"
    assert "listas 1" in result.detail
    assert "activos 1" in result.detail
    assert "alertas activas 2" in result.detail
    assert "activadas 1" in result.detail
    assert "oportunidades archivadas 1" in result.detail


def test_price_alert_monitor_diagnostic_requires_fresh_contract(tmp_path: Path):
    import json

    report = tmp_path / "price_alert_monitor.json"
    report.write_text(
        json.dumps(
            {
                "contract_version": "roxy-durable-alert-monitor/2.0.0",
                "status": "OK",
                "generated_at": "2026-07-19T08:00:00+00:00",
                "active_alerts": 2,
                "evaluated": 2,
                "blocked": 0,
                "triggered": 1,
                "notifications": 1,
                "expired": 1,
                "notification_pending": 0,
                "permanent_delivery_failures": 0,
            }
        )
    )

    result = price_alert_monitor_check(
        report,
        now=datetime(2026, 7, 19, 8, 1, tzinfo=timezone.utc),
    )

    assert result.status == "CONNECTED"
    assert "evaluadas 2" in result.detail
    assert "activadas 1" in result.detail
    assert "expiradas 1" in result.detail
    assert "entregas pendientes 0" in result.detail
    assert "entrega durable reintentable" in result.detail


def test_price_alert_monitor_diagnostic_exposes_degraded_and_stale_states(tmp_path: Path):
    import json

    report = tmp_path / "price_alert_monitor.json"
    report.write_text(
        json.dumps(
            {
                "contract_version": "roxy-durable-alert-monitor/2.0.0",
                "status": "WARNING",
                "generated_at": "2026-07-19T08:00:00+00:00",
                "active_alerts": 1,
                "evaluated": 0,
                "blocked": 1,
            }
        )
    )
    degraded = price_alert_monitor_check(report, now=datetime(2026, 7, 19, 8, 1, tzinfo=timezone.utc))
    stale = price_alert_monitor_check(report, now=datetime(2026, 7, 19, 8, 5, tzinfo=timezone.utc))

    assert degraded.status == "WARNING"
    assert "bloqueadas 1" in degraded.detail
    assert stale.status == "ERROR"
    assert "proceso background esta vencido" in stale.detail


def test_opportunity_sync_diagnostic_requires_fresh_contract(tmp_path: Path):
    report = tmp_path / "opportunity_sync.json"
    report.write_text(
        '{"contract_version":"roxy-opportunity-sync/1.0.0","generated_at":"2026-07-19T08:00:00+00:00",'
        '"status":"OK","candidate_count":3,"trade_ready_count":1,"users":{"u":{}}}',
        encoding="utf-8",
    )
    result = opportunity_sync_check(report, now=datetime(2026, 7, 19, 8, 5, tzinfo=timezone.utc))
    assert result.status == "CONNECTED"
    assert "listas para entrada 1" in result.detail


def test_ui_control_contract_accepts_callbacks_conditionals_and_disabled(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text(
        """
import streamlit as st
def reset(): pass
if st.button('Guardar'): pass
st.button('Limpiar', on_click=reset)
st.button('Automatico', disabled=True)
st.link_button('Proveedor', 'https://example.com')
""",
        encoding="utf-8",
    )
    result = ui_control_contract_check(source)
    assert result.status == "CONNECTED"
    assert "acciones huerfanas 0" in result.detail


def test_ui_control_contract_flags_orphan_and_placeholder_link(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text(
        """
import streamlit as st
st.button('No hace nada')
html = '<a href="#">Roto</a>'
""",
        encoding="utf-8",
    )
    result = ui_control_contract_check(source)
    assert result.status == "WARNING"
    assert "acciones huerfanas 1" in result.detail
    assert "href placeholder 1" in result.detail


def test_visual_strategy_engine_contract_covers_required_real_detectors():
    result = visual_strategy_engine_check(Path("roxy_trader/operational_strategies.py"))

    assert result.status == "CONNECTED"
    assert "roxy-visual-strategies/1.1.0" in result.detail
    assert "familias 20/20" in result.detail
    assert "indicadores centrales si" in result.detail
    assert "faltantes ninguna" in result.detail


def test_visual_strategy_engine_contract_warns_on_incomplete_stub(tmp_path: Path):
    source = tmp_path / "operational_strategies.py"
    source.write_text('VISUAL_STRATEGY_ENGINE_VERSION = "stub/0"\nBREAKOUT = "BREAKOUT"\n', encoding="utf-8")

    result = visual_strategy_engine_check(source)

    assert result.status == "WARNING"
    assert "familias 1/20" in result.detail
    assert "indicadores centrales no" in result.detail


def test_visual_strategy_engine_contract_is_visible_in_runtime_diagnostics():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    diagnostic_page = source[
        source.index('elif selected_page == "Diagnostico"') : source.index("def show_focused_roxy_app")
    ]

    assert "visual_strategy_engine_check" in diagnostic_page
    assert 'project_root / "roxy_trader" / "operational_strategies.py"' in diagnostic_page


def test_backtest_engine_contract_covers_reproducible_realistic_execution():
    result = backtest_engine_contract_check(
        Path("ma_backtester.py"),
        Path("roxy_trader/backtests.py"),
    )

    assert result.status == "CONNECTED"
    assert "roxy-ma-backtest/2.2.0" in result.detail
    assert "roxy-backtest-validation/1.0.0" in result.detail
    assert "contratos 7/7" in result.detail
    assert "faltantes ninguno" in result.detail


def test_backtest_engine_contract_warns_on_incomplete_stub(tmp_path: Path):
    engine = tmp_path / "engine.py"
    wrapper = tmp_path / "wrapper.py"
    engine.write_text('BACKTEST_ENGINE_VERSION = "stub/0"\n', encoding="utf-8")
    wrapper.write_text('BACKTEST_VALIDATION_VERSION = "stub/0"\n', encoding="utf-8")

    result = backtest_engine_contract_check(engine, wrapper)

    assert result.status == "WARNING"
    assert "contratos 0/7" in result.detail


def test_backtest_engine_contract_is_visible_in_runtime_diagnostics():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    diagnostic_page = source[
        source.index('elif selected_page == "Diagnostico"') : source.index("def show_focused_roxy_app")
    ]

    assert "backtest_engine_contract_check" in diagnostic_page
    assert 'project_root / "roxy_trader" / "backtests.py"' in diagnostic_page


def test_navigation_route_contract_accepts_registered_literal_destinations(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text(
        """
news = '<a href="?view=Noticias">Noticias</a>'
market = '<a href="?view=Dashboard&module=acciones-operar&tab=mapa">Mapa</a>'
charts = '<a href="?view=Dashboard&amp;module=acciones-operar&amp;tab=analisis">Graficas</a>'
""",
        encoding="utf-8",
    )
    result = navigation_route_contract_check(source)
    assert result.status == "CONNECTED"
    assert "pestañas invalidas 0" in result.detail


def test_navigation_route_contract_flags_silent_fallback_destinations(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text(
        """
bad_view = '<a href="?view=Settings">Ajustes</a>'
bad_module = '<a href="?view=Dashboard&module=unknown">Modulo</a>'
bad_tab = '<a href="?view=Dashboard&module=acciones-operar&tab=noticias">Noticias</a>'
""",
        encoding="utf-8",
    )
    result = navigation_route_contract_check(source)
    assert result.status == "WARNING"
    assert "view=Settings" in result.detail
    assert "module=unknown" in result.detail
    assert "tab=noticias" in result.detail


def test_device_sync_diagnostic_is_explicit_about_remote_authentication():
    local_only = device_sync_configuration_check({})
    configured = device_sync_configuration_check(
        {
            "VOICE_API_KEY": "configured",
            "ROXY_STATE_SYNC_USERS": "local_user,trader",
            "ROXY_VOICE_BIND_HOST": "0.0.0.0",
            "ROXY_VOICE_PUBLIC_BASE_URL": "https://roxy.example",
        }
    )

    assert local_only.status == "NOT_CONFIGURED"
    assert "iPad/telefono remotos requieren" in local_only.detail
    assert "tareas y compras" in local_only.detail
    assert configured.status == "CONNECTED"
    assert "usuarios permitidos 2" in configured.detail


def test_remote_voice_and_device_sync_recognize_isolated_gateway_without_claiming_physical_test(tmp_path: Path):
    report = tmp_path / "mobile_gateway_check.json"
    report.write_text(
        json.dumps(
            {
                "contract_version": "roxy-mobile-gateway/1.0.0",
                "contract_status": "OK",
                "gateway_status": "READY_FOR_PHYSICAL_TEST",
                "physical_reachability": "UNVERIFIED",
                "secrets_exposed": False,
            }
        ),
        encoding="utf-8",
    )
    env = {"ROXY_STATE_SYNC_USERS": "local_user"}

    voice = voice_remote_access_check(env, mobile_gateway_path=report)
    sync = device_sync_configuration_check(env, mobile_gateway_path=report)

    assert voice.status == "WARNING"
    assert sync.status == "WARNING"
    assert "intencionalmente privado" in voice.detail
    assert "Bearer del gateway" in sync.detail
    assert "UNVERIFIED" in voice.detail


def test_remote_voice_and_device_sync_connect_after_physical_gateway_proof(tmp_path: Path):
    report = tmp_path / "mobile_gateway_check.json"
    report.write_text(
        json.dumps(
            {
                "contract_version": "roxy-mobile-gateway/1.0.0",
                "contract_status": "OK",
                "gateway_status": "CONNECTED_PHYSICAL",
                "physical_reachability": "VERIFIED_REMOTE_CLIENT",
                "secrets_exposed": False,
            }
        ),
        encoding="utf-8",
    )
    env = {"ROXY_STATE_SYNC_USERS": "local_user"}

    assert voice_remote_access_check(env, mobile_gateway_path=report).status == "CONNECTED"
    assert device_sync_configuration_check(env, mobile_gateway_path=report).status == "CONNECTED"


def test_mobile_gateway_diagnostic_preserves_physical_test_boundary(tmp_path: Path):
    report = tmp_path / "mobile_gateway_check.json"
    report.write_text(
        json.dumps(
            {
                "contract_version": "roxy-mobile-gateway/1.0.0",
                "contract_status": "OK",
                "gateway_status": "READY_FOR_PHYSICAL_TEST",
                "physical_reachability": "UNVERIFIED",
                "secrets_exposed": False,
            }
        ),
        encoding="utf-8",
    )

    result = mobile_gateway_configuration_check(report)

    assert result.status == "WARNING"
    assert "verificados localmente" in result.detail
    assert "UNVERIFIED" in result.detail
    assert "iPad/telefono" in result.detail


def test_mobile_gateway_diagnostic_fails_closed_without_valid_evidence(tmp_path: Path):
    missing = mobile_gateway_configuration_check(tmp_path / "missing.json")
    report = tmp_path / "bad.json"
    report.write_text('{"contract_status":"OK"}', encoding="utf-8")
    invalid = mobile_gateway_configuration_check(report)

    assert missing.status == "NOT_CONFIGURED"
    assert invalid.status == "ERROR"


def test_mobile_gateway_diagnostic_connects_after_verified_remote_client(tmp_path: Path):
    report = tmp_path / "mobile_gateway_check.json"
    report.write_text(
        json.dumps(
            {
                "contract_version": "roxy-mobile-gateway/1.0.0",
                "contract_status": "OK",
                "gateway_status": "CONNECTED_PHYSICAL",
                "physical_reachability": "VERIFIED_REMOTE_CLIENT",
                "secrets_exposed": False,
            }
        ),
        encoding="utf-8",
    )

    result = mobile_gateway_configuration_check(report)

    assert result.status == "CONNECTED"
    assert "VERIFIED_REMOTE_CLIENT" in result.detail


def test_frontend_function_contract_accepts_internal_and_declared_external_consumers(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text(
        """
def active(): return 1
active()
def _container_width_to_width(): return 2
""",
        encoding="utf-8",
    )

    result = frontend_function_contract_check(source)

    assert result.status == "CONNECTED"
    assert "APIs externas declaradas 1" in result.detail
    assert "sin contrato 0" in result.detail


def test_frontend_function_contract_flags_unconsumed_definition(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def dead_renderer():\n    return 'unused'\n", encoding="utf-8")

    result = frontend_function_contract_check(source)

    assert result.status == "WARNING"
    assert "dead_renderer" in result.detail


def test_responsive_matrix_diagnostic_requires_fresh_complete_canonical_report(tmp_path: Path):
    report = tmp_path / "responsive.json"
    route_names = [f"route_{index}" for index in range(14)]
    rows = [
        {"status": "OK", "route": route, "device": device}
        for route in route_names
        for device in ("desktop", "ipad", "mobile")
    ]
    report.write_text(
        __import__("json").dumps(
            {
                "contract_version": "roxy-responsive-matrix/1.2.0",
                "generated_at": "2026-07-19T12:00:00+00:00",
                "status": "OK",
                "checked": 42,
                "passed": 42,
                "failed": 0,
                "devices": {
                    "desktop": {"checked": 14, "passed": 14},
                    "ipad": {"checked": 14, "passed": 14},
                    "mobile": {"checked": 14, "passed": 14},
                },
                "routes": {name: {"checked": 3, "passed": 3} for name in route_names},
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )

    fresh = responsive_matrix_check(report, now=datetime(2026, 7, 19, 13, tzinfo=timezone.utc))
    stale = responsive_matrix_check(report, now=datetime(2026, 7, 21, 13, tzinfo=timezone.utc))

    assert fresh.status == "CONNECTED"
    assert "42/42" in fresh.detail
    assert stale.status == "WARNING"
    assert "vencido" in stale.detail


def test_responsive_matrix_diagnostic_rejects_inconsistent_report(tmp_path: Path):
    report = tmp_path / "responsive.json"
    report.write_text(
        '{"contract_version":"roxy-responsive-matrix/1.2.0","generated_at":"2026-07-19T12:00:00Z",'
        '"status":"OK","checked":24,"passed":24,"failed":0,"devices":{},"rows":[]}',
        encoding="utf-8",
    )

    result = responsive_matrix_check(report)

    assert result.status == "ERROR"
    assert "conteos inconsistentes" in result.detail


def test_macro_calendar_diagnostic_does_not_call_empty_file_connected(tmp_path: Path):
    calendar = tmp_path / "macro_events.csv"
    calendar.write_text("date,time,event,severity,currency,notes\n", encoding="utf-8")

    result = macro_calendar_data_check(calendar)

    assert result.status == "NO_DATA"
    assert "eventos validos 0" in result.detail
    assert "no se presenta como conectado" in result.detail


def test_macro_calendar_sync_diagnostic_validates_fresh_official_report(tmp_path: Path):
    report = tmp_path / "macro_sync.json"
    report.write_text(
        '{"contract_version":"roxy-macro-calendar-sync/1.0.0",'
        '"generated_at":"2026-07-19T12:00:00+00:00","status":"OK",'
        '"event_count":24,"future_event_count":24,"cache_kept":false}',
        encoding="utf-8",
    )

    result = macro_calendar_sync_check(
        report,
        now=datetime(2026, 7, 19, 13, tzinfo=timezone.utc),
    )

    assert result.status == "CONNECTED"
    assert "eventos 24" in result.detail
    assert "antiguedad 1.0h" in result.detail


def test_macro_calendar_sync_diagnostic_marks_stale_report_warning(tmp_path: Path):
    report = tmp_path / "macro_sync.json"
    report.write_text(
        '{"contract_version":"roxy-macro-calendar-sync/1.0.0",'
        '"generated_at":"2026-07-10T12:00:00+00:00","status":"OK",'
        '"event_count":24,"future_event_count":24,"cache_kept":false}',
        encoding="utf-8",
    )

    result = macro_calendar_sync_check(
        report,
        now=datetime(2026, 7, 19, 13, tzinfo=timezone.utc),
    )

    assert result.status == "WARNING"
    assert "vencido" in result.detail


def test_macro_calendar_service_diagnostic_requires_loaded_valid_job(monkeypatch):
    monkeypatch.setattr(
        "tools.macro_calendar_launchd.status",
        lambda: {
            "installed": True,
            "loaded": True,
            "interval_seconds": 21_600,
            "command": "/python tools/macro_calendar_sync.py --no-fail",
            "path": "/tmp/com.roxy.macro-calendar.plist",
        },
    )

    result = macro_calendar_service_check()

    assert result.status == "CONNECTED"
    assert "intervalo 21600s" in result.detail


def test_realtime_report_checks_exposes_runtime_auth_and_market_gates(tmp_path: Path):
    report = tmp_path / "roxy_realtime_check.json"
    report.write_text(
        '{"generated_at":"2026-07-19T03:00:00+00:00","status":"WARN",'
        '"checks":[{"name":"streamlit_app","status":"OK","detail":"HTTP 200"},'
        '{"name":"live_backend_process_guard","status":"OK","detail":"ma_live=1"},'
        '{"name":"live_scan_efficiency","status":"OK","detail":"saved 50 provider request(s)/cycle"},'
        '{"name":"opportunity_lifecycle","status":"OK","detail":"archived 1, active overlap 0"},'
        '{"name":"report_metrics_contract","status":"OK","detail":"metrics aliases OK"}],'
        '"provider_recovery":{"alpaca_account_auth_ok":false,"alpaca_account_probe_status":"WARN",'
        '"alpaca_account_error_category":"AUTH_INVALID","alpaca_account_mode":"paper",'
        '"detail":"Alpaca account auth failed en modo paper (AUTH_INVALID)."},'
        '"market_realtime":{"rows":['
        '{"market":"stock","status":"WARN","label":"Acciones bloqueadas","detail":"Sin premium.","alerts_allowed":false},'
        '{"market":"crypto","status":"OK","label":"Cripto realtime","detail":"3 fuentes validas.","alerts_allowed":true}'
        ']}}'
    )

    rows = realtime_report_checks(
        report,
        now=datetime(2026, 7, 19, 3, 5, tzinfo=timezone.utc),
    )

    assert rows[0].component == "Salud realtime"
    assert rows[0].status == "WARNING"
    assert "reporte vigente" in rows[0].detail
    alpaca = next(row for row in rows if row.component == "Alpaca runtime")
    assert alpaca.status == "ERROR"
    assert "AUTH_INVALID" in alpaca.detail
    stock = next(row for row in rows if row.component == "Mercado STOCK")
    crypto = next(row for row in rows if row.component == "Mercado CRYPTO")
    assert stock.status == "WARNING"
    assert "Alertas=OFF" in stock.detail
    assert crypto.status == "CONNECTED"
    assert "Alertas=ON" in crypto.detail
    assert next(row for row in rows if row.component == "Frontend watchdog").status == "CONNECTED"
    assert next(row for row in rows if row.component == "Backend de mercado").status == "CONNECTED"
    assert next(row for row in rows if row.component == "Eficiencia del scanner").status == "CONNECTED"
    assert next(row for row in rows if row.component == "Ciclo de oportunidades").status == "CONNECTED"
    assert next(row for row in rows if row.component == "Contrato de telemetria").status == "CONNECTED"


def test_realtime_report_checks_marks_stale_ok_market_as_warning(tmp_path: Path):
    report = tmp_path / "roxy_realtime_check.json"
    report.write_text(
        '{"generated_at":"2026-07-19T02:00:00+00:00","status":"OK",'
        '"market_realtime":{"rows":[{"market":"crypto","status":"OK",'
        '"label":"Cripto realtime","detail":"validado","alerts_allowed":true}]}}'
    )

    rows = realtime_report_checks(
        report,
        now=datetime(2026, 7, 19, 3, 0, tzinfo=timezone.utc),
    )

    assert rows[0].status == "WARNING"
    assert "reporte vencido" in rows[0].detail
    assert next(row for row in rows if row.component == "Mercado CRYPTO").status == "WARNING"


def test_collect_system_diagnostics_can_avoid_recursive_frontend_http_probe(tmp_path: Path):
    (tmp_path / "db").mkdir()
    (tmp_path / "alerts").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "data").mkdir()

    rows = collect_system_diagnostics(
        root=tmp_path,
        env={},
        voice_urls=("http://127.0.0.1:9/health",),
        live_http_checks=False,
    )

    frontend = next(row for row in rows if row["component"] == "Frontend")
    voice = next(row for row in rows if row["component"] == "Backend de voz")
    assert frontend["status"] == "CONNECTED"
    assert "probe HTTP recursivo omitido" in frontend["detail"]
    assert voice["status"] == "DISCONNECTED"
