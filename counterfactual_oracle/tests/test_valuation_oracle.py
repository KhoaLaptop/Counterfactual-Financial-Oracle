"""
Tests for the Oracle orchestrator, debate layer, filing input, and CLI.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from counterfactual_oracle.src.models import DebateResult, FinancialReport
from counterfactual_oracle.src.valuation.cli import main
from counterfactual_oracle.src.valuation.debate import (
    DebateAgentReviewer,
    to_aggregated_simulation,
    to_financial_report,
)
from counterfactual_oracle.src.valuation.models import DebateReview, Fundamentals, MarketSnapshot
from counterfactual_oracle.src.valuation.oracle import Oracle, fundamentals_from_report

SAMPLE_REPORT = str(Path(__file__).resolve().parents[1] / "data" / "nvidia_fy26_q3.json")

FUNDAMENTALS = Fundamentals(
    ticker="TEST", name="Test Corp", sic=3571, period_end=date(2025, 6, 30), basis="TTM",
    revenue=1000.0, revenue_prior=900.0, revenue_3y_ago=750.0, operating_income=200.0,
    depreciation_amortization=50.0, capex=60.0, change_in_working_capital=10.0,
    income_tax=40.0, pretax_income=200.0, interest_expense=10.0, cash=100.0,
    total_debt=200.0, shares=100.0,
)


class FakeSec:
    def __init__(self, fundamentals=FUNDAMENTALS):
        self.f = fundamentals

    def fundamentals(self, ticker):
        return self.f.model_copy(update={"ticker": ticker.upper()})


class FakeMarket:
    def snapshot(self, ticker):
        return MarketSnapshot(price=8.0, beta=1.2, risk_free_rate=0.04)


class FakeReviewer:
    def __init__(self, confidence="Low"):
        self.confidence = confidence
        self.calls = 0

    def review(self, fundamentals, verdict):
        self.calls += 1
        return DebateReview(narrative="Critic flagged margin risk.", confidence=self.confidence)


def test_oracle_judges_ticker_without_debate():
    verdict = Oracle(FakeSec(), FakeMarket()).judge("test", num_simulations=2000)

    assert verdict.ticker == "TEST"
    assert verdict.price_position != "NOT_ASSESSABLE"
    assert verdict.debate is None


def test_debate_can_only_lower_confidence():
    base = Oracle(FakeSec(), FakeMarket()).judge("test", num_simulations=2000)
    lowered = Oracle(FakeSec(), FakeMarket(), reviewer=FakeReviewer("Low")).judge("test", num_simulations=2000)
    raised = Oracle(FakeSec(), FakeMarket(), reviewer=FakeReviewer("High")).judge("test", num_simulations=2000)

    assert lowered.confidence == "Low"
    assert lowered.debate.narrative == "Critic flagged margin risk."
    assert raised.confidence == base.confidence
    # numbers are untouched by the debate
    assert lowered.fair_value == base.fair_value
    assert lowered.price_position == base.price_position


def test_debate_skipped_for_not_assessable():
    reviewer = FakeReviewer()
    bank = FUNDAMENTALS.model_copy(update={"sic": 6021})

    verdict = Oracle(FakeSec(bank), FakeMarket(), reviewer=reviewer).judge("bank", num_simulations=100)

    assert verdict.price_position == "NOT_ASSESSABLE"
    assert reviewer.calls == 0


def test_debate_adapter_feeds_existing_agent_and_maps_result():
    verdict = Oracle(FakeSec(), FakeMarket()).judge("test", num_simulations=2000)

    class FakeAgent:
        def run_debate(self, report, simulation, params, max_rounds):
            self.args = (report, simulation, max_rounds)
            return DebateResult(total_rounds=2, converged=True, consensus_summary="Agreed.",
                                final_verdict="Cautious Buy", confidence_level="medium")

    agent = FakeAgent()
    review = DebateAgentReviewer(agent, max_rounds=3).review(FUNDAMENTALS, verdict)

    report, simulation, rounds = agent.args
    assert rounds == 3
    assert report.income_statement.EBIT == 200.0
    assert simulation.median_npv == pytest.approx(verdict.fair_value.p50 * 100 + 100)
    assert review.confidence == "Medium"
    assert "verdict" not in review.model_dump()  # no buy/sell call from the LLMs


def test_financial_report_mapping_is_internally_consistent():
    report = to_financial_report(FUNDAMENTALS)
    sim = to_aggregated_simulation(Oracle(FakeSec(), FakeMarket()).judge("t", num_simulations=500))

    assert report.income_statement.EBITDA == pytest.approx(250.0)
    assert report.cash_flow.FreeCashFlow == pytest.approx(160 + 50 - 10 - 60)
    assert len(sim.fcf_forecast_p50) == 5


def test_fundamentals_from_filing_report_annualizes_quarterly():
    report = FinancialReport.model_validate(json.loads(Path(SAMPLE_REPORT).read_text()))

    annual = fundamentals_from_report(report, ticker="NVDA", shares=10.0)
    quarterly = fundamentals_from_report(report, ticker="NVDA", shares=10.0, quarterly=True)

    assert annual.revenue == report.income_statement.Revenue
    assert annual.operating_income == report.income_statement.EBIT
    assert quarterly.revenue == pytest.approx(4 * annual.revenue)
    assert quarterly.cash == annual.cash  # balance sheet is not annualized


def test_cli_ticker_prints_verdict_json(capsys):
    code = main(["TEST", "--simulations", "1000"], oracle=Oracle(FakeSec(), FakeMarket()))

    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["ticker"] == "TEST"
    assert set(out) >= {"price_position", "gap_pct", "p_upside", "fair_value", "confidence",
                        "market_implied_growth", "sensitivity", "context_note"}
    assert "label" not in out


def test_cli_filing_requires_price_and_shares(capsys):
    with pytest.raises(SystemExit):
        main(["--report", SAMPLE_REPORT])


def test_cli_filing_prints_verdict_json(capsys):
    code = main([
        "--report", SAMPLE_REPORT,
        "--price", "50", "--shares", "1e9", "--simulations", "500",
    ])

    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["price"] == 50
