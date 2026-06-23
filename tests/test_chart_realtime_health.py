import json

from tools import chart_realtime_health


def test_selected_chart_symbols_includes_active_alert_symbols_by_default(tmp_path, monkeypatch):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    captured = {}

    def fake_active_symbols(path, *, limit):
        captured["path"] = path
        captured["limit"] = limit
        return ["ETH/USD", "AAPL", "SOL/USD"]

    monkeypatch.setattr(chart_realtime_health, "active_chart_symbols_from_alerts", fake_active_symbols)

    symbols = chart_realtime_health.selected_chart_symbols(alerts_path=alerts, active_symbol_limit=3)

    assert symbols == ["AAPL", "NVDA", "AMD", "MSFT", "QQQ", "BTC/USD", "ETH/USD", "SOL/USD"]
    assert captured == {"path": alerts, "limit": 3}


def test_selected_chart_symbols_can_disable_active_alert_symbols(tmp_path, monkeypatch):
    def fail_active_symbols(path, *, limit):
        raise AssertionError("active alert symbols should not be read")

    monkeypatch.setattr(chart_realtime_health, "active_chart_symbols_from_alerts", fail_active_symbols)

    symbols = chart_realtime_health.selected_chart_symbols(
        symbols_arg="ETH/USD,SOL/USD",
        include_active_alert_symbols=False,
        alerts_path=tmp_path,
    )

    assert symbols == ["ETH/USD", "SOL/USD"]


def test_parse_args_includes_active_alert_symbols_by_default(monkeypatch):
    monkeypatch.setattr("sys.argv", ["chart_realtime_health.py"])

    args = chart_realtime_health.parse_args()

    assert args.include_active_alert_symbols is True


def test_parse_args_allows_only_configured_symbols(monkeypatch):
    monkeypatch.setattr("sys.argv", ["chart_realtime_health.py", "--no-active-alert-symbols"])

    args = chart_realtime_health.parse_args()

    assert args.include_active_alert_symbols is False


def test_main_uses_report_parent_for_active_symbols(tmp_path, monkeypatch):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    report_path = alerts / "chart_realtime_health.json"
    captured = {}

    def fake_active_symbols(path, *, limit):
        captured["path"] = path
        return ["ETH/USD"]

    def fake_collect_chart_health(*, symbols, timeframes, now=None):
        captured["symbols"] = list(symbols)
        return [
            {
                "symbol": symbol,
                "market": chart_realtime_health.market_for_symbol(symbol),
                "timeframe": timeframes[0],
                "status": "OK",
                "label": "Live",
                "tone": "buy",
                "detail": "fresh",
                "rows": 200,
                "has_rsi": True,
                "has_macd": True,
                "indicator_status": "OK",
            }
            for symbol in symbols
        ]

    monkeypatch.setattr("sys.argv", ["chart_realtime_health.py", "--report-path", str(report_path), "--no-fail"])
    monkeypatch.setattr(chart_realtime_health, "active_chart_symbols_from_alerts", fake_active_symbols)
    monkeypatch.setattr(chart_realtime_health, "collect_chart_health", fake_collect_chart_health)

    chart_realtime_health.main()

    assert captured["path"] == alerts
    assert "ETH/USD" in captured["symbols"]
    payload = json.loads(report_path.read_text())
    assert payload["summary"]["status"] == "OK"
