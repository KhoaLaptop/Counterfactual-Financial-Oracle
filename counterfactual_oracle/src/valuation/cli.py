"""
Command line: print a single-company verdict as JSON.

    python -m counterfactual_oracle.src.valuation NVDA
    python -m counterfactual_oracle.src.valuation NVDA --debate
    python -m counterfactual_oracle.src.valuation --report filing.json --price 180 --shares 24.3e9 --scale 1e6 --quarterly

Ticker mode needs SEC_USER_AGENT ("Name email@example.com") and the yfinance package.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from ..models import FinancialReport
from .models import MarketSnapshot
from .oracle import Oracle, fundamentals_from_report

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "counterfactual_oracle" / "sec"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="oracle", description="Single-company valuation verdict (JSON).")
    p.add_argument("ticker", nargs="?", help="Ticker symbol, e.g. NVDA")
    p.add_argument("--report", help="Path to a FinancialReport JSON (filing mode)")
    p.add_argument("--price", type=float, help="Market price per share (filing mode)")
    p.add_argument("--shares", type=float, help="Shares outstanding (filing mode)")
    p.add_argument("--beta", type=float, help="Equity beta (filing mode, default 1.0)")
    p.add_argument("--risk-free", type=float, default=0.043, help="Risk-free rate (filing mode)")
    p.add_argument("--quarterly", action="store_true", help="Annualize a quarterly filing (x4)")
    p.add_argument("--scale", type=float, default=1.0, help="Unit multiplier for filing money, e.g. 1e6")
    p.add_argument("--debate", action="store_true", help="Add the LLM optimist-vs-critic review")
    p.add_argument("--simulations", type=int, default=10000)
    p.add_argument("--seed", type=int, default=42)
    return p


def _debate_reviewer():
    from ..agents.debate_agent import DebateAgent
    from .debate import DebateAgentReviewer

    optimist_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    critic_key = os.getenv("DEEPSEEK_API_KEY")
    if not optimist_key or not critic_key:
        raise SystemExit("--debate needs GEMINI_API_KEY (or OPENAI_API_KEY) and DEEPSEEK_API_KEY")
    return DebateAgentReviewer(DebateAgent(optimist_key, critic_key))


def _live_oracle(reviewer) -> Oracle:
    from .edgar import SecClient
    from .market import YFinanceMarketData

    return Oracle(SecClient(cache_dir=DEFAULT_CACHE_DIR), YFinanceMarketData(), reviewer=reviewer)


def main(argv: Optional[List[str]] = None, oracle: Optional[Oracle] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if bool(args.ticker) == bool(args.report):
        parser.error("give either a ticker or --report")
    reviewer = _debate_reviewer() if args.debate else None

    if args.report:
        if args.price is None or args.shares is None:
            parser.error("--report needs --price and --shares")
        report = FinancialReport.model_validate(json.loads(Path(args.report).read_text()))
        name = args.ticker or Path(args.report).stem
        fundamentals = fundamentals_from_report(
            report, ticker=name, shares=args.shares, quarterly=args.quarterly, scale=args.scale,
        )
        market = MarketSnapshot(price=args.price, beta=args.beta, risk_free_rate=args.risk_free)
        judge = oracle or Oracle(sec=None, market=None, reviewer=reviewer)
        verdict = judge.judge_fundamentals(fundamentals, market, args.simulations, args.seed)
    else:
        verdict = (oracle or _live_oracle(reviewer)).judge(args.ticker, args.simulations, args.seed)

    print(verdict.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
