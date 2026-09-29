"""
Tests for the point-in-time backtest (B2).
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from counterfactual_oracle.src.valuation.backtest import (
    PriceHistory,
    quarter_ends,
    run_backtest,
    spearman,
    summarize,
)
from counterfactual_oracle.src.valuation.models import Fundamentals

WEEKS = pd.date_range("2018-01-05", "2023-12-29", freq="W-FRI")


def _prices():
    """Weekly frames: ^GSPC, ^TNX, CHEAP (steady +), RICH (steady -), SPLIT (2:1 split mid-2021)."""
    n = len(WEEKS)
    rng = np.random.default_rng(1)
    market_returns = rng.normal(0.002, 0.02, n)
    market = 2500 * np.cumprod(1 + market_returns)
    # Shared market factor, opposite small drifts: CHEAP stays cheaper than RICH throughout,
    # and always out-returns it.
    cheap = 20 * np.cumprod(1 + 0.2 * market_returns + 0.001)
    rich = 50 * np.cumprod(1 + 0.2 * market_returns - 0.001)
    split_week = WEEKS.get_indexer([pd.Timestamp("2021-06-04")])[0]
    split_raw = np.where(np.arange(n) < split_week, 100.0, 50.0)  # unadjusted close halves at the split
    close = pd.DataFrame({"^GSPC": market, "^TNX": np.full(n, 3.0), "CHEAP": cheap, "RICH": rich,
                          "SPLIT": split_raw / np.where(np.arange(n) < split_week, 2.0, 1.0)}, index=WEEKS)
    splits = pd.DataFrame(0.0, index=WEEKS, columns=close.columns)
    splits.loc[pd.Timestamp("2021-06-04"), "SPLIT"] = 2.0
    return close.copy(), close.copy(), splits  # adjusted close == split-adjusted close (no dividends)


def _fundamentals(ticker, as_of):
    return Fundamentals(
        ticker=ticker, name=ticker, sic=3571, period_end=as_of, basis="TTM",
        revenue=1000.0, revenue_prior=950.0, revenue_3y_ago=860.0, operating_income=150.0,
        depreciation_amortization=40.0, capex=45.0, income_tax=30.0, pretax_income=150.0,
        interest_expense=5.0, cash=50.0, total_debt=100.0, shares=100.0,
    )


class FakeHistory:
    """Point-in-time fundamentals; SPLIT reports pre-split share counts before mid-2021."""

    def __init__(self):
        self.calls = []

    def fundamentals_at(self, ticker, as_of):
        self.calls.append((ticker, as_of))
        f = _fundamentals(ticker, as_of)
        if ticker == "SPLIT" and as_of < date(2021, 6, 4):
            f = f.model_copy(update={"shares": 50.0})  # 50 pre-split = 100 post-split
        return f


def _history():
    adj, close, splits = _prices()
    return PriceHistory(adjusted=adj, close=close, splits=splits)


# --- building blocks ------------------------------------------------------------

def test_quarter_ends():
    assert quarter_ends(date(2020, 2, 1), date(2020, 12, 31)) == [
        date(2020, 3, 31), date(2020, 6, 30), date(2020, 9, 30), date(2020, 12, 31)]


def test_split_factor_puts_old_share_counts_on_todays_basis():
    prices = _history()
    assert prices.split_factor_after("SPLIT", date(2021, 1, 1)) == 2.0
    assert prices.split_factor_after("SPLIT", date(2022, 1, 1)) == 1.0
    assert prices.split_factor_after("CHEAP", date(2019, 1, 1)) == 1.0


def test_forward_return_uses_prices_after_the_date_only():
    prices = _history()
    adj = _prices()[0]["CHEAP"]
    start = adj.loc[:"2019-06-30"].iloc[-1]
    end = adj.loc[:"2020-06-30"].iloc[-1]

    assert prices.forward_return("CHEAP", date(2019, 6, 30), weeks=52) == pytest.approx(end / start - 1, rel=0.02)
    assert prices.forward_return("CHEAP", date(2023, 6, 30), weeks=52) is None  # future not available


def test_snapshot_as_of_uses_only_past_prices():
    prices = _history()
    snap = prices.snapshot("CHEAP", date(2020, 3, 31))

    assert snap.price == pytest.approx(_prices()[1]["CHEAP"].loc[:"2020-03-31"].iloc[-1])
    assert snap.risk_free_rate == pytest.approx(0.03)
    assert snap.as_of == date(2020, 3, 31)


def test_spearman():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


# --- end to end ------------------------------------------------------------------

def test_run_backtest_scores_every_date_with_point_in_time_inputs():
    history = FakeHistory()
    dates = quarter_ends(date(2020, 3, 31), date(2023, 12, 31))

    result = run_backtest(["CHEAP", "RICH", "SPLIT"], history, _history(), dates, num_simulations=300)

    # only dates with 52 weeks of future prices are evaluated
    evaluated = sorted({row.as_of for row in result.rows})
    assert evaluated[0] == date(2020, 3, 31) and evaluated[-1] <= date(2022, 12, 31)
    # fundamentals were requested ticker by ticker, never for a date after the rebalance
    assert all(as_of in dates for _, as_of in history.calls)
    # identical fundamentals + adjusted SPLIT shares => the cheaper price ranks higher every date
    for d in evaluated:
        rows = {r.ticker: r for r in result.rows if r.as_of == d}
        assert rows["CHEAP"].score > rows["RICH"].score


def test_split_adjustment_keeps_valuations_consistent_across_the_split():
    result = run_backtest(["SPLIT"], FakeHistory(), _history(),
                          [date(2021, 3, 31), date(2021, 9, 30)], num_simulations=300)
    before, after = sorted((r for r in result.rows), key=lambda r: r.as_of)

    # same business, same split-adjusted price => nearly the same gap before and after the split
    assert before.gap_pct == pytest.approx(after.gap_pct, abs=0.05)


def test_summarize_reports_rank_correlation_and_quintile_spread():
    history = FakeHistory()
    dates = quarter_ends(date(2019, 3, 31), date(2022, 6, 30))
    result = run_backtest(["CHEAP", "RICH"], history, _history(), dates, num_simulations=300)

    summary = summarize(result, quantiles=2)

    # CHEAP ranks top and rises; RICH ranks bottom and falls: a perfect synthetic signal
    assert summary["mean_rank_correlation"] > 0.5
    assert summary["top_minus_bottom"] > 0
    assert summary["hit_rate"] == pytest.approx(1.0)
    assert summary["dates"] == len({r.as_of for r in result.rows})


class StaleCoverHistory(FakeHistory):
    """After the split, SEC still only has the pre-split cover count (measured in April)."""

    def fundamentals_at(self, ticker, as_of):
        f = _fundamentals(ticker, as_of)
        if ticker == "SPLIT" and as_of < date(2021, 9, 1):
            f = f.model_copy(update={"shares": 50.0, "shares_as_of": date(2021, 4, 20)})
        return f


def test_split_adjustment_uses_when_shares_were_measured():
    # Rebalance on 2021-06-30 is after the 2021-06-04 split, but the share count is pre-split.
    result = run_backtest(["SPLIT"], StaleCoverHistory(), _history(),
                          [date(2021, 6, 30), date(2021, 9, 30)], num_simulations=300)
    stale, fresh = sorted(result.rows, key=lambda r: r.as_of)

    assert stale.gap_pct == pytest.approx(fresh.gap_pct, abs=0.05)


# --- ablation support -------------------------------------------------------------

def test_summarize_can_use_another_score_and_a_date_window():
    dates = quarter_ends(date(2019, 3, 31), date(2022, 6, 30))
    result = run_backtest(["CHEAP", "RICH"], FakeHistory(), _history(), dates, num_simulations=300)

    train = summarize(result, quantiles=2, score_field="p_upside", end=date(2020, 12, 31))

    assert train["dates"] == len([d for d in dates if d <= date(2020, 12, 31)])
    assert train["score_field"] == "p_upside"


def test_model_options_reach_the_valuation():
    dates = [date(2020, 6, 30)]
    ten = run_backtest(["CHEAP"], FakeHistory(), _history(), dates, num_simulations=300)
    five = run_backtest(["CHEAP"], FakeHistory(), _history(), dates, num_simulations=300,
                        model_options={"horizon_years": 5, "hold_years": 1})

    assert ten.rows[0].gap_pct != pytest.approx(five.rows[0].gap_pct, abs=1e-3)
