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


def _growth_path(result, revenue=100.0):
    rev = np.array([revenue] + result.revenue_forecast_p50)
    return rev[1:] / rev[:-1] - 1


def test_default_horizon_holds_growth_then_fades_by_year_ten():
    result = simulate_fair_value(
        _assumptions(growth_start=0.30, terminal_growth_low=0.02, terminal_growth_high=0.02),
        num_simulations=10,
        seed=1,
    )

    growth = _growth_path(result)
    assert len(growth) == 10
    # hold 3 years at the starting rate, then fade linearly to terminal in year 10
    assert growth[:3] == pytest.approx([0.30, 0.30, 0.30])
    assert growth[3:] == pytest.approx([0.26, 0.22, 0.18, 0.14, 0.10, 0.06, 0.02])


def test_horizon_is_configurable():
    result = simulate_fair_value(
        _assumptions(growth_start=0.30, terminal_growth_low=0.02, terminal_growth_high=0.02,
                     years=5, hold_years=1),
        num_simulations=10,
        seed=1,
    )

    assert _growth_path(result) == pytest.approx([0.30, 0.23, 0.16, 0.09, 0.02])


def test_terminal_value_share_is_reported():
    result = simulate_fair_value(_assumptions(), num_simulations=10, seed=1)

    # EV is 255 (Gordon); the terminal share is whatever the 10 explicit years don't cover
    fcf = [20.4 * 1.02 ** t for t in range(10)]
    pv_explicit = sum(f / 1.10 ** (t + 1) for t, f in enumerate(fcf))
    assert result.terminal_value_share == pytest.approx(1 - pv_explicit / 255.0)


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


def test_capex_fades_to_maintenance_level():
    # Peak build-out: capex 25% of revenue vs depreciation 5%.
    result = simulate_fair_value(
        _assumptions(capex_pct=0.25, capex_fade=True, growth_start=0.02), num_simulations=10, seed=1,
    )
    rev, fcf = np.array(result.revenue_forecast_p50), np.array(result.fcf_forecast_p50)
    capex = 0.20 + 0.05 - fcf / rev  # FCF = rev * (margin*(1-tax) + da - capex), tax 0, no WC change

    assert capex[:3] == pytest.approx([0.25, 0.25, 0.25])      # held while growth is held
    assert capex[-1] == pytest.approx(0.05 * 1.02)              # maintenance: D&A x (1 + g)
    assert np.all(np.diff(capex[2:]) < 0)                       # fades down in between


def test_constant_capex_is_still_available():
    result = simulate_fair_value(_assumptions(capex_pct=0.25), num_simulations=10, seed=1)
    rev, fcf = np.array(result.revenue_forecast_p50), np.array(result.fcf_forecast_p50)
    assert 0.20 + 0.05 - fcf / rev == pytest.approx(np.full(10, 0.25))
    assert np.isfinite(result.terminal_value_share)  # EV is 0 here: no 0/0 NaN


def test_per_share_value_is_floored_at_zero():
    # Shareholders can lose at most their stake: equity value can't go below zero.
    result = simulate_fair_value(_assumptions(net_debt=10_000.0), num_simulations=100, seed=1)

    assert result.per_share_samples.min() == 0.0
    assert result.per_share_p50 == 0.0


def test_capex_below_depreciation_is_not_raised():
    # Pfizer-style: D&A is inflated by amortization of acquired intangibles, not
    # equipment that needs replacing, so the fade must never push capex up.
    result = simulate_fair_value(
        _assumptions(capex_pct=0.02, da_pct=0.08, capex_fade=True), num_simulations=10, seed=1,
    )
    rev, fcf = np.array(result.revenue_forecast_p50), np.array(result.fcf_forecast_p50)

    assert 0.20 + 0.08 - fcf / rev == pytest.approx(np.full(10, 0.02))


def test_margin_fades_toward_target():
    # tax 0, capex == D&A, no WC: FCF / revenue is exactly the operating margin.
    result = simulate_fair_value(_assumptions(ebit_margin=0.40, margin_target=0.25), num_simulations=10, seed=1)
    margin = np.array(result.fcf_forecast_p50) / np.array(result.revenue_forecast_p50)

    assert margin[:3] == pytest.approx([0.40, 0.40, 0.40])
    assert margin[-1] == pytest.approx(0.25)
    assert np.all(np.diff(margin[2:]) < 0)
