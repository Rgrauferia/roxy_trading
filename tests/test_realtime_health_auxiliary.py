import json
from datetime import datetime, timezone

from roxy_ai import realtime_health_status


def test_auxiliary_storage_failure_does_not_block_healthy_crypto_route(tmp_path):
    report = tmp_path / "roxy_realtime_check.json"
    report.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "generated_at": "2026-07-18T20:00:00+00:00",
                "market_realtime": {
                    "allowed_markets": ["crypto"],
                    "blocked_markets": ["stock", "options"],
                    "active_route_label": "Operar solo CRYPTO",
                    "active_route_detail": "Operable CRYPTO; bloqueado STOCK, OPTIONS.",
                },
                "provider_recovery": {"premium_blocked": True},
                "checks": [
                    {
                        "name": "external_disk",
                        "status": "FAIL",
                        "detail": "/Volumes/RoxyData mounted but not writable",
                    },
                    {
                        "name": "runtime_backup_service",
                        "status": "FAIL",
                        "detail": "not installed",
                    },
                    {
                        "name": "dashboard_render_probe",
                        "status": "FAIL",
                        "detail": "BrowserType.launch: Executable doesn't exist at playwright/chromium",
                    },
                ],
            }
        )
    )

    status = realtime_health_status(
        report,
        now=datetime(2026, 7, 18, 20, 1, tzinfo=timezone.utc),
    )

    assert status["status"] == "WARN"
    assert status["alerts_allowed"] is True
    assert status["crypto_alerts_allowed"] is True
    assert status["stock_alerts_allowed"] is False
    assert status["auxiliary_failures"] == [
        "dashboard_render_probe",
        "external_disk",
        "runtime_backup_service",
    ]


def test_market_data_failure_still_blocks_all_alerts(tmp_path):
    report = tmp_path / "roxy_realtime_check.json"
    report.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "generated_at": "2026-07-18T20:00:00+00:00",
                "market_realtime": {"allowed_markets": ["crypto"], "blocked_markets": ["stock"]},
                "checks": [{"name": "chart_indicators", "status": "FAIL", "detail": "sin velas"}],
            }
        )
    )

    status = realtime_health_status(
        report,
        now=datetime(2026, 7, 18, 20, 1, tzinfo=timezone.utc),
    )

    assert status["status"] == "FAIL"
    assert status["alerts_allowed"] is False
