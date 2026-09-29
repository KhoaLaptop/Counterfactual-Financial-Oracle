"""
Vectorized Monte Carlo DCF producing a per-share fair-value distribution.

MODEL (per simulated path):
    g_t      = g0 + (gT - g0) * (t - 1) / (years - 1)      growth fades to terminal by the last year
    Rev_t    = Rev_{t-1} * (1 + g_t)
    FCF_t    = Rev_t * (m * (1 - tax) + da - capex) - wc * (Rev_t - Rev_{t-1})
    TV       = FCF_T * (1 + gT) / (r - gT)
    EV       = sum(FCF_t / (1 + r)^t) + TV / (1 + r)^T
    PerShare = (EV - net_debt) / shares

Sampled per path: g0 ~ N, m ~ N, r ~ N (floored at gT + 1pt), gT ~ U.
"""

from dataclasses import dataclass
from typing import List

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
    years: int = 5


@dataclass
class FairValueDistribution:
    per_share_samples: np.ndarray
    wacc_samples: np.ndarray
    enterprise_value_p50: float
    per_share_p10: float
    per_share_p50: float
    per_share_p90: float
    revenue_forecast_p50: List[float]
    fcf_forecast_p50: List[float]


def simulate_fair_value(
    a: ValuationAssumptions, num_simulations: int = 10000, seed: int = 42
) -> FairValueDistribution:
    rng = np.random.default_rng(seed)
    n, years = num_simulations, a.years

    g0 = rng.normal(a.growth_start, a.growth_sigma, n)
    g_term = rng.uniform(a.terminal_growth_low, a.terminal_growth_high, n)
    margin = rng.normal(a.ebit_margin, a.margin_sigma, n)
    wacc = np.maximum(rng.normal(a.wacc, a.wacc_sigma, n), g_term + MIN_WACC_SPREAD)

    # (n, years) growth path fading linearly from g0 to g_term
    fade = np.arange(years) / max(years - 1, 1)
    growth = g0[:, None] + (g_term - g0)[:, None] * fade[None, :]

    revenue = a.revenue * np.cumprod(1 + growth, axis=1)
    prev_revenue = np.hstack([np.full((n, 1), a.revenue), revenue[:, :-1]])
    cash_margin = margin * (1 - a.tax_rate) + a.da_pct - a.capex_pct
    fcf = revenue * cash_margin[:, None] - a.wc_pct * (revenue - prev_revenue)

    discount = (1 + wacc)[:, None] ** np.arange(1, years + 1)[None, :]
    terminal_value = fcf[:, -1] * (1 + g_term) / (wacc - g_term)
    enterprise_value = (fcf / discount).sum(axis=1) + terminal_value / discount[:, -1]
    per_share = (enterprise_value - a.net_debt) / a.shares

    p10, p50, p90 = np.percentile(per_share, [10, 50, 90])
    return FairValueDistribution(
        per_share_samples=per_share,
        wacc_samples=wacc,
        enterprise_value_p50=float(np.median(enterprise_value)),
        per_share_p10=float(p10),
        per_share_p50=float(p50),
        per_share_p90=float(p90),
        revenue_forecast_p50=np.median(revenue, axis=0).tolist(),
        fcf_forecast_p50=np.median(fcf, axis=0).tolist(),
    )
