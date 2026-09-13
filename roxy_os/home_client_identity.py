"""Home-only client identity for abuse-limit buckets, never authentication.

``render_cf`` is an explicit deployment trust decision: public requests enter
through Render/Cloudflare, which overwrites CF-Connecting-IP, and administrators
and services able to reach the workspace's private network are trusted. Host and
Render metadata checks prevent accidental use elsewhere; they do not attest that
a private-network caller traversed Cloudflare. This does not grant account access
or replace CAPTCHA, durable admission caps, or authenticated member isolation.

Uvicorn proxy trust is unchanged. No X-Forwarded-* header is trusted here. The
returned identity is for internal hashing/counting; do not log it or expose it.
See https://render.com/articles/host-pocketbase-on-render and
https://render.com/docs/private-network for the deployment boundary.
"""
from __future__ import annotations

import ipaddress
import os
import re
from urllib.parse import urlsplit

from starlette.requests import Request


class HomeClientIdentityError(RuntimeError):
    """Fail closed without disclosing configuration, headers, or IP addresses."""

    def __init__(self) -> None:
        super().__init__("No se pudo verificar la conexión de Roxy Home.")


class HomeClientIdentityConfigError(HomeClientIdentityError):
    """The explicitly selected deployment mode is not valid."""


class HomeClientIdentityHeaderError(HomeClientIdentityError):
    """The request does not satisfy the configured ingress contract."""


def _canonical_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    # Scoped IPv6 is not a globally routable visitor identity. ip_address itself
    # accepts zone suffixes, so reject them before parsing.
    if "%" in value:
        raise ValueError
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def _render_hostname() -> str:
    if os.getenv("RENDER") != "true" or not os.getenv("RENDER_SERVICE_ID", "").strip():
        raise HomeClientIdentityConfigError
    raw = os.getenv("RENDER_EXTERNAL_URL", "")
    # urlsplit silently removes some control characters. Reject them first,
    # along with even empty query/fragment delimiters and non-ASCII host forms.
    if (not raw or not raw.isascii() or "\\" in raw or "?" in raw or "#" in raw
            or any(ord(char) < 32 or ord(char) == 127 or char.isspace() for char in raw)):
        raise HomeClientIdentityConfigError
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname or ""
        if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
                or parsed.port not in {None, 443} or parsed.path not in {"", "/"}
                or not 1 <= len(hostname) <= 253 or "." not in hostname
                or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                           for label in hostname.split("."))
                or parsed.netloc.lower() not in {hostname, hostname + ":443"}):
            raise HomeClientIdentityConfigError
        # Render's external URL must name a DNS host, not an IP literal.
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            return hostname
        raise HomeClientIdentityConfigError
    except ValueError:
        raise HomeClientIdentityConfigError from None


def _single_header(request: Request, name: bytes) -> str:
    values = [value for key, value in request.scope.get("headers", ()) if key.lower() == name]
    if len(values) != 1:
        raise HomeClientIdentityHeaderError
    try:
        return values[0].decode("ascii")
    except UnicodeDecodeError:
        raise HomeClientIdentityHeaderError from None


def client_ip_identity(request: Request) -> str:
    """Return a canonical bucket identity, using socket unless explicitly opted in.

    Socket mode preserves non-IP ASGI test/client names and the existing
    ``unknown`` fallback. Render mode never silently falls back to a proxy IP.
    The incoming Origin header remains the responsibility of CSRF checks.
    """
    mode = os.getenv("ROXY_HOME_CLIENT_IP_SOURCE", "socket")
    if mode == "socket":
        value = request.client.host if request.client else "unknown"
        try:
            return str(_canonical_address(value))
        except ValueError:
            return value
    if mode != "render_cf":
        raise HomeClientIdentityConfigError

    hostname = _render_hostname()
    host = _single_header(request, b"host").lower()
    if host not in {hostname, hostname + ":443"}:
        raise HomeClientIdentityHeaderError
    value = _single_header(request, b"cf-connecting-ip")
    try:
        address = _canonical_address(value)
    except ValueError:
        raise HomeClientIdentityHeaderError from None
    if (not address.is_global or address.is_multicast or address.is_reserved
            or address.is_unspecified or address.is_loopback or address.is_link_local):
        raise HomeClientIdentityHeaderError
    return str(address)
