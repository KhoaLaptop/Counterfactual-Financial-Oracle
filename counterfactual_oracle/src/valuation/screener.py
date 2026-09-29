"""
Universe ranker: run the single-company verdict over many tickers and rank them.

Score = median gap / ((P90 - P10) / price): margin of safety per unit of
uncertainty. The optional debate runs only on the top N after ranking and can
lower confidence but never changes the order.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .debate import Reviewer
from .models import Confidence, DebateReview, FairValue, Fundamentals, Label, Verdict
from .oracle import Oracle
from .verdict import apply_debate, evaluate


class RankedEntry(BaseModel):
    rank: int
    ticker: str
    company_name: str = ""
    score: float
    label: Label
    price: float
    gap_pct: float
    p_upside: float
    confidence: Confidence
    fair_value: FairValue
    period_end: Optional[date] = None
    basis: Optional[str] = None
    debate: Optional[DebateReview] = None


class Excluded(BaseModel):
    ticker: str
    reason: str


class Ranking(BaseModel):
    universe: str
    universe_as_of: Optional[str] = None
    generated_at: str
    simulations: int
    seed: int
    entries: List[RankedEntry] = Field(default_factory=list)
    excluded: List[Excluded] = Field(default_factory=list)


MIN_SPREAD = 0.05  # a zero-width distribution (e.g. fair value $0 everywhere) still ranks


def risk_adjusted_gap(verdict) -> Optional[float]:
    """Median gap divided by the P10-P90 spread relative to price; None if not ranked."""
    if verdict.label == "NOT_ASSESSABLE" or verdict.fair_value is None:
        return None
    spread = (verdict.fair_value.p90 - verdict.fair_value.p10) / verdict.price
    return verdict.gap_pct / max(spread, MIN_SPREAD)


def rank_universe(
    tickers: List[str],
    oracle: Oracle,
    workers: int = 4,
    num_simulations: int = 5000,
    seed: int = 42,
    debate_top: int = 0,
    reviewer: Optional[Reviewer] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    universe: str = "custom",
    universe_as_of: Optional[str] = None,
) -> Ranking:
    results: Dict[str, Tuple[Optional[Fundamentals], Optional[Verdict], Optional[str]]] = {}
    done = [0]
    lock = threading.Lock()

    def judge(ticker: str) -> None:
        try:
            fundamentals = oracle.sec.fundamentals(ticker)
            verdict = evaluate(fundamentals, oracle.market.snapshot(ticker), num_simulations, seed)
            outcome = (fundamentals, verdict, None)
        except Exception as exc:  # one bad ticker must not stop a 500-name scan
            outcome = (None, None, f"{type(exc).__name__}: {exc}")
        with lock:
            results[ticker] = outcome
            done[0] += 1
            if on_progress:
                on_progress(done[0], len(tickers), ticker)

    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        list(pool.map(judge, tickers))

    scored, excluded = [], []
    for ticker in tickers:  # input order keeps exclusions stable
        fundamentals, verdict, error = results[ticker]
        score = risk_adjusted_gap(verdict) if verdict else None
        if score is None:
            excluded.append(Excluded(ticker=ticker, reason=error or verdict.reason or "No fair-value distribution"))
        else:
            scored.append((score, ticker, fundamentals, verdict))
    scored.sort(key=lambda item: (-item[0], item[1]))

    entries = []
    for rank, (score, ticker, fundamentals, verdict) in enumerate(scored, start=1):
        if reviewer is not None and rank <= debate_top:
            verdict = apply_debate(verdict, reviewer.review(fundamentals, verdict))
        entries.append(RankedEntry(
            rank=rank, ticker=ticker, company_name=verdict.company_name, score=score, label=verdict.label,
            price=verdict.price, gap_pct=verdict.gap_pct, p_upside=verdict.p_upside,
            confidence=verdict.confidence, fair_value=verdict.fair_value, period_end=verdict.period_end,
            basis=verdict.basis, debate=verdict.debate,
        ))

    return Ranking(
        universe=universe, universe_as_of=universe_as_of,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        simulations=num_simulations, seed=seed, entries=entries, excluded=excluded,
    )
