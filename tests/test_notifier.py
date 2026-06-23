import json
from datetime import datetime, timezone

import notifier


def _clear_channels(monkeypatch):
    monkeypatch.setattr(notifier, "SLACK_WEBHOOK", "")
    monkeypatch.setattr(notifier, "GENERIC_WEBHOOK", "")
    monkeypatch.setattr(notifier, "DISCORD_WEBHOOK", "")
    monkeypatch.setattr(notifier, "PUSHOVER_APP_TOKEN", "")
    monkeypatch.setattr(notifier, "PUSHOVER_USER_KEY", "")
    monkeypatch.setattr(notifier, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(notifier, "TELEGRAM_CHAT_ID", "")
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


def test_configured_channels_supports_mobile_push_channels(monkeypatch):
    _clear_channels(monkeypatch)
    monkeypatch.setattr(notifier, "PUSHOVER_APP_TOKEN", "app-token")
    monkeypatch.setattr(notifier, "PUSHOVER_USER_KEY", "user-key")
    monkeypatch.setattr(notifier, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(notifier, "TELEGRAM_CHAT_ID", "chat-id")

    assert notifier.configured_channels() == ["pushover", "telegram"]
    rows = {row["channel"]: row for row in notifier.notification_channel_status()}
    assert rows["pushover"]["configured"] is True
    assert rows["telegram"]["configured"] is True


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


def test_append_history_trims_notification_history_by_bytes(tmp_path, monkeypatch):
    history_path = tmp_path / "notification_history.jsonl"
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", history_path)

    for idx in range(6):
        notifier._append_history(
            {
                "ts": f"2026-06-10T00:0{idx}:00+00:00",
                "reason": "recorded_local",
                "sent": False,
                "channels": [],
                "message": f"alert-{idx}-" + "x" * 180,
            },
            max_lines=6,
            max_bytes=520,
            min_lines=2,
        )

    lines = history_path.read_text().splitlines()
    rows = notifier.read_notification_history(limit=10)
    summary = notifier.notification_history_summary(limit=10)
    assert len(lines) == 2
    assert [row["message"].split("-")[1] for row in rows] == ["4", "5"]
    assert summary["sample_size"] == 2
    assert summary["line_count"] == 2
    assert summary["size_bytes"] == history_path.stat().st_size
    assert summary["max_bytes"] == notifier.NOTIFICATION_HISTORY_MAX_BYTES
    assert summary["max_lines"] == notifier.NOTIFICATION_HISTORY_MAX_LINES


def test_append_history_compacts_repeated_local_notification_rows(tmp_path, monkeypatch):
    history_path = tmp_path / "notification_history.jsonl"
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", history_path)
    base = {
        "reason": "recorded_local",
        "sent": False,
        "effective_sent": False,
        "channels": [],
        "incident_key": "WARN|PREMIUM_BLOCKED",
        "message": "ROXY HEALTH WARN | Premium bloqueado",
    }
    history_path.write_text(
        "\n".join(
            [
                json.dumps({"ts": "2026-06-10T00:00:00+00:00", **base}, sort_keys=True),
                json.dumps({"ts": "2026-06-10T00:01:00+00:00", **base}, sort_keys=True),
            ]
        )
        + "\n"
    )

    notifier._append_history({"ts": "2026-06-10T00:02:00+00:00", **base})

    rows = notifier.read_notification_history(limit=10)
    summary = notifier.notification_history_summary(limit=10)
    assert len(history_path.read_text().splitlines()) == 1
    assert rows[0]["ts"] == "2026-06-10T00:00:00+00:00"
    assert rows[0]["last_ts"] == "2026-06-10T00:02:00+00:00"
    assert rows[0]["repeat_count"] == 3
    assert summary["sample_size"] == 1
    assert summary["sample_event_count"] == 3
    assert summary["suppressed_count"] == 3
    assert summary["local_recorded_count"] == 3
    assert summary["reason_counts"]["recorded_local"] == 3
    assert summary["health_event_count"] == 3
    assert summary["last_health_incident_key"] == "WARN|PREMIUM_BLOCKED"


def test_append_history_does_not_compact_sent_notification_rows(tmp_path, monkeypatch):
    history_path = tmp_path / "notification_history.jsonl"
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", history_path)
    base = {
        "reason": "health_watchdog",
        "sent": True,
        "effective_sent": True,
        "channels": ["macos"],
        "incident_key": "FAIL|heartbeat",
        "message": "ROXY HEALTH FAIL | heartbeat",
    }

    notifier._append_history({"ts": "2026-06-10T00:00:00+00:00", **base})
    notifier._append_history({"ts": "2026-06-10T00:01:00+00:00", **base})

    rows = notifier.read_notification_history(limit=10)
    summary = notifier.notification_history_summary(limit=10)
    assert len(rows) == 2
    assert "repeat_count" not in rows[-1]
    assert summary["sample_size"] == 2
    assert summary["sample_event_count"] == 2
    assert summary["sent_count"] == 2


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


def test_notification_history_summary_tracks_health_incident_key_coverage(tmp_path, monkeypatch):
    history_path = tmp_path / "notification_history.jsonl"
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", history_path)
    history_path.write_text(
        "\n".join(
            [
                '{"channels": [], "message": "ROXY HEALTH FAIL | heartbeat: failed", "reason": "recorded_local", "sent": false, "ts": "2026-06-10T00:00:00+00:00"}',
                '{"channels": [], "incident_key": "WARN|PREMIUM_BLOCKED", "message": "ROXY HEALTH WARN | Premium bloqueado", "reason": "recorded_local", "sent": false, "ts": "2026-06-10T00:01:00+00:00"}',
                '{"channels": [], "message": "AAPL watch", "reason": "recorded_local", "sent": false, "ts": "2026-06-10T00:02:00+00:00"}',
            ]
        )
    )

    summary = notifier.notification_history_summary(limit=10)

    assert summary["health_event_count"] == 2
    assert summary["health_incident_key_missing_count"] == 1
    assert summary["latest_health_incident_key_missing"] is False
    assert summary["last_health_incident_key"] == "WARN|PREMIUM_BLOCKED"
    assert summary["last_incident_key"] == ""


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
        metadata={"incident_key": "FAIL|heartbeat|FAIL"},
    )

    assert result["sent"] is True
    assert result["reason"] == "health_watchdog"
    assert result["channels"] == ["macos"]
    assert result["incident_key"] == "FAIL|heartbeat|FAIL"
    assert calls == [{"msg": "ROXY HEALTH\n\nROXY HEALTH FAIL | heartbeat: network unavailable", "force": False}]
    history = notifier.read_notification_history()
    assert history[-1]["reason"] == "health_watchdog"
    assert history[-1]["incident_key"] == "FAIL|heartbeat|FAIL"
    assert history[-1]["effective_sent"] is True


def test_send_notification_message_records_local_when_no_channels(tmp_path, monkeypatch):
    _clear_channels(monkeypatch)
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", tmp_path / "notification_history.jsonl")

    result = notifier.send_notification_message(
        "ROXY HEALTH WARN | delivery local only",
        reason="health_watchdog",
        metadata={"incident_key": "WARN|notification_delivery|INFO"},
    )

    assert result["sent"] is False
    assert result["reason"] == "recorded_local"
    assert result["channels"] == []
    assert result["incident_key"] == "WARN|notification_delivery|INFO"
    history = notifier.read_notification_history()
    assert history[-1]["reason"] == "recorded_local"
    assert history[-1]["incident_key"] == "WARN|notification_delivery|INFO"
    assert history[-1]["effective_sent"] is False


def test_send_notification_message_posts_to_mobile_and_structured_webhook(tmp_path, monkeypatch):
    calls = []
    _clear_channels(monkeypatch)
    monkeypatch.setattr(notifier, "NOTIFICATION_HISTORY_FILE", tmp_path / "notification_history.jsonl")
    monkeypatch.setattr(notifier, "PUSHOVER_APP_TOKEN", "app-token")
    monkeypatch.setattr(notifier, "PUSHOVER_USER_KEY", "user-key")
    monkeypatch.setattr(notifier, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(notifier, "TELEGRAM_CHAT_ID", "chat-id")
    monkeypatch.setattr(notifier, "GENERIC_WEBHOOK", "https://hooks.example/roxy")

    def fake_post(url, json, timeout=10):
        calls.append({"url": url, "json": json, "timeout": timeout})

    monkeypatch.setattr(notifier, "_safe_post", fake_post)

    result = notifier.send_notification_message(
        "AAPL | ENTRA AHORA | entrada 100 | stop 98",
        reason="actionable_alert_transition",
        metadata={"incident_key": "actionable_alert_transition", "ticker": "AAPL"},
    )

    urls = [call["url"] for call in calls]
    assert result["sent"] is True
    assert result["channels"] == ["pushover", "telegram", "webhook"]
    assert "https://api.pushover.net/1/messages.json" in urls
    assert "https://api.telegram.org/botbot-token/sendMessage" in urls
    webhook = next(call for call in calls if call["url"] == "https://hooks.example/roxy")
    assert webhook["json"]["source"] == "roxy_trading"
    assert webhook["json"]["metadata"]["reason"] == "actionable_alert_transition"
    assert webhook["json"]["metadata"]["ticker"] == "AAPL"
