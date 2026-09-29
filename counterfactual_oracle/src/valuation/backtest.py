"""
Point-in-time backtest of the ranking (B2).

At each quarter-end the universe is re-scored using only information public
then: SEC facts filed by that date and prices up to that date. Each name's
forward total return (default 52 weeks) is then compared with its score.

Split handling: SEC share counts from the past are pre-split while Yahoo's
history is split-adjusted, so past share counts are converted to today's
split basis before computing per-share values.

Known bias: the universe is today's constituents (survivorship bias), which
flatters absolute returns; the ranking metrics (top vs bottom, rank
correlation) are less affected but not immune.

    python -m counterfactual_oracle.src.valuation.backtest --universe sp500 --start 2016-03-31
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .market import LOOKBACK_WEEKS, MARKET_INDEX, TREASURY_10Y, weekly_beta
from .models import MarketSnapshot
from .screener import risk_adjusted_gap
from .verdict import evaluate


def quarter_ends(start: date, end: date) -> List[date]:
    return [d.date() for d in pd.date_range(start, end, freq="QE") if start <= d.date() <= end]


def spearman(x, y) -> float:
    return float(pd.Series(list(x)).rank().corr(pd.Series(list(y)).rank()))


@dataclass
class PriceHistory:
    adjusted: pd.DataFrame  # split- and dividend-adjusted weekly closes (total return)
    close: pd.DataFrame     # split-adjusted weekly closes (today's share basis)
    splits: pd.DataFrame    # split ratio in the week it happened, 0 otherwise

    def _series(self, frame: pd.DataFrame, ticker: str, as_of: date) -> pd.Series:
        if ticker not in frame:
            return pd.Series(dtype=float)
        return frame[ticker].loc[: pd.Timestamp(as_of)].dropna()

    def split_factor_after(self, ticker: str, as_of: date) -> float:
        """Multiply a share count reported at `as_of` by this to put it on today's basis."""
        if ticker not in self.splits:
            return 1.0
        ratios = self.splits[ticker].loc[pd.Timestamp(as_of) + pd.Timedelta(days=1):]
        ratios = ratios[ratios > 0]
        return float(np.prod(ratios)) if len(ratios) else 1.0

    def forward_return(self, ticker: str, as_of: date, weeks: int = 52) -> Optional[float]:
        target = pd.Timestamp(as_of) + pd.Timedelta(weeks=weeks)
        if self.adjusted.index.max() < target - pd.Timedelta(days=6):
            return None
        start = self._series(self.adjusted, ticker, as_of)
        end = self._series(self.adjusted, ticker, target.date())
        if start.empty or end.empty or end.index[-1] <= start.index[-1]:
            return None
        return float(end.iloc[-1] / start.iloc[-1] - 1)

    def snapshot(self, ticker: str, as_of: date) -> MarketSnapshot:
        close = self._series(self.close, ticker, as_of)
        if close.empty:
            raise LookupError(f"No price for {ticker!r} on {as_of}")
        window = slice(-(LOOKBACK_WEEKS + 1), None)
        beta = weekly_beta(
            self._series(self.adjusted, ticker, as_of).iloc[window],
            self._series(self.adjusted, MARKET_INDEX, as_of).iloc[window],
        )
        treasury = self._series(self.close, TREASURY_10Y, as_of)
        return MarketSnapshot(
            price=float(close.iloc[-1]), beta=beta,
            risk_free_rate=float(treasury.iloc[-1]) / 100 if len(treasury) else 0.043,
            as_of=as_of,
        )


@dataclass
class BacktestRow:
    ticker: str
    as_of: date
    score: float
    label: str
    gap_pct: float
    p_upside: float
    confidence: str
    forward_return: float


@dataclass
class BacktestResult:
    rows: List[BacktestRow] = field(default_factory=list)
    errors: List[Tuple[str, str, str]] = field(default_factory=list)  # (ticker, date, error)
    skipped: int = 0  # not assessable, or no forward return


def run_backtest(
    tickers: List[str],
    history,
    prices: PriceHistory,
    dates: List[date],
    num_simulations: int = 1000,
    seed: int = 42,
    horizon_weeks: int = 52,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> BacktestResult:
    """`history.fundamentals_at(ticker, as_of)` must only use data public on `as_of`."""
    last_price = prices.adjusted.index.max()
    dates = [d for d in dates if pd.Timestamp(d) + pd.Timedelta(weeks=horizon_weeks) <= last_price + pd.Timedelta(days=6)]
    result = BacktestResult()

    for i, ticker in enumerate(tickers, start=1):  # ticker-major: each company's SEC data loads once
        for as_of in dates:
            try:
                f = history.fundamentals_at(ticker, as_of)
                if f.shares:
                    # Splits after the count was measured (not after as_of: the latest
                    # SEC count can predate a split that already happened).
                    measured = min(f.shares_as_of or as_of, as_of)
                    f = f.model_copy(update={"shares": f.shares * prices.split_factor_after(ticker, measured)})
                verdict = evaluate(f, prices.snapshot(ticker, as_of), num_simulations, seed)
            except Exception as exc:
                result.errors.append((ticker, as_of.isoformat(), f"{type(exc).__name__}: {exc}"))
                continue
            score = risk_adjusted_gap(verdict)
            forward = prices.forward_return(ticker, as_of, horizon_weeks)
            if score is None or forward is None:
                result.skipped += 1
                continue
            result.rows.append(BacktestRow(
                ticker=ticker, as_of=as_of, score=score, label=verdict.label, gap_pct=verdict.gap_pct,
                p_upside=verdict.p_upside, confidence=verdict.confidence, forward_return=forward,
            ))
        if on_progress:
            on_progress(i, len(tickers), ticker)
    return result


def summarize(result: BacktestResult, quantiles: int = 5) -> Dict:
    """Per-date cross-sectional metrics, averaged over dates."""
    frame = pd.DataFrame([asdict(r) for r in result.rows])
    if frame.empty:
        return {"dates": 0}

    per_date = []
    for as_of, group in frame.groupby("as_of"):
        if len(group) < max(quantiles, 2):
            continue
        ordered = group.sort_values("score", ascending=False)
        buckets = [
            ordered["forward_return"].iloc[positions].mean()
            for positions in np.array_split(np.arange(len(ordered)), quantiles)
        ]
        universe = group["forward_return"].mean()
        per_date.append({
            "as_of": str(as_of),
            "names": len(group),
            "rank_correlation": spearman(group["score"], group["forward_return"]),
            "quantile_returns": buckets,
            "top_minus_bottom": buckets[0] - buckets[-1],
            "universe_return": universe,
            "label_excess": {
                label: g["forward_return"].mean() - universe for label, g in group.groupby("label")
            },
        })

    ics = np.array([d["rank_correlation"] for d in per_date])
    spreads = np.array([d["top_minus_bottom"] for d in per_date])
    labels = sorted({label for d in per_date for label in d["label_excess"]})
    return {
        "dates": len(per_date),
        "names_per_date": float(np.mean([d["names"] for d in per_date])),
        "mean_rank_correlation": float(ics.mean()),
        "rank_correlation_t_stat": float(ics.mean() / ics.std(ddof=1) * np.sqrt(len(ics))) if len(ics) > 1 and ics.std(ddof=1) > 0 else None,
        "top_minus_bottom": float(spreads.mean()),
        "hit_rate": float((spreads > 0).mean()),
        "quantile_returns": [float(np.mean([d["quantile_returns"][q] for d in per_date])) for q in range(quantiles)],
        "universe_return": float(np.mean([d["universe_return"] for d in per_date])),
        "label_excess_return": {
            label: float(np.mean([d["label_excess"][label] for d in per_date if label in d["label_excess"]]))
            for label in labels
        },
        "per_date": per_date,
    }


# --- live data ----------------------------------------------------------------------

class SecHistory:
    """Point-in-time fundamentals from SEC companyfacts; keeps one company's facts in memory."""

    def __init__(self, sec):
        self.sec = sec
        self._ticker: Optional[str] = None
        self._facts: Dict = {}
        self._profile: Dict = {}

    def fundamentals_at(self, ticker: str, as_of: date):
        from .edgar import parse_company_facts

        if ticker != self._ticker:
            self._facts = self.sec.company_facts(ticker)
            self._profile = self.sec.submissions(ticker)
            self._ticker = ticker
        sic = self._profile.get("sic")
        return parse_company_facts(
            self._facts, ticker=ticker, sic=int(sic) if sic else None,
            name=self._profile.get("name", ""), as_of=as_of,
        )


def download_price_history(tickers: List[str], start: date, end: date) -> PriceHistory:
    import yfinance

    symbols = list(dict.fromkeys([*tickers, MARKET_INDEX, TREASURY_10Y]))
    data = yfinance.download(
        symbols, start=(start - timedelta(weeks=LOOKBACK_WEEKS + 4)).isoformat(), end=end.isoformat(),
        interval="1wk", auto_adjust=False, actions=True, progress=False, threads=True,
    )
    return PriceHistory(adjusted=data["Adj Close"], close=data["Close"], splits=data["Stock Splits"].fillna(0.0))


def main(argv: Optional[List[str]] = None) -> int:
    from .universe import load_sp500, load_watchlist

    parser = argparse.ArgumentParser(description="Point-in-time backtest of the valuation ranking.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--universe", choices=["sp500"])
    source.add_argument("--watchlist")
    parser.add_argument("--start", default="2016-03-31")
    parser.add_argument("--end", default=None, help="Last rebalance date (default: one horizon before today)")
    parser.add_argument("--horizon-weeks", type=int, default=52)
    parser.add_argument("--simulations", type=int, default=1000)
    parser.add_argument("--quantiles", type=int, default=5)
    parser.add_argument("--out", help="Write the full result (summary + rows) as JSON")
    args = parser.parse_args(argv)

    from .cli import DEFAULT_CACHE_DIR
    from .edgar import SecClient

    tickers = load_sp500().tickers if args.universe else load_watchlist(args.watchlist)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end) if args.end else date.today() - timedelta(weeks=args.horizon_weeks)
    prices = download_price_history(tickers, start, date.today())
    history = SecHistory(SecClient(cache_dir=DEFAULT_CACHE_DIR, cache_ttl_seconds=30 * 24 * 3600))

    result = run_backtest(
        tickers, history, prices, quarter_ends(start, end), args.simulations,
        horizon_weeks=args.horizon_weeks,
        on_progress=lambda i, n, t: print(f"[{i}/{n}] {t}", file=sys.stderr),
    )
    summary = summarize(result, args.quantiles)
    report = {k: v for k, v in summary.items() if k != "per_date"}
    report["errors"] = len(result.errors)
    report["skipped"] = result.skipped
    print(json.dumps(report, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps({
            "summary": summary, "errors": result.errors,
            "rows": [{**asdict(r), "as_of": r.as_of.isoformat()} for r in result.rows],
        }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
