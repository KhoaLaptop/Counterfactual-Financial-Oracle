"""
Accuracy benchmark for PDF extractors, using SEC XBRL as ground truth.

For each filing PDF, every extractor's output goes through the normal
FinancialMapper, and each field is compared with the XBRL value for the
same filing. Two scores:

- accuracy: the FinancialReport holds the right number (extractor + mapper)
- recall:   the right number appears anywhere in the extractor's markdown
            (a miss here is the extractor's fault, not the mapper's)

Usage:
    SEC_USER_AGENT="Name email" python -m counterfactual_oracle.src.parsers.benchmark \\
        --manifest filings.json --extractors docling,mistral

filings.json: [{"pdf": "aapl-q3.pdf", "ticker": "AAPL", "period_end": "2025-06-28", "form": "10-Q"}]
"""

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional

from ..models import FinancialReport
from ..valuation.edgar import CAPEX_TAGS, CASH_TAGS, OPERATING_INCOME_TAGS, REVENUE_TAGS, merged_entries
from .mapper import FinancialMapper
from .normalizer import FinancialNormalizer

DATE_TOLERANCE = timedelta(days=7)
QUARTER_DAYS = (80, 100)
ANNUAL_DAYS = (350, 380)
SCALES = (1.0, 1e3, 1e6, 1e9)  # PDFs report in dollars, thousands, millions or billions
RELATIVE_TOLERANCE = 0.005
COST_PER_PAGE = {"docling": 0.0, "mistral": 0.004}
LANDING_AI_USD_PER_CREDIT = 0.01


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: str  # "period" (income statement), "ytd" (cash flow), "instant" (balance sheet)
    tags: List[str]
    get: Callable[[FinancialReport], Optional[float]]
    compare_magnitude: bool = False  # sign conventions vary (e.g. CapEx)


FIELDS = [
    FieldSpec("Revenue", "period", REVENUE_TAGS, lambda r: r.income_statement.Revenue),
    FieldSpec("CostOfGoodsSold", "period", ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"],
              lambda r: r.income_statement.CostOfGoodsSold),
    FieldSpec("GrossProfit", "period", ["GrossProfit"], lambda r: r.income_statement.GrossProfit),
    FieldSpec("EBIT", "period", OPERATING_INCOME_TAGS, lambda r: r.income_statement.EBIT),
    FieldSpec("NetIncome", "period", ["NetIncomeLoss", "ProfitLoss"], lambda r: r.income_statement.NetIncome),
    FieldSpec("Cash", "instant", CASH_TAGS, lambda r: r.balance_sheet.Cash),
    FieldSpec("TotalAssets", "instant", ["Assets"], lambda r: r.balance_sheet.Assets.get("TotalAssets")),
    FieldSpec("TotalLiabilities", "instant", ["Liabilities"],
              lambda r: r.balance_sheet.Liabilities.get("TotalLiabilities")),
    FieldSpec("TotalEquity", "instant",
              ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
              lambda r: r.balance_sheet.Equity.get("TotalEquity")),
    FieldSpec("CashFromOperations", "ytd", ["NetCashProvidedByUsedInOperatingActivities"],
              lambda r: r.cash_flow.CashFromOperations),
    FieldSpec("CapEx", "ytd", CAPEX_TAGS, lambda r: r.cash_flow.CapEx, compare_magnitude=True),
]


@dataclass
class FieldScore:
    truth: float
    extracted: Optional[float]
    correct: bool
    in_markdown: bool


@dataclass
class ExtractorResult:
    fields: Dict[str, FieldScore] = field(default_factory=dict)
    scale: Optional[float] = None
    accuracy: float = 0.0
    recall: float = 0.0
    seconds: float = 0.0
    pages: int = 0
    estimated_cost_usd: Optional[float] = None
    error: Optional[str] = None


# --- ground truth ---------------------------------------------------------------

def _days(e: Dict) -> int:
    return (date.fromisoformat(e["end"]) - date.fromisoformat(e["start"])).days


def _ends_at(e: Dict, period_end: date) -> bool:
    return abs(date.fromisoformat(e["end"]) - period_end) <= DATE_TOLERANCE


def _truth_value(entries: List[Dict], kind: str, period_end: date, annual: bool) -> Optional[float]:
    at_end = [e for e in entries if _ends_at(e, period_end)]
    if kind == "instant":
        candidates = [e for e in at_end if "start" not in e]
    else:
        durations = [e for e in at_end if "start" in e]
        if annual:
            candidates = [e for e in durations if ANNUAL_DAYS[0] <= _days(e) <= ANNUAL_DAYS[1]]
        elif kind == "period":
            candidates = [e for e in durations if QUARTER_DAYS[0] <= _days(e) <= QUARTER_DAYS[1]]
        else:  # year-to-date: the longest period within the fiscal year
            candidates = sorted((e for e in durations if _days(e) < ANNUAL_DAYS[0]), key=_days)[-1:]
    return float(candidates[0]["val"]) if candidates else None


def edgar_truth(facts: Dict, period_end: date, form: str) -> Dict[str, float]:
    """XBRL values for one filing, keyed by benchmark field name."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    annual = form.upper().startswith("10-K")
    truth = {}
    for spec in FIELDS:
        value = _truth_value(merged_entries(gaap, spec.tags), spec.kind, period_end, annual)
        if value is not None:
            truth[spec.name] = value
    return truth


# --- scoring ----------------------------------------------------------------------

NUMBER = re.compile(r"(\()?-?\$?\s?(\d[\d,]*(?:\.\d+)?)(\))?")


def markdown_numbers(markdown: str) -> List[float]:
    """Every number in the text, plus the magnitude of negatives ("(1,234)" -> -1234 and 1234)."""
    numbers = []
    for match in NUMBER.finditer(markdown):
        value = float(match.group(2).replace(",", ""))
        negative = (match.group(1) and match.group(3)) or match.group(0).lstrip("($ ").startswith("-")
        numbers.extend([-value, value] if negative else [value])
    return numbers


def _matches(value: float, truth: float, scale: float, magnitude: bool = False) -> bool:
    if magnitude:
        value, truth = abs(value), abs(truth)
    return abs(value * scale - truth) <= max(RELATIVE_TOLERANCE * abs(truth), 0.5 * scale)


def _estimated_cost(name: str, pages: int, metadata: Dict) -> Optional[float]:
    if name == "landing_ai" and metadata.get("credit_usage") is not None:
        return metadata["credit_usage"] * LANDING_AI_USD_PER_CREDIT
    if name in COST_PER_PAGE:
        return pages * COST_PER_PAGE[name]
    return None


def score(raw: Dict, truth: Dict[str, float], form: str) -> ExtractorResult:
    markdown = raw.get("markdown", "")
    report = FinancialMapper().parse_raw_response(raw)
    # The mapper annualizes quarterly income statements (x4); undo it to compare with the filing.
    deannualize = 4.0 if FinancialNormalizer.detect_quarterly_data(markdown) else 1.0
    numbers = markdown_numbers(markdown)

    extracted = {}
    for spec in FIELDS:
        if spec.name in truth:
            value = spec.get(report)
            if value is not None and spec.kind == "period":
                value /= deannualize
            extracted[spec.name] = value

    def correct(spec: FieldSpec, scale: float) -> bool:
        value = extracted.get(spec.name)
        return bool(value) and _matches(value, truth[spec.name], scale, spec.compare_magnitude)

    scored = [s for s in FIELDS if s.name in truth]
    best_scale = max(SCALES, key=lambda sc: sum(correct(s, sc) for s in scored))

    fields = {
        s.name: FieldScore(
            truth=truth[s.name],
            extracted=extracted[s.name],
            correct=correct(s, best_scale),
            in_markdown=any(_matches(n, truth[s.name], sc, True) for n in numbers for sc in SCALES),
        )
        for s in scored
    }
    n = max(len(fields), 1)
    return ExtractorResult(
        fields=fields,
        scale=best_scale,
        accuracy=sum(f.correct for f in fields.values()) / n,
        recall=sum(f.in_markdown for f in fields.values()) / n,
    )


def run_benchmark(pdf: str, extractors: Dict, truth: Dict[str, float], form: str) -> Dict[str, ExtractorResult]:
    results = {}
    for name, extractor in extractors.items():
        started = time.perf_counter()
        try:
            raw = extractor.extract(pdf)
        except Exception as exc:  # one failing extractor must not stop the others
            results[name] = ExtractorResult(error=f"{type(exc).__name__}: {exc}", seconds=time.perf_counter() - started)
            continue
        result = score(raw, truth, form)
        metadata = raw.get("metadata", {})
        result.seconds = time.perf_counter() - started
        result.pages = metadata.get("page_count", 0)
        result.estimated_cost_usd = _estimated_cost(name, result.pages, metadata)
        results[name] = result
    return results


def summarize(runs: List[Dict[str, ExtractorResult]]) -> Dict[str, Dict]:
    """Aggregate per-filing results into per-extractor totals."""
    summary: Dict[str, Dict] = {}
    for run in runs:
        for name, result in run.items():
            s = summary.setdefault(name, {"filings": 0, "errors": 0, "correct": 0, "found": 0, "scored": 0,
                                          "seconds": 0.0, "cost_usd": 0.0, "field_hits": {}, "field_counts": {}})
            s["filings"] += 1
            s["errors"] += result.error is not None
            s["seconds"] += result.seconds
            s["cost_usd"] += result.estimated_cost_usd or 0.0
            for field_name, f in result.fields.items():
                s["scored"] += 1
                s["correct"] += f.correct
                s["found"] += f.in_markdown
                s["field_hits"][field_name] = s["field_hits"].get(field_name, 0) + f.correct
                s["field_counts"][field_name] = s["field_counts"].get(field_name, 0) + 1

    for s in summary.values():
        scored = max(s["scored"], 1)
        s["accuracy"] = s.pop("correct") / scored
        s["recall"] = s.pop("found") / scored
        s["field_accuracy"] = {k: s["field_hits"][k] / c for k, c in s.pop("field_counts").items()}
        del s["field_hits"]
    return summary


# --- CLI --------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Score PDF extractors against SEC XBRL.")
    parser.add_argument("--manifest", required=True, help="JSON list of {pdf, ticker, period_end, form}")
    parser.add_argument("--extractors", default="docling", help="Comma-separated: docling,mistral,landing_ai")
    args = parser.parse_args(argv)

    from ..valuation.edgar import SecClient
    from .extractors import create_extractor

    cases = json.loads(open(args.manifest).read())
    extractors = {name: create_extractor(name) for name in args.extractors.split(",")}
    sec = SecClient()

    filings, runs = [], []
    for case in cases:
        period_end = date.fromisoformat(case["period_end"])
        truth = edgar_truth(sec.company_facts(case["ticker"]), period_end, case.get("form", "10-Q"))
        run = run_benchmark(case["pdf"], extractors, truth, case.get("form", "10-Q"))
        runs.append(run)
        filings.append({**case, "results": {name: asdict(r) for name, r in run.items()}})
        print(f"{case['ticker']} {case['period_end']}: "
              + ", ".join(f"{n} {r.accuracy:.0%}" for n, r in run.items()), file=sys.stderr)

    print(json.dumps({"summary": summarize(runs), "filings": filings}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
