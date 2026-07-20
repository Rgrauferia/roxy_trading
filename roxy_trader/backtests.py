from __future__ import annotations

import json
import hashlib
import math
import os
import re
import tempfile
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ma_backtester import BACKTEST_ENGINE_VERSION, MovingAverageBacktestConfig, run_ma_backtest
from moving_average_strategy import MovingAverageConfig
from roxy_trader.market_data import normalize_candle_batch

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


BACKTEST_STORE_SCHEMA_VERSION = 1
BACKTEST_STRATEGY_VERSION = "sma-20-40-100-200/1.0.0"
DEFAULT_BACKTEST_PATH = Path(os.environ.get("ROXY_BACKTEST_PATH", "data/roxy_backtests.json"))
MAX_RUNS_PER_USER = 100
BACKTEST_VALIDATION_VERSION = "roxy-backtest-validation/1.0.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_user(value: Any) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_.@-]+", "_", str(value or "local_user").strip().lower()).strip("_")
    return clean[:96] or "local_user"


def _clean_symbol(value: Any) -> str:
    return re.sub(r"[^A-Z0-9./_-]+", "", str(value or "").strip().upper())[:32]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is pd.NA:
        return None
    return value


def _profit_factor_for_trades(trades: list[dict[str, Any]]) -> float:
    gross_profit = sum(float(item.get("pnl") or 0.0) for item in trades if float(item.get("pnl") or 0.0) > 0)
    gross_loss = abs(sum(float(item.get("pnl") or 0.0) for item in trades if float(item.get("pnl") or 0.0) < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _equity_slice_metrics(points: list[dict[str, Any]], *, annualization_periods: float) -> dict[str, Any]:
    values = pd.Series(
        [float(item.get("equity")) for item in points if _json_safe(item.get("equity")) is not None],
        dtype="float64",
    )
    if len(values) < 2 or float(values.iloc[0]) <= 0:
        return {"bars": int(len(values)), "return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe": 0.0}
    running_peak = values.cummax().replace(0, pd.NA)
    drawdown = ((running_peak - values) / running_peak).fillna(0.0)
    returns = values.pct_change().dropna()
    deviation = float(returns.std(ddof=1)) if len(returns) >= 2 else 0.0
    sharpe = (
        float((returns.mean() / deviation) * math.sqrt(max(1.0, annualization_periods)))
        if deviation > 0
        else 0.0
    )
    return {
        "bars": int(len(values)),
        "return_pct": float(values.iloc[-1] / values.iloc[0] - 1.0),
        "max_drawdown_pct": float(drawdown.max()),
        "sharpe": sharpe,
    }


def _time_split_validation(
    *,
    frame: pd.DataFrame,
    trades: list[dict[str, Any]],
    equity_curve: list[dict[str, Any]],
    warmup: int,
    annualization_periods: float,
    split_ratio: float = 0.70,
) -> dict[str, Any]:
    minimum_rows = max(450, int(warmup) + 120)
    if len(frame) < minimum_rows or "ts" not in frame.columns:
        return {
            "version": BACKTEST_VALIDATION_VERSION,
            "status": "DATA_INSUFFICIENT",
            "reason": f"Se requieren al menos {minimum_rows} velas para separar muestra 70/30; se recibieron {len(frame)}.",
            "split_ratio": split_ratio,
        }
    split_index = max(int(warmup) + 1, min(len(frame) - 60, int(len(frame) * split_ratio)))
    split_ts = pd.to_datetime(frame["ts"].iloc[split_index], utc=True, errors="coerce")
    if pd.isna(split_ts):
        return {
            "version": BACKTEST_VALIDATION_VERSION,
            "status": "ERROR",
            "reason": "La vela de corte no tiene timestamp válido.",
            "split_ratio": split_ratio,
        }
    in_trades = [item for item in trades if int(item.get("exit_index") or 0) < split_index]
    out_trades = [item for item in trades if int(item.get("entry_index") or 0) >= split_index]
    crossing = [
        item
        for item in trades
        if int(item.get("entry_index") or 0) < split_index <= int(item.get("exit_index") or 0)
    ]
    in_points: list[dict[str, Any]] = []
    out_points: list[dict[str, Any]] = []
    for item in equity_curve:
        item_ts = pd.to_datetime(item.get("ts"), utc=True, errors="coerce")
        if pd.isna(item_ts):
            continue
        (in_points if item_ts < split_ts else out_points).append(item)

    def segment(points: list[dict[str, Any]], segment_trades: list[dict[str, Any]]) -> dict[str, Any]:
        metrics = _equity_slice_metrics(points, annualization_periods=annualization_periods)
        wins = sum(float(item.get("pnl") or 0.0) > 0 for item in segment_trades)
        profit_factor = _profit_factor_for_trades(segment_trades)
        metrics.update(
            {
                "trades": len(segment_trades),
                "wins": wins,
                "win_rate": wins / len(segment_trades) if segment_trades else 0.0,
                "profit_factor": profit_factor,
                "profit_factor_unbounded": math.isinf(profit_factor),
                "total_pnl": sum(float(item.get("pnl") or 0.0) for item in segment_trades),
            }
        )
        return metrics

    in_sample = segment(in_points, in_trades)
    out_sample = segment(out_points, out_trades)
    return {
        "version": BACKTEST_VALIDATION_VERSION,
        "status": "AVAILABLE" if out_sample["bars"] >= 30 else "DATA_INSUFFICIENT",
        "method": "anchored_time_split_no_refit",
        "split_ratio": split_ratio,
        "split_index": split_index,
        "split_candle": split_ts.isoformat(),
        "cross_boundary_trades_excluded": len(crossing),
        "in_sample": in_sample,
        "out_of_sample": out_sample,
        "generalization_gap_return_pct": in_sample["return_pct"] - out_sample["return_pct"],
    }


def run_moving_average_backtest(
    frame: pd.DataFrame | None,
    *,
    symbol: str,
    market: str,
    timeframe: str,
    source_metadata: dict[str, Any] | None = None,
    backtest_config: MovingAverageBacktestConfig | None = None,
    strategy_config: MovingAverageConfig | None = None,
) -> dict[str, Any]:
    """Run the canonical MA engine and return a provenance-complete durable record."""
    clean_symbol = _clean_symbol(symbol)
    clean_market = "crypto" if str(market).lower() == "crypto" or "/" in clean_symbol else "stock"
    clean_timeframe = str(timeframe or "1h").strip().lower()
    cfg = backtest_config or MovingAverageBacktestConfig()
    strategy_cfg = strategy_config or MovingAverageConfig()
    batch = normalize_candle_batch(
        frame,
        symbol=clean_symbol,
        market=clean_market,
        timeframe=clean_timeframe,
        metadata=dict(source_metadata or {}),
    )
    run_at = _now_iso()
    config_payload = {
        "backtest": asdict(cfg),
        "strategy": asdict(strategy_cfg),
    }
    hash_frame = batch.frame[[column for column in ("ts", "open", "high", "low", "close", "volume") if column in batch.frame.columns]]
    contract_payload = {
        "symbol": clean_symbol,
        "market": clean_market,
        "timeframe": clean_timeframe,
        "engine_version": BACKTEST_ENGINE_VERSION,
        "strategy_version": BACKTEST_STRATEGY_VERSION,
        "config": config_payload,
    }
    hash_material = hash_frame.to_csv(index=False) + json.dumps(
        contract_payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    input_contract_hash = hashlib.sha256(hash_material.encode("utf-8")).hexdigest()
    base = {
        "id": uuid.uuid4().hex,
        "status": "DATA_INSUFFICIENT",
        "run_at": run_at,
        "symbol": clean_symbol,
        "market": clean_market,
        "timeframe": clean_timeframe,
        "engine_version": BACKTEST_ENGINE_VERSION,
        "strategy_version": BACKTEST_STRATEGY_VERSION,
        "strategy": "SMA 20/40/100/200",
        "config": config_payload,
        "input_contract_hash": input_contract_hash,
        "source": _json_safe(batch.metadata),
        "row_count": int(len(batch.frame)),
        "first_candle": batch.frame["ts"].iloc[0].isoformat() if not batch.frame.empty else None,
        "last_candle": batch.frame["ts"].iloc[-1].isoformat() if not batch.frame.empty else None,
        "metrics": {},
        "trades": [],
        "equity_curve": [],
        "validation": {},
        "reason": "",
    }
    if not batch.available:
        base["reason"] = "El proveedor no entregó velas OHLC válidas."
        return base
    minimum_rows = max(200, int(cfg.warmup)) + 1
    if len(batch.frame) < minimum_rows:
        base["reason"] = f"Se requieren al menos {minimum_rows} velas; se recibieron {len(batch.frame)}."
        return base
    try:
        result = run_ma_backtest(
            batch.frame,
            symbol=clean_symbol,
            market=clean_market,
            timeframe=clean_timeframe,
            ma_config=strategy_cfg,
            backtest_config=cfg,
        )
    except Exception as exc:
        base["status"] = "ERROR"
        base["reason"] = f"{type(exc).__name__}: {exc}"
        return base

    trades = list(result.pop("trades_detail", []) or [])
    equity_curve = list(result.pop("equity_curve", []) or [])
    profit_factor_unbounded = result.get("profit_factor") == float("inf")
    sortino_unbounded = result.get("sortino") == float("inf")
    validation = _time_split_validation(
        frame=batch.frame,
        trades=trades,
        equity_curve=equity_curve,
        warmup=int(cfg.warmup),
        annualization_periods=float(result.get("annualization_periods") or 252.0),
    )
    base.update(
        {
            "status": "COMPLETED" if trades else "NO_TRADES",
            "reason": "" if trades else "La estrategia no produjo entradas con estos datos y parámetros.",
            "metrics": _json_safe(result),
            "trades": _json_safe(trades),
            "equity_curve": _json_safe(equity_curve),
            "validation": _json_safe(validation),
            "profit_factor_unbounded": profit_factor_unbounded,
            "sortino_unbounded": sortino_unbounded,
        }
    )
    return base


class BacktestStore:
    def __init__(self, path: str | Path = DEFAULT_BACKTEST_PATH, *, max_runs_per_user: int = MAX_RUNS_PER_USER):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.max_runs_per_user = max(1, int(max_runs_per_user))

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": BACKTEST_STORE_SCHEMA_VERSION, "updated_at": _now_iso(), "users": {}}

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("users"), dict):
            return self._empty()
        payload["schema_version"] = BACKTEST_STORE_SCHEMA_VERSION
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = BACKTEST_STORE_SCHEMA_VERSION
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

    def save(self, user_id: Any, record: dict[str, Any]) -> dict[str, Any]:
        clean_user = _clean_user(user_id)
        safe_record = _json_safe(record)
        if not isinstance(safe_record, dict) or not safe_record.get("id"):
            raise ValueError("Backtest record requires an id")
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
                users = payload.setdefault("users", {})
                user = users.setdefault(clean_user, {"runs": []})
                runs = user.setdefault("runs", [])
                runs.insert(0, safe_record)
                user["runs"] = runs[: self.max_runs_per_user]
                self._write_unlocked(payload)
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return safe_record

    def list_runs(
        self,
        user_id: Any,
        *,
        symbol: str | None = None,
        market: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        payload = self._read_unlocked()
        user = payload.get("users", {}).get(_clean_user(user_id), {})
        runs = user.get("runs", []) if isinstance(user, dict) else []
        clean_symbol = _clean_symbol(symbol) if symbol else ""
        clean_market = str(market or "").lower()
        selected = [
            dict(run)
            for run in runs
            if isinstance(run, dict)
            and (not clean_symbol or run.get("symbol") == clean_symbol)
            and (not clean_market or run.get("market") == clean_market)
        ]
        return selected[: max(0, int(limit))]

    def latest(self, user_id: Any, *, symbol: str, market: str, timeframe: str | None = None) -> dict[str, Any] | None:
        for run in self.list_runs(user_id, symbol=symbol, market=market, limit=self.max_runs_per_user):
            if timeframe is None or run.get("timeframe") == str(timeframe).lower():
                return run
        return None
