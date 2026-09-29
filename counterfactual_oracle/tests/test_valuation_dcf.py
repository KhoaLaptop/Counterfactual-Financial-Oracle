"""
Tests for the per-share Monte Carlo DCF used by the single-company verdict.
"""

import numpy as np
import pytest

from counterfactual_oracle.src.valuation.dcf import ValuationAssumptions, simulate_fair_value


def _assumptions(**overrides):
    base = dict(
        revenue=100.0,
        growth_start=0.02,
        growth_sigma=0.0,
        terminal_growth_low=0.02,
        terminal_growth_high=0.02,
        ebit_margin=0.20,
        margin_sigma=0.0,
        tax_rate=0.0,
        da_pct=0.05,
        capex_pct=0.05,
        wc_pct=0.0,
        wacc=0.10,
        wacc_sigma=0.0,
        net_debt=55.0,
        shares=10.0,
    )
    base.update(overrides)
    return ValuationAssumptions(**base)


def test_deterministic_constant_growth_matches_gordon_formula():
    # FCF_1 = 100 * 1.02 * 0.20 = 20.4; EV = FCF_1 / (r - g) = 20.4 / 0.08 = 255
    result = simulate_fair_value(_assumptions(), num_simulations=50, seed=1)

    assert result.enterprise_value_p50 == pytest.approx(255.0)
    # (255 - 55 net debt) / 10 shares
    assert result.per_share_p50 == pytest.approx(20.0)
    assert result.per_share_p10 == pytest.approx(result.per_share_p90)


def test_growth_fades_linearly_to_terminal_rate():
    result = simulate_fair_value(
        _assumptions(growth_start=0.30, terminal_growth_low=0.02, terminal_growth_high=0.02),
        num_simulations=10,
        seed=1,
    )

    growth = np.array(result.revenue_forecast_p50[1:]) / np.array(result.revenue_forecast_p50[:-1]) - 1
    assert result.revenue_forecast_p50[0] == pytest.approx(130.0)
    assert growth == pytest.approx([0.23, 0.16, 0.09, 0.02])


def test_working_capital_scales_with_revenue_change():
    no_wc = simulate_fair_value(_assumptions(growth_start=0.10), num_simulations=10, seed=1)
    with_wc = simulate_fair_value(_assumptions(growth_start=0.10, wc_pct=0.2), num_simulations=10, seed=1)

    # Year 1 revenue change is 10, so FCF drops by 0.2 * 10
    assert no_wc.fcf_forecast_p50[0] - with_wc.fcf_forecast_p50[0] == pytest.approx(2.0)


def test_uncertainty_produces_ordered_reproducible_distribution():
    assumptions = _assumptions(growth_sigma=0.03, margin_sigma=0.02, wacc_sigma=0.01,
                               terminal_growth_low=0.015, terminal_growth_high=0.03)

    first = simulate_fair_value(assumptions, num_simulations=5000, seed=7)
    second = simulate_fair_value(assumptions, num_simulations=5000, seed=7)

    assert first.per_share_p10 < first.per_share_p50 < first.per_share_p90
    assert first.per_share_p50 == second.per_share_p50
    assert len(first.per_share_samples) == 5000


def test_wacc_never_falls_to_terminal_growth():
    # A WACC draw below terminal growth would make the terminal value explode or flip sign.
    result = simulate_fair_value(
        _assumptions(wacc=0.03, wacc_sigma=0.05, terminal_growth_low=0.03, terminal_growth_high=0.03),
        num_simulations=2000,
        seed=3,
    )

    assert np.all(np.isfinite(result.per_share_samples))
    assert result.wacc_samples.min() >= 0.03 + 0.01 - 1e-12
