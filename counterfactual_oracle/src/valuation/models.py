"""
Data models for the single-company verdict.
"""

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Label = Literal["UNDERVALUED", "FAIRLY_VALUED", "OVERVALUED", "NOT_ASSESSABLE"]
Confidence = Literal["High", "Medium", "Low"]


class Fundamentals(BaseModel):
    """Annualized company financials (USD). Flows are TTM or fiscal-year per `basis`."""
    ticker: str
    name: str = ""
    cik: Optional[str] = None
    sic: Optional[int] = None
    period_end: Optional[date] = None
    basis: Literal["TTM", "FY"] = "FY"

    revenue: Optional[float] = None
    revenue_prior: Optional[float] = None  # same-length period one year earlier
    revenue_3y_ago: Optional[float] = None
    operating_income: Optional[float] = None
    depreciation_amortization: Optional[float] = None
    capex: Optional[float] = None
    change_in_working_capital: Optional[float] = None  # positive = cash absorbed
    income_tax: Optional[float] = None
    pretax_income: Optional[float] = None
    interest_expense: Optional[float] = None

    cash: Optional[float] = None  # cash + short-term investments
    total_debt: Optional[float] = None
    shares: Optional[float] = None
    shares_as_of: Optional[date] = None  # when the share count was measured (for split adjustment)
    operating_margin_5y: Optional[float] = None  # median of up to 5 fiscal years (needs 3)
    data_note: str = ""  # caveats from parsing, e.g. estimated fields or thin history


class MarketSnapshot(BaseModel):
    price: float
    beta: Optional[float] = None
    risk_free_rate: float = 0.043
    shares_outstanding: Optional[float] = None
    as_of: Optional[date] = None


class FairValue(BaseModel):
    """Per-share fair-value distribution summary."""
    p10: float
    p50: float
    p90: float
    mean: float


class DebateReview(BaseModel):
    """Qualitative review layered on top of the quantitative verdict."""
    narrative: str
    verdict: str
    confidence: Confidence
    agreements: List[str] = Field(default_factory=list)
    disagreements: List[str] = Field(default_factory=list)


class Verdict(BaseModel):
    ticker: str
    company_name: str = ""
    label: Label
    price: Optional[float] = None
    gap_pct: Optional[float] = None  # median fair value / price - 1
    p_upside: Optional[float] = None  # P(fair value > price)
    fair_value: Optional[FairValue] = None
    confidence: Optional[Confidence] = None
    confidence_reasons: List[str] = Field(default_factory=list)
    reason: str = ""  # why NOT_ASSESSABLE
    period_end: Optional[date] = None
    basis: Optional[str] = None
    assumptions: Dict[str, float] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    revenue_forecast_p50: List[float] = Field(default_factory=list)
    fcf_forecast_p50: List[float] = Field(default_factory=list)
    debate: Optional[DebateReview] = None
    simulations: int = 0
    seed: int = 0
