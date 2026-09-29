"""
Optional qualitative layer: run the existing optimist-vs-critic debate on a verdict.

The debate never changes the numbers; `apply_debate` may only lower confidence.
"""

from typing import Protocol

from ..models import (
    AggregatedSimulation,
    BalanceSheet,
    CashFlow,
    DebateResult,
    FinancialReport,
    IncomeStatement,
    ScenarioParams,
)
from .models import Confidence, DebateReview, Fundamentals, Verdict


class Reviewer(Protocol):
    def review(self, fundamentals: Fundamentals, verdict: Verdict) -> DebateReview: ...


def to_financial_report(f: Fundamentals) -> FinancialReport:
    """Map annualized fundamentals onto the legacy report shape the debate prompts read."""
    revenue = f.revenue or 0.0
    ebit = f.operating_income or 0.0
    da = f.depreciation_amortization or 0.0
    capex = abs(f.capex or 0.0)
    tax = f.income_tax or 0.0
    interest = f.interest_expense or 0.0
    net_income = (f.pretax_income if f.pretax_income is not None else ebit - interest) - tax
    cfo = net_income + da - (f.change_in_working_capital or 0.0)
    return FinancialReport(
        income_statement=IncomeStatement(
            Revenue=revenue, CostOfGoodsSold=0.0, GrossProfit=revenue, OpEx=revenue - ebit - da,
            EBITDA=ebit + da, DepreciationAndAmortization=da, EBIT=ebit, InterestExpense=interest,
            Taxes=tax, NetIncome=net_income,
        ),
        balance_sheet=BalanceSheet(
            Assets={"Cash": f.cash or 0.0}, Liabilities={"TotalDebt": f.total_debt or 0.0}, Equity={},
            Cash=f.cash or 0.0, LongTermDebt=f.total_debt,
        ),
        cash_flow=CashFlow(
            NetIncome=net_income, Depreciation=da, ChangeInWorkingCapital=f.change_in_working_capital or 0.0,
            CashFromOperations=cfo, CapEx=capex, CashFromInvesting=-capex, DebtRepayment=0.0, Dividends=0.0,
            CashFromFinancing=0.0, NetChangeInCash=0.0, FreeCashFlow=cfo - capex,
        ),
        kpis={"TaxRate": (tax / f.pretax_income) if f.pretax_income else 0.21},
    )


def to_aggregated_simulation(verdict: Verdict) -> AggregatedSimulation:
    """Express the per-share distribution in the enterprise-value terms the debate prompts use."""
    shares = verdict.assumptions["shares"]
    net_debt = verdict.assumptions["net_debt"]

    def ev(per_share: float) -> float:
        return per_share * shares + net_debt

    fv = verdict.fair_value
    return AggregatedSimulation(
        median_npv=ev(fv.p50), p10_npv=ev(fv.p10), p90_npv=ev(fv.p90),
        median_revenue=verdict.revenue_forecast_p50[0], median_ebitda=0.0, median_fcf=verdict.fcf_forecast_p50[0],
        revenue_forecast_p50=verdict.revenue_forecast_p50,
        ebitda_forecast_p50=[0.0] * len(verdict.revenue_forecast_p50),
        fcf_forecast_p50=verdict.fcf_forecast_p50,
        assumption_log=[f"{k}: {v:,.4g}" for k, v in verdict.assumptions.items()],
        traceability={"FairValue": "(EV - net debt) / shares", "EV": "5y FCF DCF + Gordon terminal value"},
        simulation_runs=[],
    )


def _confidence(level: str) -> Confidence:
    normalized = (level or "").strip().capitalize()
    return normalized if normalized in ("High", "Medium", "Low") else "Medium"


def to_review(result: DebateResult) -> DebateReview:
    return DebateReview(
        narrative=result.consensus_summary,
        verdict=result.final_verdict,
        confidence=_confidence(result.confidence_level),
        agreements=result.key_agreements,
        disagreements=result.key_disagreements,
    )


class DebateAgentReviewer:
    """Adapts the existing DebateAgent (Gemini optimist vs DeepSeek critic) to the Reviewer protocol."""

    def __init__(self, agent, max_rounds: int = 4):
        self.agent = agent
        self.max_rounds = max_rounds

    def review(self, fundamentals: Fundamentals, verdict: Verdict) -> DebateReview:
        result = self.agent.run_debate(
            to_financial_report(fundamentals),
            to_aggregated_simulation(verdict),
            ScenarioParams(),
            max_rounds=self.max_rounds,
        )
        return to_review(result)
