"""
Market data (price, beta, risk-free rate) behind a small interface.
"""

from datetime import date
from typing import Protocol

from .models import MarketSnapshot

TREASURY_10Y = "^TNX"  # quoted in percent


class MarketData(Protocol):
    def snapshot(self, ticker: str) -> MarketSnapshot: ...


class YFinanceMarketData:
    """Market data from Yahoo Finance via yfinance (unofficial; may break or rate-limit)."""

    def __init__(self):
        import yfinance  # imported lazily so the rest of the package works without it

        self._yf = yfinance
        self._risk_free = None

    def risk_free_rate(self) -> float:
        if self._risk_free is None:
            closes = self._yf.Ticker(TREASURY_10Y).history(period="5d")["Close"]
            self._risk_free = float(closes.iloc[-1]) / 100
        return self._risk_free

    def snapshot(self, ticker: str) -> MarketSnapshot:
        t = self._yf.Ticker(ticker)
        fast = t.fast_info
        price = fast.get("lastPrice") or fast.get("last_price")
        if not price:
            raise LookupError(f"No market price for {ticker!r}")
        info = t.info or {}
        return MarketSnapshot(
            price=float(price),
            beta=info.get("beta"),
            risk_free_rate=self.risk_free_rate(),
            shares_outstanding=fast.get("shares") or info.get("sharesOutstanding"),
            as_of=date.today(),
        )
