"""
Command line: rank a universe of stocks by risk-adjusted valuation gap (JSON).

    python -m counterfactual_oracle.src.valuation.rank --watchlist my.txt
    python -m counterfactual_oracle.src.valuation.rank --universe sp500 --top 25 --debate-top 5

Needs SEC_USER_AGENT ("Name email@example.com") and the yfinance package.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .oracle import Oracle
from .screener import rank_universe
from .universe import load_sp500, load_watchlist


def main(argv: Optional[List[str]] = None, oracle: Optional[Oracle] = None) -> int:
    parser = argparse.ArgumentParser(prog="oracle-rank", description="Rank stocks by risk-adjusted valuation gap.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--universe", choices=["sp500"], help="Built-in universe (dated snapshot in data/universe)")
    source.add_argument("--watchlist", help="File with one ticker per line")
    parser.add_argument("--top", type=int, help="Only output the top N ranked names")
    parser.add_argument("--debate-top", type=int, default=0, help="Run the LLM debate on the top N (costs API calls)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--simulations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", help="Also write the JSON here")
    args = parser.parse_args(argv)

    if args.universe:
        universe = load_sp500()
        tickers, name, as_of = universe.tickers, universe.name, universe.as_of
    else:
        tickers, name, as_of = load_watchlist(args.watchlist), "watchlist", None

    reviewer = None
    if args.debate_top > 0:
        from .cli import _debate_reviewer

        reviewer = _debate_reviewer()
    if oracle is None:
        from .cli import _live_oracle

        oracle = _live_oracle(reviewer=None)

    def progress(done: int, total: int, ticker: str) -> None:
        print(f"[{done}/{total}] {ticker}", file=sys.stderr)

    ranking = rank_universe(
        tickers, oracle, workers=args.workers, num_simulations=args.simulations, seed=args.seed,
        debate_top=args.debate_top, reviewer=reviewer, on_progress=progress,
        universe=name, universe_as_of=as_of,
    )
    if args.top is not None:
        ranking.entries = ranking.entries[: args.top]

    output = ranking.model_dump_json(indent=2)
    if args.out:
        Path(args.out).write_text(output)
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
