"""
Tests for the Streamlit valuation views: pure display helpers, the PDF report,
and app-level smoke tests (no network).
"""

from datetime import date
from pathlib import Path

import pytest

from counterfactual_oracle.src.models import (
    AggregatedSimulation,
    CriticVerdict,
    DebateResult,
    FinancialReport,
)
from counterfactual_oracle.src.ui.valuation_view import (
    debate_summary,
    position_sentence,
    screener_rows,
    sensitivity_rows,
    summary_metrics,
)
from counterfactual_oracle.src.valuation.models import Fundamentals, MarketSnapshot
from counterfactual_oracle.src.valuation.oracle import Oracle
from counterfactual_oracle.src.valuation.screener import rank_universe
from counterfactual_oracle.src.valuation.verdict import evaluate

APP = Path(__file__).resolve().parents[1] / "app.py"
SAMPLE_REPORT = Path(__file__).resolve().parents[1] / "data" / "nvidia_fy26_q3.json"


def _fundamentals(ticker="TEST", **overrides):
    base = dict(
        ticker=ticker, name="Test Corp", sic=3571, period_end=date(2025, 6, 30), basis="TTM",
        revenue=1000.0, revenue_prior=900.0, revenue_3y_ago=750.0, operating_income=200.0,
        depreciation_amortization=50.0, capex=60.0, change_in_working_capital=10.0,
        income_tax=40.0, pretax_income=200.0, interest_expense=10.0, cash=100.0,
        total_debt=200.0, shares=100.0,
    )
    base.update(overrides)
    return Fundamentals(**base)


def _verdict(price=30.0, **overrides):
    return evaluate(_fundamentals(**overrides), MarketSnapshot(price=price, beta=1.1, risk_free_rate=0.04),
                    num_simulations=500)


# --- display helpers ------------------------------------------------------------------

@pytest.mark.parametrize("price, fragment", [
    (2.0, "below the model's P10–P90 range"),
    (30.0, "within the model's P10–P90 range"),
    (500.0, "above the model's P10–P90 range"),
])
def test_position_sentence_is_descriptive(price, fragment):
    sentence = position_sentence(_verdict(price=price))
    assert fragment in sentence
    assert not any(word in sentence.lower() for word in ("buy", "sell", "undervalued", "overvalued"))


def test_position_sentence_for_not_assessable():
    assert "Not assessable" in position_sentence(_verdict(sic=6021))


def test_summary_metrics_show_price_range_and_implied_growth():
    metrics = dict((label, value) for label, value, _ in summary_metrics(_verdict()))

    assert metrics["Market price"] == "$30.00"
    assert metrics["Model value (P50)"].startswith("$")
    assert "–" in metrics["Model range (P10–P90)"]
    assert metrics["Market-implied growth"].endswith("%")
    assert metrics["Recent growth used"].endswith("%")


def test_sensitivity_rows_show_change_against_base():
    rows = {r["Scenario"]: r for r in sensitivity_rows(_verdict())}

    assert rows["base"]["Change vs base"] == "+0.0%"
    assert rows["wacc +1pt"]["Change vs base"].startswith("-")
    assert rows["growth +5pt"]["Change vs base"].startswith("+")


def test_screener_rows_list_positions_without_buy_sell_labels():
    class Sec:
        def fundamentals(self, ticker):
            return _fundamentals(ticker)

    class Market:
        def snapshot(self, ticker):
            return MarketSnapshot(price={"A": 8.0, "B": 80.0}[ticker], beta=1.1, risk_free_rate=0.04)

    rows = screener_rows(rank_universe(["A", "B"], Oracle(Sec(), Market()), num_simulations=300))

    assert [r["Ticker"] for r in rows] == ["A", "B"]
    assert rows[0]["Price position"] == "Below model range"
    assert all("label" not in r for r in rows)


def test_debate_summary_drops_the_buy_sell_verdict():
    result = DebateResult(total_rounds=3, converged=True, consensus_summary="Margins are the key risk.",
                          final_verdict="Strong Buy", confidence_level="Medium")

    summary = debate_summary(result)

    assert summary == {"summary": "Margins are the key risk.", "confidence": "Medium"}


# --- PDF report -------------------------------------------------------------------------

def test_pdf_report_has_no_investment_verdict(tmp_path):
    from pypdf import PdfReader

    from counterfactual_oracle.src.agents.evaluator import EvaluatorAgent

    report = FinancialReport.model_validate_json(SAMPLE_REPORT.read_text())
    simulation = AggregatedSimulation(
        median_npv=1e9, p10_npv=5e8, p90_npv=2e9, median_revenue=1e9, median_ebitda=2e8, median_fcf=1e8,
        revenue_forecast_p50=[1e9] * 5, ebitda_forecast_p50=[2e8] * 5, fcf_forecast_p50=[1e8] * 5,
        assumption_log=["test"], traceability={}, simulation_runs=[],
    )
    critic = CriticVerdict(verdict="approve", balance_sheet_check={}, cash_flow_check={},
                           comparative_analysis=[], unsupported_assumptions=[])
    debate = DebateResult(total_rounds=2, converged=True, consensus_summary="Agreed on margin risk.",
                          final_verdict="Strong Buy", confidence_level="High")
    path = tmp_path / "report.pdf"

    EvaluatorAgent().generate_pdf(simulation, critic, report, str(path), debate)
    text = " ".join(page.extract_text() for page in PdfReader(path).pages)

    assert "Strong Buy" not in text
    assert "Investment Verdict" not in text
    assert "not a buy/sell signal" in text.replace("\n", " ")


# --- app smoke tests (Streamlit AppTest, no network) ------------------------------------------

@pytest.fixture(autouse=True)
def _app_import_path(monkeypatch):
    # `streamlit run app.py` puts the script's folder on sys.path, so `import src...` works;
    # AppTest doesn't, so mirror it.
    monkeypatch.syspath_prepend(str(APP.parent))


def _app():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP), default_timeout=60)


def _mode_radio(at):
    return next(r for r in at.sidebar.radio if "Mode" in r.label)


def test_app_starts_in_ticker_mode_with_context_note():
    at = _app().run()

    assert not at.exception
    assert _mode_radio(at).value.startswith("🔎")
    assert any("Ticker" in t.label for t in at.text_input)
    assert any("not a buy/sell signal" in (i.value or "") for i in at.info)


@pytest.mark.parametrize("mode_prefix, expected_widget", [("📊", "text_area"), ("📄", "file_uploader")])
def test_app_switches_modes(mode_prefix, expected_widget):
    at = _app().run()
    radio = _mode_radio(at)
    radio.set_value(next(o for o in radio.options if o.startswith(mode_prefix))).run()

    assert not at.exception
    if expected_widget == "text_area":
        assert len(at.text_area) == 1
    else:
        assert at.get("file_uploader")


def test_app_has_no_fake_status_footer():
    at = _app().run()
    html = " ".join(m.value for m in at.markdown)

    assert "All systems operational" not in html
    assert "Last updated: 2024" not in html
