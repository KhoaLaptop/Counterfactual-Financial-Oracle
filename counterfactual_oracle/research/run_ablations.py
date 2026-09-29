"""
Apply the pre-registered selection rule in ablations.md to backtest outputs.

    python -m counterfactual_oracle.research.run_ablations DIR

DIR holds abl_base.json, abl_h5.json, abl_flat.json and abl_w156.json, written by
`python -m counterfactual_oracle.src.valuation.backtest ... --out`. Train metrics are
printed for every variant; the test period is evaluated only for the selected one.
"""

import json
import sys
from datetime import date
from pathlib import Path

from counterfactual_oracle.src.valuation.backtest import BacktestResult, BacktestRow, summarize

TRAIN_END = date(2020, 12, 31)
TEST_START = date(2021, 3, 31)
MIN_T = 2.0

# id: (run file, score field, description), exactly as pre-registered
VARIANTS = {
    "V0": ("abl_base", "score", "baseline: risk-adjusted gap"),
    "V1": ("abl_base", "gap_pct", "raw median gap"),
    "V2": ("abl_base", "p_upside", "P(upside)"),
    "V3": ("abl_h5", "score", "5-year horizon, 1-year hold"),
    "V4": ("abl_flat", "score", "no margin fade"),
    "V5": ("abl_w156", "score", "156-week forward returns"),
}


def load(path: Path) -> BacktestResult:
    rows = json.loads(path.read_text())["rows"]
    return BacktestResult(rows=[BacktestRow(**{**r, "as_of": date.fromisoformat(r["as_of"])}) for r in rows])


def line(label: str, s: dict) -> str:
    t = s.get("rank_correlation_t_stat")
    q = s.get("quantile_returns", [])
    return (f"{label:4s} dates {s['dates']:3d}  IC {s.get('mean_rank_correlation', float('nan')):+.3f}  "
            f"t {t:+.2f}  top-bottom {s.get('top_minus_bottom', float('nan')):+.1%}  "
            f"hit {s.get('hit_rate', float('nan')):.0%}  quintiles {' '.join(f'{x:.1%}' for x in q)}"
            if t is not None else f"{label:4s} dates {s['dates']:3d}  (not enough dates)")


def main(directory: str) -> int:
    base = Path(directory)
    runs = {name: load(base / f"{name}.json") for name in {v[0] for v in VARIANTS.values()}}

    print("TRAIN (rebalances through 2020-12-31)")
    train = {}
    for vid, (run, field, description) in VARIANTS.items():
        train[vid] = summarize(runs[run], score_field=field, end=TRAIN_END)
        print(line(vid, train[vid]), f"  [{description}]")

    best = max(train, key=lambda v: train[v].get("rank_correlation_t_stat") or float("-inf"))
    best_t = train[best].get("rank_correlation_t_stat") or float("-inf")
    print(f"\nSelected: {best} (train t = {best_t:+.2f})")
    if best_t <= MIN_T:
        print(f"No variant reaches train t > {MIN_T}: NO SIGNAL. Test period not evaluated; stop tuning.")
        return 0

    run, field, _ = VARIANTS[best]
    test = summarize(runs[run], score_field=field, start=TEST_START)
    print("\nTEST (rebalances from 2021-03-31), evaluated once")
    print(line(best, test))
    held = (test.get("rank_correlation_t_stat") or 0) > MIN_T and test.get("mean_rank_correlation", 0) > 0
    print("HOLDS UP" if held else "DOES NOT HOLD UP out of sample")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
