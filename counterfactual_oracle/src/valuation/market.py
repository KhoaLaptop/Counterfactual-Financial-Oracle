"""
Market data (price, beta, risk-free rate) behind a small interface.

BatchMarketData downloads weekly closes for every ticker in one request and
computes beta itself (2 years of weekly returns vs the S&P 500), so a 500-name
scan is one call instead of hundreds, and any past date can be served without
look-ahead (`as_of`).
"""

from datetime import date, timedelta
from typing import Callable, List, Optional, Protocol

import numpy as np
import pandas as pd

from .models import MarketSnapshot

MARKET_INDEX = "^GSPC"
TREASURY_10Y = "^TNX"  # quoted in percent
DEFAULT_RISK_FREE = 0.043
LOOKBACK_WEEKS = 104
MIN_BETA_WEEKS = 52


class MarketData(Protocol):
    def snapshot(self, ticker: str) -> MarketSnapshot: ...


def weekly_beta(stock: pd.Series, market: pd.Series) -> Optional[float]:
    """OLS beta of weekly returns; None with less than a year of overlapping data."""
    returns = pd.concat([stock, market], axis=1).dropna().pct_change().dropna()
    if len(returns) < MIN_BETA_WEEKS:
        return None
    cov = np.cov(returns.iloc[:, 0], returns.iloc[:, 1])
    return float(cov[0, 1] / cov[1, 1])


def _yahoo_weekly_closes(start: date, end: date) -> Callable[[List[str]], pd.DataFrame]:
    def download(symbols: List[str]) -> pd.DataFrame:
        import yfinance  # imported lazily so the rest of the package works without it

        data = yfinance.download(
            symbols, start=start.isoformat(), end=end.isoformat(), interval="1wk",
            auto_adjust=True, progress=False, threads=True,
        )
        return data["Close"]

    return download


class BatchMarketData:
    def __init__(
        self,
        tickers: List[str],
        download: Optional[Callable[[List[str]], pd.DataFrame]] = None,
        as_of: Optional[date] = None,
    ):
        end = as_of or date.today()
        download = download or _yahoo_weekly_closes(end - timedelta(weeks=LOOKBACK_WEEKS + 4), end + timedelta(days=1))
        closes = download(list(dict.fromkeys([*tickers, MARKET_INDEX, TREASURY_10Y])))
        if as_of is not None:
            closes = closes.loc[: pd.Timestamp(as_of)]
        self.closes = closes.iloc[-(LOOKBACK_WEEKS + 1):]
        self.as_of = as_of or self.closes.index[-1].date()

        treasury = self.closes[TREASURY_10Y].dropna() if TREASURY_10Y in self.closes else pd.Series(dtype=float)
        self.risk_free_rate = float(treasury.iloc[-1]) / 100 if len(treasury) else DEFAULT_RISK_FREE

    def snapshot(self, ticker: str) -> MarketSnapshot:
        series = self.closes[ticker].dropna() if ticker in self.closes else pd.Series(dtype=float)
        if series.empty:
            raise LookupError(f"No market price for {ticker!r}")
        return MarketSnapshot(
            price=float(series.iloc[-1]),
            beta=weekly_beta(series, self.closes[MARKET_INDEX]),
            risk_free_rate=self.risk_free_rate,
            as_of=self.as_of,
        )
