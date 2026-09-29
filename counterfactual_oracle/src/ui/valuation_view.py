"""
Streamlit views for the SEC-based valuation tools: one company, or a watchlist.

Everything here is presented as valuation context, not buy/sell advice: in
point-in-time backtests the model/price gap did not predict returns.
"""

import os
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..valuation.models import Verdict
from ..valuation.screener import Ranking
from ..valuation.verdict import CONTEXT_NOTE

POSITION_TEXT = {
    "PRICE_BELOW_MODEL_RANGE": "Below model range",
    "PRICE_WITHIN_MODEL_RANGE": "Within model range",
    "PRICE_ABOVE_MODEL_RANGE": "Above model range",
}


def _money(value: Optional[float]) -> str:
    return f"${value:,.2f}" if value is not None else "n/a"


def _pct(value: Optional[float]) -> str:
    return f"{value:.1%}" if value is not None else "n/a"


# --- pure display helpers (unit-tested) --------------------------------------------------

def position_sentence(v: Verdict) -> str:
    if v.price_position == "NOT_ASSESSABLE":
        return f"Not assessable: {v.reason}"
    where = {"PRICE_BELOW_MODEL_RANGE": "below", "PRICE_WITHIN_MODEL_RANGE": "within",
             "PRICE_ABOVE_MODEL_RANGE": "above"}[v.price_position]
    return (f"The market price ({_money(v.price)}) is {where} the model's P10–P90 range "
            f"({_money(v.fair_value.p10)} – {_money(v.fair_value.p90)}).")


def summary_metrics(v: Verdict) -> List[Tuple[str, str, str]]:
    """(label, value, help) for the headline metrics."""
    metrics = [("Market price", _money(v.price), "Latest weekly close")]
    if v.fair_value is None:
        return metrics
    return metrics + [
        ("Model value (P50)", _money(v.fair_value.p50), "Median of the Monte Carlo fair-value distribution"),
        ("Model range (P10–P90)", f"{_money(v.fair_value.p10)} – {_money(v.fair_value.p90)}",
         "80% of simulated fair values fall in this range"),
        ("Market-implied growth", _pct(v.market_implied_growth),
         "Reverse DCF: starting revenue growth at which the model value equals the price"),
        ("Recent growth used", _pct(v.assumptions.get("growth_start")),
         "Starting revenue growth the model assumes, from the company's own history"),
        ("Model confidence", v.confidence or "n/a", "How wide and data-complete the model range is"),
    ]


def sensitivity_rows(v: Verdict) -> List[Dict[str, str]]:
    base = v.sensitivity.get("base")
    return [
        {"Scenario": name, "Value per share": _money(value),
         "Change vs base": f"{value / base - 1:+.1%}" if base else "n/a"}
        for name, value in v.sensitivity.items()
    ]


def screener_rows(ranking: Ranking) -> List[Dict[str, object]]:
    return [
        {
            "Rank": e.rank,
            "Ticker": e.ticker,
            "Company": e.company_name,
            "Price": round(e.price, 2),
            "Model P50": round(e.fair_value.p50, 2),
            "Gap vs price": f"{e.gap_pct:+.0%}",
            "Price position": POSITION_TEXT[e.price_position],
            "Implied growth": _pct(e.market_implied_growth),
            "Model confidence": e.confidence,
        }
        for e in ranking.entries
    ]


def debate_summary(result) -> Dict[str, str]:
    """Consensus narrative and confidence only; the agents' Buy/Hold/Sell call is dropped."""
    return {"summary": result.consensus_summary, "confidence": result.confidence_level}


def range_chart(v: Verdict):
    """P10–P90 band with the P50 tick and the market price marked."""
    import altair as alt

    band = pd.DataFrame([{"label": "Model", "p10": v.fair_value.p10, "p90": v.fair_value.p90, "p50": v.fair_value.p50}])
    price = pd.DataFrame([{"price": v.price}])
    x = alt.X("p10:Q", title="Value per share ($)")
    bar = alt.Chart(band).mark_bar(height=26, opacity=0.35).encode(x=x, x2="p90:Q", y=alt.Y("label:N", title=None))
    median = alt.Chart(band).mark_tick(thickness=3, size=30).encode(x="p50:Q", y="label:N")
    market = alt.Chart(price).mark_rule(strokeWidth=2, color="#dc2626").encode(x="price:Q")
    return (bar + median + market).properties(height=90)


# --- Streamlit views ---------------------------------------------------------------------------

def _live_oracle(tickers: List[str], contact: str):
    from ..valuation.cli import DEFAULT_CACHE_DIR
    from ..valuation.edgar import SecClient
    from ..valuation.market import BatchMarketData
    from ..valuation.oracle import Oracle

    return Oracle(SecClient(user_agent=contact, cache_dir=DEFAULT_CACHE_DIR), BatchMarketData(tickers))


def _sec_contact(st, key: str) -> str:
    return st.text_input(
        "SEC contact (name and email)", value=os.getenv("SEC_USER_AGENT", ""), key=key,
        help="SEC requires every request to identify a contact. Stored only for this session.",
    ).strip()


def render_verdict(st, v: Verdict) -> None:
    st.markdown(f"### {v.company_name or v.ticker} ({v.ticker})")
    if v.price_position == "NOT_ASSESSABLE":
        st.warning(position_sentence(v))
        return

    st.markdown(position_sentence(v))
    metrics = summary_metrics(v)
    for column, (label, value, help_text) in zip(st.columns(len(metrics)), metrics):
        column.metric(label, value, help=help_text)
    st.altair_chart(range_chart(v), use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.markdown("**What moves the value** (one assumption changed at a time)")
        st.dataframe(pd.DataFrame(sensitivity_rows(v)), hide_index=True, use_container_width=True)
    with right:
        st.markdown("**Why the model is (un)certain**")
        for reason in v.confidence_reasons:
            st.markdown(f"- {reason}")

    basis = f"{v.basis} ending {v.period_end}" if v.period_end else v.basis
    st.caption(f"Financials: SEC XBRL, {basis}. {v.simulations:,} simulations.")
    with st.expander("Assumptions and full output"):
        st.json(v.model_dump(mode="json"))


def render_ticker_valuation(st) -> None:
    st.markdown("## 🔎 Value a US-listed company")
    st.info(CONTEXT_NOTE)
    ticker = st.text_input("Ticker", value="", placeholder="e.g. NVDA", key="valuation_ticker").strip().upper()
    contact = _sec_contact(st, "valuation_contact")

    if st.button("Value company", type="primary", disabled=not ticker):
        if not contact:
            st.error("Enter an SEC contact (name and email) first.")
            return
        with st.spinner(f"Fetching SEC filings and prices for {ticker}..."):
            try:
                st.session_state["valuation"] = _live_oracle([ticker], contact).judge(ticker, num_simulations=5000)
            except Exception as exc:
                st.error(f"Could not value {ticker}: {exc}")
                return

    verdict = st.session_state.get("valuation")
    if verdict is not None:
        render_verdict(st, verdict)


def render_screener(st) -> None:
    from ..valuation.screener import rank_universe
    from ..valuation.universe import normalize_ticker

    st.markdown("## 📊 Screen a watchlist")
    st.info(CONTEXT_NOTE)
    st.caption("Sorted by model value vs price per unit of model uncertainty. A sort for context, not a forecast.")
    text = st.text_area("Tickers (one per line or comma-separated)", value="AAPL\nMSFT\nNVDA\nKO\nPEP\nWMT",
                        key="screener_tickers")
    contact = _sec_contact(st, "screener_contact")
    tickers = list(dict.fromkeys(normalize_ticker(t) for t in text.replace(",", "\n").splitlines() if t.strip()))

    if st.button("Screen", type="primary", disabled=not tickers):
        if not contact:
            st.error("Enter an SEC contact (name and email) first.")
            return
        with st.spinner(f"Valuing {len(tickers)} companies..."):
            try:
                st.session_state["screen"] = rank_universe(tickers, _live_oracle(tickers, contact),
                                                           num_simulations=3000)
            except Exception as exc:
                st.error(f"Screen failed: {exc}")
                return

    ranking = st.session_state.get("screen")
    if ranking is not None:
        st.dataframe(pd.DataFrame(screener_rows(ranking)), hide_index=True, use_container_width=True)
        if ranking.excluded:
            st.markdown("**Not assessed**")
            st.dataframe(pd.DataFrame([{"Ticker": x.ticker, "Reason": x.reason} for x in ranking.excluded]),
                         hide_index=True, use_container_width=True)
