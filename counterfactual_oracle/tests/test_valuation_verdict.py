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
    # Blume beta = 0.67 * 1.2 + 0.33; Re = 4% + beta * 5%; E = 8 * 100 = 800, D = 200,
    # Rd = 10/200 = 5%, tax = 20%
    cost_of_equity = 0.04 + (0.67 * 1.2 + 0.33) * 0.05
    assert a.wacc == pytest.approx(0.8 * cost_of_equity + 0.2 * 0.05 * 0.8)


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


def test_financial_company_reason_wins_over_missing_fields():
    verdict = evaluate(_fundamentals(sic=6021, operating_income=None), _market(), num_simulations=100)
    assert "financial" in verdict.reason.lower()


def test_data_note_explains_not_assessable():
    verdict = evaluate(
        _fundamentals(revenue=None, data_note="no full fiscal year in SEC XBRL data (new registrant?)"),
        _market(), num_simulations=100,
    )
    assert verdict.label == "NOT_ASSESSABLE"
    assert "new registrant" in verdict.reason


def test_data_note_is_reported_on_assessable_verdicts():
    note = "operating income estimated as pretax income + interest expense"
    verdict = evaluate(_fundamentals(data_note=note), _market(), num_simulations=500)

    assert verdict.label != "NOT_ASSESSABLE"
    assert note in verdict.confidence_reasons


def test_investment_phase_lowers_confidence():
    level, reasons = quantitative_confidence(90, 130, price=100.0, missing_fields=[], capex_to_da=3.9)

    assert level == "Medium"
    assert any("investment phase" in r.lower() for r in reasons)


def test_builder_fades_capex():
    a, _ = build_assumptions(_fundamentals(capex=300.0), _market())
    assert a.capex_fade


def test_wacc_uses_blume_adjusted_beta():
    # Blume: 0.67 * raw + 0.33 * 1.0, damping noisy historical betas toward the market.
    raw_beta = 0.9
    a, _ = build_assumptions(_fundamentals(total_debt=0.0, interest_expense=0.0), _market(beta=raw_beta))
    assert a.wacc == pytest.approx(0.04 + (0.67 * raw_beta + 0.33) * 0.05)


def test_growth_jump_uses_the_lower_of_recent_and_three_year_rates():
    # AMCR-style: a merger lifts reported revenue +40% while the business grows ~5%.
    f = _fundamentals(revenue=1400.0, revenue_prior=1000.0, revenue_3y_ago=1200.0)
    a, _ = build_assumptions(f, _market())

    assert a.growth_start == pytest.approx((1400 / 1200) ** (1 / 3) - 1)


def test_growth_jump_is_explained_in_the_verdict():
    f = _fundamentals(revenue=1400.0, revenue_prior=1000.0, revenue_3y_ago=1200.0)
    verdict = evaluate(f, _market(price=2.0), num_simulations=500)
    assert any("acquisition" in r.lower() for r in verdict.confidence_reasons)


def test_high_leverage_lowers_confidence():
    # CHTR-style: net debt several times the market value of equity.
    level, reasons = quantitative_confidence(90, 130, price=100.0, missing_fields=[], leverage=6.9)

    assert level == "Medium"
    assert any("leverage" in r.lower() for r in reasons)
