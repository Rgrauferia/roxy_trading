from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from roxy_paths import output_dir
from roxy_trader.cache_policy import cache_ttl
from roxy_trader.api_budget import observe_api_call


DEFAULT_CACHE_DIR = output_dir() / "asset_identity_cache"
DEFAULT_CACHE_TTL = timedelta(seconds=cache_ttl("asset_identity_disk"))
HTTP_TIMEOUT_SECONDS = 4.0

STOCK_IDENTITIES: dict[str, dict[str, str]] = {
    "AAPL": {"name": "Apple Inc.", "domain": "apple.com", "slug": "apple", "exchange": "NASDAQ", "sector": "Technology", "industry": "Consumer Electronics", "bg": "111827", "color": "ffffff"},
    "NVDA": {"name": "NVIDIA Corporation", "domain": "nvidia.com", "slug": "nvidia", "exchange": "NASDAQ", "sector": "Technology", "industry": "Semiconductors", "bg": "16a34a", "color": "ffffff"},
    "MSFT": {"name": "Microsoft Corporation", "domain": "microsoft.com", "slug": "microsoft", "exchange": "NASDAQ", "sector": "Technology", "industry": "Software", "bg": "111827", "color": "ffffff"},
    "TSLA": {"name": "Tesla, Inc.", "domain": "tesla.com", "slug": "tesla", "exchange": "NASDAQ", "sector": "Consumer Cyclical", "industry": "Auto Manufacturers", "bg": "dc2626", "color": "ffffff"},
    "AMD": {"name": "Advanced Micro Devices, Inc.", "domain": "amd.com", "slug": "amd", "exchange": "NASDAQ", "sector": "Technology", "industry": "Semiconductors", "bg": "111827", "color": "ffffff"},
    "META": {"name": "Meta Platforms, Inc.", "domain": "meta.com", "slug": "meta", "exchange": "NASDAQ", "sector": "Communication Services", "industry": "Internet Content & Information", "bg": "2563eb", "color": "ffffff"},
    "AMZN": {"name": "Amazon.com, Inc.", "domain": "amazon.com", "slug": "amazon", "exchange": "NASDAQ", "sector": "Consumer Cyclical", "industry": "Internet Retail", "bg": "111827", "color": "ffffff"},
    "GOOG": {"name": "Alphabet Inc.", "domain": "abc.xyz", "slug": "google", "exchange": "NASDAQ", "sector": "Communication Services", "industry": "Internet Content & Information", "bg": "111827", "color": "ffffff"},
    "GOOGL": {"name": "Alphabet Inc.", "domain": "abc.xyz", "slug": "google", "exchange": "NASDAQ", "sector": "Communication Services", "industry": "Internet Content & Information", "bg": "111827", "color": "ffffff"},
    "NFLX": {"name": "Netflix, Inc.", "domain": "netflix.com", "slug": "netflix", "exchange": "NASDAQ", "sector": "Communication Services", "industry": "Entertainment", "bg": "b91c1c", "color": "ffffff"},
    "COIN": {"name": "Coinbase Global, Inc.", "domain": "coinbase.com", "slug": "coinbase", "exchange": "NASDAQ", "sector": "Financial Services", "industry": "Financial Data & Exchanges", "bg": "2563eb", "color": "ffffff"},
    "BABA": {"name": "Alibaba Group Holding Limited", "domain": "alibabagroup.com", "slug": "alibabadotcom", "exchange": "NYSE", "sector": "Consumer Cyclical", "industry": "Internet Retail", "bg": "f97316", "color": "ffffff"},
    "JPM": {"name": "JPMorgan Chase & Co.", "domain": "jpmorganchase.com", "slug": "jpmorgan", "exchange": "NYSE", "sector": "Financial Services", "industry": "Banks—Diversified", "bg": "111827", "color": "ffffff"},
    "QQQ": {"name": "Invesco QQQ Trust", "domain": "invesco.com", "slug": "invesco", "exchange": "NASDAQ", "sector": "ETF", "industry": "Large Growth", "bg": "1d4ed8", "color": "ffffff"},
    "SPY": {"name": "SPDR S&P 500 ETF Trust", "domain": "ssga.com", "slug": "spdr", "exchange": "NYSE Arca", "sector": "ETF", "industry": "Large Blend", "bg": "1d4ed8", "color": "ffffff"},
}

CRYPTO_IDENTITIES: dict[str, dict[str, str]] = {
    "BTC": {"name": "Bitcoin", "coingecko_id": "bitcoin", "slug": "bitcoin", "bg": "f7931a", "color": "ffffff"},
    "ETH": {"name": "Ethereum", "coingecko_id": "ethereum", "slug": "ethereum", "bg": "627eea", "color": "ffffff"},
    "SOL": {"name": "Solana", "coingecko_id": "solana", "slug": "solana", "bg": "111827", "color": "14f195"},
    "XRP": {"name": "XRP", "coingecko_id": "ripple", "slug": "xrp", "bg": "111827", "color": "ffffff"},
    "BNB": {"name": "BNB", "coingecko_id": "binancecoin", "slug": "binance", "bg": "f0b90b", "color": "111827"},
    "DOGE": {"name": "Dogecoin", "coingecko_id": "dogecoin", "slug": "dogecoin", "bg": "c2a633", "color": "ffffff"},
    "ADA": {"name": "Cardano", "coingecko_id": "cardano", "slug": "cardano", "bg": "0033ad", "color": "ffffff"},
    "AVAX": {"name": "Avalanche", "coingecko_id": "avalanche-2", "slug": "avalanche", "bg": "e84142", "color": "ffffff"},
    "LTC": {"name": "Litecoin", "coingecko_id": "litecoin", "slug": "litecoin", "bg": "345d9d", "color": "ffffff"},
    "LINK": {"name": "Chainlink", "coingecko_id": "chainlink", "slug": "chainlink", "bg": "2a5ada", "color": "ffffff"},
    "MATIC": {"name": "MATIC (migrated to POL)", "coingecko_id": "matic-network", "slug": "polygon", "logo_url": "https://coin-images.coingecko.com/coins/images/4713/large/polygon.png", "bg": "8247e5", "color": "ffffff"},
    "PEPE": {"name": "Pepe", "coingecko_id": "pepe", "logo_url": "https://coin-images.coingecko.com/coins/images/29850/large/pepe-token.jpeg", "bg": "4c9f38", "color": "ffffff"},
    "RNDR": {"name": "Render", "coingecko_id": "render-token", "slug": "render", "logo_url": "https://coin-images.coingecko.com/coins/images/11636/large/rndr.png", "bg": "111827", "color": "ffffff"},
    "BONK": {"name": "Bonk", "coingecko_id": "bonk", "logo_url": "https://coin-images.coingecko.com/coins/images/28600/large/bonk.jpg", "bg": "f59e0b", "color": "111827"},
    "DOT": {"name": "Polkadot", "coingecko_id": "polkadot", "slug": "polkadot", "logo_url": "https://coin-images.coingecko.com/coins/images/12171/large/polkadot.jpg", "bg": "e6007a", "color": "ffffff"},
    "FET": {"name": "Artificial Superintelligence Alliance", "coingecko_id": "fetch-ai", "logo_url": "https://coin-images.coingecko.com/coins/images/5681/large/ASI.png", "bg": "111827", "color": "ffffff"},
    "FLOKI": {"name": "FLOKI", "coingecko_id": "floki", "logo_url": "https://coin-images.coingecko.com/coins/images/16746/large/PNG_image.png", "bg": "f5a623", "color": "111827"},
    "GLM": {"name": "Golem", "coingecko_id": "golem", "slug": "golem", "logo_url": "https://coin-images.coingecko.com/coins/images/542/large/Golem_Submark_Positive_RGB.png", "bg": "181ea9", "color": "ffffff"},
    "GRT": {"name": "The Graph", "coingecko_id": "the-graph", "slug": "thegraph", "logo_url": "https://coin-images.coingecko.com/coins/images/13397/large/Graph_Token.png", "bg": "6747ed", "color": "ffffff"},
    "NEAR": {"name": "NEAR Protocol", "coingecko_id": "near", "slug": "near", "logo_url": "https://coin-images.coingecko.com/coins/images/10365/large/near.jpg", "bg": "111827", "color": "ffffff"},
    "OCEAN": {"name": "Ocean Protocol", "coingecko_id": "ocean-protocol", "slug": "oceanprotocol", "logo_url": "https://coin-images.coingecko.com/coins/images/3687/large/ocean-protocol-logo.jpg", "bg": "141414", "color": "ffffff"},
    "RLC": {"name": "iExec RLC", "coingecko_id": "iexec-rlc", "logo_url": "https://coin-images.coingecko.com/coins/images/646/large/pL1VuXm.png", "bg": "f5a800", "color": "111827"},
    "SHIB": {"name": "Shiba Inu", "coingecko_id": "shiba-inu", "slug": "shibainu", "logo_url": "https://coin-images.coingecko.com/coins/images/11939/large/shiba.png", "bg": "f97316", "color": "ffffff"},
    "TRAC": {"name": "OriginTrail", "coingecko_id": "origintrail", "logo_url": "https://coin-images.coingecko.com/coins/images/1877/large/TRAC.jpg", "bg": "5b2c83", "color": "ffffff"},
    "WIF": {"name": "dogwifhat", "coingecko_id": "dogwifcoin", "logo_url": "https://coin-images.coingecko.com/coins/images/33566/large/dogwifhat.jpg", "bg": "a16207", "color": "ffffff"},
}

ALLOWED_IMAGE_HOSTS = {
    "assets.coingecko.com",
    "coin-images.coingecko.com",
    "cdn.simpleicons.org",
    "static.finnhub.io",
    "static2.finnhub.io",
    *(item["domain"] for item in STOCK_IDENTITIES.values() if item.get("domain")),
}


@dataclass(frozen=True)
class AssetIdentity:
    symbol: str
    market: str
    name: str
    exchange: str = ""
    sector: str = ""
    industry: str = ""
    domain: str = ""
    logo_source: str = "fallback_generic"
    logo_source_url: str = ""
    logo_data_uri: str = ""
    logo_cached: bool = False
    logo_fallback: bool = True
    updated_at: str = ""
    provider_status: str = "FALLBACK"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_market(market: str, symbol: str) -> str:
    value = str(market or "").strip().lower()
    return "crypto" if value == "crypto" or "/" in str(symbol) else "stock"


def normalize_symbol(symbol: str, market: str = "") -> str:
    value = str(symbol or "").strip().upper().replace("-", "/")
    if normalize_market(market, value) == "crypto":
        if "/" in value:
            return value.split("/", 1)[0]
        for suffix in ("USDT", "USDC", "USD"):
            if value.endswith(suffix) and len(value) > len(suffix):
                return value[: -len(suffix)]
    return re.sub(r"[^A-Z0-9.]", "", value)


def _cache_key(symbol: str, market: str) -> str:
    normalized = normalize_symbol(symbol, market)
    return hashlib.sha256(f"{market}:{normalized}".encode()).hexdigest()[:20]


def _metadata_path(cache_dir: Path, symbol: str, market: str) -> Path:
    return cache_dir / f"{_cache_key(symbol, market)}.json"


def _safe_image_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_IMAGE_HOSTS


def _request_bytes(url: str, *, timeout: float = HTTP_TIMEOUT_SECONDS) -> tuple[bytes, str]:
    if not _safe_image_url(url):
        raise ValueError("image host is not allowlisted")
    request = Request(url, headers={"User-Agent": "RoxyTrading/1.0 asset-identity"})
    with urlopen(request, timeout=timeout) as response:
        data = response.read(1_500_001)
        content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if not data or len(data) > 1_500_000:
        raise ValueError("logo payload empty or too large")
    if content_type not in {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/svg+xml",
        "image/x-icon",
        "image/vnd.microsoft.icon",
    }:
        raise ValueError(f"unsupported logo content type: {content_type}")
    return data, content_type


def _request_json(url: str, *, headers: Mapping[str, str] | None = None, timeout: float = HTTP_TIMEOUT_SECONDS) -> Any:
    request_headers = {"User-Agent": "RoxyTrading/1.0 asset-identity", "Accept": "application/json"}
    request_headers.update(dict(headers or {}))
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(2_000_001).decode("utf-8"))


def _generic_logo_data_uri() -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="14" fill="#0f172a"/>'
        '<path d="M13 43l12-13 9 8 17-20" fill="none" stroke="#7dd3fc" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M43 18h8v8" fill="none" stroke="#7dd3fc" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _data_uri(data: bytes, content_type: str) -> str:
    return f"data:{content_type};base64,{base64.b64encode(data).decode()}"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _load_cached_identity(cache_dir: Path, symbol: str, market: str, ttl: timedelta) -> AssetIdentity | None:
    path = _metadata_path(cache_dir, symbol, market)
    try:
        payload = json.loads(path.read_text())
        updated = datetime.fromisoformat(str(payload.get("updated_at") or "").replace("Z", "+00:00"))
        if utc_now() - updated > ttl:
            return None
        logo_file = cache_dir / str(payload.get("logo_file") or "")
        content_type = str(payload.get("logo_content_type") or "")
        if not logo_file.is_file() or not content_type.startswith("image/"):
            return None
        data = logo_file.read_bytes()
        fields = {key: payload.get(key) for key in AssetIdentity.__dataclass_fields__ if key in payload}
        fields["logo_data_uri"] = _data_uri(data, content_type)
        fields["logo_cached"] = True
        return AssetIdentity(**fields)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _store_identity(cache_dir: Path, identity: AssetIdentity, data: bytes, content_type: str) -> AssetIdentity:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(identity.symbol, identity.market)
    suffix = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
        "image/x-icon": ".ico",
        "image/vnd.microsoft.icon": ".ico",
    }[content_type]
    image_path = cache_dir / f"{key}{suffix}"
    _atomic_write(image_path, data)
    stored = AssetIdentity(**{**asdict(identity), "logo_data_uri": _data_uri(data, content_type), "logo_cached": True})
    payload = {**asdict(stored), "logo_data_uri": "", "logo_file": image_path.name, "logo_content_type": content_type}
    metadata_path = _metadata_path(cache_dir, identity.symbol, identity.market)
    _atomic_write(
        metadata_path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
    )
    return stored


def _profile_value(profile: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(profile.get(key) or "").strip()
        if value and value != "-":
            return value
    return ""


def _finnhub_profile(symbol: str) -> dict[str, Any]:
    token = str(os.getenv("FINNHUB_KEY") or os.getenv("FINNHUB_API_KEY") or "").strip()
    if not token:
        return {}
    query = urlencode({"symbol": symbol, "token": token})
    with observe_api_call("finnhub", "company_profile"):
        payload = _request_json(f"https://finnhub.io/api/v1/stock/profile2?{query}")
    return payload if isinstance(payload, dict) else {}


def _coingecko_profile(base: str) -> dict[str, Any]:
    config = CRYPTO_IDENTITIES.get(base, {})
    coin_id = config.get("coingecko_id")
    if not coin_id:
        return {}
    query = urlencode({"vs_currency": "usd", "ids": coin_id, "per_page": 1, "page": 1})
    with observe_api_call("coingecko", "asset_identity"):
        payload = _request_json(f"https://api.coingecko.com/api/v3/coins/markets?{query}")
    return payload[0] if isinstance(payload, list) and payload and isinstance(payload[0], dict) else {}


def resolve_asset_identity(
    symbol: str,
    market: str = "stock",
    *,
    profile: Mapping[str, Any] | None = None,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    allow_network: bool = True,
    cache_ttl: timedelta = DEFAULT_CACHE_TTL,
) -> AssetIdentity:
    resolved_market = normalize_market(market, symbol)
    normalized = normalize_symbol(symbol, resolved_market)
    cache_root = Path(cache_dir)
    cached = _load_cached_identity(cache_root, normalized, resolved_market, cache_ttl)
    if cached:
        return cached

    static = (CRYPTO_IDENTITIES if resolved_market == "crypto" else STOCK_IDENTITIES).get(normalized, {})
    supplied = dict(profile or {})
    provider_profile: dict[str, Any] = {}
    if allow_network:
        try:
            provider_profile = _coingecko_profile(normalized) if resolved_market == "crypto" else _finnhub_profile(normalized)
        except Exception:
            provider_profile = {}

    name = _profile_value(provider_profile, "name") or _profile_value(supplied, "longName", "shortName", "name") or static.get("name", "") or normalized
    exchange = _profile_value(provider_profile, "exchange") or _profile_value(supplied, "exchange", "fullExchangeName") or static.get("exchange", "")
    sector = _profile_value(supplied, "sector") or static.get("sector", "")
    industry = _profile_value(provider_profile, "finnhubIndustry") or _profile_value(supplied, "industry") or static.get("industry", "")
    website = _profile_value(provider_profile, "weburl") or _profile_value(supplied, "website")
    domain = (urlparse(website).hostname or "").removeprefix("www.") if website else static.get("domain", "")
    provider_logo_url = _profile_value(provider_profile, "image", "logo") or static.get("logo_url", "")
    logo_candidates: list[tuple[str, str]] = []
    if provider_logo_url:
        logo_candidates.append(("coingecko" if resolved_market == "crypto" else "finnhub", provider_logo_url))
    if static.get("slug"):
        logo_candidates.append(
            ("simple_icons", f"https://cdn.simpleicons.org/{static['slug']}/{static.get('color', 'ffffff')}")
        )
    if resolved_market == "stock" and domain:
        logo_candidates.append(("official_domain", f"https://{domain}/favicon.ico"))

    now = utc_now().isoformat()
    if allow_network:
        for logo_source, logo_url in logo_candidates:
            try:
                data, content_type = _request_bytes(logo_url)
                identity = AssetIdentity(
                    symbol=normalized,
                    market=resolved_market,
                    name=name,
                    exchange=exchange,
                    sector=sector,
                    industry=industry,
                    domain=domain,
                    logo_source=logo_source,
                    logo_source_url=logo_url,
                    logo_fallback=False,
                    updated_at=now,
                    provider_status="CONNECTED",
                )
                return _store_identity(cache_root, identity, data, content_type)
            except Exception:
                continue

    return AssetIdentity(
        symbol=normalized,
        market=resolved_market,
        name=name,
        exchange=exchange,
        sector=sector,
        industry=industry,
        domain=domain,
        logo_source="fallback_generic",
        logo_data_uri=_generic_logo_data_uri(),
        logo_cached=False,
        logo_fallback=True,
        updated_at=now,
        provider_status="NOT_CONFIGURED" if resolved_market == "stock" and not os.getenv("FINNHUB_KEY") and not os.getenv("FINNHUB_API_KEY") else "DEGRADED",
    )


def identity_status(identity: AssetIdentity) -> dict[str, Any]:
    return {
        "symbol": identity.symbol,
        "market": identity.market,
        "name": identity.name,
        "exchange": identity.exchange,
        "sector": identity.sector,
        "industry": identity.industry,
        "logo_source": identity.logo_source,
        "logo_cached": identity.logo_cached,
        "logo_fallback": identity.logo_fallback,
        "provider_status": identity.provider_status,
        "updated_at": identity.updated_at,
    }
