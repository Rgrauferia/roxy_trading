from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseBroker(ABC):
    """Abstract broker interface used by execution and backtests.

    Implementations should provide a minimal set of methods used by the
    `PaperTrader`/execution layer: `buy`, `sell`, `get_position`, `get_cash`.
    """

    @abstractmethod
    def buy(self, symbol: str, qty: float, price: float) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def sell(self, symbol: str, qty: float, price: float) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_position(self, symbol: str) -> float:
        raise NotImplementedError()

    @abstractmethod
    def get_cash(self) -> float:
        raise NotImplementedError()


class PaperBroker(BaseBroker):
    """Adapter that wraps the existing `PaperTrader` implementation.

    This allows switching the execution backend in `backtester.py` or other
    modules by depending on the abstract `BaseBroker`.
    """

    def __init__(self, paper_trader):
        self._pt = paper_trader

    def buy(self, symbol: str, qty: float, price: float) -> None:
        return self._pt.buy(symbol, qty, price)

    def sell(self, symbol: str, qty: float, price: float) -> None:
        return self._pt.sell(symbol, qty, price)

    def get_position(self, symbol: str) -> float:
        return self._pt.get_position(symbol)

    def get_cash(self) -> float:
        return getattr(self._pt, 'cash', 0.0)


class AlpacaBroker(BaseBroker):
    """Placeholder for an Alpaca broker adapter. To be implemented with
    credentials and REST/ws handling. Not implemented by default for safety.
    """
    def __init__(self, api_key: str | None = None, api_secret: str | None = None, base_url: str | None = None):
        # allow env var based configuration but remain disabled unless configured
        api_key = api_key or os.environ.get("ALPACA_API_KEY")
        api_secret = api_secret or os.environ.get("ALPACA_API_SECRET")
        base_url = base_url or os.environ.get("ALPACA_BASE_URL")
        if not (api_key and api_secret and base_url):
            raise NotImplementedError(
                "AlpacaBroker is disabled — set ALPACA_API_KEY, ALPACA_API_SECRET and ALPACA_BASE_URL to enable."
            )
        # lazy import
        try:
            import alpaca_trade_api as tradeapi
        except Exception as e:
            raise ImportError("alpaca-trade-api is required for AlpacaBroker") from e
        self._api = tradeapi.REST(api_key, api_secret, base_url=base_url)

    def buy(self, symbol: str, qty: float, price: float) -> None:
        # market orders by quantity for simplicity
        self._api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')

    def sell(self, symbol: str, qty: float, price: float) -> None:
        self._api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')

    def get_position(self, symbol: str) -> float:
        try:
            p = self._api.get_position(symbol)
            return float(p.qty)
        except Exception:
            return 0.0

    def get_cash(self) -> float:
        try:
            acct = self._api.get_account()
            return float(acct.cash)
        except Exception:
            return 0.0


class CCXTBroker(BaseBroker):
    """Placeholder for a CCXT-based broker adapter for crypto exchanges.
    Implement when you want live trading via CCXT-supported exchanges.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError("CCXTBroker is a placeholder. Configure exchange keys to enable.")
