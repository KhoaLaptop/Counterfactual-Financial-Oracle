"""
Vectorized Monte Carlo DCF producing a per-share fair-value distribution.

MODEL (per simulated path):
    g_t      = g0                                           for t <= hold_years
             = g0 + (gT - g0) * (t - hold) / (years - hold)  fading to terminal in the last year
    Rev_t    = Rev_{t-1} * (1 + g_t)
    capex_t  = capex, or with capex_fade: held, then faded (same path as growth) down to
               maintenance capex min(capex, da * (1 + gT)) by the last year
    m_t      = m, or with margin_target: held, then faded (same path) to the target
    FCF_t    = Rev_t * (m_t * (1 - tax) + da - capex_t) - wc * (Rev_t - Rev_{t-1})
    TV       = FCF_T * (1 + gT) / (r - gT)
    EV       = sum(FCF_t / (1 + r)^t) + TV / (1 + r)^T
    PerShare = max(0, (EV - net_debt) / shares)     equity can't be worth less than zero

Sampled per path: g0 ~ N, m ~ N, r ~ N (floored at gT + 1pt), gT ~ U.
"""

from dataclasses import dataclass, replace
from typing import List, Optional

import numpy as np

# Minimum spread between WACC and terminal growth, so terminal value stays finite.
MIN_WACC_SPREAD = 0.01


@dataclass(frozen=True)
class ValuationAssumptions:
    """Inputs to the DCF. Rates are decimals; money is in the same unit as revenue."""
    revenue: float
    growth_start: float
    growth_sigma: float
    terminal_growth_low: float
    terminal_growth_high: float
    ebit_margin: float
    margin_sigma: float
    tax_rate: float
    da_pct: float
    capex_pct: float
    wc_pct: float  # change in working capital per unit of revenue change
    wacc: float
    wacc_sigma: float
    net_debt: float
    shares: float
    years: int = 10
    hold_years: int = 3
    capex_fade: bool = False  # fade today's capex intensity to maintenance level
    margin_target: Optional[float] = None  # long-run operating margin to fade toward


@dataclass
class FairValueDistribution:
    per_share_samples: np.ndarray
    wacc_samples: np.ndarray
    enterprise_value_p50: float
    terminal_value_share: float  # median PV(terminal value) / EV
    per_share_p10: float
    per_share_p50: float
    per_share_p90: float
    revenue_forecast_p50: List[float]
    fcf_forecast_p50: List[float]


def _terminal_share(pv_terminal: np.ndarray, enterprise_value: np.ndarray) -> float:
    """Median PV(terminal)/EV over paths with positive EV; 1.0 if none (all value is terminal, if any)."""
    positive = enterprise_value > 0
    if not positive.any():
        return 1.0
    return float(np.median(pv_terminal[positive] / enterprise_value[positive]))


def simulate_fair_value(
    a: ValuationAssumptions, num_simulations: int = 10000, seed: int = 42
) -> FairValueDistribution:
    rng = np.random.default_rng(seed)
    n, years = num_simulations, a.years

    g0 = rng.normal(a.growth_start, a.growth_sigma, n)
    g_term = rng.uniform(a.terminal_growth_low, a.terminal_growth_high, n)
    margin = rng.normal(a.ebit_margin, a.margin_sigma, n)
    wacc = np.maximum(rng.normal(a.wacc, a.wacc_sigma, n), g_term + MIN_WACC_SPREAD)

    # (n, years) growth path: hold g0, then fade linearly to g_term by the last year
    t = np.arange(1, years + 1)
    fade = np.clip((t - a.hold_years) / max(years - a.hold_years, 1), 0.0, 1.0)
    growth = g0[:, None] + (g_term - g0)[:, None] * fade[None, :]

    revenue = a.revenue * np.cumprod(1 + growth, axis=1)
    prev_revenue = np.hstack([np.full((n, 1), a.revenue), revenue[:, :-1]])
    capex = np.full((n, years), a.capex_pct)
    if a.capex_fade:
        # Only relax peak build-out; D&A can exceed real maintenance needs (acquired intangibles).
        maintenance = np.minimum(a.da_pct * (1 + g_term), a.capex_pct)
        capex = a.capex_pct + (maintenance - a.capex_pct)[:, None] * fade[None, :]
    margin_path = np.repeat(margin[:, None], years, axis=1)
    if a.margin_target is not None:
        margin_path = margin_path + (a.margin_target - a.ebit_margin) * fade[None, :]
    operating_cash = margin_path * (1 - a.tax_rate) + a.da_pct
    fcf = revenue * (operating_cash - capex) - a.wc_pct * (revenue - prev_revenue)

    discount = (1 + wacc)[:, None] ** np.arange(1, years + 1)[None, :]
    terminal_value = fcf[:, -1] * (1 + g_term) / (wacc - g_term)
    pv_terminal = terminal_value / discount[:, -1]
    enterprise_value = (fcf / discount).sum(axis=1) + pv_terminal
    per_share = np.maximum((enterprise_value - a.net_debt) / a.shares, 0.0)

    p10, p50, p90 = np.percentile(per_share, [10, 50, 90])
    return FairValueDistribution(
        per_share_samples=per_share,
        wacc_samples=wacc,
        enterprise_value_p50=float(np.median(enterprise_value)),
        terminal_value_share=_terminal_share(pv_terminal, enterprise_value),
        per_share_p10=float(p10),
        per_share_p50=float(p50),
        per_share_p90=float(p90),
        revenue_forecast_p50=np.median(revenue, axis=0).tolist(),
        fcf_forecast_p50=np.median(fcf, axis=0).tolist(),
    )


def implied_growth(
    a: ValuationAssumptions, price: float, low: float = -0.20, high: float = 0.60, tolerance: float = 1e-5
) -> Optional[float]:
    """
    Reverse DCF: the starting revenue growth at which the (deterministic, central-case)
    model value per share equals `price`. None if no rate in [low, high] gets there.
    """
    mid = (a.terminal_growth_low + a.terminal_growth_high) / 2
    central = replace(a, growth_sigma=0.0, margin_sigma=0.0, wacc_sigma=0.0,
                      terminal_growth_low=mid, terminal_growth_high=mid)

    def gap(g: float) -> float:
        return simulate_fair_value(replace(central, growth_start=g), num_simulations=1, seed=0).per_share_p50 - price

    lo_gap, hi_gap = gap(low), gap(high)
    if lo_gap > 0 or hi_gap < 0:
        return None
    while high - low > tolerance:
        mid_g = (low + high) / 2
        if gap(mid_g) < 0:
            low = mid_g
        else:
            high = mid_g
    return (low + high) / 2
