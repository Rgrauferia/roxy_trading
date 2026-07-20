from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Union

import pandas as pd


MARKET_DATA_CONTRACT_VERSION = "roxy-market-data/1.0.0"
CANDLE_COLUMNS = ("ts", "open", "high", "low", "close", "volume")


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_candle_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    data = frame.copy()
    if "ts" not in data.columns and isinstance(data.index, pd.DatetimeIndex):
        data = data.reset_index().rename(columns={data.index.name or "index": "ts"})
    if not set(CANDLE_COLUMNS).issubset(data.columns):
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    data["ts"] = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    for column in CANDLE_COLUMNS[1:]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["ts", "open", "high", "low", "close"])
    data = data[(data[["open", "high", "low", "close"]] > 0).all(axis=1)]
    data = data[(data["high"] >= data[["open", "close"]].max(axis=1))]
    data = data[(data["low"] <= data[["open", "close"]].min(axis=1))]
    data["volume"] = data["volume"].fillna(0).clip(lower=0)
    return data.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)


def _latency_class(metadata: dict[str, Any]) -> str:
    explicit = _text(metadata.get("latency_class"))
    if explicit:
        return explicit
    mode = _text(metadata.get("mode")).upper()
    if bool(metadata.get("fallback")) or mode == "FALLBACK":
        return "public_fallback"
    if mode in {"BROKER_DATA", "PREMIUM_DATA", "EXCHANGE_API", "STREAMING"}:
        return "provider_native"
    return "unknown"


@dataclass(frozen=True)
class CandleBatch:
    frame: pd.DataFrame
    metadata: dict[str, Any]

    @property
    def available(self) -> bool:
        return not self.frame.empty and self.metadata.get("status") == "OK"


def normalize_candle_batch(
    frame: pd.DataFrame | None,
    *,
    symbol: str,
    market: str,
    timeframe: str,
    metadata: dict[str, Any] | None = None,
    attempts: list[dict[str, Any]] | None = None,
) -> CandleBatch:
    clean = normalize_candle_frame(frame)
    source = dict(metadata or {})
    now = datetime.now(timezone.utc).isoformat()
    last_timestamp = clean["ts"].iloc[-1].isoformat() if not clean.empty else None
    source.update(
        {
            "contract_version": MARKET_DATA_CONTRACT_VERSION,
            "symbol": _text(symbol).upper(),
            "market": _text(market).lower(),
            "timeframe": _text(timeframe).lower(),
            "status": "OK" if not clean.empty else "NO_DATA",
            "row_count": int(len(clean)),
            "last_timestamp": last_timestamp,
            "fetched_at": _text(source.get("fetched_at")) or now,
            "latency_class": _latency_class(source),
            "is_delayed": bool(source.get("is_delayed")) or bool(source.get("fallback")),
            "is_realtime": bool(source.get("is_realtime")) and not bool(source.get("fallback")),
            "attempts": list(attempts or source.get("attempts") or []),
        }
    )
    if not _text(source.get("provider")):
        source["provider"] = "unavailable"
    if not _text(source.get("source")):
        source["source"] = "unavailable"
    if clean.empty:
        source["is_realtime"] = False
    return CandleBatch(frame=clean, metadata=source)


HistoryFetcher = Callable[
    [str, str, int],
    Union[pd.DataFrame, tuple[pd.DataFrame, dict[str, Any]]],
]


@dataclass(order=True)
class HistoryProvider:
    priority: int
    provider_id: str = field(compare=False)
    market: str = field(compare=False)
    fetcher: HistoryFetcher = field(compare=False)
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)


class MarketDataGateway:
    """Provider chain with one normalized, provenance-preserving candle contract."""

    def __init__(self) -> None:
        self._history: dict[str, list[HistoryProvider]] = {}

    def register_history_provider(
        self,
        *,
        market: str,
        provider_id: str,
        fetcher: HistoryFetcher,
        priority: int = 100,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        key = _text(market).lower()
        provider = HistoryProvider(
            priority=int(priority),
            provider_id=_text(provider_id),
            market=key,
            fetcher=fetcher,
            metadata=dict(metadata or {}),
        )
        self._history.setdefault(key, []).append(provider)
        self._history[key].sort()

    def fetch_history(self, *, symbol: str, market: str, timeframe: str, limit: int = 1000) -> CandleBatch:
        key = _text(market).lower()
        attempts: list[dict[str, Any]] = []
        for provider in self._history.get(key, []):
            try:
                result = provider.fetcher(symbol, timeframe, int(limit))
                if isinstance(result, tuple):
                    frame, dynamic_metadata = result
                else:
                    frame, dynamic_metadata = result, {}
                metadata = {**provider.metadata, **dict(dynamic_metadata or {})}
                metadata.setdefault("provider", provider.provider_id)
                metadata.setdefault("source", provider.provider_id)
                batch = normalize_candle_batch(
                    frame,
                    symbol=symbol,
                    market=key,
                    timeframe=timeframe,
                    metadata=metadata,
                    attempts=attempts,
                )
                attempts.append(
                    {
                        "provider": provider.provider_id,
                        "status": batch.metadata["status"],
                        "rows": batch.metadata["row_count"],
                    }
                )
                if batch.available:
                    batch.metadata["attempts"] = list(attempts)
                    return batch
            except Exception as exc:
                attempts.append(
                    {
                        "provider": provider.provider_id,
                        "status": "ERROR",
                        "detail": f"{type(exc).__name__}: {exc}",
                    }
                )
        return normalize_candle_batch(
            pd.DataFrame(),
            symbol=symbol,
            market=key,
            timeframe=timeframe,
            metadata={
                "provider": "unavailable",
                "source": "unavailable",
                "mode": "NO_DATA",
                "label": "Sin proveedor disponible",
                "detail": "Ningun proveedor registrado entrego velas validas.",
            },
            attempts=attempts,
        )
