"""
Tests for the universe ranker (B1): universes, scoring, ranking, exclusions, debate.
"""

import json
from datetime import date

import pytest

from counterfactual_oracle.src.valuation.models import DebateReview, Fundamentals, MarketSnapshot
from counterfactual_oracle.src.valuation.oracle import Oracle
from counterfactual_oracle.src.valuation.rank import main as rank_main
from counterfactual_oracle.src.valuation.screener import rank_universe, risk_adjusted_gap
from counterfactual_oracle.src.valuation.universe import load_sp500, load_watchlist, parse_sp500_html


def _fundamentals(ticker, **overrides):
    base = dict(
        ticker=ticker, name=f"{ticker} Inc", sic=3571, period_end=date(2025, 6, 30), basis="TTM",
        revenue=1000.0, revenue_prior=900.0, revenue_3y_ago=750.0, operating_income=200.0,
        depreciation_amortization=50.0, capex=60.0, change_in_working_capital=10.0,
        income_tax=40.0, pretax_income=200.0, interest_expense=10.0, cash=100.0,
        total_debt=200.0, shares=100.0,
    )
    base.update(overrides)
    return Fundamentals(**base)


class FakeSec:
    """CHEAP/MID/RICH differ only in price; BANK is a financial; BOOM raises."""

    def fundamentals(self, ticker):
        if ticker == "BOOM":
            raise ConnectionError("SEC dropped the connection")
        return _fundamentals(ticker, sic=6021 if ticker == "BANK" else 3571)


class FakeMarket:
    PRICES = {"CHEAP": 8.0, "MID": 25.0, "RICH": 80.0, "BANK": 50.0}

    def snapshot(self, ticker):
        return MarketSnapshot(price=self.PRICES[ticker], beta=1.1, risk_free_rate=0.04)


class CountingReviewer:
    def __init__(self):
        self.tickers = []

    def review(self, fundamentals, verdict):
        self.tickers.append(fundamentals.ticker)
        return DebateReview(narrative="Reviewed.", confidence="Low")


# --- universes ------------------------------------------------------------------

def test_load_watchlist_normalizes_and_skips_comments(tmp_path):
    path = tmp_path / "watch.txt"
    path.write_text("# my picks\nnvda\n\nBRK.B  # class B\nNVDA\n  aapl \n")

    assert load_watchlist(path) == ["NVDA", "BRK-B", "AAPL"]


def test_load_sp500_reads_dated_csv(tmp_path):
    path = tmp_path / "sp500.csv"
    path.write_text("# as_of: 2026-09-29, source: test\nticker,name,sector\nAAPL,Apple Inc.,Information Technology\n"
                    "BRK-B,Berkshire Hathaway,Financials\n")

    universe = load_sp500(path)

    assert universe.tickers == ["AAPL", "BRK-B"]
    assert universe.as_of == "2026-09-29"
    assert universe.sectors["BRK-B"] == "Financials"


def test_parse_sp500_html_extracts_constituents_table():
    html = """
    <table class="wikitable" id="constituents"><tbody>
    <tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>GICS Sub-Industry</th></tr>
    <tr><td><a href="#">MMM</a></td><td><a>3M</a></td><td>Industrials</td><td>Conglomerates</td></tr>
    <tr><td><a href="#">BRK.B</a></td><td><a>Berkshire Hathaway</a></td><td>Financials</td><td>Insurance</td></tr>
    </tbody></table>
    <table id="changes"><tr><th>Date</th></tr><tr><td>X</td></tr></table>
    """

    rows = parse_sp500_html(html)

    assert rows == [("MMM", "3M", "Industrials"), ("BRK-B", "Berkshire Hathaway", "Financials")]


# --- scoring & ranking -------------------------------------------------------------

def test_risk_adjusted_gap():
    class V:
        price_position, price, gap_pct = "PRICE_BELOW_MODEL_RANGE", 100.0, 0.30

        class fair_value:
            p10, p90 = 80.0, 180.0

    assert risk_adjusted_gap(V) == pytest.approx(0.30 / 1.0)


def test_rank_universe_orders_by_score_and_excludes_with_reasons():
    oracle = Oracle(FakeSec(), FakeMarket())

    ranking = rank_universe(["RICH", "BOOM", "CHEAP", "BANK", "MID"], oracle, workers=3, num_simulations=2000)

    assert [e.ticker for e in ranking.entries] == ["CHEAP", "MID", "RICH"]
    assert [e.rank for e in ranking.entries] == [1, 2, 3]
    assert ranking.entries[0].score > ranking.entries[1].score > ranking.entries[2].score
    excluded = {x.ticker: x.reason for x in ranking.excluded}
    assert "financial" in excluded["BANK"].lower()
    assert excluded["BOOM"] == "ConnectionError: SEC dropped the connection"


def test_ranking_is_deterministic_across_worker_counts():
    tickers = ["RICH", "CHEAP", "MID"]
    one = rank_universe(tickers, Oracle(FakeSec(), FakeMarket()), workers=1, num_simulations=1000)
    many = rank_universe(tickers, Oracle(FakeSec(), FakeMarket()), workers=3, num_simulations=1000)

    assert [(e.ticker, e.score) for e in one.entries] == [(e.ticker, e.score) for e in many.entries]


def test_debate_runs_only_on_top_n_and_never_reorders():
    reviewer = CountingReviewer()
    oracle = Oracle(FakeSec(), FakeMarket())

    ranking = rank_universe(["RICH", "CHEAP", "MID"], oracle, num_simulations=1000,
                            debate_top=2, reviewer=reviewer)

    assert sorted(reviewer.tickers) == ["CHEAP", "MID"]
    assert [e.ticker for e in ranking.entries] == ["CHEAP", "MID", "RICH"]
    assert ranking.entries[0].debate.narrative == "Reviewed."
    assert ranking.entries[0].confidence == "Low"  # debate may lower confidence
    assert ranking.entries[2].debate is None


def test_progress_callback_sees_every_ticker():
    seen = []
    rank_universe(["RICH", "BOOM", "CHEAP"], Oracle(FakeSec(), FakeMarket()), num_simulations=500,
                  on_progress=lambda done, total, ticker: seen.append((done, total)))

    assert sorted(seen) == [(1, 3), (2, 3), (3, 3)]


# --- CLI ----------------------------------------------------------------------------

def test_rank_cli_watchlist_prints_ranked_json(tmp_path, capsys):
    watchlist = tmp_path / "w.txt"
    watchlist.write_text("RICH\nCHEAP\nBANK\n")

    code = rank_main(["--watchlist", str(watchlist), "--simulations", "500", "--top", "1"],
                     oracle=Oracle(FakeSec(), FakeMarket()))

    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert [e["ticker"] for e in out["entries"]] == ["CHEAP"]  # --top trims the list
    assert out["universe"] == "watchlist"
    assert [x["ticker"] for x in out["excluded"]] == ["BANK"]


def test_zero_fair_value_ranks_last_instead_of_being_excluded():
    class V:
        price_position, price, gap_pct = "PRICE_ABOVE_MODEL_RANGE", 50.0, -1.0

        class fair_value:
            p10 = p90 = 0.0

    assert risk_adjusted_gap(V) == pytest.approx(-1.0 / 0.05)



def test_ranked_entries_report_price_position_not_a_label():
    ranking = rank_universe(["CHEAP"], Oracle(FakeSec(), FakeMarket()), num_simulations=500)
    entry = ranking.entries[0].model_dump()

    assert entry["price_position"] == "PRICE_BELOW_MODEL_RANGE"
    assert "label" not in entry
    assert "not a buy/sell signal" in ranking.context_note
