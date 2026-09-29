# Ranking ablations: pre-registration

Written and committed **before** running any variant, so the choice of what to
test and how to pick a winner can't be shaped by the results.

## Background

Baseline backtest (S&P 500 constituents as of 2026-09-29, quarterly rebalances
2016-03-31 to 2025-09-30, 52-week forward total return):

- mean rank correlation (score vs forward return) -0.021, t = -1.27
- quintile returns, top to bottom score: 19.7%, 16.6%, 18.0%, 17.4%, 26.7%
- top quintile beat bottom in 41% of quarters

Conclusion so far: no demonstrated predictive power.

## Split

- **Train:** rebalance dates 2016-03-31 to 2020-12-31
- **Test:** rebalance dates 2021-03-31 onward (limited by the forward horizon)

All variants are compared on **train only**. The test period is evaluated once,
for the single selected variant, and reported whatever it shows.

## Variants (fixed list)

| ID | Change from baseline | Why it might matter |
|----|----------------------|---------------------|
| V0 | none: score = gap / (P10-P90 spread / price), 10-year horizon, margin and capex fade | reference |
| V1 | score = raw median gap | uncertainty scaling may reward low-dispersion names for the wrong reason |
| V2 | score = P(upside) | a probability rather than a magnitude |
| V3 | 5-year forecast horizon (1 year hold) | the original A design; less terminal-value weight |
| V4 | no margin fade (margins held flat) | tests the mean-reversion choice made on 2026-09-29 |
| V5 | V0 scored against 156-week (3-year) forward returns | valuation gaps may take longer than a year to close |

## Selection rule

Pick the variant with the highest **train** rank-correlation t-statistic.

- If no variant reaches **t > 2.0** on train, report "no signal" and stop
  tuning: the ranking stays a valuation display, not a return predictor.
- Otherwise evaluate the winner **once** on test. It "holds up" only if test
  rank correlation is positive with t > 2.0.

Known caveats that apply to every variant:

- survivorship bias: the universe is today's index members
- six comparisons: a train t of ~2 is weak evidence after multiple testing
- V5 uses overlapping 3-year windows, so its t-statistic is overstated
