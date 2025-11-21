import os
import sys
import time
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.join(os.getcwd(), 'counterfactual_oracle'))

from src.models import FinancialReport, IncomeStatement, CashFlow, BalanceSheet, ScenarioParams
from src.logic import run_monte_carlo
from src.agents.debate_agent import DebateAgent

def verify_backend():
    print("🔍 Starting Backend Verification...")
    
    # 1. Load Environment
    load_dotenv(os.path.join(os.getcwd(), 'counterfactual_oracle', '.env'))
    gemini_key = os.getenv("GEMINI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    
    if not gemini_key:
        print("❌ Missing GEMINI_API_KEY")
        return
    if not deepseek_key:
        print("❌ Missing DEEPSEEK_API_KEY")
        return
    print("✅ API Keys Found")

    # 2. Create Dummy Data
    print("\n📊 Generating Dummy Report...")
    report = FinancialReport(
        company_name="TestCorp",
        fiscal_period="FY24",
        income_statement=IncomeStatement(
            Revenue=100000,
            CostOfGoodsSold=60000,
            GrossProfit=40000,
            OpEx=20000,
            EBITDA=20000,
            DepreciationAndAmortization=5000,
            EBIT=15000,
            InterestExpense=1000,
            Taxes=3500,
            NetIncome=10500
        ),
        balance_sheet=BalanceSheet(
            Assets={"Total": 200000},
            Liabilities={"Total": 100000},
            Equity={"Total": 100000}
        ),
        cash_flow=CashFlow(
            NetIncome=10500,
            Depreciation=5000,
            ChangeInWorkingCapital=1000,
            CashFromOperations=15000,
            CapEx=5000,
            CashFromInvesting=-5000,
            DebtRepayment=0,
            Dividends=0,
            CashFromFinancing=0,
            NetChangeInCash=10000,
            FreeCashFlow=10000
        ),
        kpis={"TaxRate": 0.25}
    )
    
    # 3. Test Simulation (Layer 2)
    print("\n🎲 Testing Causal Simulation Engine...")
    params = ScenarioParams(
        opex_delta_bps=-500, # -5% OpEx
        revenue_growth_bps=200, # +2% Growth
        discount_rate_bps=0,
        tax_rate_delta_bps=0
    )
    
    try:
        sim_result = run_monte_carlo(report, params, num_simulations=100)
        print(f"✅ Simulation Successful!")
        print(f"   Median NPV: ${sim_result.median_npv:,.2f}")
        print(f"   Forecast Year 5 Revenue: ${sim_result.revenue_forecast_p50[-1]:,.2f}")
    except Exception as e:
        print(f"❌ Simulation Failed: {e}")
        return

    # 4. Test Agents (Layer 3)
    print("\n🤖 Testing AI Agents (Single Turn)...")
    agent = DebateAgent(gemini_api_key=gemini_key, deepseek_api_key=deepseek_key)
    
    try:
        # We'll just inspect the internal methods to avoid running a full loop
        print("   Requesting Gemini Opening (with rate limit pause)...")
        # The agent handles the pause internally now
        opening = agent._get_validated_gemini_position(report, sim_result, params, [])
        print(f"✅ Gemini Responded: {opening[:100]}...")
        
    except Exception as e:
        print(f"❌ Agent Test Failed: {e}")
        return

    print("\n🎉 ALL SYSTEMS GO! Backend is healthy.")

if __name__ == "__main__":
    verify_backend()
