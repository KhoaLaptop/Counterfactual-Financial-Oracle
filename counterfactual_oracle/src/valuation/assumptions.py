"""
Derive DCF assumptions from a company's own fundamentals and market data.
"""

from typing import List, Optional, Tuple

import numpy as np

from .dcf import ValuationAssumptions
from .models import Fundamentals, MarketSnapshot

EQUITY_RISK_PREMIUM = 0.05
DEFAULT_BETA = 1.0
DEFAULT_TAX_RATE = 0.21
DEFAULT_WC_PCT = 0.05
GROWTH_CAP = (-0.20, 0.40)
RECENT_GROWTH_WEIGHT = 0.7
WACC_BOUNDS = (0.05, 0.16)
WACC_SIGMA = 0.01
TERMINAL_GROWTH = (0.015, 0.03)

# Optional inputs whose absence is reported (and lowers confidence).
TRACKED_OPTIONALS = [
    "revenue_prior", "revenue_3y_ago", "depreciation_amortization", "capex",
    "change_in_working_capital", "income_tax", "pretax_income", "interest_expense",
    "cash", "total_debt",
]


def _ratio(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or not den:
        return None
    return num / den


def _growth_start(f: Fundamentals) -> float:
    recent = _ratio(f.revenue, f.revenue_prior)
    recent = recent - 1 if recent is not None else 0.03
    cagr = _ratio(f.revenue, f.revenue_3y_ago)
    if cagr is not None and cagr > 0:
        g = RECENT_GROWTH_WEIGHT * recent + (1 - RECENT_GROWTH_WEIGHT) * (cagr ** (1 / 3) - 1)
    else:
        g = recent
    return float(np.clip(g, *GROWTH_CAP))


def _tax_rate(f: Fundamentals) -> float:
    rate = _ratio(f.income_tax, f.pretax_income)
    if rate is None or f.pretax_income <= 0:
        return DEFAULT_TAX_RATE
    return float(np.clip(rate, 0.0, 0.35))


def _wacc(f: Fundamentals, m: MarketSnapshot, shares: float, tax_rate: float) -> float:
    beta = float(np.clip(m.beta if m.beta is not None else DEFAULT_BETA, 0.5, 2.5))
    cost_of_equity = m.risk_free_rate + beta * EQUITY_RISK_PREMIUM

    debt = f.total_debt or 0.0
    equity = m.price * shares
    cost_of_debt = _ratio(f.interest_expense, debt)
    if cost_of_debt is None:
        cost_of_debt = m.risk_free_rate + 0.02
    cost_of_debt = float(np.clip(cost_of_debt, m.risk_free_rate, m.risk_free_rate + 0.06))

    weight_debt = debt / (equity + debt) if equity + debt > 0 else 0.0
    wacc = (1 - weight_debt) * cost_of_equity + weight_debt * cost_of_debt * (1 - tax_rate)
    return float(np.clip(wacc, *WACC_BOUNDS))


def build_assumptions(
    f: Fundamentals, m: MarketSnapshot, shares: Optional[float] = None
) -> Tuple[ValuationAssumptions, List[str]]:
    """Return DCF assumptions plus the names of optional inputs that were missing."""
    shares = shares or f.shares or m.shares_outstanding
    missing = [name for name in TRACKED_OPTIONALS if getattr(f, name) is None]
    if m.beta is None:
        missing.append("beta")

    revenue = f.revenue
    growth = _growth_start(f)
    margin = f.operating_income / revenue
    tax_rate = _tax_rate(f)

    revenue_change = revenue - f.revenue_prior if f.revenue_prior else None
    wc_pct = _ratio(f.change_in_working_capital, revenue_change) if revenue_change and revenue_change > 0 else None
    wc_pct = float(np.clip(wc_pct, 0.0, 0.3)) if wc_pct is not None else DEFAULT_WC_PCT

    assumptions = ValuationAssumptions(
        revenue=revenue,
        growth_start=growth,
        growth_sigma=max(0.02, 0.2 * abs(growth)),
        terminal_growth_low=TERMINAL_GROWTH[0],
        terminal_growth_high=TERMINAL_GROWTH[1],
        ebit_margin=margin,
        margin_sigma=max(0.01, 0.1 * abs(margin)),
        tax_rate=tax_rate,
        da_pct=(f.depreciation_amortization or 0.0) / revenue,
        capex_pct=abs(f.capex or 0.0) / revenue,
        wc_pct=wc_pct,
        wacc=_wacc(f, m, shares, tax_rate),
        wacc_sigma=WACC_SIGMA,
        net_debt=(f.total_debt or 0.0) - (f.cash or 0.0),
        shares=shares,
    )
    return assumptions, missing
