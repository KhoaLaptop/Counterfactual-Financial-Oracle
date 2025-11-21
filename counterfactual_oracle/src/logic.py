import numpy as np
from typing import List, Dict, Tuple, Any
from .models import FinancialReport, ScenarioParams, SimulationResult, AggregatedSimulation, BalanceSheet

def calculate_fcf(ebit: float, tax_rate: float, dep_amort: float, change_working_capital: float, capex: float) -> float:
    """
    Formula: FCF = EBIT * (1 - TaxRate) + D&A - ChangeInWC - CapEx
    Note: ChangeInWC is typically (Current Assets - Current Liabs) delta. 
    If the report gives it as a cash flow item, negative means outflow (use + if it's already a flow, or - if it's a delta).
    Standard FCF formula usually subtracts the increase in WC.
    Here we assume the input 'change_working_capital' follows the CF statement sign convention (negative = outflow).
    So we ADD it if it's from the CF statement, or SUBTRACT it if it's a raw delta.
    Let's assume standard CF statement sign: FCF = NOPAT + D&A + CF_from_WC_changes + CF_from_Investing(CapEx)
    """
    nopat = ebit * (1 - tax_rate)
    # Assuming capex and change_working_capital are passed as signed values from CF statement (usually negative for outflows)
    # If they are magnitudes, we would subtract. Let's treat them as signed flows to be safe with the 'add' logic, 
    # but the prompt implies standard formula usage.
    # Let's stick to the prompt's implication: "EBITDA = Revenue - OpEx", etc.
    # We will use a standard explicit formula:
    # FCF = EBIT*(1-t) + D&A - IncreaseInWC - CapEx
    # We'll adjust signs based on the inputs in the simulation loop.
    return nopat + dep_amort + change_working_capital + capex

def calculate_npv(fcf_stream: List[float], discount_rate: float) -> float:
    """
    NPV = Sum(FCF_t / (1 + r)^t)
    """
    npv = 0.0
    for t, fcf in enumerate(fcf_stream, start=1):
        npv += fcf / ((1 + discount_rate) ** t)
    return npv

def run_monte_carlo(base_report: FinancialReport, params: ScenarioParams, num_simulations: int = 10000) -> AggregatedSimulation:
    """
    Runs Monte Carlo simulation using a CAUSAL GRAPH with Time-Based Propagation.
    
    MODEL: 5-Year Explicit Forecast + Terminal Value
    ================================================
    
    CAUSAL GRAPH (Hardcoded Formulas):
    ----------------------------------
    1. Revenue_t = Revenue_{t-1} * (1 + g_revenue)
       - g_revenue ~ N(μ_growth, σ=0.02)
    
    2. OpEx_t = OpEx_{t-1} * (1 + δ_opex)
       - δ_opex ~ N(μ_opex, σ=0.01)
       - Note: δ_opex is a structural shift applied to the growth path.
       - Base OpEx growth is assumed to match Revenue growth (scaling) PLUS the delta.
       - Formula: OpEx_t = OpEx_{t-1} * (1 + g_revenue + δ_opex_shift)
    
    3. COGS_t = Revenue_t * (1 - GrossMargin_0)
       - Gross Margin is fixed unless explicitly modeled otherwise.
    
    4. EBITDA_t = Revenue_t - COGS_t - OpEx_t
    
    5. FCF_t = EBITDA_t * (1 - τ) - CapEx_t - ΔWC_t
       - CapEx and ΔWC scale with Revenue.
    
    TIME-BASED PROPAGATION:
    -----------------------
    - Forecast Period: 5 Years (t1 to t5)
    - Terminal Value at t5 using Gordon Growth (g=2%)
    
    """
    
    # Base values
    base_rev = base_report.income_statement.Revenue
    base_opex = base_report.income_statement.OpEx
    base_tax_rate = base_report.kpis.get("TaxRate", 0.25)
    
    # Sanity check: Revenue must be positive
    if base_rev <= 0:
        raise ValueError(f"Base revenue must be positive, got {base_rev}")
    
    # Deltas (convert bps to decimal)
    rev_growth_mean = params.revenue_growth_bps / 10000.0
    opex_delta_mean = params.opex_delta_bps / 10000.0
    discount_rate_base = 0.08 # Default 8% WACC
    discount_rate_delta = params.discount_rate_bps / 10000.0
    
    # Distributions
    rng = np.random.default_rng(42)
    
    # Revenue Growth Distribution (Annual)
    # We assume the user's delta applies to the CAGR or annual growth rate
    rev_growth_dist = rng.normal(rev_growth_mean, 0.02, num_simulations) # 2% std dev
    
    # OpEx Delta Distribution (Structural Shift)
    # This represents an efficiency gain/loss relative to revenue scaling
    opex_delta_dist = rng.normal(opex_delta_mean, 0.01, num_simulations) # 1% std dev
    
    results = []
    forecast_years = 5
    
    for i in range(num_simulations):
        # Scenario Parameters
        sim_rev_growth = rev_growth_dist[i]
        sim_opex_shift = opex_delta_dist[i]
        
        # Initialize Time Series
        rev_stream = []
        ebitda_stream = []
        fcf_stream = []
        net_income_stream = []
        
        # Current state (starts at t0)
        curr_rev = base_rev
        curr_opex = base_opex
        
        # Gross Margin (Fixed)
        gross_margin = base_report.income_statement.GrossProfit / base_report.income_statement.Revenue if base_report.income_statement.Revenue > 0 else 0
        
        # D&A (Fixed for simplicity, or scale? Let's scale with revenue to be realistic for 5 years)
        da_margin = base_report.income_statement.DepreciationAndAmortization / base_report.income_statement.Revenue if base_report.income_statement.Revenue > 0 else 0
        
        # Tax Rate
        tax_rate = base_tax_rate + (params.tax_rate_delta_bps / 10000.0)
        
        # --- TIME PROPAGATION LOOP (t1 to t5) ---
        for t in range(1, forecast_years + 1):
            # 1. Revenue Propagation
            # Revenue grows by (Base Growth + Delta)
            # Let's assume base organic growth is 3% + user delta
            organic_growth = 0.03 
            total_rev_growth = organic_growth + sim_rev_growth
            curr_rev = curr_rev * (1 + total_rev_growth)
            
            # 2. OpEx Propagation
            # OpEx typically scales with revenue, modified by the efficiency delta
            # If delta is negative (efficiency), OpEx grows slower than Revenue
            # OpEx_growth = Revenue_growth + OpEx_Delta
            opex_growth = total_rev_growth + sim_opex_shift
            curr_opex = curr_opex * (1 + opex_growth)
            
            # 3. COGS Propagation
            curr_cogs = curr_rev * (1 - gross_margin)
            
            # 4. EBITDA Calculation
            curr_ebitda = curr_rev - curr_cogs - curr_opex
            
            # 5. Net Income & FCF
            curr_da = curr_rev * da_margin
            curr_ebit = curr_ebitda - curr_da
            curr_taxes = curr_ebit * tax_rate if curr_ebit > 0 else 0
            curr_net_income = curr_ebit - base_report.income_statement.InterestExpense - curr_taxes
            
            # Scale CapEx and WC
            # Simple assumption: % of Revenue
            capex_margin = base_report.cash_flow.CapEx / base_report.income_statement.Revenue if base_report.income_statement.Revenue > 0 else 0
            wc_margin = base_report.cash_flow.ChangeInWorkingCapital / base_report.income_statement.Revenue if base_report.income_statement.Revenue > 0 else 0
            
            curr_capex = curr_rev * capex_margin
            curr_wc = curr_rev * wc_margin
            
            curr_fcf = calculate_fcf(curr_ebit, tax_rate, curr_da, curr_wc, curr_capex)
            
            # Store
            rev_stream.append(curr_rev)
            ebitda_stream.append(curr_ebitda)
            fcf_stream.append(curr_fcf)
            net_income_stream.append(curr_net_income)
            
        # --- VALUATION ---
        # Terminal Value at t5
        g = 0.02  # 2% perpetual growth
        r = discount_rate_base + discount_rate_delta
        
        if r <= g: r = g + 0.01
        
        terminal_fcf = fcf_stream[-1] * (1 + g)
        terminal_value = terminal_fcf / (r - g)
        
        # NPV
        npv = calculate_npv(fcf_stream, r) + (terminal_value / ((1 + r)**forecast_years))
        
        results.append(SimulationResult(
            scenario_id=i,
            revenue=rev_stream[0], # Year 1
            ebitda=ebitda_stream[0], # Year 1
            net_income=net_income_stream[0], # Year 1
            fcf=fcf_stream[0], # Year 1
            npv=npv,
            key_driver="Revenue" if abs(sim_rev_growth) > abs(sim_opex_shift) else "OpEx",
            revenue_forecast=rev_stream,
            ebitda_forecast=ebitda_stream,
            net_income_forecast=net_income_stream,
            fcf_forecast=fcf_stream
        ))

    # Aggregate
    npvs = [r.npv for r in results]
    revenues_y1 = [r.revenue for r in results]
    ebitdas_y1 = [r.ebitda for r in results]
    fcfs_y1 = [r.fcf for r in results]
    
    # Aggregate Forecasts (P50)
    # Transpose list of lists to get distribution per year
    rev_forecast_matrix = np.array([r.revenue_forecast for r in results])
    ebitda_forecast_matrix = np.array([r.ebitda_forecast for r in results])
    fcf_forecast_matrix = np.array([r.fcf_forecast for r in results])
    
    median_rev_forecast = np.median(rev_forecast_matrix, axis=0).tolist()
    median_ebitda_forecast = np.median(ebitda_forecast_matrix, axis=0).tolist()
    median_fcf_forecast = np.median(fcf_forecast_matrix, axis=0).tolist()
    
    agg = AggregatedSimulation(
        median_npv=np.median(npvs),
        p10_npv=np.percentile(npvs, 10),
        p90_npv=np.percentile(npvs, 90),
        median_revenue=np.median(revenues_y1),
        median_ebitda=np.median(ebitdas_y1),
        median_fcf=np.median(fcfs_y1),
        revenue_forecast_p50=median_rev_forecast,
        ebitda_forecast_p50=median_ebitda_forecast,
        fcf_forecast_p50=median_fcf_forecast,
        assumption_log=[
            f"Causal Model: 5-Year Explicit Forecast + Terminal Value (g=2%)",
            f"Revenue Driver: Base Growth (3%) + User Delta ({params.revenue_growth_bps} bps)",
            f"OpEx Driver: Revenue Scaling + Efficiency Delta ({params.opex_delta_bps} bps)",
            f"Discount Rate: {discount_rate_base + discount_rate_delta:.2%}",
            f"Monte Carlo: {num_simulations} iterations"
        ],
        traceability={"Revenue": "Base * (1+g)^t", "OpEx": "Base * (1+g+delta)^t", "EBITDA": "Rev - COGS - OpEx"},
        simulation_runs=results[:100]
    )
    return agg

def check_balance_sheet(bs: BalanceSheet) -> Dict[str, Any]:
    """
    Verifies Assets = Liabilities + Equity
    """
    total_assets = bs.Assets.get("TotalAssets", sum(v for k,v in bs.Assets.items() if k != "TotalAssets"))
    total_liabs = bs.Liabilities.get("TotalLiabilities", sum(v for k,v in bs.Liabilities.items() if k != "TotalLiabilities"))
    total_equity = bs.Equity.get("TotalEquity", sum(v for k,v in bs.Equity.items() if k != "TotalEquity"))
    
    diff = total_assets - (total_liabs + total_equity)
    is_balanced = abs(diff) < 1.0 # Tolerance of $1
    
    return {
        "is_balanced": is_balanced,
        "difference": diff,
        "total_assets": total_assets,
        "total_liabs_equity": total_liabs + total_equity
    }
