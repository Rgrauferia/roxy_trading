from datetime import datetime, timezone

import notifier


def _clear_channels(monkeypatch):
    monkeypatch.setattr(notifier, "SLACK_WEBHOOK", "")
    monkeypatch.setattr(notifier, "GENERIC_WEBHOOK", "")
    monkeypatch.setattr(notifier, "DISCORD_WEBHOOK", "")
    monkeypatch.setattr(notifier, "SMTP_HOST", "")
    monkeypatch.setattr(notifier, "ALERT_EMAIL_FROM", "")
    monkeypatch.setattr(notifier, "ALERT_EMAIL_TO", "")
    monkeypatch.setattr(notifier, "MACOS_NOTIFICATIONS", False)


def test_configured_channels_supports_email_discord_and_macos(monkeypatch):
    _clear_channels(monkeypatch)
    monkeypatch.setattr(notifier, "DISCORD_WEBHOOK", "https://discord.example/webhook")
    monkeypatch.setattr(notifier, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(notifier, "ALERT_EMAIL_FROM", "roxy@example.com")
    monkeypatch.setattr(notifier, "ALERT_EMAIL_TO", "user@example.com")
    monkeypatch.setattr(notifier, "MACOS_NOTIFICATIONS", True)

    assert notifier.configured_channels() == ["discord", "email", "macos"]


def test_configured_channels_empty_when_no_external_channel(monkeypatch):
    _clear_channels(monkeypatch)

    assert notifier.configured_channels() == []


def test_notify_if_changed_records_history(tmp_path, monkeypatch):
    _clear_channels(monkeypatch)
    monkeypatch.setattr(notifier, "LAST_SENT_FILE", tmp_path / "last_sent.txt")
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", tmp_path / "notification_history.jsonl")
    monkeypatch.setattr(notifier, "NOTIFICATION_COOLDOWN_FILE", tmp_path / "notification_cooldowns.json")

    first = notifier.notify_if_changed(["AAPL | BUY WATCH | Entry 203.40"])
    second = notifier.notify_if_changed(["AAPL | BUY WATCH | Entry 203.40"])

    assert first["sent"] is False
    assert first["reason"] == "recorded_local"
    assert first["channels"] == []
    assert second["sent"] is False
    assert second["reason"] == "unchanged"

    rows = notifier.read_notification_history(limit=10)
    assert [row["reason"] for row in rows] == ["recorded_local", "unchanged"]
    assert rows[0]["message"] == "AAPL | BUY WATCH | Entry 203.40"
    assert rows[0]["effective_sent"] is False
    assert rows[1]["effective_sent"] is False
    summary = notifier.notification_history_summary(
        limit=10,
        now=datetime.fromisoformat(rows[-1]["ts"].replace("Z", "+00:00")),
    )
    assert summary["sample_size"] == 2
    assert summary["sent_count"] == 0
    assert summary["suppressed_count"] == 2
    assert summary["local_recorded_count"] == 2
    assert summary["reason_counts"]["recorded_local"] == 1
    assert summary["last_reason"] == "unchanged"
    assert summary["last_age_minutes"] == 0.0
    assert summary["delivery_mode"] == "local_file"


def test_notification_history_summary_ignores_legacy_sent_without_channels(tmp_path, monkeypatch):
    history_path = tmp_path / "notification_history.jsonl"
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", history_path)
    history_path.write_text(
        "\n".join(
            [
                '{"channels": [], "message": "old", "reason": "health_watchdog", "sent": true, "ts": "2026-06-10T00:00:00+00:00"}',
                '{"channels": ["macos"], "message": "new", "reason": "health_watchdog", "sent": true, "ts": "2026-06-10T00:01:00+00:00"}',
            ]
        )
    )

    summary = notifier.notification_history_summary(limit=10)

    assert summary["sample_size"] == 2
    assert summary["sent_count"] == 1
    assert summary["suppressed_count"] == 1
    assert summary["last_sent"] is True
    assert summary["last_effective_sent"] is True


def test_notification_history_summary_skips_malformed_recent_lines(tmp_path, monkeypatch):
    history_path = tmp_path / "notification_history.jsonl"
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", history_path)
    history_path.write_text(
        "\n".join(
            [
                '{"channels": [], "message": "old", "reason": "recorded_local", "sent": false, "ts": "2026-06-10T00:00:00+00:00"}',
                "not-json",
                '["wrong-shape"]',
                '{"channels": [], "message": "new", "reason": "recorded_local", "sent": false, "ts": "2026-06-10T00:01:00+00:00"}',
            ]
        )
    )

    rows = notifier.read_notification_history(limit=10)
    summary = notifier.notification_history_summary(limit=10)

    assert [row["message"] for row in rows] == ["old", "new"]
    assert summary["sample_size"] == 2
    assert summary["malformed_recent_lines"] == 2


def test_notify_if_changed_uses_symbol_cooldown_for_changed_alert(tmp_path, monkeypatch):
    _clear_channels(monkeypatch)
    monkeypatch.setattr(notifier, "LAST_SENT_FILE", tmp_path / "last_sent.txt")
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", tmp_path / "notification_history.jsonl")
    monkeypatch.setattr(notifier, "NOTIFICATION_COOLDOWN_FILE", tmp_path / "notification_cooldowns.json")

    first = notifier.notify_if_changed(["STOCK AAPL TRADE_FOR_5PCT | entry 203.40"])
    second = notifier.notify_if_changed(["STOCK AAPL TRADE_FOR_5PCT | entry 203.75"])

    assert first["sent"] is False
    assert first["reason"] == "recorded_local"
    assert second["sent"] is False
    assert second["reason"] == "cooldown"
    assert second["cooldown_skipped"] == 1


def test_notify_if_changed_sends_new_alerts_and_reports_cooldown_skips(tmp_path, monkeypatch):
    _clear_channels(monkeypatch)
    monkeypatch.setattr(notifier, "LAST_SENT_FILE", tmp_path / "last_sent.txt")
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", tmp_path / "notification_history.jsonl")
    monkeypatch.setattr(notifier, "NOTIFICATION_COOLDOWN_FILE", tmp_path / "notification_cooldowns.json")

    first = notifier.notify_if_changed(
        [
            "STOCK AAPL TRADE_FOR_5PCT | entry 203.40",
            "CRYPTO BTC/USD TRADE_FOR_5PCT | entry 65000.00",
        ]
    )
    second = notifier.notify_if_changed(
        [
            "STOCK AAPL TRADE_FOR_5PCT | entry 203.75",
            "STOCK MSFT TRADE_FOR_5PCT | entry 410.00",
        ]
    )

    assert first["sent"] is False
    assert first["reason"] == "recorded_local"
    assert second["sent"] is False
    assert second["reason"] == "recorded_local"
    assert second["cooldown_skipped"] == 1
    assert "MSFT" in second["message"]
    assert "AAPL" not in second["message"]


def test_filter_alerts_by_cooldown_prunes_old_keys(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timedelta, timezone

    cooldown_path = tmp_path / "notification_cooldowns.json"
    monkeypatch.setattr(notifier, "NOTIFICATION_COOLDOWN_FILE", cooldown_path)
    cooldown_path.write_text(
        json.dumps(
            {
                "STOCK:OLD": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
                "STOCK:AAPL": datetime.now(timezone.utc).isoformat(),
            }
        )
    )

    sendable, skipped = notifier.filter_alerts_by_cooldown(
        ["STOCK AAPL TRADE_FOR_5PCT", "STOCK MSFT TRADE_FOR_5PCT"],
        cooldown_minutes=60,
    )

    saved = json.loads(cooldown_path.read_text())
    assert skipped == ["STOCK AAPL TRADE_FOR_5PCT"]
    assert sendable == ["STOCK MSFT TRADE_FOR_5PCT"]
    assert "STOCK:OLD" not in saved
    assert "STOCK:MSFT" in saved


def test_send_test_macos_notification_records_history(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", tmp_path / "notification_history.jsonl")

    def fake_macos(msg, *, force=False):
        calls.append({"msg": msg, "force": force})

    monkeypatch.setattr(notifier, "send_macos_notification", fake_macos)

    result = notifier.send_test_macos_notification()

    assert result["sent"] is True
    assert result["reason"] == "test_macos"
    assert calls == [{"msg": "Roxy test alert. Mac notifications are working.", "force": True}]
    history = notifier.read_notification_history()
    assert history[-1]["reason"] == "test_macos"
    assert history[-1]["effective_sent"] is True


def test_send_notification_message_records_operational_history(tmp_path, monkeypatch):
    calls = []
    _clear_channels(monkeypatch)
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", tmp_path / "notification_history.jsonl")
    monkeypatch.setattr(notifier, "MACOS_NOTIFICATIONS", True)

    def fake_macos(msg, *, force=False):
        calls.append({"msg": msg, "force": force})

    monkeypatch.setattr(notifier, "send_macos_notification", fake_macos)

    result = notifier.send_notification_message(
        "ROXY HEALTH FAIL | heartbeat: network unavailable",
        reason="health_watchdog",
        header="ROXY HEALTH",
    )

    assert result["sent"] is True
    assert result["reason"] == "health_watchdog"
    assert result["channels"] == ["macos"]
    assert calls == [{"msg": "ROXY HEALTH\n\nROXY HEALTH FAIL | heartbeat: network unavailable", "force": False}]
    history = notifier.read_notification_history()
    assert history[-1]["reason"] == "health_watchdog"
    assert history[-1]["effective_sent"] is True


def test_send_notification_message_records_local_when_no_channels(tmp_path, monkeypatch):
    _clear_channels(monkeypatch)
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", tmp_path / "notification_history.jsonl")

    result = notifier.send_notification_message("ROXY HEALTH WARN | delivery local only", reason="health_watchdog")

    assert result["sent"] is False
    assert result["reason"] == "recorded_local"
    assert result["channels"] == []
    history = notifier.read_notification_history()
    assert history[-1]["reason"] == "recorded_local"
    assert history[-1]["effective_sent"] is False
