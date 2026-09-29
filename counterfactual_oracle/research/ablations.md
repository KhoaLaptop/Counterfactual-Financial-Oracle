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

## Results (run 2026-09-29, after the rules above were committed in 0a66b13)

Reproduce: run the four backtests (`--out abl_base.json`, `abl_h5.json` with
`--horizon-years 5 --hold-years 1`, `abl_flat.json` with `--no-margin-fade`,
`abl_w156.json` with `--horizon-weeks 156`), then
`python -m counterfactual_oracle.research.run_ablations DIR`.

Train (20 rebalances, 2016-03-31 to 2020-12-31):

| ID | Rank corr. | t | Top − bottom | Hit rate | Quintiles (top → bottom score) |
|----|-----------|---|--------------|----------|-------------------------------|
| V0 baseline | −0.049 | −1.83 | −4.9% | 50% | 24.3 / 21.2 / 21.8 / 23.5 / 29.2% |
| V1 raw gap | −0.066 | −2.55 | −6.3% | 35% | 21.8 / 22.7 / 22.9 / 24.4 / 28.2% |
| V2 P(upside) | −0.065 | −2.45 | −7.0% | 35% | 22.1 / 22.5 / 22.5 / 23.9 / 29.1% |
| V3 5-year horizon | −0.071 | −2.24 | −8.8% | 20% | 23.0 / 21.9 / 21.1 / 22.1 / 31.9% |
| V4 no margin fade | −0.054 | −2.04 | −5.8% | 40% | 23.4 / 21.6 / 22.4 / 23.4 / 29.2% |
| V5 3-year returns | +0.025 | +2.28 | +2.2% | 60% | 69.7 / 58.2 / 60.6 / 64.0 / 67.5% |

Selected by the rule: **V5** (train t = +2.28, the only positive one, and its
t is overstated by overlapping 3-year windows).

Test (11 rebalances from 2021-03-31), evaluated once:

| ID | Rank corr. | t | Top − bottom | Hit rate |
|----|-----------|---|--------------|----------|
| V5 | +0.013 | +0.54 | +13.6% | 55% |

**Verdict: does not hold up out of sample.** Per the rule, tuning stops. The
ranking is a valuation display, not a demonstrated return predictor.

Not acted on (not pre-registered, would be data mining): every 1-year variant
had a *negative* train correlation (t between −1.8 and −2.6), i.e. cheap-looking
names underperformed in 2016–2020. That matches the well-known value drawdown
of that period; flipping the signal to exploit it would be fitting to history.
