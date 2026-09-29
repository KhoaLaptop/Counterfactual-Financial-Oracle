"""
Tests for parsing SEC EDGAR XBRL companyfacts into annualized fundamentals.
"""

from datetime import date

import pytest

from counterfactual_oracle.src.valuation.edgar import SecClient, flow_at, parse_company_facts


def _e(start, end, val, filed="2025-08-01", form="10-Q"):
    entry = {"end": end, "val": val, "filed": filed, "form": form, "accn": f"acc-{filed}"}
    if start:
        entry["start"] = start
    return entry


def _concept(*entries, unit="USD"):
    return {"units": {unit: list(entries)}}


def _facts():
    """Calendar-year company, latest filing is the Q2 2025 10-Q."""
    revenue_new = _concept(
        _e("2023-01-01", "2023-12-31", 900, filed="2024-02-01", form="10-K"),
        _e("2024-01-01", "2024-12-31", 1000, filed="2025-02-01", form="10-K"),
        # 2024 re-reported in a later filing: latest filed wins
        _e("2024-01-01", "2024-12-31", 1000, filed="2025-08-01", form="10-Q"),
        _e("2023-01-01", "2023-06-30", 430, filed="2023-08-01"),
        _e("2024-01-01", "2024-06-30", 480, filed="2024-08-01"),
        _e("2025-01-01", "2025-06-30", 550, filed="2025-08-01"),
        _e("2025-04-01", "2025-06-30", 290, filed="2025-08-01"),  # quarter-only noise
    )
    # Older years were tagged with a different revenue concept.
    revenue_old = _concept(
        _e("2021-01-01", "2021-12-31", 700, filed="2022-02-01", form="10-K"),
        _e("2022-01-01", "2022-12-31", 800, filed="2023-02-01", form="10-K"),
    )
    op_income = _concept(
        _e("2024-01-01", "2024-12-31", 200, form="10-K"),
        _e("2024-01-01", "2024-06-30", 90),
        _e("2025-01-01", "2025-06-30", 110),
    )
    capex = _concept(_e("2024-01-01", "2024-12-31", 60, form="10-K"))  # no YTD -> FY fallback
    cash = _concept(
        _e(None, "2024-12-31", 120, form="10-K"),
        _e(None, "2025-06-30", 150),
    )
    debt = _concept(_e(None, "2025-06-30", 300))
    shares = _concept(
        _e(None, "2025-07-20", 60, filed="2025-08-01"),  # class A
        _e(None, "2025-07-20", 40, filed="2025-08-01"),  # class B
        _e(None, "2025-04-20", 99, filed="2025-05-01"),  # older cover page
        unit="shares",
    )
    return {
        "entityName": "Example Inc",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": revenue_new,
                "Revenues": revenue_old,
                "OperatingIncomeLoss": op_income,
                "PaymentsToAcquirePropertyPlantAndEquipment": capex,
                "CashAndCashEquivalentsAtCarryingValue": cash,
                "LongTermDebt": debt,
            },
            "dei": {"EntityCommonStockSharesOutstanding": shares},
        },
    }


def test_flow_at_stitches_trailing_twelve_months():
    entries = _facts()["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    assert flow_at(entries, date(2025, 6, 30)) == pytest.approx(1000 + 550 - 480)
    assert flow_at(entries, date(2024, 12, 31)) == pytest.approx(1000)
    assert flow_at(entries, date(2022, 3, 31)) is None


def test_parse_company_facts_builds_ttm_fundamentals():
    f = parse_company_facts(_facts(), ticker="EXM", sic=3571)

    assert f.name == "Example Inc"
    assert f.basis == "TTM"
    assert f.period_end == date(2025, 6, 30)
    assert f.revenue == pytest.approx(1070)
    assert f.revenue_prior == pytest.approx(900 + 480 - 430)
    assert f.operating_income == pytest.approx(200 + 110 - 90)


def test_parse_merges_revenue_tags_and_falls_back_to_nearby_annual():
    f = parse_company_facts(_facts(), ticker="EXM")
    # 3y before 2025-06-30 has no TTM data; nearest fiscal year (2021, old tag) is used
    assert f.revenue_3y_ago == pytest.approx(700)


def test_parse_falls_back_to_latest_annual_for_flows_without_ytd():
    f = parse_company_facts(_facts(), ticker="EXM")
    assert f.capex == pytest.approx(60)


def test_parse_balance_sheet_and_shares():
    f = parse_company_facts(_facts(), ticker="EXM")

    assert f.cash == pytest.approx(150)
    assert f.total_debt == pytest.approx(300)
    assert f.shares == pytest.approx(100)  # both share classes from the latest cover page
    assert f.depreciation_amortization is None


def test_parse_uses_fiscal_year_basis_when_no_quarter_after_it():
    facts = _facts()
    rev = facts["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    rev[:] = [e for e in rev if e["form"] == "10-K" or e["end"] < "2025-01-01"]

    f = parse_company_facts(facts, ticker="EXM")

    assert f.basis == "FY"
    assert f.period_end == date(2024, 12, 31)
    assert f.revenue == pytest.approx(1000)


class _FakeHttp:
    def __init__(self):
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        if url.endswith("company_tickers.json"):
            return {"0": {"cik_str": 1234, "ticker": "EXM", "title": "Example Inc"}}
        if "/submissions/" in url:
            return {"name": "Example Inc", "sic": "3571"}
        if "/companyfacts/" in url:
            return _facts()
        raise AssertionError(url)


def test_sec_client_resolves_ticker_and_fetches_fundamentals():
    http = _FakeHttp()
    client = SecClient(fetch_json=http)

    f = client.fundamentals("exm")

    assert f.ticker == "EXM"
    assert f.cik == "0000001234"
    assert f.sic == 3571
    assert any("CIK0000001234.json" in u for u in http.urls)


def test_sec_client_unknown_ticker():
    with pytest.raises(LookupError):
        SecClient(fetch_json=_FakeHttp()).fundamentals("NOPE")


# --- HTTP fetcher retries -----------------------------------------------------------

import requests  # noqa: E402

from counterfactual_oracle.src.valuation.edgar import _http_fetcher  # noqa: E402


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code, self._payload = status, payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _FlakySession:
    """Returns/raises the scripted outcomes in order."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.headers = {}
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _fetcher(session):
    return _http_fetcher("Test test@example.com", None, 0, session=session, sleep=lambda s: None)


def test_fetcher_retries_dropped_connections_and_server_errors():
    session = _FlakySession(requests.ConnectionError("reset"), _Resp(503), _Resp(200, {"ok": 1}))

    assert _fetcher(session)("https://data.sec.gov/x.json") == {"ok": 1}
    assert session.calls == 3


def test_fetcher_gives_up_after_max_retries():
    session = _FlakySession(*[requests.ConnectionError("reset")] * 4)

    with pytest.raises(requests.ConnectionError):
        _fetcher(session)("https://data.sec.gov/x.json")
    assert session.calls == 4  # first try + 3 retries


def test_fetcher_does_not_retry_client_errors():
    session = _FlakySession(_Resp(404), _Resp(200))

    with pytest.raises(requests.HTTPError):
        _fetcher(session)("https://data.sec.gov/x.json")
    assert session.calls == 1


# --- live-data edge cases ----------------------------------------------------------

def test_operating_income_falls_back_to_pretax_plus_interest():
    # Exxon-style: no OperatingIncomeLoss tag, only pretax income and interest.
    facts = _facts()
    gaap = facts["facts"]["us-gaap"]
    del gaap["OperatingIncomeLoss"]
    gaap["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"] = _concept(
        _e("2024-01-01", "2024-12-31", 180, form="10-K"),
        _e("2024-01-01", "2024-06-30", 80),
        _e("2025-01-01", "2025-06-30", 100),
    )
    gaap["InterestExpense"] = _concept(_e("2024-01-01", "2024-12-31", 20, form="10-K"))

    f = parse_company_facts(facts, ticker="EXM")

    assert f.operating_income == pytest.approx((180 + 100 - 80) + 20)
    assert "operating income estimated" in f.data_note


def test_only_year_to_date_history_is_explained():
    # A new registrant (e.g. after a reorganization) has one 10-Q and no fiscal year.
    facts = {"entityName": "NewCo Holdings", "facts": {"us-gaap": {
        "Revenues": _concept(_e("2026-01-01", "2026-06-30", 201_155), _e("2026-04-01", "2026-06-30", 116_017)),
    }}}

    f = parse_company_facts(facts, ticker="NEW")

    assert f.revenue is None
    assert "no full fiscal year" in f.data_note


def test_as_of_ignores_filings_made_later():
    # Point-in-time view for backtests: on 2025-07-15 the Q2 2025 10-Q (filed 2025-08-01) was not public.
    f = parse_company_facts(_facts(), ticker="EXM", as_of=date(2025, 7, 15))

    assert f.period_end == date(2024, 12, 31)
    assert f.basis == "FY"
    assert f.revenue == pytest.approx(1000)


# --- S&P 500 scan data-quality cases -----------------------------------------------

def test_stale_cover_page_shares_fall_back_to_diluted_weighted_average():
    # MA/FOX/CMCSA: the undimensioned cover-page share count stopped years ago
    # (multi-class filers now tag it per class, which companyfacts omits).
    facts = _facts()
    facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"] = _concept(
        _e(None, "2010-10-27", 122_500_000, filed="2010-11-02"), unit="shares")
    facts["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"] = _concept(
        _e("2025-04-01", "2025-06-30", 905_000_000), unit="shares")

    f = parse_company_facts(facts, ticker="MA")

    assert f.shares == pytest.approx(905_000_000)


def test_annual_value_from_10k_beats_later_10q_retag():
    # FIX: a 10-Q re-tagged the full year with a different (wrong) value after the 10-K.
    facts = _facts()
    revenue = facts["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    revenue.append(_e("2024-01-01", "2024-12-31", 180, filed="2025-09-01", form="10-Q"))

    f = parse_company_facts(facts, ticker="FIX")

    assert f.revenue == pytest.approx(1000 + 550 - 480)


def test_stale_annual_fallback_is_not_used():
    # KLAC-style: operating income not tagged recently; a years-old annual must not stand in.
    facts = _facts()
    facts["facts"]["us-gaap"]["OperatingIncomeLoss"] = _concept(
        _e("2019-01-01", "2019-12-31", 77, form="10-K", filed="2020-02-01"))

    f = parse_company_facts(facts, ticker="KLAC")

    assert f.operating_income is None


def test_capex_sums_ppe_software_and_oil_and_gas_spending():
    # FIS/GPN capitalize software; E&Ps (EOG, FANG) tag drilling spend as oil & gas property.
    facts = _facts()
    gaap = facts["facts"]["us-gaap"]
    gaap["PaymentsToDevelopSoftware"] = _concept(_e("2024-01-01", "2024-12-31", 25, form="10-K"))
    gaap["PaymentsToAcquireOilAndGasPropertyAndEquipment"] = _concept(_e("2024-01-01", "2024-12-31", 15, form="10-K"))

    assert parse_company_facts(facts, ticker="X").capex == pytest.approx(60 + 25 + 15)


def test_capex_total_tag_is_not_double_counted():
    facts = _facts()
    gaap = facts["facts"]["us-gaap"]
    gaap["PaymentsToAcquireProductiveAssets"] = _concept(_e("2024-01-01", "2024-12-31", 90, form="10-K"))
    gaap["PaymentsToDevelopSoftware"] = _concept(_e("2024-01-01", "2024-12-31", 25, form="10-K"))

    assert parse_company_facts(facts, ticker="X").capex == pytest.approx(90)


def test_debt_uses_current_debt_and_lease_inclusive_tags():
    facts = _facts()
    gaap = facts["facts"]["us-gaap"]
    del gaap["LongTermDebt"]
    gaap["LongTermDebtAndCapitalLeaseObligations"] = _concept(_e(None, "2025-06-30", 250))
    gaap["DebtCurrent"] = _concept(_e(None, "2025-06-30", 40))

    assert parse_company_facts(facts, ticker="VZ").total_debt == pytest.approx(290)


def test_stale_balance_sheet_values_are_not_used():
    # CMCSA-style: a debt tag last reported years ago must not stand in for today's debt.
    facts = _facts()
    gaap = facts["facts"]["us-gaap"]
    gaap["LongTermDebt"] = _concept(_e(None, "2012-12-31", 5, filed="2013-02-01"))
    gaap["LongTermDebtNoncurrent"] = _concept(_e(None, "2025-06-30", 900))

    assert parse_company_facts(facts, ticker="CMCSA").total_debt == pytest.approx(900)


def test_five_year_average_operating_margin():
    facts = _facts()
    gaap = facts["facts"]["us-gaap"]
    gaap["OperatingIncomeLoss"] = _concept(
        _e("2021-01-01", "2021-12-31", 70, form="10-K", filed="2022-02-01"),    # 10% of 700
        _e("2022-01-01", "2022-12-31", 160, form="10-K", filed="2023-02-01"),   # 20% of 800
        _e("2023-01-01", "2023-12-31", 270, form="10-K", filed="2024-02-01"),   # 30% of 900
        _e("2024-01-01", "2024-12-31", 200, form="10-K", filed="2025-02-01"),   # 20% of 1000
    )

    f = parse_company_facts(facts, ticker="X")

    assert f.operating_margin_5y == pytest.approx(0.20)  # median of 10%, 20%, 30%, 20%


def test_five_year_margin_is_robust_to_extraordinary_years():
    # Cruise-line style: two pandemic years of huge losses, then normal profitability.
    facts = _facts()
    gaap = facts["facts"]["us-gaap"]
    gaap["OperatingIncomeLoss"] = _concept(
        _e("2021-01-01", "2021-12-31", -700, form="10-K", filed="2022-02-01"),   # -100%
        _e("2022-01-01", "2022-12-31", -400, form="10-K", filed="2023-02-01"),   # -50%
        _e("2023-01-01", "2023-12-31", 135, form="10-K", filed="2024-02-01"),    # 15%
        _e("2024-01-01", "2024-12-31", 180, form="10-K", filed="2025-02-01"),    # 18%
    )
    gaap["Revenues"]["units"]["USD"].append(_e("2020-01-01", "2020-12-31", 600, form="10-K", filed="2021-02-01"))
    gaap["OperatingIncomeLoss"]["units"]["USD"].append(
        _e("2020-01-01", "2020-12-31", 120, form="10-K", filed="2021-02-01"))              # 20%

    assert parse_company_facts(facts, ticker="CCL").operating_margin_5y == pytest.approx(0.15)


def test_five_year_margin_needs_three_years():
    f = parse_company_facts(_facts(), ticker="X")  # only one fiscal year of operating income
    assert f.operating_margin_5y is None
