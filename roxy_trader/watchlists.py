from __future__ import annotations

import json
import math
import os
import re
import secrets
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


WATCHLIST_SCHEMA_VERSION = 2
DEFAULT_WATCHLIST_PATH = Path(os.environ.get("ROXY_WATCHLIST_PATH", "data/roxy_watchlists.json"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    """Return strict-JSON data; unavailable non-finite metrics become null."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _alert_expiration_iso(ttl_hours: Any) -> str | None:
    try:
        hours = int(ttl_hours)
    except (TypeError, ValueError):
        return None
    if not 1 <= hours <= 8760:
        return None
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _utc_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_watchlist_symbol(value: Any) -> str:
    raw = str(value or "").strip()
    if "<" in raw or ">" in raw:
        return ""
    symbol = raw.upper().replace("-USD", "/USD")
    symbol = re.sub(r"[^A-Z0-9./_-]+", "", symbol)
    return symbol[:32]


def normalize_watchlist_market(value: Any, symbol: str = "") -> str:
    market = str(value or "").strip().lower()
    if market in {"crypto", "cryptocurrency", "coin"} or "/" in symbol:
        return "crypto"
    return "stock"


def normalize_watchlist_name(value: Any) -> str:
    name = " ".join(str(value or "").strip().split())[:48]
    return name or "Principal"


def normalize_watchlist_user(value: Any) -> str:
    user = re.sub(r"[^a-zA-Z0-9_.@-]+", "_", str(value or "local_user").strip().lower()).strip("_")
    return user[:96] or "local_user"


PRICE_ALERT_TYPES = {"price_above", "price_below"}
TECHNICAL_ALERT_TYPES = {"ema_cross_above", "ema_cross_below", "relative_volume_above"}
ALERT_TYPES = PRICE_ALERT_TYPES | TECHNICAL_ALERT_TYPES
ALERT_ACTIVE_STATES = {"Activa", "Activada"}
OPPORTUNITY_LIVE_GATES = {"LIVE_PRICE_OK", "LIVE_DATA_OK", "ANALYSIS_OK"}


def operational_opportunity_record(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize only trade-ready opportunities backed by a broker/exchange contract.

    Public fallbacks, rows without a contract and generic scanner seeds deliberately
    return ``None`` so they cannot silently become durable Roxy opportunities.
    """
    row = row if isinstance(row, dict) else {}
    symbol = normalize_watchlist_symbol(row.get("symbol"))
    gate = str(row.get("data_gate") or row.get("chart_data_gate") or row.get("live_price_gate") or "").upper()
    bucket = str(row.get("data_bucket") or "").strip()
    state = str(row.get("data_state") or "").strip()
    action = str(row.get("action") or row.get("ai_action") or "").upper()
    signal = str(row.get("signal") or "").upper()
    decision = str(row.get("decision") or row.get("trade_decision") or "").upper()
    try:
        priority = int(float(row.get("focus_priority") or 0))
    except (TypeError, ValueError):
        priority = 0
    trade_ready = action == "ALERT" or decision.startswith("TRADE_FOR") or (signal == "BUY" and priority >= 2)
    if (
        not symbol
        or gate not in OPPORTUNITY_LIVE_GATES
        or bucket != "Live real"
        or state != "Broker/exchange live"
        or not trade_ready
    ):
        return None

    def number(key: str) -> float | None:
        try:
            value = float(row.get(key))
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    return {
        "symbol": symbol,
        "market": normalize_watchlist_market(row.get("market"), symbol),
        "timeframe": str(row.get("timeframe") or "1h")[:12],
        "strategy": str(row.get("strategy_family") or row.get("strategy") or "")[:96],
        "entry": number("entry"),
        "stop": number("stop"),
        "target": number("target_price"),
        "current_price": number("current_price") or number("latest_price") or number("entry"),
        "confidence": number("alert_readiness_score") or number("ai_score") or number("readiness"),
        "reason": str(row.get("reason") or row.get("por_que") or row.get("raw_reason") or "")[:320],
        "data_source": str(row.get("data_source") or "")[:96],
        "data_gate": gate,
        "status": "Lista para entrada",
    }


def evaluate_price_alert(alert: dict[str, Any], current_price: Any) -> dict[str, Any]:
    result = dict(alert or {})
    try:
        price = float(current_price)
        threshold = float(result.get("threshold"))
    except (TypeError, ValueError):
        return result
    if price <= 0 or threshold <= 0 or result.get("status") != "Activa":
        return result
    alert_type = str(result.get("type") or "")
    triggered = (alert_type == "price_above" and price >= threshold) or (
        alert_type == "price_below" and price <= threshold
    )
    result["last_price"] = price
    result["last_evaluated_at"] = _now_iso()
    if triggered:
        result["status"] = "Activada"
        result["triggered_at"] = result["last_evaluated_at"]
        result["notification_status"] = "PENDING"
        result["notification_attempts"] = 0
    return result


def evaluate_durable_alert(alert: dict[str, Any], observation: dict[str, Any] | None) -> dict[str, Any]:
    """Evaluate one durable rule from a provider-gated price/indicator observation."""

    result = dict(alert or {})
    values = dict(observation or {})
    if result.get("status") != "Activa":
        return result
    alert_type = str(result.get("type") or "")
    if alert_type in PRICE_ALERT_TYPES:
        return evaluate_price_alert(result, values.get("price"))

    triggered = False
    if alert_type in {"ema_cross_above", "ema_cross_below"}:
        try:
            previous_fast = float(values.get("previous_fast"))
            previous_slow = float(values.get("previous_slow"))
            current_fast = float(values.get("current_fast"))
            current_slow = float(values.get("current_slow"))
        except (TypeError, ValueError):
            return result
        triggered = (
            previous_fast <= previous_slow and current_fast > current_slow
            if alert_type == "ema_cross_above"
            else previous_fast >= previous_slow and current_fast < current_slow
        )
        result.update(
            {
                "last_previous_fast": previous_fast,
                "last_previous_slow": previous_slow,
                "last_current_fast": current_fast,
                "last_current_slow": current_slow,
            }
        )
    elif alert_type == "relative_volume_above":
        try:
            relative_volume = float(values.get("relative_volume"))
            threshold = float(result.get("threshold"))
        except (TypeError, ValueError):
            return result
        if relative_volume < 0 or threshold <= 0:
            return result
        triggered = relative_volume >= threshold
        result["last_relative_volume"] = relative_volume
    else:
        return result

    result["last_evaluated_at"] = _now_iso()
    result["indicator_engine"] = str(values.get("indicator_engine") or "")[:64]
    if triggered:
        result["status"] = "Activada"
        result["triggered_at"] = result["last_evaluated_at"]
        result["notification_status"] = "PENDING"
        result["notification_attempts"] = 0
    return result


def _watchlist_sync_revision_semantic(user: Any) -> dict[str, Any]:
    """Return only user-authored state; autonomous telemetry must not cause edit conflicts."""
    row = user if isinstance(user, dict) else {}
    manual_lists: dict[str, Any] = {}
    for name, candidate in (row.get("lists") or {}).items():
        target = candidate if isinstance(candidate, dict) else {}
        if target.get("system_managed"):
            continue
        manual_lists[str(name)] = {
            "items": [
                {
                    "symbol": normalize_watchlist_symbol(item.get("symbol")),
                    "market": normalize_watchlist_market(item.get("market"), item.get("symbol")),
                }
                for item in target.get("items", [])
                if isinstance(item, dict) and normalize_watchlist_symbol(item.get("symbol"))
            ]
        }
    alert_fields = (
        "id", "symbol", "market", "type", "threshold", "timeframe", "watchlist_name", "status",
        "fast_period", "slow_period", "expires_at",
    )
    alerts = [
        {key: alert.get(key) for key in alert_fields}
        for alert in row.get("alerts", [])
        if isinstance(alert, dict)
    ]
    return {
        "active_list": str(row.get("active_list") or "Principal"),
        "lists": manual_lists,
        "alerts": alerts,
    }


class WatchlistStore:
    def __init__(self, path: str | Path = DEFAULT_WATCHLIST_PATH):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": WATCHLIST_SCHEMA_VERSION, "updated_at": _now_iso(), "users": {}}

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("users"), dict):
            return self._empty()
        payload["schema_version"] = WATCHLIST_SCHEMA_VERSION
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = WATCHLIST_SCHEMA_VERSION
        payload["updated_at"] = _now_iso()
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(_json_safe(payload), stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _mutate(self, callback):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            try:
                self.lock_path.chmod(0o600)
            except OSError:
                pass
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._read_unlocked()
                before_users = deepcopy(payload.get("users") or {})
                result = callback(payload)
                changed_at = _now_iso()
                users = payload.get("users") if isinstance(payload.get("users"), dict) else {}
                for user_id, user in users.items():
                    if not isinstance(user, dict):
                        continue
                    previous = before_users.get(user_id) if isinstance(before_users.get(user_id), dict) else {}
                    before_semantic = _watchlist_sync_revision_semantic(previous)
                    after_semantic = _watchlist_sync_revision_semantic(user)
                    if before_semantic != after_semantic:
                        user["revision"] = max(0, int(previous.get("revision") or 0)) + 1
                        user["updated_at"] = changed_at
                if isinstance(result, dict) and result.pop("_include_revision", False):
                    revision_user = normalize_watchlist_user(result.pop("_revision_user", "local_user"))
                    revision_row = users.get(revision_user) if isinstance(users.get(revision_user), dict) else {}
                    result["revision"] = max(0, int(revision_row.get("revision") or 0))
                self._write_unlocked(payload)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _user(payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        users = payload.setdefault("users", {})
        user = users.setdefault(user_id, {"active_list": "Principal", "lists": {}})
        user.setdefault("active_list", "Principal")
        user.setdefault("lists", {})
        user.setdefault("alerts", [])
        user.setdefault("opportunity_archive", [])
        user.setdefault("revision", 0)
        user.setdefault("updated_at", "")
        user["lists"].setdefault("Principal", {"created_at": _now_iso(), "items": []})
        return user

    def snapshot(self, user_id: Any) -> dict[str, Any]:
        user_key = normalize_watchlist_user(user_id)
        payload = self._read_unlocked()
        user = self._user(payload, user_key)
        return {
            "user_id": user_key,
            "active_list": str(user.get("active_list") or "Principal"),
            "lists": _json_safe(deepcopy(user.get("lists") or {})),
            "alerts": _json_safe(deepcopy(user.get("alerts") or [])),
            "opportunity_archive": _json_safe(deepcopy(user.get("opportunity_archive") or [])),
            "updated_at": str(payload.get("updated_at") or ""),
            "revision": max(0, int(user.get("revision") or 0)),
            "user_updated_at": str(user.get("updated_at") or ""),
            "source": str(self.path),
        }

    def replace_user_snapshot(
        self,
        user_id: Any,
        snapshot: dict[str, Any],
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        """Replace one user's syncable state only when its revision still matches."""
        user_key = normalize_watchlist_user(user_id)
        incoming = snapshot if isinstance(snapshot, dict) else {}

        def apply(payload):
            current = self._user(payload, user_key)
            revision = max(0, int(current.get("revision") or 0))
            if revision != max(0, int(expected_revision)):
                return {
                    "updated": False,
                    "conflict": True,
                    "expected_revision": max(0, int(expected_revision)),
                    "current_revision": revision,
                }
            lists: dict[str, dict[str, Any]] = {}
            raw_lists = incoming.get("lists") if isinstance(incoming.get("lists"), dict) else {}
            for raw_name, raw_list in list(raw_lists.items())[:32]:
                name = normalize_watchlist_name(raw_name)
                source_list = raw_list if isinstance(raw_list, dict) else {}
                existing_list = current.get("lists", {}).get(name) if isinstance(current.get("lists"), dict) else {}
                if source_list.get("system_managed") or (
                    isinstance(existing_list, dict) and existing_list.get("system_managed")
                ):
                    continue
                items: list[dict[str, Any]] = []
                for raw_item in list(source_list.get("items") or [])[:500]:
                    if not isinstance(raw_item, dict):
                        continue
                    symbol = normalize_watchlist_symbol(raw_item.get("symbol"))
                    if not symbol:
                        continue
                    clean_item = deepcopy(raw_item)
                    clean_item["symbol"] = symbol
                    clean_item["market"] = normalize_watchlist_market(raw_item.get("market"), symbol)
                    items.append(clean_item)
                lists[name] = {
                    **{key: deepcopy(value) for key, value in source_list.items() if key != "items"},
                    "items": items,
                }
            lists.setdefault("Principal", {"created_at": _now_iso(), "items": []})
            for name, existing_list in (current.get("lists") or {}).items():
                if isinstance(existing_list, dict) and existing_list.get("system_managed"):
                    lists[normalize_watchlist_name(name)] = deepcopy(existing_list)
            current_alerts = {
                str(row.get("id") or ""): row
                for row in current.get("alerts", [])
                if isinstance(row, dict) and row.get("id")
            }
            autonomous_alert_fields = (
                "status", "triggered_at", "expired_at", "last_evaluated_at", "last_price",
                "last_previous_fast", "last_previous_slow", "last_current_fast", "last_current_slow",
                "last_relative_volume", "indicator_engine", "monitor_status", "monitor_detail",
                "last_monitor_at", "last_source", "last_freshness", "notification_status",
                "notification_attempts", "last_notification_attempt_at", "notification_detail",
                "notification_channels", "notified_at",
            )
            alerts: list[dict[str, Any]] = []
            for raw_alert in list(incoming.get("alerts") or [])[:500]:
                if not isinstance(raw_alert, dict):
                    continue
                clean_alert = deepcopy(raw_alert)
                alert_id = str(clean_alert.get("id") or "")[:64]
                symbol = normalize_watchlist_symbol(clean_alert.get("symbol"))
                alert_type = str(clean_alert.get("type") or "")
                if not alert_id or not symbol or alert_type not in ALERT_TYPES:
                    continue
                clean_alert["id"] = alert_id
                clean_alert["symbol"] = symbol
                clean_alert["market"] = normalize_watchlist_market(clean_alert.get("market"), symbol)
                existing = current_alerts.get(alert_id)
                if isinstance(existing, dict):
                    requested_archive = clean_alert.get("status") == "Archivada"
                    for field in autonomous_alert_fields:
                        if field in existing:
                            clean_alert[field] = deepcopy(existing[field])
                        else:
                            clean_alert.pop(field, None)
                    if requested_archive and existing.get("status") != "Archivada":
                        clean_alert["status"] = "Archivada"
                        clean_alert["archived_at"] = _now_iso()
                    if existing.get("expires_at"):
                        clean_alert["expires_at"] = existing["expires_at"]
                else:
                    # A remote device may add a new authored rule, but it cannot
                    # forge an already-triggered/expired lifecycle state.
                    clean_alert["status"] = "Activa"
                    for field in autonomous_alert_fields:
                        if field != "status":
                            clean_alert.pop(field, None)
                alerts.append(clean_alert)
            payload.setdefault("users", {})[user_key] = {
                "active_list": normalize_watchlist_name(incoming.get("active_list")),
                "lists": lists,
                "alerts": alerts,
                "opportunity_archive": deepcopy(current.get("opportunity_archive") or []),
                "revision": revision,
                "updated_at": str(current.get("updated_at") or ""),
            }
            return {
                "updated": True,
                "conflict": False,
                "_include_revision": True,
                "_revision_user": user_key,
            }

        return self._mutate(apply)

    def user_ids(self) -> list[str]:
        """Return durable watchlist users without creating synthetic accounts."""
        payload = self._read_unlocked()
        users = payload.get("users") if isinstance(payload.get("users"), dict) else {}
        return sorted(normalize_watchlist_user(user_id) for user_id in users)

    def alerts_snapshot(self, user_id: Any, *, include_archived: bool = False) -> list[dict[str, Any]]:
        user_key = normalize_watchlist_user(user_id)
        payload = self._read_unlocked()
        user = self._user(payload, user_key)
        rows = [dict(item) for item in user.get("alerts", []) if isinstance(item, dict)]
        if not include_archived:
            rows = [item for item in rows if item.get("status") != "Archivada"]
        return sorted(rows, key=lambda item: str(item.get("created_at") or ""), reverse=True)

    def active_alert_inventory(self) -> list[dict[str, Any]]:
        """Return active durable rules across users for the background monitor."""
        payload = self._read_unlocked()
        users = payload.get("users") if isinstance(payload.get("users"), dict) else {}
        rows: list[dict[str, Any]] = []
        for user_id, user in users.items():
            if not isinstance(user, dict):
                continue
            for alert in user.get("alerts", []):
                if not isinstance(alert, dict) or alert.get("status") != "Activa":
                    continue
                rows.append({**dict(alert), "user_id": normalize_watchlist_user(user_id)})
        return sorted(rows, key=lambda item: (str(item.get("symbol") or ""), str(item.get("created_at") or "")))

    def expire_due_alerts(self, *, now: datetime | None = None) -> int:
        """Expire active rules whose explicit UTC lifetime has elapsed."""

        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)

        def apply(payload):
            expired = 0
            users = payload.get("users") if isinstance(payload.get("users"), dict) else {}
            for user in users.values():
                if not isinstance(user, dict):
                    continue
                for alert in user.get("alerts", []):
                    if not isinstance(alert, dict) or alert.get("status") != "Activa":
                        continue
                    expires_at = _utc_datetime(alert.get("expires_at"))
                    if expires_at is None or expires_at > current:
                        continue
                    alert["status"] = "Expirada"
                    alert["expired_at"] = current.isoformat()
                    alert["monitor_status"] = "EXPIRADA"
                    alert["monitor_detail"] = "La vigencia configurada termino sin activarse."
                    alert["last_monitor_at"] = current.isoformat()
                    expired += 1
            return expired

        return int(self._mutate(apply))

    def pending_notification_inventory(self, *, max_attempts: int = 10) -> list[dict[str, Any]]:
        """Return triggered alerts whose durable delivery has not succeeded."""
        payload = self._read_unlocked()
        users = payload.get("users") if isinstance(payload.get("users"), dict) else {}
        rows: list[dict[str, Any]] = []
        for user_id, user in users.items():
            if not isinstance(user, dict):
                continue
            for alert in user.get("alerts", []):
                if not isinstance(alert, dict) or alert.get("status") != "Activada":
                    continue
                delivery = str(alert.get("notification_status") or "").upper()
                try:
                    attempts = max(0, int(alert.get("notification_attempts") or 0))
                except (TypeError, ValueError):
                    attempts = 0
                if delivery not in {"PENDING", "RETRY_PENDING"} or attempts >= max(1, int(max_attempts)):
                    continue
                rows.append({**dict(alert), "user_id": normalize_watchlist_user(user_id)})
        return sorted(rows, key=lambda row: str(row.get("triggered_at") or ""))

    def alert_notification_status_counts(self) -> dict[str, int]:
        payload = self._read_unlocked()
        users = payload.get("users") if isinstance(payload.get("users"), dict) else {}
        counts: dict[str, int] = {}
        for user in users.values():
            if not isinstance(user, dict):
                continue
            for alert in user.get("alerts", []):
                if not isinstance(alert, dict) or alert.get("status") != "Activada":
                    continue
                status = str(alert.get("notification_status") or "LEGACY_UNKNOWN").upper()
                counts[status] = counts.get(status, 0) + 1
        return counts

    def record_alert_notification_state(
        self,
        user_id: Any,
        alert_id: Any,
        *,
        delivered: bool,
        detail: str,
        channels: list[Any] | None = None,
        max_attempts: int = 10,
    ) -> dict[str, Any]:
        """Persist delivery success/failure so failed notifications can retry."""
        user_key = normalize_watchlist_user(user_id)
        clean_id = str(alert_id or "").strip()

        def apply(payload):
            user = self._user(payload, user_key)
            for alert in user.setdefault("alerts", []):
                if not isinstance(alert, dict) or str(alert.get("id") or "") != clean_id:
                    continue
                try:
                    attempts = max(0, int(alert.get("notification_attempts") or 0)) + 1
                except (TypeError, ValueError):
                    attempts = 1
                alert["notification_attempts"] = attempts
                alert["last_notification_attempt_at"] = _now_iso()
                alert["notification_detail"] = str(detail or "")[:240]
                alert["notification_channels"] = [str(item)[:32] for item in list(channels or [])[:12]]
                alert["notification_status"] = (
                    "DELIVERED" if delivered else "DELIVERY_FAILED" if attempts >= max_attempts else "RETRY_PENDING"
                )
                if delivered:
                    alert["notified_at"] = alert["last_notification_attempt_at"]
                return {"updated": True, "alert": dict(alert)}
            return {"updated": False, "reason": "not_found"}

        return self._mutate(apply)

    def record_alert_monitor_state(
        self,
        user_id: Any,
        *,
        symbol: Any,
        market: Any,
        status: str,
        detail: str,
        source: str = "",
        freshness: str = "",
        alert_id: str = "",
    ) -> int:
        """Persist an honest monitor state without changing the alert lifecycle."""
        user_key = normalize_watchlist_user(user_id)
        clean_symbol = normalize_watchlist_symbol(symbol)
        clean_market = normalize_watchlist_market(market, clean_symbol)

        def apply(payload):
            user = self._user(payload, user_key)
            updated = 0
            observed_at = _now_iso()
            for alert in user.setdefault("alerts", []):
                if not isinstance(alert, dict) or alert.get("status") != "Activa":
                    continue
                if (
                    normalize_watchlist_symbol(alert.get("symbol")) != clean_symbol
                    or normalize_watchlist_market(alert.get("market"), clean_symbol) != clean_market
                ):
                    continue
                if alert_id and str(alert.get("id") or "") != str(alert_id):
                    continue
                alert["monitor_status"] = str(status or "")[:32]
                alert["monitor_detail"] = str(detail or "")[:240]
                alert["last_monitor_at"] = observed_at
                alert["last_source"] = str(source or "")[:64]
                alert["last_freshness"] = str(freshness or "")[:48]
                updated += 1
            return updated

        return int(self._mutate(apply))

    def opportunity_archive_snapshot(self, user_id: Any) -> list[dict[str, Any]]:
        user_key = normalize_watchlist_user(user_id)
        payload = self._read_unlocked()
        user = self._user(payload, user_key)
        rows = [dict(item) for item in user.get("opportunity_archive", []) if isinstance(item, dict)]
        return sorted(rows, key=lambda item: str(item.get("archived_at") or ""), reverse=True)

    def archive_operational_opportunity_events(
        self,
        user_id: Any,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        user_key = normalize_watchlist_user(user_id)
        events = [dict(row) for row in rows if isinstance(row, dict) and normalize_watchlist_symbol(row.get("symbol"))]

        def apply(payload):
            user = self._user(payload, user_key)
            archive = user.setdefault("opportunity_archive", [])
            added = 0
            updated = 0
            for event in events:
                symbol = normalize_watchlist_symbol(event.get("symbol"))
                market = normalize_watchlist_market(event.get("market"), symbol)
                reason = str(event.get("archive_reason") or "Candidato invalidado por el motor operativo.")[:500]
                existing = next(
                    (
                        item
                        for item in reversed(archive)
                        if isinstance(item, dict)
                        and normalize_watchlist_symbol(item.get("symbol")) == symbol
                        and normalize_watchlist_market(item.get("market"), symbol) == market
                        and item.get("status") == "Invalidada"
                        and str(item.get("archive_reason") or "") == reason
                    ),
                    None,
                )
                clean = {
                    **event,
                    "symbol": symbol,
                    "market": market,
                    "status": "Invalidada",
                    "archive_reason": reason,
                    "archived_at": str(event.get("archived_at") or _now_iso()),
                }
                if existing is not None:
                    existing.update(clean)
                    existing["last_observed_at"] = _now_iso()
                    updated += 1
                else:
                    archive.append(clean)
                    added += 1
            return {"archived": added, "updated": updated}

        return self._mutate(apply)

    def create_price_alert(
        self,
        user_id: Any,
        *,
        symbol: Any,
        market: Any,
        alert_type: str,
        threshold: Any,
        timeframe: str = "1h",
        watchlist_name: str = "Principal",
        source: str = "manual",
        ttl_hours: int = 720,
    ) -> dict[str, Any]:
        user_key = normalize_watchlist_user(user_id)
        clean_symbol = normalize_watchlist_symbol(symbol)
        clean_market = normalize_watchlist_market(market, clean_symbol)
        clean_type = str(alert_type or "").strip().lower()
        try:
            clean_threshold = float(threshold)
        except (TypeError, ValueError):
            clean_threshold = 0.0
        expires_at = _alert_expiration_iso(ttl_hours)
        if not clean_symbol or clean_type not in PRICE_ALERT_TYPES or clean_threshold <= 0 or not expires_at:
            return {"created": False, "reason": "invalid_alert"}

        def apply(payload):
            user = self._user(payload, user_key)
            alerts = user.setdefault("alerts", [])
            for existing in alerts:
                if not isinstance(existing, dict) or existing.get("status") not in ALERT_ACTIVE_STATES:
                    continue
                if (
                    normalize_watchlist_symbol(existing.get("symbol")) == clean_symbol
                    and str(existing.get("type")) == clean_type
                    and float(existing.get("threshold") or 0) == clean_threshold
                ):
                    return {"created": False, "reason": "duplicate", "alert": dict(existing)}
            record = {
                "id": secrets.token_hex(10),
                "symbol": clean_symbol,
                "market": clean_market,
                "type": clean_type,
                "threshold": clean_threshold,
                "timeframe": str(timeframe or "1h")[:12],
                "watchlist_name": normalize_watchlist_name(watchlist_name),
                "status": "Activa",
                "source": str(source or "manual")[:48],
                "created_at": _now_iso(),
                "expires_at": expires_at,
                "last_evaluated_at": "",
                "triggered_at": "",
            }
            alerts.append(record)
            return {"created": True, "alert": dict(record)}

        return self._mutate(apply)

    def create_technical_alert(
        self,
        user_id: Any,
        *,
        symbol: Any,
        market: Any,
        alert_type: str,
        timeframe: str = "15m",
        threshold: Any = 1.5,
        fast_period: int = 9,
        slow_period: int = 21,
        watchlist_name: str = "Principal",
        source: str = "manual",
        ttl_hours: int = 168,
    ) -> dict[str, Any]:
        user_key = normalize_watchlist_user(user_id)
        clean_symbol = normalize_watchlist_symbol(symbol)
        clean_market = normalize_watchlist_market(market, clean_symbol)
        clean_type = str(alert_type or "").strip().lower()
        clean_timeframe = str(timeframe or "15m")[:12]
        try:
            clean_threshold = float(threshold)
            clean_fast = int(fast_period)
            clean_slow = int(slow_period)
        except (TypeError, ValueError):
            return {"created": False, "reason": "invalid_alert"}
        expires_at = _alert_expiration_iso(ttl_hours)
        valid_cross = clean_type in {"ema_cross_above", "ema_cross_below"} and (
            2 <= clean_fast < clean_slow <= 400
        )
        valid_volume = clean_type == "relative_volume_above" and 0.1 <= clean_threshold <= 100
        if not clean_symbol or not expires_at or not (valid_cross or valid_volume):
            return {"created": False, "reason": "invalid_alert"}

        def apply(payload):
            user = self._user(payload, user_key)
            alerts = user.setdefault("alerts", [])
            effective_threshold = clean_threshold if clean_type == "relative_volume_above" else 0.0
            signature = (clean_symbol, clean_type, clean_timeframe, effective_threshold, clean_fast, clean_slow)
            for existing in alerts:
                if not isinstance(existing, dict) or existing.get("status") not in ALERT_ACTIVE_STATES:
                    continue
                try:
                    existing_signature = (
                        normalize_watchlist_symbol(existing.get("symbol")),
                        str(existing.get("type") or ""),
                        str(existing.get("timeframe") or ""),
                        float(existing.get("threshold") or 0),
                        int(existing.get("fast_period") or 9),
                        int(existing.get("slow_period") or 21),
                    )
                except (TypeError, ValueError):
                    # A malformed legacy record must not prevent creation of a
                    # valid durable rule or crash the whole user state mutation.
                    continue
                if existing_signature == signature:
                    return {"created": False, "reason": "duplicate", "alert": dict(existing)}
            record = {
                "id": secrets.token_hex(10),
                "symbol": clean_symbol,
                "market": clean_market,
                "type": clean_type,
                "threshold": effective_threshold,
                "fast_period": clean_fast,
                "slow_period": clean_slow,
                "timeframe": clean_timeframe,
                "watchlist_name": normalize_watchlist_name(watchlist_name),
                "status": "Activa",
                "source": str(source or "manual")[:48],
                "created_at": _now_iso(),
                "expires_at": expires_at,
                "last_evaluated_at": "",
                "triggered_at": "",
            }
            alerts.append(record)
            return {"created": True, "alert": dict(record)}

        return self._mutate(apply)

    def evaluate_alerts(self, user_id: Any, observations: dict[str, Any]) -> list[dict[str, Any]]:
        user_key = normalize_watchlist_user(user_id)
        normalized = {str(key).upper(): value for key, value in dict(observations or {}).items()}

        def apply(payload):
            user = self._user(payload, user_key)
            updated: list[dict[str, Any]] = []
            alerts = user.setdefault("alerts", [])
            for index, alert in enumerate(alerts):
                if not isinstance(alert, dict) or alert.get("status") != "Activa":
                    continue
                symbol = normalize_watchlist_symbol(alert.get("symbol"))
                timeframe = str(alert.get("timeframe") or "1h").upper()
                alert_id = str(alert.get("id") or "").upper()
                observation = normalized.get(alert_id) or normalized.get(f"{symbol}|{timeframe}") or normalized.get(symbol)
                if not isinstance(observation, dict):
                    continue
                evaluated = evaluate_durable_alert(alert, observation)
                if evaluated == alert:
                    # Price-only refreshes must not pretend that an EMA/RVol
                    # rule was evaluated without its candle/indicator inputs.
                    continue
                if evaluated.get("last_evaluated_at"):
                    evaluated["last_source"] = str(observation.get("source") or "")[:64]
                    evaluated["last_freshness"] = str(observation.get("freshness") or "")[:48]
                    evaluated["last_monitor_at"] = evaluated["last_evaluated_at"]
                    evaluated["monitor_status"] = (
                        "ACTIVADA" if evaluated.get("status") == "Activada" else "EVALUADA"
                    )
                    evaluated["monitor_detail"] = (
                        "Regla tecnica activada con velas e indicadores verificables."
                        if evaluated.get("status") == "Activada" and evaluated.get("type") in TECHNICAL_ALERT_TYPES
                        else "Regla activada con precio verificable."
                        if evaluated.get("status") == "Activada"
                        else "Regla evaluada; la condicion aun no se cumplio."
                    )
                alerts[index] = evaluated
                updated.append(dict(evaluated))
            return updated

        return self._mutate(apply)

    def evaluate_price_alerts(self, user_id: Any, prices: dict[str, Any]) -> list[dict[str, Any]]:
        observations = {
            normalize_watchlist_symbol(key): (value if isinstance(value, dict) else {"price": value})
            for key, value in dict(prices or {}).items()
        }
        return self.evaluate_alerts(user_id, observations)

    def archive_alert(self, user_id: Any, alert_id: Any) -> dict[str, Any]:
        user_key = normalize_watchlist_user(user_id)
        clean_id = str(alert_id or "").strip()

        def apply(payload):
            user = self._user(payload, user_key)
            for alert in user.setdefault("alerts", []):
                if isinstance(alert, dict) and str(alert.get("id")) == clean_id:
                    alert["status"] = "Archivada"
                    alert["archived_at"] = _now_iso()
                    return {"archived": True, "alert": dict(alert)}
            return {"archived": False, "reason": "not_found"}

        return self._mutate(apply)

    def sync_operational_opportunities(
        self,
        user_id: Any,
        rows: list[dict[str, Any]],
        *,
        list_name: str = "Roxy Oportunidades",
        source_healthy: bool = False,
    ) -> dict[str, Any]:
        """Replace Roxy's system list only after a healthy source-backed scan.

        A degraded/empty provider response leaves the last known list untouched;
        this avoids treating an outage as proof that every opportunity expired.
        """
        if not source_healthy:
            return {"synced": False, "reason": "source_not_healthy", "count": 0}
        user_key = normalize_watchlist_user(user_id)
        name = normalize_watchlist_name(list_name)
        records: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            record = operational_opportunity_record(row)
            if record is None:
                continue
            key = (record["symbol"], record["market"])
            if key in seen:
                continue
            seen.add(key)
            records.append(record)

        def apply(payload):
            user = self._user(payload, user_key)
            target = user["lists"].setdefault(
                name,
                {"created_at": _now_iso(), "items": [], "system_managed": True},
            )
            previous = {
                (normalize_watchlist_symbol(item.get("symbol")), normalize_watchlist_market(item.get("market"), item.get("symbol"))): item
                for item in target.get("items", [])
                if isinstance(item, dict)
            }
            synced_at = _now_iso()
            items: list[dict[str, Any]] = []
            for record in records:
                key = (record["symbol"], record["market"])
                old = previous.get(key, {})
                items.append(
                    {
                        **record,
                        "added_at": str(old.get("added_at") or synced_at),
                        "synced_at": synced_at,
                    }
                )
            current_keys = {(item["symbol"], item["market"]) for item in items}
            expired = [dict(item) for key, item in previous.items() if key not in current_keys]
            archive = user.setdefault("opportunity_archive", [])
            for item in expired:
                archive.append(
                    {
                        **item,
                        "status": "Expirada",
                        "archived_at": synced_at,
                        "archive_reason": "No presente en el ultimo scan saludable",
                    }
                )
            target["items"] = items
            target["system_managed"] = True
            target["last_source_sync"] = synced_at
            return {"synced": True, "count": len(items), "archived": len(expired), "list_name": name}

        return self._mutate(apply)

    def create_list(self, user_id: Any, name: Any) -> dict[str, Any]:
        user_key = normalize_watchlist_user(user_id)
        list_name = normalize_watchlist_name(name)

        def apply(payload):
            user = self._user(payload, user_key)
            created = list_name not in user["lists"]
            user["lists"].setdefault(list_name, {"created_at": _now_iso(), "items": []})
            user["active_list"] = list_name
            return {"created": created, "name": list_name}

        return self._mutate(apply)

    def add_asset(self, user_id: Any, list_name: Any, symbol: Any, market: Any = "") -> dict[str, Any]:
        user_key = normalize_watchlist_user(user_id)
        name = normalize_watchlist_name(list_name)
        clean_symbol = normalize_watchlist_symbol(symbol)
        if not clean_symbol:
            return {"added": False, "reason": "invalid_symbol"}
        clean_market = normalize_watchlist_market(market, clean_symbol)

        def apply(payload):
            user = self._user(payload, user_key)
            target = user["lists"].setdefault(name, {"created_at": _now_iso(), "items": []})
            if target.get("system_managed"):
                return {
                    "added": False,
                    "reason": "system_managed",
                    "symbol": clean_symbol,
                    "market": clean_market,
                    "list_name": name,
                }
            items = target.setdefault("items", [])
            exists = any(
                normalize_watchlist_symbol(item.get("symbol")) == clean_symbol
                and normalize_watchlist_market(item.get("market"), clean_symbol) == clean_market
                for item in items
                if isinstance(item, dict)
            )
            if not exists:
                items.append({"symbol": clean_symbol, "market": clean_market, "added_at": _now_iso()})
            user["active_list"] = name
            return {"added": not exists, "symbol": clean_symbol, "market": clean_market, "list_name": name}

        return self._mutate(apply)

    def remove_asset(self, user_id: Any, list_name: Any, symbol: Any, market: Any = "") -> dict[str, Any]:
        user_key = normalize_watchlist_user(user_id)
        name = normalize_watchlist_name(list_name)
        clean_symbol = normalize_watchlist_symbol(symbol)
        clean_market = normalize_watchlist_market(market, clean_symbol)

        def apply(payload):
            user = self._user(payload, user_key)
            target = user["lists"].setdefault(name, {"created_at": _now_iso(), "items": []})
            if target.get("system_managed"):
                return {
                    "removed": False,
                    "reason": "system_managed",
                    "symbol": clean_symbol,
                    "list_name": name,
                }
            before = list(target.setdefault("items", []))
            target["items"] = [
                item
                for item in before
                if not (
                    isinstance(item, dict)
                    and normalize_watchlist_symbol(item.get("symbol")) == clean_symbol
                    and normalize_watchlist_market(item.get("market"), clean_symbol) == clean_market
                )
            ]
            return {"removed": len(target["items"]) < len(before), "symbol": clean_symbol, "list_name": name}

        return self._mutate(apply)
