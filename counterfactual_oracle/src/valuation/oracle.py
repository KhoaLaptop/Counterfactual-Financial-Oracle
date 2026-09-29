"""
The Oracle: ticker (or filing) in, single-company verdict out.
"""

from typing import Optional, Protocol

from ..models import FinancialReport
from .debate import Reviewer
from .market import MarketData
from .models import Fundamentals, MarketSnapshot, Verdict
from .verdict import apply_debate, evaluate


class FundamentalsSource(Protocol):
    def fundamentals(self, ticker: str) -> Fundamentals: ...


class Oracle:
    def __init__(self, sec: FundamentalsSource, market: MarketData, reviewer: Optional[Reviewer] = None):
        self.sec = sec
        self.market = market
        self.reviewer = reviewer

    def judge(self, ticker: str, num_simulations: int = 10000, seed: int = 42) -> Verdict:
        fundamentals = self.sec.fundamentals(ticker)
        return self.judge_fundamentals(fundamentals, self.market.snapshot(ticker), num_simulations, seed)

    def judge_fundamentals(
        self, fundamentals: Fundamentals, market: MarketSnapshot, num_simulations: int = 10000, seed: int = 42
    ) -> Verdict:
        verdict = evaluate(fundamentals, market, num_simulations=num_simulations, seed=seed)
        if self.reviewer and verdict.label != "NOT_ASSESSABLE":
            verdict = apply_debate(verdict, self.reviewer.review(fundamentals, verdict))
        return verdict


def fundamentals_from_report(
    report: FinancialReport,
    ticker: str,
    shares: float,
    quarterly: bool = False,
    scale: float = 1.0,
) -> Fundamentals:
    """
    Map a parsed filing (the existing FinancialReport shape) onto Fundamentals.

    `quarterly` annualizes flows (x4); `scale` converts reported units (e.g. 1e6 for
    "in millions") so money and `shares` share a unit.
    """
    flow = (4.0 if quarterly else 1.0) * scale
    inc, bs, cf = report.income_statement, report.balance_sheet, report.cash_flow
    growth = report.kpis.get("RevenueGrowth")
    debt = [v for v in (bs.ShortTermDebt, bs.LongTermDebt) if v is not None]
    return Fundamentals(
        ticker=ticker.upper(),
        basis="FY",
        revenue=inc.Revenue * flow,
        revenue_prior=inc.Revenue * flow / (1 + growth) if growth is not None else None,
        operating_income=inc.EBIT * flow,
        depreciation_amortization=inc.DepreciationAndAmortization * flow,
        capex=abs(cf.CapEx) * flow,
        # cash-flow statements show cash absorbed by working capital as negative
        change_in_working_capital=-cf.ChangeInWorkingCapital * flow,
        income_tax=inc.Taxes * flow,
        pretax_income=(inc.NetIncome + inc.Taxes) * flow,
        interest_expense=abs(inc.InterestExpense) * flow,
        cash=bs.Cash * scale if bs.Cash is not None else None,
        total_debt=sum(debt) * scale if debt else None,
        shares=shares,
    )
