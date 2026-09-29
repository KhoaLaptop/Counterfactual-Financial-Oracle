"""
Tests for batch market data: one download for many tickers, beta computed from returns.
"""

import numpy as np
import pandas as pd
import pytest

from counterfactual_oracle.src.valuation.market import BatchMarketData, weekly_beta


def _closes():
    dates = pd.date_range("2024-01-05", periods=105, freq="W-FRI")
    rng = np.random.default_rng(0)
    market = rng.normal(0.002, 0.02, len(dates))
    idio = rng.normal(0.0, 0.01, len(dates))
    return pd.DataFrame({
        "^GSPC": 4000 * np.cumprod(1 + market),
        "HIGH": 50 * np.cumprod(1 + 1.8 * market + idio),
        "LOW": 80 * np.cumprod(1 + 0.4 * market + idio),
        "^TNX": np.full(len(dates), 4.5),
    }, index=dates)


def test_weekly_beta_recovers_known_sensitivity():
    closes = _closes()
    assert weekly_beta(closes["HIGH"], closes["^GSPC"]) == pytest.approx(1.8, abs=0.15)
    assert weekly_beta(closes["LOW"], closes["^GSPC"]) == pytest.approx(0.4, abs=0.15)


def test_batch_market_data_downloads_once_and_serves_snapshots():
    calls = []

    def download(tickers):
        calls.append(tuple(tickers))
        return _closes()

    market = BatchMarketData(["HIGH", "LOW"], download=download)
    high, low = market.snapshot("HIGH"), market.snapshot("LOW")

    assert len(calls) == 1 and set(calls[0]) >= {"HIGH", "LOW", "^GSPC", "^TNX"}
    assert high.price == pytest.approx(_closes()["HIGH"].iloc[-1])
    assert high.beta > low.beta
    assert high.risk_free_rate == pytest.approx(0.045)


def test_batch_market_data_as_of_uses_only_past_prices():
    market = BatchMarketData(["HIGH"], download=lambda tickers: _closes(), as_of=pd.Timestamp("2025-01-10").date())

    snap = market.snapshot("HIGH")

    assert snap.price == pytest.approx(_closes()["HIGH"].loc[:"2025-01-10"].iloc[-1])
    assert snap.as_of == pd.Timestamp("2025-01-10").date()


def test_missing_ticker_raises_lookup_error():
    market = BatchMarketData(["HIGH"], download=lambda tickers: _closes())
    with pytest.raises(LookupError):
        market.snapshot("NOPE")
