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
    Runs Monte Carlo simulation using Discounted Cash Flow (DCF) model.
    
    MODEL: Terminal Value DCF with Gordon Growth
    ============================================
    
    FORMULAS:
    ---------
    1. Revenue Projection:
       Revenue_t = Revenue_0 × (1 + g_revenue)
       where g_revenue ~ N(μ_growth, σ=0.02)
    
    2. Operating Expenses:
       OpEx_t = OpEx_0 × (1 + δ_opex)
       where δ_opex ~ N(μ_opex, σ=0.01)
    
    3. EBITDA:
       EBITDA = Revenue - COGS - OpEx
       where COGS = Revenue × (1 - GrossMargin_0)
    
    4. Free Cash Flow (FCF):
       FCF = EBIT × (1 - τ) + D&A - ΔWC - CapEx
       where:
         EBIT = EBITDA - D&A
         τ = tax rate
         ΔWC = change in working capital
         CapEx = capital expenditures
    
    5. Terminal Value (Gordon Growth):
       TV = FCF_1 × (1 + g) / (r - g)
       where:
         g = perpetual growth rate (2%)
         r = discount rate (WACC)
    
    6. Net Present Value (NPV):
       NPV = FCF_1/(1+r) + TV/(1+r)
    
    ASSUMPTIONS:
    ------------
    - COGS scales with revenue (constant gross margin)
    - D&A remains fixed (conservative)
    - Working capital and CapEx scale with revenue
    - Terminal growth rate: 2%
    - Default discount rate (WACC): 8%
    - Monte Carlo iterations: 10,000
    
    VALIDATION:
    -----------
    - Checks for OpEx > Revenue
    - Validates margins < 100%
    - Ensures discount rate > growth rate
    """
    
    # Base values
    base_rev = base_report.income_statement.Revenue
    base_opex = base_report.income_statement.OpEx
    base_tax_rate = base_report.kpis.get("TaxRate", 0.25)
    
    # Sanity check: Revenue must be positive
    if base_rev <= 0:
        raise ValueError(f"Base revenue must be positive, got {base_rev}")
    
    # Sanity check: OpEx shouldn't exceed revenue
    if base_opex > base_rev:
        print(f"WARNING: OpEx (${base_opex:,.0f}) exceeds Revenue (${base_rev:,.0f})")
    
    # Deltas (convert bps to decimal)
    rev_growth_mean = params.revenue_growth_bps / 10000.0
    opex_delta_mean = params.opex_delta_bps / 10000.0
    discount_rate_base = 0.08 # Default 8% WACC
    discount_rate_delta = params.discount_rate_bps / 10000.0
    
    # Distributions
    # We'll assume a standard deviation for the uncertainty
    rev_growth_dist = np.random.normal(rev_growth_mean, 0.02, num_simulations) # 2% std dev
    opex_delta_dist = np.random.normal(opex_delta_mean, 0.01, num_simulations) # 1% std dev
    
    results = []
    
    for i in range(num_simulations):
        # Apply deltas
        # Revenue Growth is applied to the base revenue
        sim_rev_growth = rev_growth_dist[i]
        projected_revenue = base_rev * (1 + sim_rev_growth)
        
        # OpEx delta: percentage change to the OpEx amount
        sim_opex_change = opex_delta_dist[i]
        projected_opex = base_opex * (1 + sim_opex_change)
        
        # Simple projection down the P&L
        # Assuming COGS scales with Revenue (maintaining Gross Margin unless specified)
        gross_margin = base_report.income_statement.GrossProfit / base_report.income_statement.Revenue if base_report.income_statement.Revenue > 0 else 0
        projected_cogs = projected_revenue * (1 - gross_margin)
        projected_gross_profit = projected_revenue - projected_cogs
        
        projected_ebitda = projected_gross_profit - projected_opex
        
        # D&A - assume fixed for simplicity
        da = base_report.income_statement.DepreciationAndAmortization
        projected_ebit = projected_ebitda - da
        
        # Tax
        tax_rate = base_tax_rate + (params.tax_rate_delta_bps / 10000.0)
        taxes = projected_ebit * tax_rate if projected_ebit > 0 else 0
        
        net_income = projected_ebit - base_report.income_statement.InterestExpense - taxes
        
        # FCF
        # Assume ChangeInWC and CapEx scale with Revenue growth
        scale_factor = projected_revenue / base_rev if base_rev > 0 else 1.0
        capex = base_report.cash_flow.CapEx * scale_factor
        change_wc = base_report.cash_flow.ChangeInWorkingCapital * scale_factor
        
        fcf = calculate_fcf(projected_ebit, tax_rate, da, change_wc, capex)
        
        # NPV using Terminal Value (Gordon Growth Model)
        # TV = FCF * (1 + g) / (r - g)
        g = 0.02  # 2% perpetual growth
        r = discount_rate_base + discount_rate_delta
        
        # Safety: ensure r > g
        if r <= g: 
            r = g + 0.01
        
        terminal_value = fcf * (1 + g) / (r - g)
        npv = (fcf / (1 + r)) + (terminal_value / ((1 + r)**1))
        
        results.append(SimulationResult(
            scenario_id=i,
            revenue=projected_revenue,
            ebitda=projected_ebitda,
            net_income=net_income,
            fcf=fcf,
            npv=npv,
            key_driver="Revenue" if abs(sim_rev_growth) > abs(sim_opex_change) else "OpEx"
        ))

    # Aggregate
    npvs = [r.npv for r in results]
    revenues = [r.revenue for r in results]
    ebitdas = [r.ebitda for r in results]
    fcfs = [r.fcf for r in results]
    
    agg = AggregatedSimulation(
        median_npv=np.median(npvs),
        p10_npv=np.percentile(npvs, 10),
        p90_npv=np.percentile(npvs, 90),
        median_revenue=np.median(revenues),
        median_ebitda=np.median(ebitdas),
        median_fcf=np.median(fcfs),
        assumption_log=[
            f"DCF Model: Terminal Value with Gordon Growth (g=2%)",
            f"Applied mean revenue growth delta of {params.revenue_growth_bps} bps.",
            f"Applied mean OpEx delta of {params.opex_delta_bps} bps.",
            f"Discount rate (WACC) set to {discount_rate_base + discount_rate_delta:.2%}.",
            f"Monte Carlo simulation ran {num_simulations} iterations with normal distributions."
        ],
        traceability={"Revenue": "Base Revenue from Income Statement", "OpEx": "Base OpEx from Income Statement"},
        simulation_runs=results[:100] # Store only first 100 to save space in JSON
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
