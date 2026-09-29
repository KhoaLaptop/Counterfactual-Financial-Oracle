"""
Tests for turning fundamentals + market data into a single-company verdict.
"""

from datetime import date

import pytest

from counterfactual_oracle.src.valuation.assumptions import build_assumptions
from counterfactual_oracle.src.valuation.models import Fundamentals, MarketSnapshot
from counterfactual_oracle.src.valuation.verdict import (
    CONTEXT_NOTE,
    price_position,
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
    # Rd = 10/200 = 5% raised to the 4% + 1.5% credit-spread floor; tax = 20%
    cost_of_equity = 0.04 + (0.67 * 1.2 + 0.33) * 0.05
    assert a.wacc == pytest.approx(0.8 * cost_of_equity + 0.2 * 0.055 * 0.8)


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
    "price, position",
    [
        (80.0, "PRICE_BELOW_MODEL_RANGE"),   # under P10
        (100.0, "PRICE_WITHIN_MODEL_RANGE"),
        (140.0, "PRICE_ABOVE_MODEL_RANGE"),  # over P90
    ],
)
def test_price_position_describes_where_price_sits(price, position):
    assert price_position(price, p10=90.0, p90=130.0) == position


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

    assert verdict.price_position in {"PRICE_BELOW_MODEL_RANGE", "PRICE_WITHIN_MODEL_RANGE",
                                      "PRICE_ABOVE_MODEL_RANGE"}
    assert verdict.fair_value.p10 < verdict.fair_value.p50 < verdict.fair_value.p90
    assert verdict.gap_pct == pytest.approx(verdict.fair_value.p50 / 8.0 - 1)
    assert 0.0 <= verdict.p_upside <= 1.0
    assert verdict.confidence in {"High", "Medium", "Low"}


def test_evaluate_price_below_and_above_the_model_range():
    cheap = evaluate(_fundamentals(), _market(price=2.0), num_simulations=4000, seed=1)
    pricey = evaluate(_fundamentals(), _market(price=200.0), num_simulations=4000, seed=1)

    assert cheap.price_position == "PRICE_BELOW_MODEL_RANGE"
    assert cheap.p_upside > 0.9
    assert pricey.price_position == "PRICE_ABOVE_MODEL_RANGE"
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

    assert verdict.price_position == "NOT_ASSESSABLE"
    assert reason_fragment in verdict.reason.lower()
    assert verdict.fair_value is None


def test_evaluate_falls_back_to_market_share_count():
    verdict = evaluate(_fundamentals(shares=None), _market(shares_outstanding=100.0),
                       num_simulations=500, seed=1)
    assert verdict.price_position != "NOT_ASSESSABLE"


def test_financial_company_reason_wins_over_missing_fields():
    verdict = evaluate(_fundamentals(sic=6021, operating_income=None), _market(), num_simulations=100)
    assert "financial" in verdict.reason.lower()


def test_data_note_explains_not_assessable():
    verdict = evaluate(
        _fundamentals(revenue=None, data_note="no full fiscal year in SEC XBRL data (new registrant?)"),
        _market(), num_simulations=100,
    )
    assert verdict.price_position == "NOT_ASSESSABLE"
    assert "new registrant" in verdict.reason


def test_data_note_is_reported_on_assessable_verdicts():
    note = "operating income estimated as pretax income + interest expense"
    verdict = evaluate(_fundamentals(data_note=note), _market(), num_simulations=500)

    assert verdict.price_position != "NOT_ASSESSABLE"
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


@pytest.mark.parametrize("sic, assessable", [(4911, False), (4924, False), (4941, False),
                                             (4922, True), (4953, True)])
def test_regulated_utilities_are_not_assessable(sic, assessable):
    # Electric (4911), gas distribution (4924), water (4941) are out; pipelines (4922)
    # and waste (4953) are ordinary businesses.
    verdict = evaluate(_fundamentals(sic=sic), _market(), num_simulations=200)
    assert (verdict.price_position != "NOT_ASSESSABLE") == assessable
    if not assessable:
        assert "utility" in verdict.reason.lower()


def test_cost_of_debt_has_a_credit_spread_and_wacc_a_floor():
    rf = 0.0526
    # Heavily indebted, cheap stated interest, low beta: previously WACC ~6%.
    f = _fundamentals(total_debt=4000.0, interest_expense=10.0, cash=0.0)
    a, _ = build_assumptions(f, _market(beta=0.3, risk_free_rate=rf, price=8.0))

    assert a.wacc >= rf + 0.02 - 1e-12


def test_margin_target_comes_from_history():
    a, _ = build_assumptions(_fundamentals(operating_margin_5y=0.12), _market())
    assert a.margin_target == pytest.approx(0.12)


def test_model_options_for_horizon_and_margin_fade():
    a, _ = build_assumptions(_fundamentals(operating_margin_5y=0.12), _market(),
                             horizon_years=5, hold_years=1, margin_fade=False)
    assert (a.years, a.hold_years, a.margin_target) == (5, 1, None)

    verdict = evaluate(_fundamentals(), _market(), num_simulations=300, horizon_years=5, hold_years=1)
    assert verdict.assumptions["horizon_years"] == 5


# --- valuation context --------------------------------------------------------------

def test_every_verdict_carries_the_backtest_context_note():
    assessed = evaluate(_fundamentals(), _market(), num_simulations=300)
    excluded = evaluate(_fundamentals(sic=6021), _market(), num_simulations=300)

    for verdict in (assessed, excluded):
        assert verdict.context_note == CONTEXT_NOTE
    assert "not a buy/sell signal" in CONTEXT_NOTE
    assert "did not predict" in CONTEXT_NOTE


def test_market_implied_growth_is_reported():
    # ~11% recent growth: a low price implies much less, a high price much more.
    cheap = evaluate(_fundamentals(), _market(price=15.0), num_simulations=500)
    pricey = evaluate(_fundamentals(), _market(price=60.0), num_simulations=500)
    extreme = evaluate(_fundamentals(), _market(price=2.0), num_simulations=500)

    assert cheap.market_implied_growth < cheap.assumptions["growth_start"] < pricey.market_implied_growth
    assert extreme.market_implied_growth is None  # would need < -20% growth: outside the search range


def test_sensitivities_move_in_the_expected_direction():
    s = evaluate(_fundamentals(), _market(), num_simulations=500).sensitivity

    assert s["wacc +1pt"] < s["base"] < s["wacc -1pt"]
    assert s["growth -5pt"] < s["base"] < s["growth +5pt"]
    assert s["margin -2pt"] < s["base"] < s["margin +2pt"]
