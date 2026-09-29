"""
Single-company verdict: compare the fair-value distribution to the market price.
"""

from typing import List, Optional, Tuple

import numpy as np

from .assumptions import build_assumptions
from .dcf import simulate_fair_value
from .models import Confidence, DebateReview, FairValue, Fundamentals, Label, MarketSnapshot, Verdict

GAP_THRESHOLD = 0.15
P_UPSIDE_BULL = 0.6
P_UPSIDE_BEAR = 0.4
CONFIDENCE_LEVELS: List[Confidence] = ["Low", "Medium", "High"]
MISSING_FIELDS_DOWNGRADE = 2


def classify(gap: float, p_upside: float) -> Label:
    if gap >= GAP_THRESHOLD and p_upside >= P_UPSIDE_BULL:
        return "UNDERVALUED"
    if gap <= -GAP_THRESHOLD and p_upside <= P_UPSIDE_BEAR:
        return "OVERVALUED"
    return "FAIRLY_VALUED"


def _downgrade(level: Confidence) -> Confidence:
    return CONFIDENCE_LEVELS[max(CONFIDENCE_LEVELS.index(level) - 1, 0)]


def lower_confidence(a: Confidence, b: Confidence) -> Confidence:
    return min(a, b, key=CONFIDENCE_LEVELS.index)


def quantitative_confidence(
    p10: float, p90: float, price: float, missing_fields: List[str]
) -> Tuple[Confidence, List[str]]:
    spread = (p90 - p10) / price
    level: Confidence = "High" if spread < 0.5 else "Medium" if spread < 1.0 else "Low"
    reasons = [f"P10-P90 fair-value spread is {spread:.0%} of price"]
    if len(missing_fields) >= MISSING_FIELDS_DOWNGRADE:
        level = _downgrade(level)
        reasons.append(f"{len(missing_fields)} inputs missing: {', '.join(missing_fields)}")
    return level, reasons


def _is_financial(sic: Optional[int]) -> bool:
    # Banks, credit, brokers, insurers (6000-6411) and REITs (6798): FCF DCF doesn't apply.
    return sic is not None and (6000 <= sic <= 6411 or sic == 6798)


def _unfit_reason(f: Fundamentals, shares: Optional[float]) -> Optional[str]:
    if f.revenue is None or f.revenue <= 0:
        return "Revenue is missing or not positive"
    if f.operating_income is None:
        return "Operating income is missing"
    if not shares:
        return "Share count is missing"
    if _is_financial(f.sic):
        return f"Financial company (SIC {f.sic}): free-cash-flow DCF does not apply"
    base_fcf = f.operating_income + (f.depreciation_amortization or 0) - abs(f.capex or 0)
    if f.operating_income <= 0 and base_fcf <= 0:
        return "Operating income and free cash flow are negative"
    return None


def evaluate(
    f: Fundamentals,
    m: MarketSnapshot,
    num_simulations: int = 10000,
    seed: int = 42,
) -> Verdict:
    shares = f.shares or m.shares_outstanding
    header = dict(
        ticker=f.ticker, company_name=f.name, price=m.price, period_end=f.period_end,
        basis=f.basis, simulations=num_simulations, seed=seed,
    )

    reason = _unfit_reason(f, shares)
    if reason:
        return Verdict(label="NOT_ASSESSABLE", reason=reason, **header)

    assumptions, missing = build_assumptions(f, m, shares=shares)
    dist = simulate_fair_value(assumptions, num_simulations=num_simulations, seed=seed)

    gap = dist.per_share_p50 / m.price - 1
    p_upside = float(np.mean(dist.per_share_samples > m.price))
    confidence, reasons = quantitative_confidence(dist.per_share_p10, dist.per_share_p90, m.price, missing)

    return Verdict(
        label=classify(gap, p_upside),
        gap_pct=gap,
        p_upside=p_upside,
        fair_value=FairValue(
            p10=dist.per_share_p10, p50=dist.per_share_p50, p90=dist.per_share_p90,
            mean=float(np.mean(dist.per_share_samples)),
        ),
        confidence=confidence,
        confidence_reasons=reasons,
        assumptions={
            "growth_start": assumptions.growth_start,
            "ebit_margin": assumptions.ebit_margin,
            "tax_rate": assumptions.tax_rate,
            "wacc": assumptions.wacc,
            "terminal_growth_low": assumptions.terminal_growth_low,
            "terminal_growth_high": assumptions.terminal_growth_high,
            "net_debt": assumptions.net_debt,
            "shares": assumptions.shares,
        },
        missing_fields=missing,
        revenue_forecast_p50=dist.revenue_forecast_p50,
        fcf_forecast_p50=dist.fcf_forecast_p50,
        **header,
    )


def apply_debate(verdict: Verdict, review: DebateReview) -> Verdict:
    """Attach a debate review. It may lower confidence, never raise it or change the numbers."""
    if verdict.confidence is None:
        return verdict.model_copy(update={"debate": review})
    confidence = lower_confidence(verdict.confidence, review.confidence)
    reasons = list(verdict.confidence_reasons)
    if confidence != verdict.confidence:
        reasons.append(f"Debate confidence was {review.confidence}")
    return verdict.model_copy(update={"debate": review, "confidence": confidence, "confidence_reasons": reasons})
