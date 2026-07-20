import json

import streamlit_app
from datetime import datetime, timezone
from types import SimpleNamespace

from roxy_trader.watchlists import (
    WatchlistStore,
    evaluate_price_alert,
    evaluate_durable_alert,
    normalize_watchlist_symbol,
    operational_opportunity_record,
)
from streamlit_app import alert_command_request, watchlist_command_action


def test_watchlist_snapshot_and_persistence_are_strict_json_when_metric_is_non_finite(tmp_path):
    path = tmp_path / "watchlists.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "users": {
                    "local_user": {
                        "active_list": "Principal",
                        "lists": {"Principal": {"items": []}},
                        "alerts": [],
                        "opportunity_archive": [{"symbol": "AAPL", "recommended_target_pct": float("nan")}],
                        "revision": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    store = WatchlistStore(path)

    snapshot = store.snapshot("local_user")
    store.create_list("local_user", "Otra")

    assert snapshot["opportunity_archive"][0]["recommended_target_pct"] is None
    assert "NaN" not in json.dumps(snapshot, allow_nan=False)
    assert "NaN" not in path.read_text(encoding="utf-8")


def test_watchlist_store_supports_multiple_lists_and_deduplicates(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")

    assert store.create_list("Roberto", "Swing Trades")["created"] is True
    assert store.add_asset("Roberto", "Swing Trades", "aapl", "stock")["added"] is True
    assert store.add_asset("Roberto", "Swing Trades", "AAPL", "stock")["added"] is False
    assert store.add_asset("Roberto", "Principal", "btc-usd", "crypto")["added"] is True

    snapshot = store.snapshot("Roberto")
    assert set(snapshot["lists"]) == {"Principal", "Swing Trades"}
    assert snapshot["lists"]["Swing Trades"]["items"][0]["symbol"] == "AAPL"
    assert snapshot["lists"]["Principal"]["items"][0]["symbol"] == "BTC/USD"


def test_watchlist_store_removes_only_requested_market_asset(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.add_asset("user", "Principal", "AAPL", "stock")
    store.add_asset("user", "Principal", "ETH/USD", "crypto")

    result = store.remove_asset("user", "Principal", "AAPL", "stock")

    assert result["removed"] is True
    items = store.snapshot("user")["lists"]["Principal"]["items"]
    assert [item["symbol"] for item in items] == ["ETH/USD"]


def test_watchlist_revision_rejects_stale_device_snapshot(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.add_asset("user", "Principal", "AAPL", "stock")
    stale = store.snapshot("user")
    store.add_asset("user", "Principal", "MSFT", "stock")

    conflict = store.replace_user_snapshot("user", stale, expected_revision=stale["revision"])

    assert conflict["conflict"] is True
    assert conflict["current_revision"] == 2
    assert [item["symbol"] for item in store.snapshot("user")["lists"]["Principal"]["items"]] == [
        "AAPL",
        "MSFT",
    ]


def test_autonomous_system_list_does_not_churn_user_edit_revision_or_accept_remote_override(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.add_asset("user", "Principal", "AAPL", "stock")
    user_revision = store.snapshot("user")["revision"]
    live = {
        "symbol": "BTC/USD",
        "market": "crypto",
        "action": "ALERT",
        "focus_priority": 2,
        "data_bucket": "Live real",
        "data_state": "Broker/exchange live",
        "data_gate": "LIVE_DATA_OK",
    }
    store.sync_operational_opportunities("user", [live], source_healthy=True)
    synced = store.snapshot("user")
    assert synced["revision"] == user_revision

    incoming = {**synced, "lists": {**synced["lists"], "Roxy Oportunidades": {"items": []}}}
    result = store.replace_user_snapshot("user", incoming, expected_revision=user_revision)

    assert result["updated"] is True
    assert store.snapshot("user")["lists"]["Roxy Oportunidades"]["items"][0]["symbol"] == "BTC/USD"


def test_watchlist_symbol_normalization_rejects_markup():
    assert normalize_watchlist_symbol(" <script>AAPL</script> ") == ""


def test_voice_watchlist_command_uses_current_asset_without_reasking_symbol():
    assert watchlist_command_action("Roxy, agregala a mi watchlist") == "add"
    assert watchlist_command_action("Roxy, quitala de mi lista de seguimiento") == "remove"
    assert watchlist_command_action("Roxy, explicame esta oportunidad") == ""


def test_voice_watchlist_command_falls_back_from_managed_list_to_personal_list(tmp_path, monkeypatch):
    state_path = tmp_path / "watchlists.json"
    store = WatchlistStore(state_path)
    store.sync_operational_opportunities(
        "voice-user",
        [
            {
                "symbol": "BTC/USD",
                "market": "crypto",
                "action": "ALERT",
                "data_bucket": "Live real",
                "data_state": "Broker/exchange live",
                "data_gate": "LIVE_DATA_OK",
            }
        ],
        source_healthy=True,
    )
    snapshot = store.snapshot("voice-user")
    incoming = {**snapshot, "active_list": "Roxy Oportunidades"}
    assert store.replace_user_snapshot(
        "voice-user", incoming, expected_revision=snapshot["revision"]
    )["updated"] is True
    fake_st = SimpleNamespace(
        query_params={"symbol": "ETH/USD", "market": "crypto", "tf": "1h"},
        session_state={},
    )
    monkeypatch.setattr(streamlit_app, "st", fake_st)
    monkeypatch.setattr(streamlit_app, "project_path", lambda *_parts: state_path)
    monkeypatch.setattr(streamlit_app, "roxy_os_user_id", lambda: "voice-user")

    result = streamlit_app.execute_roxy_watchlist_command("Roxy, agregala a mi watchlist")

    assert result["ok"] is True
    assert result["data"]["list_name"] == "Principal"
    assert "Principal" in result["message"]
    assert "administrada automaticamente" in result["message"]
    principal = WatchlistStore(state_path).snapshot("voice-user")["lists"]["Principal"]
    assert [item["symbol"] for item in principal["items"]] == ["ETH/USD"]


def test_price_alert_transitions_once_when_real_price_crosses_threshold(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    created = store.create_price_alert(
        "user",
        symbol="AAPL",
        market="stock",
        alert_type="price_above",
        threshold=200,
        timeframe="15m",
    )
    assert created["created"] is True

    waiting = store.evaluate_price_alerts("user", {"AAPL": 199.5})[0]
    assert waiting["status"] == "Activa"
    assert waiting["monitor_status"] == "EVALUADA"
    triggered = store.evaluate_price_alerts("user", {"AAPL": 200.01})[0]
    assert triggered["status"] == "Activada"
    assert triggered["monitor_status"] == "ACTIVADA"
    assert triggered["triggered_at"]
    assert store.evaluate_price_alerts("user", {"AAPL": 198}) == []
    assert store.alerts_snapshot("user")[0]["status"] == "Activada"


def test_price_alert_rejects_invalid_or_duplicate_rules_and_can_archive(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    assert store.create_price_alert(
        "user", symbol="AAPL", market="stock", alert_type="price_above", threshold=0
    )["created"] is False
    first = store.create_price_alert(
        "user", symbol="AAPL", market="stock", alert_type="price_below", threshold=180
    )
    duplicate = store.create_price_alert(
        "user", symbol="AAPL", market="stock", alert_type="price_below", threshold=180
    )
    assert duplicate["reason"] == "duplicate"
    assert store.archive_alert("user", first["alert"]["id"])["archived"] is True
    assert store.alerts_snapshot("user") == []


def test_alert_lifecycle_expires_only_due_active_rules_and_preserves_history(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    due = store.create_price_alert(
        "user", symbol="AAPL", market="stock", alert_type="price_above", threshold=200
    )["alert"]
    future = store.create_technical_alert(
        "user", symbol="BTC/USD", market="crypto", alert_type="relative_volume_above", threshold=2
    )["alert"]
    payload = store._read_unlocked()
    rows = payload["users"]["user"]["alerts"]
    rows[0]["expires_at"] = "2026-07-18T12:00:00+00:00"
    rows[1]["expires_at"] = "2026-07-20T12:00:00+00:00"
    store._write_unlocked(payload)

    expired = store.expire_due_alerts(now=datetime(2026, 7, 19, 12, tzinfo=timezone.utc))

    assert expired == 1
    snapshot = {row["id"]: row for row in store.alerts_snapshot("user")}
    assert snapshot[due["id"]]["status"] == "Expirada"
    assert snapshot[due["id"]]["monitor_status"] == "EXPIRADA"
    assert snapshot[future["id"]]["status"] == "Activa"
    assert [row["id"] for row in store.active_alert_inventory()] == [future["id"]]


def test_legacy_trigger_without_delivery_contract_is_not_replayed(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    created = store.create_price_alert(
        "user", symbol="AAPL", market="stock", alert_type="price_above", threshold=200
    )["alert"]
    payload = store._read_unlocked()
    alert = payload["users"]["user"]["alerts"][0]
    alert["status"] = "Activada"
    alert["triggered_at"] = "2026-07-18T12:00:00+00:00"
    alert.pop("notification_status", None)
    store._write_unlocked(payload)

    assert store.pending_notification_inventory() == []
    assert store.alert_notification_status_counts() == {"LEGACY_UNKNOWN": 1}
    assert store.alerts_snapshot("user")[0]["id"] == created["id"]


def test_alert_creation_rejects_invalid_lifetime(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    assert store.create_price_alert(
        "user", symbol="AAPL", market="stock", alert_type="price_above", threshold=200, ttl_hours=0
    )["created"] is False
    assert store.create_technical_alert(
        "user", symbol="BTC/USD", market="crypto", alert_type="ema_cross_above", ttl_hours=9000
    )["created"] is False


def test_price_alert_evaluator_does_not_trigger_without_valid_price():
    alert = {"type": "price_above", "threshold": 100, "status": "Activa"}
    assert evaluate_price_alert(alert, None) == alert


def test_technical_alerts_require_a_real_cross_event_and_trigger_once(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    created = store.create_technical_alert(
        "user", symbol="BTC/USD", market="crypto", alert_type="ema_cross_above",
        timeframe="15m", fast_period=9, slow_period=21,
    )
    assert created["created"] is True
    duplicate = store.create_technical_alert(
        "user", symbol="BTC/USD", market="crypto", alert_type="ema_cross_above",
        timeframe="15m", fast_period=9, slow_period=21,
    )
    assert duplicate["reason"] == "duplicate"

    waiting = store.evaluate_alerts(
        "user",
        {"BTC/USD|15M": {"previous_fast": 101, "previous_slow": 100, "current_fast": 102,
                          "current_slow": 101, "indicator_engine": "roxy-indicators/1.1.0"}},
    )[0]
    assert waiting["status"] == "Activa"
    triggered = store.evaluate_alerts(
        "user",
        {"BTC/USD|15M": {"previous_fast": 99, "previous_slow": 100, "current_fast": 101,
                          "current_slow": 100, "indicator_engine": "roxy-indicators/1.1.0",
                          "source": "BinanceUS klines", "freshness": "FRESH"}},
    )[0]
    assert triggered["status"] == "Activada"
    assert triggered["indicator_engine"] == "roxy-indicators/1.1.0"
    assert triggered["last_source"] == "BinanceUS klines"
    assert store.evaluate_alerts("user", {"BTC/USD|15M": {"previous_fast": 1}}) == []


def test_relative_volume_alert_uses_configurable_real_indicator_threshold(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    assert store.create_technical_alert(
        "user", symbol="AAPL", market="stock", alert_type="relative_volume_above",
        timeframe="15m", threshold=1.8,
    )["created"] is True

    waiting = store.evaluate_alerts("user", {"AAPL|15M": {"relative_volume": 1.79}})[0]
    assert waiting["status"] == "Activa"
    triggered = store.evaluate_alerts(
        "user", {"AAPL|15M": {"relative_volume": 1.81, "indicator_engine": "roxy-indicators/1.1.0"}}
    )[0]
    assert triggered["status"] == "Activada"
    assert triggered["last_relative_volume"] == 1.81


def test_technical_alert_validation_rejects_bad_periods_thresholds_and_missing_observations(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    assert store.create_technical_alert(
        "user", symbol="AAPL", market="stock", alert_type="ema_cross_above", fast_period=21, slow_period=9
    )["created"] is False
    assert store.create_technical_alert(
        "user", symbol="AAPL", market="stock", alert_type="relative_volume_above", threshold=0
    )["created"] is False
    alert = {"type": "ema_cross_below", "status": "Activa", "threshold": 0}
    assert evaluate_durable_alert(alert, {"current_fast": 1}) == alert


def test_technical_alert_labels_are_explicit_and_chart_workspace_exposes_creation_controls():
    assert streamlit_app.roxy_durable_alert_rule_label(
        {"type": "ema_cross_above", "fast_period": 9, "slow_period": 21, "timeframe": "15m"}
    ) == "EMA9 cruza sobre EMA21 · 15m"
    assert streamlit_app.roxy_durable_alert_rule_label(
        {"type": "relative_volume_above", "threshold": 1.8, "timeframe": "1h"}
    ) == "RVol alcanza 1.80x · 1h"
    source = open("streamlit_app.py", encoding="utf-8").read()
    chart_section = source[
        source.index("def render_roxy_chart_alert_controls") : source.index("def sync_roxy_operational_watchlist")
    ]
    assert "Se crean desde esta gráfica" in chart_section
    assert '"EMA rápida"' in chart_section
    assert '"EMA lenta"' in chart_section
    assert "fast_period=int(fast_period)" in chart_section
    assert "slow_period=int(slow_period)" in chart_section
    assert "Cruce EMA{int(fast_period)} ↑ EMA{int(slow_period)}" in chart_section
    assert "Cruce EMA{int(fast_period)} ↓ EMA{int(slow_period)}" in chart_section
    assert "RVol supera umbral" in chart_section
    assert 'source="chart_workspace"' in chart_section


def test_custom_ema_alert_periods_are_persisted_and_labeled_consistently(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    result = store.create_technical_alert(
        "user",
        symbol="BTC/USD",
        market="crypto",
        alert_type="ema_cross_below",
        timeframe="2h",
        fast_period=12,
        slow_period=34,
    )

    assert result["created"] is True
    alert = store.alerts_snapshot("user")[0]
    assert alert["fast_period"] == 12
    assert alert["slow_period"] == 34
    assert streamlit_app.roxy_durable_alert_rule_label(alert) == "EMA12 cruza debajo de EMA34 · 2h"


def test_voice_alert_command_extracts_direction_and_exact_level_for_visible_asset():
    assert alert_command_request("Roxy, avisame si esta accion sube a 350.50") == {
        "alert_type": "price_above",
        "threshold": 350.5,
    }
    assert alert_command_request("Crea una alerta si baja debajo de 199,25") == {
        "alert_type": "price_below",
        "threshold": 199.25,
    }
    assert alert_command_request("explicame la grafica") is None


def test_voice_alert_command_extracts_technical_rule_from_visible_context():
    assert alert_command_request("Roxy, avisame cuando EMA9 cruce sobre EMA21") == {
        "alert_type": "ema_cross_above",
        "fast_period": 9,
        "slow_period": 21,
    }
    assert alert_command_request("Crea una alerta cuando EMA9 cruce debajo de EMA21") == {
        "alert_type": "ema_cross_below",
        "fast_period": 9,
        "slow_period": 21,
    }
    assert alert_command_request("Notifica si el volumen relativo supera 1,75") == {
        "alert_type": "relative_volume_above",
        "threshold": 1.75,
    }


def test_voice_technical_alert_uses_visible_symbol_timeframe_and_durable_store(tmp_path, monkeypatch):
    state_path = tmp_path / "watchlists.json"
    fake_st = SimpleNamespace(
        query_params={"symbol": "ETH/USD", "market": "crypto", "tf": "1h"},
        session_state={},
    )
    monkeypatch.setattr(streamlit_app, "st", fake_st)
    monkeypatch.setattr(streamlit_app, "project_path", lambda *_parts: state_path)
    monkeypatch.setattr(streamlit_app, "roxy_os_user_id", lambda: "voice-user")

    result = streamlit_app.execute_roxy_alert_command(
        "Roxy, avisame cuando EMA9 cruce sobre EMA21"
    )

    assert result["ok"] is True
    assert "ETH/USD" in result["message"]
    assert "1h" in result["message"]
    alerts = WatchlistStore(state_path).snapshot("voice-user")["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["type"] == "ema_cross_above"
    assert alerts[0]["timeframe"] == "1h"
    assert alerts[0]["source"] == "voice_command"


def test_price_only_refresh_does_not_mark_technical_rule_as_evaluated(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.create_technical_alert(
        "user", symbol="BTC/USD", market="crypto", alert_type="ema_cross_above"
    )

    assert store.evaluate_price_alerts("user", {"BTC/USD": 123.0}) == []
    alert = store.snapshot("user")["alerts"][0]
    assert alert["last_evaluated_at"] == ""
    assert alert.get("monitor_status", "") == ""


def test_malformed_legacy_rule_does_not_block_new_technical_alert(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.create_technical_alert(
        "user", symbol="BTC/USD", market="crypto", alert_type="ema_cross_above"
    )
    payload = store._read_unlocked()
    payload["users"]["user"]["alerts"][0]["fast_period"] = "broken"
    store._write_unlocked(payload)

    created = store.create_technical_alert(
        "user", symbol="ETH/USD", market="crypto", alert_type="ema_cross_above"
    )
    assert created["created"] is True


def test_operational_opportunity_rejects_public_fallback_and_missing_contract():
    base = {
        "symbol": "AAPL",
        "action": "ALERT",
        "focus_priority": 2,
        "data_source": "yfinance direct seed",
    }
    assert operational_opportunity_record({**base, "data_bucket": "Fallback", "data_gate": "NO_TRADE_FROM_FALLBACK"}) is None
    assert operational_opportunity_record(base) is None


def test_store_syncs_only_source_backed_trade_ready_opportunities(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    rows = [
        {
            "symbol": "AAPL",
            "market": "stock",
            "action": "ALERT",
            "focus_priority": 2,
            "data_bucket": "Live real",
            "data_state": "Broker/exchange live",
            "data_gate": "LIVE_DATA_OK",
            "data_source": "Alpaca IEX",
            "strategy_family": "Ruptura",
            "entry": 200,
            "stop": 195,
            "target_price": 210,
        },
        {
            "symbol": "MSFT",
            "action": "WATCH",
            "focus_priority": 1,
            "data_bucket": "Live real",
            "data_state": "Broker/exchange live",
            "data_gate": "LIVE_DATA_OK",
        },
        {
            "symbol": "TSLA",
            "action": "ALERT",
            "focus_priority": 2,
            "data_bucket": "Fallback",
            "data_state": "Fallback publico",
            "data_gate": "NO_TRADE_FROM_PUBLIC_PRICE",
        },
    ]
    result = store.sync_operational_opportunities("user", rows, source_healthy=True)
    assert result == {"synced": True, "count": 1, "archived": 0, "list_name": "Roxy Oportunidades"}
    system_list = store.snapshot("user")["lists"]["Roxy Oportunidades"]
    assert system_list["system_managed"] is True
    assert [item["symbol"] for item in system_list["items"]] == ["AAPL"]
    assert system_list["items"][0]["data_source"] == "Alpaca IEX"
    assert system_list["items"][0]["status"] == "Lista para entrada"


def test_voice_can_read_autonomous_system_watchlist_without_visible_table(tmp_path, monkeypatch):
    state_path = tmp_path / "roxy_watchlists.json"
    store = WatchlistStore(state_path)
    store.sync_operational_opportunities(
        "local_user",
        [
            {
                "symbol": "BTC/USD",
                "market": "crypto",
                "action": "ALERT",
                "focus_priority": 2,
                "data_bucket": "Live real",
                "data_state": "Broker/exchange live",
                "data_gate": "LIVE_DATA_OK",
                "data_source": "BinanceUS API",
                "entry": 65000,
                "stop": 64000,
                "target_price": 67000,
                "current_price": 65100,
                "reason": "Ruptura confirmada con proveedor live.",
            }
        ],
        source_healthy=True,
    )
    monkeypatch.setattr(streamlit_app, "project_path", lambda _value: state_path)
    monkeypatch.setattr(streamlit_app, "roxy_os_user_id", lambda: "local_user")

    snapshot = streamlit_app.roxy_durable_voice_opportunity_snapshot()

    assert snapshot["source"] == "watchlist_autonoma"
    assert snapshot["rows"][0]["symbol"] == "BTC/USD"
    assert snapshot["rows"][0]["entry"] != "-"
    streamlit_app.st.session_state.pop("roxy_voice_opportunity_snapshot", None)
    response = streamlit_app.run_roxy_os_command("Roxy, dime las mejores oportunidades")
    assert response["data"]["source"] == "watchlist_autonoma"
    assert response["data"]["snapshot_available"] is True
    assert "BTC/USD" in response["message"]


def test_voice_uses_central_ai_brief_when_managed_watchlist_is_empty(tmp_path, monkeypatch):
    state_path = tmp_path / "roxy_watchlists.json"
    generated_at = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(streamlit_app, "project_path", lambda _value: state_path)
    monkeypatch.setattr(streamlit_app, "roxy_os_user_id", lambda: "new_session_user")
    monkeypatch.setattr(
        streamlit_app,
        "read_summary_json",
        lambda _path: {
            "generated_at": generated_at,
            "source_freshness": {"status": "FRESH", "detail": "actualizado hace 1 min."},
            "opportunities": [
                {
                    "symbol": "LINK/USD",
                    "market": "crypto",
                    "action": "WATCH",
                    "close_15m": 8.41,
                    "entry": 8.43,
                    "stop": 8.21,
                    "recommended_target_price": 8.76,
                    "chart_timeframe": "15m",
                    "ai_score": 74,
                    "explanation": "Ruptura pendiente de confirmacion.",
                    "alert_primary_blocker": "Falta cierre sobre resistencia.",
                    "source_freshness": {
                        "status": "FRESH",
                        "detail": "live/confluencia actualizados hace 1 min.",
                    },
                }
            ],
        },
    )

    snapshot = streamlit_app.roxy_durable_voice_opportunity_snapshot()

    assert snapshot["source"] == "roxy_ai_brief_candidates"
    assert snapshot["snapshot_kind"] == "watch_candidate"
    assert snapshot["updated_at"] == generated_at
    assert snapshot["rows"][0] == {
        "symbol": "LINK/USD",
        "market": "crypto",
        "price": "8.4100",
        "price_basis": "ultimo cierre 15m",
        "entry": "8.4300",
        "stop": "8.2100",
        "target": "8.7600",
        "timeframe": "15m",
        "decision": "WATCH",
        "confidence": "74",
        "risk": "-",
        "reason": "Ruptura pendiente de confirmacion.",
        "next_step": "Falta cierre sobre resistencia.",
        "data_state": "live/confluencia actualizados hace 1 min.",
        "data_source": "-",
        "target_contract": "-",
        "levels_status": "-",
        "levels_source": "-",
    }


def test_voice_rejects_stale_brief_and_session_snapshot_from_another_module(tmp_path, monkeypatch):
    state_path = tmp_path / "roxy_watchlists.json"
    monkeypatch.setattr(streamlit_app, "project_path", lambda _value: state_path)
    monkeypatch.setattr(streamlit_app, "roxy_os_user_id", lambda: "new_session_user")
    monkeypatch.setattr(
        streamlit_app,
        "read_summary_json",
        lambda _path: {
            "generated_at": "2026-07-19T10:00:00+00:00",
            "source_freshness": {"status": "FRESH"},
            "opportunities": [{"symbol": "BTC/USD", "action": "WATCH"}],
        },
    )

    assert streamlit_app.roxy_durable_voice_opportunity_snapshot() is None
    now = datetime(2026, 7, 19, 17, 45, tzinfo=timezone.utc)
    snapshot = {
        "module": "crypto-2h",
        "updated_at": "2026-07-19T17:44:00+00:00",
        "rows": [{"symbol": "ETH/USD"}],
    }
    assert streamlit_app.roxy_voice_snapshot_is_current(
        snapshot, page_context={"module": "acciones-operar"}, now=now
    ) is False
    assert streamlit_app.roxy_voice_snapshot_is_current(
        snapshot, page_context={"module": "crypto-2h"}, now=now
    ) is True
    assert streamlit_app.roxy_voice_snapshot_is_current(
        {**snapshot, "updated_at": "2026-07-19T17:30:00+00:00"},
        page_context={"module": "crypto-2h"},
        now=now,
    ) is False


def test_voice_labels_watch_candidates_as_observation_not_ready_opportunities(monkeypatch):
    monkeypatch.setattr(
        streamlit_app,
        "roxy_elevenlabs_page_context",
        lambda: {"module": "crypto-2h", "symbol": "ETH/USD", "market": "crypto", "timeframe": "2h"},
    )
    monkeypatch.setattr(
        streamlit_app,
        "roxy_resolved_voice_opportunity_snapshot",
        lambda: {
            "module": "crypto-2h",
            "snapshot_kind": "watch_candidate",
            "rows": [{"symbol": "ETH/USD", "decision": "CRYPTO_SCAN_WATCH", "price": "1871.60"}],
        },
    )

    reply = streamlit_app.roxy_voice_local_context_reply("Roxy, dime las mejores oportunidades")

    assert "candidatas en observacion" in reply
    assert "ninguna esta lista para entrada" in reply
    assert "Score de vigilancia" in reply
    assert "Referencia del scan" in reply
    assert "Target sin definir; no hay objetivo explicito" in reply
    assert "Niveles incompletos para operar" in reply
    assert "Confianza" not in reply
    assert "mejores oportunidades" not in reply
    contract = streamlit_app.roxy_voice_response_contract(
        {"module": "crypto-2h"},
        {
            "snapshot_kind": "watch_candidate",
            "rows": [{"symbol": "ETH/USD", "decision": "WATCH", "confidence": "85"}],
        },
    )
    assert "candidatas WATCH, no oportunidades listas para entrada" in contract
    assert "score de vigilancia 85" in contract


def test_degraded_opportunity_sync_preserves_last_known_system_list(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    live = {
        "symbol": "AAPL",
        "action": "ALERT",
        "focus_priority": 2,
        "data_bucket": "Live real",
        "data_state": "Broker/exchange live",
        "data_gate": "LIVE_PRICE_OK",
    }
    store.sync_operational_opportunities("user", [live], source_healthy=True)
    result = store.sync_operational_opportunities("user", [], source_healthy=False)
    assert result["reason"] == "source_not_healthy"
    items = store.snapshot("user")["lists"]["Roxy Oportunidades"]["items"]
    assert [item["symbol"] for item in items] == ["AAPL"]


def test_healthy_opportunity_sync_archives_rows_that_expire(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    live = {
        "symbol": "AAPL",
        "action": "ALERT",
        "focus_priority": 2,
        "data_bucket": "Live real",
        "data_state": "Broker/exchange live",
        "data_gate": "LIVE_PRICE_OK",
    }
    store.sync_operational_opportunities("user", [live], source_healthy=True)
    result = store.sync_operational_opportunities("user", [], source_healthy=True)

    assert result["archived"] == 1
    assert store.snapshot("user")["lists"]["Roxy Oportunidades"]["items"] == []
    archived = store.opportunity_archive_snapshot("user")
    assert archived[0]["symbol"] == "AAPL"
    assert archived[0]["status"] == "Expirada"
    assert archived[0]["archive_reason"] == "No presente en el ultimo scan saludable"


def test_crypto_alert_summary_reads_durable_rules_not_scanner_rows(tmp_path, monkeypatch):
    state_path = tmp_path / "roxy_watchlists.json"
    store = WatchlistStore(state_path)
    store.create_price_alert(
        "browser-user",
        symbol="BTC/USD",
        market="crypto",
        alert_type="price_above",
        threshold=70000,
        source="test",
    )
    monkeypatch.setattr(streamlit_app, "project_path", lambda _value: state_path)
    monkeypatch.setattr(streamlit_app, "roxy_os_user_id", lambda: "browser-user")

    html, count = streamlit_app.roxy_durable_alerts_html(market="crypto")

    assert count == 1
    assert "BTC/USDT" in html
    assert "70,000.00" in html
    assert "Activa" in html


def test_crypto_surfaces_do_not_embed_fake_change_alert_or_macro_values():
    source = open("streamlit_app.py", encoding="utf-8").read()
    crypto_source = source[source.index("def render_roxy_crypto20_folder") : source.index("def roxy_trade_plan_from_row")]

    for fake in ('+0.11%', '+0.31%', 'notifications</i><b>3', 'Decision de tasas BCE', 'PCE EE.UU.', 'Reunion Fed'):
        assert fake not in crypto_source
    assert crypto_source.count('roxy_durable_alerts_html(market="crypto"') == 3
    assert "roxy_macro_events_html(limit=3)" in crypto_source


def test_system_managed_opportunity_list_rejects_manual_mutations(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    live = {
        "symbol": "AAPL",
        "market": "stock",
        "action": "ALERT",
        "focus_priority": 2,
        "data_bucket": "Live real",
        "data_state": "Broker/exchange live",
        "data_gate": "LIVE_DATA_OK",
    }
    store.sync_operational_opportunities("user", [live], source_healthy=True)

    added = store.add_asset("user", "Roxy Oportunidades", "MSFT", "stock")
    removed = store.remove_asset("user", "Roxy Oportunidades", "AAPL", "stock")

    assert added["reason"] == "system_managed"
    assert removed["reason"] == "system_managed"
    assert [
        item["symbol"]
        for item in store.snapshot("user")["lists"]["Roxy Oportunidades"]["items"]
    ] == ["AAPL"]


def test_system_managed_watchlist_uses_status_not_disabled_fake_action():
    source = __import__("pathlib").Path("streamlit_app.py").read_text(encoding="utf-8")
    panel = source[
        source.index("def render_roxy_watchlists_panel") : source.index("def render_roxy_actions_folder")
    ]

    assert 'st.info("Sincronización automática activa · lista de solo lectura")' in panel
    assert 'st.button("Sincronización automática", disabled=True' not in panel


def test_alerts_fall_back_to_personal_list_and_refresh_voice_session_context(tmp_path, monkeypatch):
    store = WatchlistStore(tmp_path / "watchlists.json")
    live = {
        "symbol": "AAPL",
        "market": "stock",
        "action": "ALERT",
        "focus_priority": 2,
        "data_bucket": "Live real",
        "data_state": "Broker/exchange live",
        "data_gate": "LIVE_DATA_OK",
    }
    store.sync_operational_opportunities("user", [live], source_healthy=True)
    fake_session = {}
    monkeypatch.setattr(streamlit_app.st, "session_state", fake_session)

    selected = streamlit_app.roxy_mutable_watchlist_name(store, "user", "Roxy Oportunidades")
    store.add_asset("user", selected, "ETH/USD", "crypto")
    symbols = streamlit_app.sync_roxy_watchlist_session(store, "user", selected)

    assert selected == "Principal"
    assert symbols == ["ETH/USD"]
    assert fake_session["roxy_watchlist_selected"] == "Principal"
    assert fake_session["watchlist"] == ["ETH/USD"]
