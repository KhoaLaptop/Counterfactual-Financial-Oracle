"""
SEC EDGAR XBRL "companyfacts" -> annualized Fundamentals.

Flows (revenue, operating income, ...) are trailing-twelve-month when a 10-Q
follows the latest 10-K: TTM = FY + YTD - prior-year YTD. Otherwise the latest
fiscal year is used. Balance-sheet items are the latest instant on or before
the period end.
"""

import hashlib
import json
import os
import threading
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .models import Fundamentals

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

DATE_TOLERANCE = timedelta(days=7)
ANNUAL_DAYS = (350, 380)
NEARBY_ANNUAL = timedelta(days=183)
STALE_AFTER = timedelta(days=450)  # older values don't describe the current business
ANNUAL_FORMS = ("10-K", "20-F", "40-F")

# Tags in priority order; companies switch tags over the years, so they're merged.
REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
]
OPERATING_INCOME_TAGS = ["OperatingIncomeLoss"]
DA_TAGS = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
    "Depreciation",
]
CAPEX_TAGS = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]
# Capital spending: a total tag if reported, else the sum of component groups
# (first tag found per group). Software and oil & gas development are real capex.
CAPEX_TOTAL_TAGS = ["PaymentsToAcquireProductiveAssets"]
CAPEX_COMPONENT_TAGS = [
    ["PaymentsToAcquirePropertyPlantAndEquipment"],
    ["PaymentsToDevelopSoftware", "PaymentsToAcquireSoftware"],
    ["PaymentsToAcquireOilAndGasPropertyAndEquipment", "PaymentsToExploreAndDevelopOilAndGasProperties"],
]
WORKING_CAPITAL_TAGS = ["IncreaseDecreaseInOperatingCapital"]
TAX_TAGS = ["IncomeTaxExpenseBenefit"]
PRETAX_TAGS = [
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
]
INTEREST_TAGS = ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"]
CASH_TAGS = ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]
SHORT_TERM_INVESTMENT_TAGS = ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"]
SHORT_TERM_DEBT_TAGS = ["ShortTermBorrowings", "CommercialPaper"]


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _years_before(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - years, day=28)


def _near(a: date, b: date) -> bool:
    return abs(a - b) <= DATE_TOLERANCE


def _duration(e: Dict) -> int:
    return (_d(e["end"]) - _d(e["start"])).days


def _is_annual(e: Dict) -> bool:
    return ANNUAL_DAYS[0] <= _duration(e) <= ANNUAL_DAYS[1]


def _dedupe(entries: List[Dict]) -> List[Dict]:
    """
    One entry per (start, end): the most recently filed, except that for a
    full-year period an annual report (10-K) beats later quarterly re-tags.
    """
    def rank(e: Dict):
        from_annual_report = "start" in e and _is_annual(e) and e.get("form", "").startswith(ANNUAL_FORMS)
        return (from_annual_report, e.get("filed", ""))

    latest: Dict = {}
    for e in sorted(entries, key=rank):
        latest[(e.get("start"), e["end"])] = e
    return list(latest.values())


def merged_entries(gaap: Dict, tags: List[str], unit: str = "USD") -> List[Dict]:
    """Entries across tags; on the same period an earlier tag wins."""
    merged: Dict = {}
    for tag in reversed(tags):
        for e in _dedupe(gaap.get(tag, {}).get("units", {}).get(unit, [])):
            merged[(e.get("start"), e["end"])] = e
    return list(merged.values())


def flow_at(entries: List[Dict], end: date) -> Optional[float]:
    """Twelve-month value of a flow ending at `end`, or None if it can't be built."""
    durations = [e for e in entries if "start" in e]
    for e in durations:
        if _is_annual(e) and _near(_d(e["end"]), end):
            return float(e["val"])

    # YTD candidates ending at `end`, longest first (YTD beats a lone quarter)
    ytds = sorted(
        (e for e in durations if _near(_d(e["end"]), end) and _duration(e) < ANNUAL_DAYS[0]),
        key=_duration, reverse=True,
    )
    for ytd in ytds:
        fy_end = _d(ytd["start"]) - timedelta(days=1)
        annual = next((e for e in durations if _is_annual(e) and _near(_d(e["end"]), fy_end)), None)
        prior = next(
            (e for e in durations
             if _near(_d(e["end"]), _years_before(end, 1)) and abs(_duration(e) - _duration(ytd)) <= 7),
            None,
        )
        if annual and prior:
            return float(annual["val"]) + float(ytd["val"]) - float(prior["val"])
    return None


def _latest_flow_end(entries: List[Dict]) -> Optional[date]:
    for end in sorted({_d(e["end"]) for e in entries if "start" in e}, reverse=True):
        if flow_at(entries, end) is not None:
            return end
    return None


def _annual_near(entries: List[Dict], target: date, window: timedelta) -> Optional[float]:
    annuals = [e for e in entries if "start" in e and _is_annual(e) and abs(_d(e["end"]) - target) <= window]
    if not annuals:
        return None
    return float(min(annuals, key=lambda e: abs(_d(e["end"]) - target))["val"])


def _latest_annual(entries: List[Dict], on_or_before: date) -> Optional[float]:
    annuals = [
        e for e in entries
        if "start" in e and _is_annual(e)
        and on_or_before - STALE_AFTER <= _d(e["end"]) <= on_or_before + DATE_TOLERANCE
    ]
    return float(max(annuals, key=lambda e: e["end"])["val"]) if annuals else None


def _flow(gaap: Dict, tags: List[str], end: date) -> Optional[float]:
    entries = merged_entries(gaap, tags)
    value = flow_at(entries, end)
    return value if value is not None else _latest_annual(entries, end)


def _average_annual_margin(gaap: Dict, end: date, years: int = 5, minimum: int = 3) -> Optional[float]:
    """
    Median operating margin over the last `years` fiscal years (None with fewer than
    `minimum`). A median, so extraordinary years (e.g. pandemic losses) can't dominate.
    """
    def annual_by_end(tags: List[str]) -> Dict[date, float]:
        return {
            _d(e["end"]): float(e["val"])
            for e in merged_entries(gaap, tags)
            if "start" in e and _is_annual(e) and _d(e["end"]) <= end + DATE_TOLERANCE
        }

    revenue = annual_by_end(REVENUE_TAGS)
    operating = annual_by_end(OPERATING_INCOME_TAGS)
    margins = [operating[y] / revenue[y] for y in sorted(revenue, reverse=True)[:years] if y in operating and revenue[y] > 0]
    return float(np.median(margins)) if len(margins) >= minimum else None


def _capex(gaap: Dict, end: date) -> Optional[float]:
    total = _flow(gaap, CAPEX_TOTAL_TAGS, end)
    if total is not None:
        return total
    return _sum_present(*(_flow(gaap, group, end) for group in CAPEX_COMPONENT_TAGS))


def _instant(gaap: Dict, tags: List[str], end: date) -> Optional[float]:
    """Latest balance-sheet value on or before `end`, ignoring stale ones."""
    entries = [
        e for e in merged_entries(gaap, tags)
        if end - STALE_AFTER <= _d(e["end"]) <= end + DATE_TOLERANCE
    ]
    return float(max(entries, key=lambda e: e["end"])["val"]) if entries else None


def _sum_present(*values: Optional[float]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


TOTAL_LONG_TERM_DEBT_TAGS = [  # include the current portion of long-term debt
    "LongTermDebt",
    "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
    "DebtLongtermAndShorttermCombinedAmount",
]
NONCURRENT_DEBT_TAGS = ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"]
CURRENT_LTD_TAGS = ["LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"]
ALL_CURRENT_DEBT_TAGS = ["DebtCurrent"]  # current LTD + short-term borrowings + commercial paper


def _total_debt(gaap: Dict, end: date) -> Optional[float]:
    short_term = _sum_present(*(_instant(gaap, [t], end) for t in SHORT_TERM_DEBT_TAGS))
    total_long = _instant(gaap, TOTAL_LONG_TERM_DEBT_TAGS, end)
    if total_long is not None:
        return _sum_present(total_long, short_term)

    noncurrent = _instant(gaap, NONCURRENT_DEBT_TAGS, end)
    all_current = _instant(gaap, ALL_CURRENT_DEBT_TAGS, end)
    if all_current is not None:
        return _sum_present(noncurrent, all_current)
    return _sum_present(noncurrent, _instant(gaap, CURRENT_LTD_TAGS, end), short_term)


def _shares(facts: Dict, period_end: Optional[date] = None) -> Tuple[Optional[float], Optional[date]]:
    """
    (share count, date it was measured). From the latest cover page, unless that value
    is stale: multi-class filers tag cover shares per class, which companyfacts omits,
    leaving years-old totals. Otherwise the latest diluted weighted-average count.
    The date matters for split adjustment in backtests.
    """
    cover = facts.get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    if period_end is not None:
        cover = [e for e in cover if _d(e["end"]) >= period_end - STALE_AFTER]
    if cover:
        latest_end = max(e["end"] for e in cover)
        at_end = [e for e in cover if e["end"] == latest_end]
        latest_filed = max(e.get("filed", "") for e in at_end)
        # Multi-class companies report one entry per share class.
        return float(sum(e["val"] for e in at_end if e.get("filed", "") == latest_filed)), _d(latest_end)
    # Statement share counts (balance-sheet total, then diluted weighted average) cover all
    # classes and are restated for splits before issuance: their basis is the filing date.
    for tag in ("CommonStockSharesOutstanding", "WeightedAverageNumberOfDilutedSharesOutstanding"):
        entries = facts.get("us-gaap", {}).get(tag, {}).get("units", {}).get("shares", [])
        if period_end is not None:
            entries = [e for e in entries if _d(e["end"]) >= period_end - STALE_AFTER]
        if entries:
            latest = max(entries, key=lambda e: (e["end"], e.get("filed", "")))
            return float(latest["val"]), _d(latest.get("filed") or latest["end"])
    return None, None


def _filed_by(facts: Dict, as_of: date) -> Dict:
    """Copy of companyfacts keeping only facts filed on or before `as_of` (point-in-time view)."""
    cutoff = as_of.isoformat()
    return {
        **facts,
        "facts": {
            taxonomy: {
                tag: {**concept, "units": {
                    unit: [e for e in entries if e.get("filed", "") <= cutoff]
                    for unit, entries in concept.get("units", {}).items()
                }}
                for tag, concept in concepts.items()
            }
            for taxonomy, concepts in facts.get("facts", {}).items()
        },
    }


def parse_company_facts(
    facts: Dict,
    ticker: str,
    sic: Optional[int] = None,
    cik: Optional[str] = None,
    name: str = "",
    as_of: Optional[date] = None,
) -> Fundamentals:
    """Annualized fundamentals; with `as_of`, only from filings public on that date."""
    if as_of is not None:
        facts = _filed_by(facts, as_of)
    gaap = facts.get("facts", {}).get("us-gaap", {})
    revenue_entries = merged_entries(gaap, REVENUE_TAGS)
    end = _latest_flow_end(revenue_entries)
    base = Fundamentals(ticker=ticker.upper(), name=name or facts.get("entityName", ""), cik=cik, sic=sic)
    if end is None:
        note = "no full fiscal year in SEC XBRL data (new registrant?)" if revenue_entries else ""
        shares, shares_as_of = _shares(facts.get("facts", {}))
        return base.model_copy(update={"shares": shares, "shares_as_of": shares_as_of, "data_note": note})

    def revenue_near(years: int) -> Optional[float]:
        target = _years_before(end, years)
        value = flow_at(revenue_entries, target)
        return value if value is not None else _annual_near(revenue_entries, target, NEARBY_ANNUAL)

    notes = []
    pretax = _flow(gaap, PRETAX_TAGS, end)
    interest = _flow(gaap, INTEREST_TAGS, end)
    operating_income = _flow(gaap, OPERATING_INCOME_TAGS, end)
    if operating_income is None and pretax is not None:
        # Some companies (e.g. oil majors) never report operating income; use an EBIT proxy.
        operating_income = pretax + (interest or 0.0)
        notes.append("operating income estimated as pretax income + interest expense")

    shares, shares_as_of = _shares(facts.get("facts", {}), end)
    is_fiscal_year = _annual_near(revenue_entries, end, DATE_TOLERANCE) is not None
    return base.model_copy(update=dict(
        period_end=end,
        basis="FY" if is_fiscal_year else "TTM",
        revenue=flow_at(revenue_entries, end),
        revenue_prior=revenue_near(1),
        revenue_3y_ago=revenue_near(3),
        operating_income=operating_income,
        depreciation_amortization=_flow(gaap, DA_TAGS, end),
        capex=_capex(gaap, end),
        operating_margin_5y=_average_annual_margin(gaap, end),
        change_in_working_capital=_flow(gaap, WORKING_CAPITAL_TAGS, end),
        income_tax=_flow(gaap, TAX_TAGS, end),
        pretax_income=pretax,
        interest_expense=interest,
        cash=_sum_present(_instant(gaap, CASH_TAGS, end), _instant(gaap, SHORT_TERM_INVESTMENT_TAGS, end)),
        total_debt=_total_debt(gaap, end),
        shares=shares,
        shares_as_of=shares_as_of,
        data_note="; ".join(notes),
    ))


class SecClient:
    """Fetches fundamentals for a ticker from SEC EDGAR."""

    def __init__(
        self,
        fetch_json: Optional[Callable[[str], Dict]] = None,
        user_agent: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        cache_ttl_seconds: int = 24 * 3600,
    ):
        self._fetch = fetch_json or _http_fetcher(user_agent or os.getenv("SEC_USER_AGENT"), cache_dir, cache_ttl_seconds)
        self._tickers: Optional[Dict[str, Dict]] = None

    def cik_for(self, ticker: str) -> str:
        if self._tickers is None:
            self._tickers = {row["ticker"].upper(): row for row in self._fetch(TICKERS_URL).values()}
        row = self._tickers.get(ticker.upper())
        if row is None:
            raise LookupError(f"Ticker {ticker!r} not found in SEC company list")
        return f"{int(row['cik_str']):010d}"

    def submissions(self, ticker: str) -> Dict:
        """Company profile (name, SIC code, filings index)."""
        return self._fetch(SUBMISSIONS_URL.format(cik=self.cik_for(ticker)))

    def company_facts(self, ticker: str) -> Dict:
        """Raw XBRL companyfacts JSON for a ticker."""
        return self._fetch(FACTS_URL.format(cik=self.cik_for(ticker)))

    def fundamentals(self, ticker: str, as_of: Optional[date] = None) -> Fundamentals:
        cik = self.cik_for(ticker)
        submissions = self._fetch(SUBMISSIONS_URL.format(cik=cik))
        sic = submissions.get("sic")
        facts = self.company_facts(ticker)
        return parse_company_facts(
            facts, ticker=ticker, cik=cik, sic=int(sic) if sic else None, name=submissions.get("name", ""),
            as_of=as_of,
        )


RETRY_STATUSES = {429, 500, 502, 503, 504}


def _http_fetcher(
    user_agent: Optional[str],
    cache_dir: Optional[Path],
    ttl: int,
    session=None,
    retries: int = 3,
    backoff_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[[str], Dict]:
    if not user_agent:
        raise ValueError("SEC requires a contact User-Agent: set SEC_USER_AGENT='Name email@example.com'")
    import requests

    if session is None:
        session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    min_interval = 0.12  # SEC allows 10 requests/second
    last_call = [0.0]
    throttle = threading.Lock()  # the ranker fetches from several threads

    def get_with_retries(url: str):
        for attempt in range(retries + 1):
            with throttle:
                wait = min_interval - (time.monotonic() - last_call[0])
                if wait > 0:
                    sleep(wait)
                last_call[0] = time.monotonic()
            try:
                response = session.get(url, timeout=30)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == retries:
                    raise
            else:
                if response.status_code not in RETRY_STATUSES or attempt == retries:
                    response.raise_for_status()
                    return response
            sleep(backoff_seconds * 2 ** attempt)

    def fetch(url: str) -> Dict:
        cache_file = None
        if cache_dir:
            cache_file = Path(cache_dir) / f"{hashlib.sha1(url.encode()).hexdigest()}.json"
            if cache_file.exists() and time.time() - cache_file.stat().st_mtime < ttl:
                return json.loads(cache_file.read_text())

        data = get_with_retries(url).json()

        if cache_file:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data))
        return data

    return fetch
