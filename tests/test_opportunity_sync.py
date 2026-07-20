from datetime import datetime, timezone
from pathlib import Path

from roxy_trader.opportunity_sync import (
    brief_source_health,
    opportunity_source_contract,
    sync_brief_opportunities,
)
from roxy_trader.watchlists import WatchlistStore
from tools import roxy_realtime_check


def live_brief(tmp_path: Path, *, action: str = "ALERT") -> dict:
    scan = tmp_path / "scan.csv"
    confluence = tmp_path / "confluence.csv"
    scan.write_text("symbol\nBTC/USD\n", encoding="utf-8")
    confluence.write_text("symbol\nBTC/USD\n", encoding="utf-8")
    return {
        "generated_at": "2026-07-19T08:00:00+00:00",
        "source_files": {"scan": str(scan), "confluence": str(confluence)},
        "source_freshness": {"status": "FRESH", "detail": "current"},
        "realtime_health": {
            "alerts_allowed": True,
            "market_realtime": {"markets": {"crypto": {"alerts_allowed": True}}},
        },
        "opportunities": [
            {
                "symbol": "BTC/USD",
                "market": "crypto",
                "timeframe": "15m",
                "ai_action": action,
                "action": action,
                "signal": "BUY" if action == "ALERT" else "WATCH",
                "focus_priority": 2 if action == "ALERT" else 1,
                "entry": 65000,
                "stop": 64000,
                "target_price": 67000,
                "chart_data_gate": "LIVE_DATA_OK",
                "chart_operable": True,
                "chart_data_contract": {"gate": "LIVE_DATA_OK", "operable": True, "source_label": "BTC/USD"},
            }
        ],
    }


def test_source_contract_requires_chart_and_market_gate(tmp_path):
    row = live_brief(tmp_path)["opportunities"][0]
    realtime = {"market_realtime": {"markets": {"crypto": {"alerts_allowed": True}}}}
    contracted = opportunity_source_contract(row, realtime)
    assert contracted["data_bucket"] == "Live real"
    assert contracted["data_source"] == "BinanceUS API"

    blocked = opportunity_source_contract(row, {"market_realtime": {"markets": {"crypto": {"alerts_allowed": False}}}})
    assert blocked["data_bucket"] == "Bloqueadas"


def test_background_sync_writes_ready_rows_for_existing_users(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.create_list("roberto", "Principal")
    report = sync_brief_opportunities(live_brief(tmp_path), store=store)
    assert report["status"] == "OK"
    assert report["trade_ready_count"] == 1
    rows = store.snapshot("roberto")["lists"]["Roxy Oportunidades"]["items"]
    assert rows[0]["symbol"] == "BTC/USD"
    assert rows[0]["data_source"] == "BinanceUS API"


def test_degraded_sync_preserves_last_known_opportunity(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.create_list("roberto", "Principal")
    sync_brief_opportunities(live_brief(tmp_path), store=store)
    degraded = live_brief(tmp_path)
    degraded["source_freshness"] = {"status": "STALE", "detail": "provider delayed"}
    degraded["opportunities"] = []
    report = sync_brief_opportunities(degraded, store=store)
    assert report["status"] == "WARNING"
    assert report["users"]["roberto"]["reason"] == "source_not_healthy"
    assert store.snapshot("roberto")["lists"]["Roxy Oportunidades"]["items"][0]["symbol"] == "BTC/USD"


def test_healthy_watch_only_scan_expires_old_ready_row(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.create_list("roberto", "Principal")
    sync_brief_opportunities(live_brief(tmp_path), store=store)
    report = sync_brief_opportunities(live_brief(tmp_path, action="WATCH"), store=store)
    assert report["status"] == "OK"
    assert store.snapshot("roberto")["lists"]["Roxy Oportunidades"]["items"] == []
    assert store.opportunity_archive_snapshot("roberto")[0]["status"] == "Expirada"


def test_sync_archives_invalidated_watch_event_once_per_persistent_episode(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    brief = live_brief(tmp_path, action="WATCH")
    brief["opportunities"] = []
    brief["archived_opportunities"] = [
        {
            "symbol": "LTC/USD",
            "market": "crypto",
            "status": "Invalidada",
            "archive_reason": "Stale sin gatillo.",
            "archived_at": "2026-07-19T22:00:00+00:00",
            "resume_condition": "Confirmacion 15m.",
        }
    ]

    first = sync_brief_opportunities(brief, store=store, configured_user="roberto")
    second = sync_brief_opportunities(brief, store=store, configured_user="roberto")

    assert first["invalidated_archive_event_count"] == 1
    assert first["users"]["roberto"]["invalidated_archive"]["archived"] == 1
    assert second["users"]["roberto"]["invalidated_archive"]["updated"] == 1
    archive = store.opportunity_archive_snapshot("roberto")
    assert len(archive) == 1
    assert archive[0]["status"] == "Invalidada"


def test_brief_health_requires_real_artifacts(tmp_path):
    brief = live_brief(tmp_path)
    assert brief_source_health(brief)[0] is True
    Path(brief["source_files"]["scan"]).unlink()
    assert brief_source_health(brief)[0] is False


def test_realtime_validator_exposes_fresh_sync_contract(tmp_path):
    report_path = tmp_path / "opportunity_sync.json"
    report_path.write_text(
        '{"contract_version":"roxy-opportunity-sync/1.0.0","generated_at":"2026-07-19T08:00:00+00:00",'
        '"status":"OK","source_healthy":true,"candidate_count":3,"trade_ready_count":1,"users":{"u":{}}}',
        encoding="utf-8",
    )
    result = roxy_realtime_check.validate_opportunity_sync_report(
        report_path, now=datetime(2026, 7, 19, 8, 5, tzinfo=timezone.utc)
    )
    assert result["status"] == "OK"
    assert result["trade_ready_count"] == 1
