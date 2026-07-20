from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import requests


EMAIL_CONTRACT = "roxy-email-readonly/1.1.0"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
OUTLOOK_API_BASE = "https://graph.microsoft.com/v1.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GmailReadonlyClient:
    def __init__(self, token: str | None = None, *, session: Any = None, timeout_seconds: float = 5.0) -> None:
        self.token = str(token if token is not None else os.environ.get("ROXY_GMAIL_ACCESS_TOKEN") or "").strip()
        self.session = session or requests.Session()
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 15.0))

    def _request(self, path: str, *, params: dict[str, Any] | None = None) -> tuple[str, Any, str]:
        if not self.token:
            return "SERVICE_NOT_CONFIGURED", None, "Configura ROXY_GMAIL_ACCESS_TOKEN con alcance gmail.readonly."
        try:
            response = self.session.request(
                "GET",
                f"{GMAIL_API_BASE}{path}",
                headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                params=params or {},
                timeout=self.timeout_seconds,
            )
        except requests.Timeout:
            return "UNAVAILABLE", None, "Gmail excedio el timeout."
        except requests.RequestException as exc:
            return "UNAVAILABLE", None, f"Gmail no responde: {type(exc).__name__}."
        if response.status_code in {401, 403}:
            return "AUTH_INVALID", None, "Gmail rechazo el token o su alcance."
        if response.status_code == 429:
            return "RATE_LIMITED", None, "Gmail alcanzo el limite temporal de peticiones."
        if not 200 <= int(response.status_code) < 300:
            return "ERROR", None, f"Gmail respondio HTTP {int(response.status_code)}."
        try:
            payload = response.json()
        except (TypeError, ValueError):
            return "ERROR", None, "Gmail devolvio una respuesta no JSON."
        return "CONNECTED", payload, "Conexion de solo lectura verificada."

    def status(self) -> dict[str, Any]:
        state, payload, detail = self._request("/profile", params={"fields": "emailAddress,messagesTotal,threadsTotal"})
        profile = payload if isinstance(payload, dict) else {}
        return {
            "contract_version": EMAIL_CONTRACT,
            "provider": "gmail",
            "status": state,
            "connected": state == "CONNECTED",
            "read_only": True,
            "send_enabled": False,
            "checked_at": _now_iso(),
            "detail": detail,
            "account": str(profile.get("emailAddress") or "")[:160],
            "messages_total": int(profile.get("messagesTotal") or 0),
            "threads_total": int(profile.get("threadsTotal") or 0),
        }

    @staticmethod
    def _headers(payload: Any) -> dict[str, str]:
        result: dict[str, str] = {}
        headers = payload.get("headers") if isinstance(payload, dict) else []
        for row in headers if isinstance(headers, list) else []:
            if not isinstance(row, dict):
                continue
            key = str(row.get("name") or "").strip().casefold()
            if key in {"from", "subject", "date"}:
                result[key] = str(row.get("value") or "")[:500]
        return result

    def inbox(self, *, limit: int = 5) -> dict[str, Any]:
        bounded_limit = max(1, min(int(limit), 5))
        state, payload, detail = self._request(
            "/messages",
            params={"maxResults": bounded_limit, "labelIds": "INBOX", "fields": "messages(id,threadId),resultSizeEstimate"},
        )
        if state != "CONNECTED":
            return {
                "contract_version": EMAIL_CONTRACT,
                "provider": "gmail",
                "status": state,
                "detail": detail,
                "read_only": True,
                "send_enabled": False,
                "messages": [],
                "checked_at": _now_iso(),
            }
        references = payload.get("messages") if isinstance(payload, dict) else []
        messages: list[dict[str, Any]] = []
        for reference in references if isinstance(references, list) else []:
            message_id = str(reference.get("id") or "") if isinstance(reference, dict) else ""
            if not message_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", message_id):
                continue
            item_state, item, item_detail = self._request(
                f"/messages/{message_id}",
                params={
                    "format": "metadata",
                    "metadataHeaders": ["From", "Subject", "Date"],
                    "fields": "id,threadId,labelIds,internalDate,payload(headers)",
                },
            )
            if item_state != "CONNECTED" or not isinstance(item, dict):
                return {
                    "contract_version": EMAIL_CONTRACT,
                    "provider": "gmail",
                    "status": item_state,
                    "detail": item_detail,
                    "read_only": True,
                    "send_enabled": False,
                    "messages": messages,
                    "partial": bool(messages),
                    "checked_at": _now_iso(),
                }
            headers = self._headers(item.get("payload"))
            labels = [str(value)[:64] for value in item.get("labelIds", []) if str(value)]
            messages.append({
                "id": str(item.get("id") or message_id)[:128],
                "thread_id": str(item.get("threadId") or reference.get("threadId") or "")[:128],
                "from": headers.get("from", ""),
                "subject": headers.get("subject", "(sin asunto)"),
                "date": headers.get("date", ""),
                "unread": "UNREAD" in labels,
                "labels": labels,
                "body_loaded": False,
            })
        return {
            "contract_version": EMAIL_CONTRACT,
            "provider": "gmail",
            "status": "CONNECTED",
            "detail": detail,
            "read_only": True,
            "send_enabled": False,
            "result_size_estimate": int(payload.get("resultSizeEstimate") or 0) if isinstance(payload, dict) else 0,
            "messages": messages,
            "checked_at": _now_iso(),
        }

    def send(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "SEND_DISABLED",
            "sent": False,
            "detail": "Roxy no envia correo desde este adaptador de solo lectura.",
        }


class OutlookReadonlyClient:
    """Microsoft Graph adapter that never requests message bodies or sends mail."""

    def __init__(self, token: str | None = None, *, session: Any = None, timeout_seconds: float = 5.0) -> None:
        self.token = str(token if token is not None else os.environ.get("ROXY_OUTLOOK_ACCESS_TOKEN") or "").strip()
        self.session = session or requests.Session()
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 15.0))

    def _request(self, path: str, *, params: dict[str, Any] | None = None) -> tuple[str, Any, str]:
        if not self.token:
            return "SERVICE_NOT_CONFIGURED", None, "Configura ROXY_OUTLOOK_ACCESS_TOKEN con alcance Mail.Read."
        if not path.startswith("/") or "://" in path or ".." in path:
            return "ERROR", None, "Ruta Microsoft Graph rechazada por politica."
        try:
            response = self.session.request(
                "GET",
                f"{OUTLOOK_API_BASE}{path}",
                headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                params=params or {},
                timeout=self.timeout_seconds,
            )
        except requests.Timeout:
            return "UNAVAILABLE", None, "Microsoft Graph excedio el timeout."
        except requests.RequestException as exc:
            return "UNAVAILABLE", None, f"Microsoft Graph no responde: {type(exc).__name__}."
        if response.status_code in {401, 403}:
            return "AUTH_INVALID", None, "Microsoft Graph rechazo el token o el alcance Mail.Read."
        if response.status_code == 429:
            return "RATE_LIMITED", None, "Microsoft Graph alcanzo el limite temporal de peticiones."
        if not 200 <= int(response.status_code) < 300:
            return "ERROR", None, f"Microsoft Graph respondio HTTP {int(response.status_code)}."
        try:
            payload = response.json()
        except (TypeError, ValueError):
            return "ERROR", None, "Microsoft Graph devolvio una respuesta no JSON."
        return "CONNECTED", payload, "Conexion Microsoft Graph de solo lectura verificada."

    def status(self) -> dict[str, Any]:
        state, payload, detail = self._request(
            "/me", params={"$select": "displayName,mail,userPrincipalName"}
        )
        profile = payload if isinstance(payload, dict) else {}
        return {
            "contract_version": EMAIL_CONTRACT,
            "provider": "outlook",
            "status": state,
            "connected": state == "CONNECTED",
            "read_only": True,
            "send_enabled": False,
            "checked_at": _now_iso(),
            "detail": detail,
            "account": str(profile.get("mail") or profile.get("userPrincipalName") or "")[:160],
            "display_name": str(profile.get("displayName") or "")[:160],
        }

    def inbox(self, *, limit: int = 5) -> dict[str, Any]:
        bounded_limit = max(1, min(int(limit), 5))
        state, payload, detail = self._request(
            "/me/mailFolders/inbox/messages",
            params={
                "$top": bounded_limit,
                "$select": "id,conversationId,from,subject,receivedDateTime,isRead,categories",
                "$orderby": "receivedDateTime desc",
            },
        )
        if state != "CONNECTED":
            return {
                "contract_version": EMAIL_CONTRACT,
                "provider": "outlook",
                "status": state,
                "detail": detail,
                "read_only": True,
                "send_enabled": False,
                "messages": [],
                "checked_at": _now_iso(),
            }
        values = payload.get("value") if isinstance(payload, dict) else []
        messages: list[dict[str, Any]] = []
        for item in values if isinstance(values, list) else []:
            if not isinstance(item, dict):
                continue
            sender = item.get("from") if isinstance(item.get("from"), dict) else {}
            address = sender.get("emailAddress") if isinstance(sender.get("emailAddress"), dict) else {}
            display = str(address.get("name") or "")[:240]
            email = str(address.get("address") or "")[:240]
            messages.append({
                "id": str(item.get("id") or "")[:256],
                "thread_id": str(item.get("conversationId") or "")[:256],
                "from": f"{display} <{email}>" if display and email else email or display,
                "subject": str(item.get("subject") or "(sin asunto)")[:500],
                "date": str(item.get("receivedDateTime") or "")[:80],
                "unread": not bool(item.get("isRead", True)),
                "labels": [str(value)[:64] for value in item.get("categories", []) if str(value)],
                "body_loaded": False,
            })
        return {
            "contract_version": EMAIL_CONTRACT,
            "provider": "outlook",
            "status": "CONNECTED",
            "detail": detail,
            "read_only": True,
            "send_enabled": False,
            "messages": messages,
            "checked_at": _now_iso(),
        }

    def send(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "SEND_DISABLED",
            "sent": False,
            "detail": "Roxy no envia correo desde este adaptador de solo lectura.",
        }


def configured_email_provider(value: Any = None) -> str:
    provider = str(value if value is not None else os.environ.get("ROXY_EMAIL_PROVIDER") or "gmail").strip().lower()
    return provider if provider in {"gmail", "outlook"} else "gmail"


def readonly_email_client(provider: Any = None, **kwargs: Any) -> GmailReadonlyClient | OutlookReadonlyClient:
    selected = configured_email_provider(provider)
    return OutlookReadonlyClient(**kwargs) if selected == "outlook" else GmailReadonlyClient(**kwargs)
