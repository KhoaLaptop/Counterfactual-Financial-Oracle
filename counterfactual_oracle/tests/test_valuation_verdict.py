"""
Tests for turning fundamentals + market data into a single-company verdict.
"""

from datetime import date

import pytest

from counterfactual_oracle.src.valuation.assumptions import build_assumptions
from counterfactual_oracle.src.valuation.models import Fundamentals, MarketSnapshot
from counterfactual_oracle.src.valuation.verdict import (
    classify,
    evaluate,
    quantitative_confidence,
)


def _fundamentals(**overrides):
    base = dict(
        ticker="TEST",
        name="Test Corp",
        sic=3571,
        period_end=date(2025, 6, 30),
        basis="TTM",
        revenue=1000.0,
        revenue_prior=900.0,
        revenue_3y_ago=750.0,
        operating_income=200.0,
        depreciation_amortization=50.0,
        capex=60.0,
        change_in_working_capital=10.0,
        income_tax=40.0,
        pretax_income=200.0,
        interest_expense=10.0,
        cash=100.0,
        total_debt=200.0,
        shares=100.0,
    )
    base.update(overrides)
    return Fundamentals(**base)


def _market(**overrides):
    base = dict(price=8.0, beta=1.2, risk_free_rate=0.04)
    base.update(overrides)
    return MarketSnapshot(**base)


# --- assumptions -----------------------------------------------------------

def test_growth_start_blends_recent_growth_with_three_year_cagr():
    a, _ = build_assumptions(_fundamentals(revenue_prior=800.0, revenue_3y_ago=512.0), _market())
    # recent 25%, 3y CAGR 25% -> 25%
    assert a.growth_start == pytest.approx(0.25)


def test_growth_start_is_capped():
    a, _ = build_assumptions(_fundamentals(revenue_prior=500.0, revenue_3y_ago=None), _market())
    assert a.growth_start == pytest.approx(0.40)


def test_wacc_uses_capm_and_after_tax_cost_of_debt():
    a, _ = build_assumptions(_fundamentals(), _market())
    # Re = 4% + 1.2 * 5% = 10%; E = 8 * 100 = 800, D = 200, Rd = 10/200 = 5%, tax = 20%
    assert a.wacc == pytest.approx(0.8 * 0.10 + 0.2 * 0.05 * 0.8)


def test_missing_optionals_fall_back_and_are_reported():
    a, missing = build_assumptions(
        _fundamentals(depreciation_amortization=None, pretax_income=None, revenue_3y_ago=None),
        _market(beta=None),
    )
    assert a.tax_rate == pytest.approx(0.21)
    assert a.da_pct == 0.0
    assert set(missing) >= {"depreciation_amortization", "pretax_income", "revenue_3y_ago", "beta"}


def test_net_debt_and_ebit_margin():
    a, _ = build_assumptions(_fundamentals(), _market())
    assert a.net_debt == pytest.approx(100.0)
    assert a.ebit_margin == pytest.approx(0.20)


# --- classification & confidence -----------------------------------------

@pytest.mark.parametrize(
    "gap, p_upside, label",
    [
        (0.20, 0.70, "UNDERVALUED"),
        (0.20, 0.55, "FAIRLY_VALUED"),
        (0.10, 0.90, "FAIRLY_VALUED"),
        (-0.20, 0.30, "OVERVALUED"),
        (-0.20, 0.45, "FAIRLY_VALUED"),
    ],
)
def test_classify_bands(gap, p_upside, label):
    assert classify(gap, p_upside) == label


@pytest.mark.parametrize(
    "p10, p90, missing, expected",
    [
        (90, 130, [], "High"),       # spread 0.4x price
        (70, 150, [], "Medium"),     # spread 0.8x price
        (40, 200, [], "Low"),        # spread 1.6x price
        (90, 130, ["beta", "capex"], "Medium"),  # data gaps downgrade one level
        (40, 200, ["beta", "capex"], "Low"),     # never below Low
    ],
)
def test_quantitative_confidence(p10, p90, missing, expected):
    level, _ = quantitative_confidence(p10, p90, price=100.0, missing_fields=missing)
    assert level == expected


def test_confidence_drops_when_terminal_value_dominates():
    level, reasons = quantitative_confidence(90, 130, price=100.0, missing_fields=[], terminal_value_share=0.8)

    assert level == "Medium"
    assert any("terminal value" in r.lower() for r in reasons)


def test_verdict_reports_terminal_value_share():
    verdict = evaluate(_fundamentals(), _market(), num_simulations=1000, seed=1)
    assert 0.0 < verdict.assumptions["terminal_value_share"] < 1.0


# --- end-to-end verdict -----------------------------------------------------

def test_evaluate_returns_verdict_consistent_with_distribution():
    verdict = evaluate(_fundamentals(), _market(), num_simulations=4000, seed=1)

    assert verdict.label in {"UNDERVALUED", "FAIRLY_VALUED", "OVERVALUED"}
    assert verdict.fair_value.p10 < verdict.fair_value.p50 < verdict.fair_value.p90
    assert verdict.gap_pct == pytest.approx(verdict.fair_value.p50 / 8.0 - 1)
    assert 0.0 <= verdict.p_upside <= 1.0
    assert verdict.confidence in {"High", "Medium", "Low"}


def test_evaluate_cheap_stock_is_undervalued_and_expensive_is_overvalued():
    cheap = evaluate(_fundamentals(), _market(price=2.0), num_simulations=4000, seed=1)
    pricey = evaluate(_fundamentals(), _market(price=200.0), num_simulations=4000, seed=1)

    assert cheap.label == "UNDERVALUED"
    assert cheap.p_upside > 0.9
    assert pricey.label == "OVERVALUED"
    assert pricey.p_upside < 0.1


@pytest.mark.parametrize(
    "overrides, reason_fragment",
    [
        (dict(sic=6021), "financial"),
        (dict(sic=6798), "financial"),
        (dict(operating_income=-50.0), "negative"),
        (dict(revenue=None), "revenue"),
        (dict(shares=None), "share count"),
    ],
)
def test_evaluate_marks_unfit_companies_not_assessable(overrides, reason_fragment):
    verdict = evaluate(_fundamentals(**overrides), _market(), num_simulations=100, seed=1)

    assert verdict.label == "NOT_ASSESSABLE"
    assert reason_fragment in verdict.reason.lower()
    assert verdict.fair_value is None


def test_evaluate_falls_back_to_market_share_count():
    verdict = evaluate(_fundamentals(shares=None), _market(shares_outstanding=100.0),
                       num_simulations=500, seed=1)
    assert verdict.label != "NOT_ASSESSABLE"
