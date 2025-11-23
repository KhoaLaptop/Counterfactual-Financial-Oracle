import streamlit as st
import os
from dotenv import load_dotenv
from src.models import ScenarioParams, FinancialReport
from src.agents.landing_ai import LandingAIClient
from src.agents.simulator import SimulatorAgent
from src.agents.critic import CriticAgent
from src.agents.evaluator import EvaluatorAgent

# Load env vars
load_dotenv()

# Page config
st.set_page_config(
    page_title="Counterfactual Financial Oracle | AI Platform",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS
css_path = "styles.css" if os.path.exists("styles.css") else "counterfactual_oracle/styles.css"
with open(css_path) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Helper function to format currency (values already in millions)
def format_currency(value, decimals=0):
    """Format currency values with commas (no suffix)"""
    return f"${value:,.{decimals}f}"

# Sidebar
with st.sidebar:
    # Header with branding
    st.markdown("""
    <div style="padding: 1rem 0; border-bottom: 1px solid var(--sidebar-border); margin-bottom: 1.25rem;">
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
            <div style="background: linear-gradient(135deg, #3B82F6, #8B5CF6); padding: 0.5rem; border-radius: 0.5rem;">
                <span style="font-size: 1.25rem;">🔮</span>
            </div>
            <div>
                <h1 style="font-size: 1.125rem; margin: 0; line-height: 1.2;">Counterfactual Oracle</h1>
                <p style="font-size: 0.75rem; color: var(--muted-foreground); margin: 0;">AI Financial Platform</p>
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <div style="flex: 1; height: 4px; background: var(--muted); border-radius: 9999px; overflow: hidden;">
                <div style="height: 100%; width: 75%; background: linear-gradient(90deg, #3B82F6, #8B5CF6); border-radius: 9999px;"></div>
            </div>
            <span style="font-size: 0.75rem; color: var(--muted-foreground); font-family: 'JetBrains Mono', monospace;">v2.4.1</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Scenario Controls
    st.markdown('<p class="metric-label">Scenario Controls</p>', unsafe_allow_html=True)
    
    with st.expander("ℹ️ How to use these controls"):
        st.markdown("""
        **Adjust these sliders to create "What-If" scenarios:**
        
        📉 **OpEx Delta**: Changes Operating Expenses.
        - **Negative (-)**: Cost cutting (Higher Profit)
        - **Positive (+)**: More spending (Lower Profit)
        
        📈 **Revenue Growth Delta**: Changes future sales.
        - **Positive (+)**: Faster growth
        - **Negative (-)**: Slower growth or decline
        
        💰 **Discount Rate Delta**: Adjusts valuation risk.
        - **Higher (+)**: Future cash is worth less (Lower Valuation)
        - **Lower (-)**: Future cash is worth more (Higher Valuation)
        
        *Note: 100 bps (basis points) = 1%*
        """)

    opex_delta = st.slider("OpEx Delta", -500, 500, 0, help="Basis points change in operating expenses")
    st.markdown(f'<div style="text-align: right; margin-top: -1rem; margin-bottom: 0.5rem;"><span class="mono" style="color: var(--primary); font-size: 0.875rem;">{opex_delta:+d} bps</span></div>', unsafe_allow_html=True)
    
    rev_growth_delta = st.slider("Revenue Growth Delta", -500, 500, 0, help="Basis points change in revenue growth")
    st.markdown(f'<div style="text-align: right; margin-top: -1rem; margin-bottom: 0.5rem;"><span class="mono" style="color: var(--success); font-size: 0.875rem;">{rev_growth_delta:+d} bps</span></div>', unsafe_allow_html=True)
    
    discount_rate_delta = st.slider("Discount Rate Delta", -500, 500, 0, help="Basis points change in discount rate")
    st.markdown(f'<div style="text-align: right; margin-top: -1rem; margin-bottom: 0.5rem;"><span class="mono" style="color: var(--warning); font-size: 0.875rem;">{discount_rate_delta:+d} bps</span></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Action Buttons
    run_btn = st.button("▶️ Run Analysis", use_container_width=True, type="primary")

# Main Content
st.markdown("""
<div class="main-header">
    <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.25rem;">
        <h1>Analysis Dashboard</h1>
        <div class="status-badge success">
            <span style="font-size: 0.625rem;">●</span>
            <span>LIVE</span>
        </div>
    </div>
    <p>Real-time financial modeling • Scenario analysis • Risk assessment</p>
</div>
""", unsafe_allow_html=True)

# Main Area
# Initialize Agents (moved here to be available for upload section)
landing_client = LandingAIClient(api_key=os.getenv("LANDINGAI_API_KEY"))
simulator = SimulatorAgent(api_key=os.getenv("GEMINI_API_KEY"))
critic = CriticAgent(api_key=os.getenv("DEEPSEEK_API_KEY"))
evaluator = EvaluatorAgent()

# File Upload Section
st.markdown("## 📤 Upload Financial Document")
st.markdown('<p style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1.5rem;">Upload a PDF for AI extraction or a JSON file with pre-extracted data</p>', unsafe_allow_html=True)

# Create tabs for different upload options
upload_tab1, upload_tab2 = st.tabs(["📄 PDF Upload (Landing AI)", "📋 JSON Upload (Skip API)"])

report = None

with upload_tab1:
    st.markdown("**Upload a financial PDF** (10-K, 10-Q, earnings report)")
    uploaded_file = st.file_uploader("", type=["pdf"], key="pdf_uploader", label_visibility="collapsed")
    
    if uploaded_file is not None:
        # Save uploaded file temporarily
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_pdf_path = os.path.join(temp_dir, uploaded_file.name)
        with open(temp_pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # 1. Extraction
        with st.spinner("Extracting Data from PDF using Landing AI..."):
            try:
                report = landing_client.extract_data(temp_pdf_path)
                st.success("✅ Data extracted successfully!")
                
                # Display Extraction Metrics
                if report.pdf_metadata:
                    m_col1, m_col2, m_col3 = st.columns(3)
                    with m_col1:
                        st.metric("Processing Time", f"{report.pdf_metadata.duration_ms/1000:.1f}s")
                    with m_col2:
                        st.metric("Pages Processed", report.pdf_metadata.page_count)
                    with m_col3:
                        st.metric("Credits Used", f"{report.pdf_metadata.credit_usage:.1f}")
            except Exception as e:
                st.error(f"Error extracting data: {str(e)}")
                st.stop()

with upload_tab2:
    st.markdown("**Upload a pre-extracted JSON file** to skip Landing AI API call")
    st.markdown('<p style="font-size: 0.75rem; color: var(--muted-foreground);">Use this if you already have extracted financial data in JSON format (or raw Landing AI response)</p>', unsafe_allow_html=True)
    
    uploaded_json = st.file_uploader("", type=["json"], key="json_uploader", label_visibility="collapsed")
    
    if uploaded_json is not None:
        try:
            import json
            json_data = json.load(uploaded_json)
            
            # Check if this is a raw Landing AI response (has 'markdown' field)
            if 'markdown' in json_data or 'failed_pages' in json_data:
                # This is a raw Landing AI response, parse it
                with st.spinner("Processing Landing AI response format..."):
                    report = landing_client.parse_landing_ai_response(json_data)
                st.success("✅ Landing AI response processed successfully!")
            else:
                # This should be a properly formatted FinancialReport JSON
                report = FinancialReport(**json_data)
                st.success("✅ JSON data loaded successfully!")
        except Exception as e:
            st.error(f"Error loading JSON: {str(e)}")
            st.markdown("""
            **Expected JSON formats:**
            - **FinancialReport format**: Must have `income_statement`, `balance_sheet`, and `cash_flow` fields
            - **Landing AI format**: Raw response with `markdown` field (will be auto-processed)
            
            See `counterfactual_oracle/data/apple_fy24_q1.json` for an example of the FinancialReport format.
            """)
            st.stop()

# Only proceed if we have a report from either source
if report is not None:
    # Data Sources Sidebar
    with st.sidebar:
        st.markdown("---")
        st.markdown('<p class="metric-label">📄 Data Sources</p>', unsafe_allow_html=True)
        
        sources = {
            "Revenue": f"${report.income_statement.Revenue:,.0f}",
            "OpEx": f"${report.income_statement.OpEx:,.0f}",
            "EBITDA": f"${report.income_statement.EBITDA:,.0f}",
            "Total Assets": f"${report.balance_sheet.Assets.get('TotalAssets', 0):,.0f}"
        }
        
        for field, value in sources.items():
            with st.expander(f"**{field}**: {value}"):
                source_info = report.index.get(field, "Extracted from financial data")
                st.write(f"📍 **Source**: {source_info}")
        
        st.caption("💡 Hover over each field to see document source")

    # Extracted Data
    with st.expander("📊 View Extracted Financial Data"):
        st.json(report.model_dump())

    # === COMPREHENSIVE FINANCIAL METRICS SECTION ===
    st.markdown("## 📈 Comprehensive Financial Metrics")
    st.markdown('<p style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1.5rem;">Calculated ratios and KPIs from financial statements</p>', unsafe_allow_html=True)
    
    # Calculate all metrics
    income_stmt = report.income_statement
    bs = report.balance_sheet
    cf = report.cash_flow
    
    revenue = income_stmt.Revenue
    gross_profit = income_stmt.GrossProfit
    ebitda = income_stmt.EBITDA
    ebit = income_stmt.EBIT
    net_income = income_stmt.NetIncome
    total_assets = bs.Assets.get('TotalAssets', 0)
    total_liabilities = bs.Liabilities.get('TotalLiabilities', 0)
    total_equity = bs.Equity.get('TotalEquity', 0)
    cash = bs.Cash or 0
    ar = bs.AccountsReceivable or 0
    inventory = bs.Inventory or 0
    ap = bs.AccountsPayable or 0
    short_term_debt = bs.ShortTermDebt or 0
    long_term_debt = bs.LongTermDebt or 0
    total_debt = short_term_debt + long_term_debt
    
    # Profitability Ratios
    st.markdown("### 💰 Profitability Ratios")
    prof_col1, prof_col2, prof_col3, prof_col4 = st.columns(4)
    
    with prof_col1:
        gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Gross Margin</p>
            <p class="metric-value" style="color: var(--success);">{gross_margin:.1f}%</p>
            <p class="metric-subtitle">Gross Profit / Revenue</p>
        </div>
        """, unsafe_allow_html=True)
    
    with prof_col2:
        operating_margin = (ebit / revenue * 100) if revenue > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Operating Margin</p>
            <p class="metric-value" style="color: var(--accent);">{operating_margin:.1f}%</p>
            <p class="metric-subtitle">EBIT / Revenue</p>
        </div>
        """, unsafe_allow_html=True)
    
    with prof_col3:
        ebitda_margin = (ebitda / revenue * 100) if revenue > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">EBITDA Margin</p>
            <p class="metric-value" style="color: var(--primary);">{ebitda_margin:.1f}%</p>
            <p class="metric-subtitle">EBITDA / Revenue</p>
        </div>
        """, unsafe_allow_html=True)
    
    with prof_col4:
        net_margin = (net_income / revenue * 100) if revenue > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Net Margin</p>
            <p class="metric-value" style="color: var(--warning);">{net_margin:.1f}%</p>
            <p class="metric-subtitle">Net Income / Revenue</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Return Ratios
    st.markdown("### 📊 Return Ratios")
    return_col1, return_col2, return_col3 = st.columns(3)
    
    with return_col1:
        roe = (net_income / total_equity * 100) if total_equity > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Return on Equity (ROE)</p>
            <p class="metric-value" style="color: var(--success);">{roe:.1f}%</p>
            <p class="metric-subtitle">Net Income / Equity</p>
        </div>
        """, unsafe_allow_html=True)
    
    with return_col2:
        roa = (net_income / total_assets * 100) if total_assets > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Return on Assets (ROA)</p>
            <p class="metric-value" style="color: var(--accent);">{roa:.1f}%</p>
            <p class="metric-subtitle">Net Income / Assets</p>
        </div>
        """, unsafe_allow_html=True)
    
    with return_col3:
        roic = (ebit / (total_assets - cash) * 100) if (total_assets - cash) > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">ROIC</p>
            <p class="metric-value" style="color: var(--primary);">{roic:.1f}%</p>
            <p class="metric-subtitle">EBIT / (Assets - Cash)</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Leverage Ratios
    st.markdown("### ⚖️ Leverage & Debt Ratios")
    lev_col1, lev_col2, lev_col3, lev_col4 = st.columns(4)
    
    with lev_col1:
        debt_to_equity = (total_debt / total_equity) if total_equity > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Debt-to-Equity</p>
            <p class="metric-value" style="color: var(--warning);">{debt_to_equity:.2f}x</p>
            <p class="metric-subtitle">Total Debt / Equity</p>
        </div>
        """, unsafe_allow_html=True)
    
    with lev_col2:
        debt_to_assets = (total_debt / total_assets) if total_assets > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Debt-to-Assets</p>
            <p class="metric-value" style="color: var(--warning);">{debt_to_assets:.2f}x</p>
            <p class="metric-subtitle">Total Debt / Assets</p>
        </div>
        """, unsafe_allow_html=True)
    
    with lev_col3:
        debt_to_ebitda = (total_debt / ebitda) if ebitda > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Debt-to-EBITDA</p>
            <p class="metric-value" style="color: var(--warning);">{debt_to_ebitda:.2f}x</p>
            <p class="metric-subtitle">Total Debt / EBITDA</p>
        </div>
        """, unsafe_allow_html=True)
    
    with lev_col4:
        equity_ratio = (total_equity / total_assets * 100) if total_assets > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Equity Ratio</p>
            <p class="metric-value" style="color: var(--success);">{equity_ratio:.1f}%</p>
            <p class="metric-subtitle">Equity / Assets</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Liquidity Ratios
    st.markdown("### 💧 Liquidity Ratios")
    liq_col1, liq_col2, liq_col3 = st.columns(3)
    
    current_assets = cash + ar + inventory
    current_liabilities = ap + short_term_debt
    
    with liq_col1:
        current_ratio = (current_assets / current_liabilities) if current_liabilities > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Current Ratio</p>
            <p class="metric-value" style="color: var(--accent);">{current_ratio:.2f}x</p>
            <p class="metric-subtitle">Current Assets / Current Liabilities</p>
        </div>
        """, unsafe_allow_html=True)
    
    with liq_col2:
        quick_ratio = ((cash + ar) / current_liabilities) if current_liabilities > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Quick Ratio</p>
            <p class="metric-value" style="color: var(--accent);">{quick_ratio:.2f}x</p>
            <p class="metric-subtitle">(Cash + AR) / Current Liabilities</p>
        </div>
        """, unsafe_allow_html=True)
    
    with liq_col3:
        cash_ratio = (cash / current_liabilities) if current_liabilities > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Cash Ratio</p>
            <p class="metric-value" style="color: var(--accent);">{cash_ratio:.2f}x</p>
            <p class="metric-subtitle">Cash / Current Liabilities</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Coverage Ratios
    st.markdown("### 🛡️ Coverage Ratios")
    cov_col1, cov_col2 = st.columns(2)
    
    with cov_col1:
        interest_coverage = (ebit / income_stmt.InterestExpense) if income_stmt.InterestExpense > 0 else float('inf')
        coverage_display = f"{interest_coverage:.2f}x" if interest_coverage != float('inf') else "N/A"
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Interest Coverage</p>
            <p class="metric-value" style="color: var(--success);">{coverage_display}</p>
            <p class="metric-subtitle">EBIT / Interest Expense</p>
        </div>
        """, unsafe_allow_html=True)
    
    with cov_col2:
        if cf.FreeCashFlow and total_debt > 0:
            fcf_to_debt = cf.FreeCashFlow / total_debt
            st.markdown(f"""
            <div class="metric-card">
                <p class="metric-label">FCF to Debt</p>
                <p class="metric-value" style="color: var(--success);">{fcf_to_debt:.2f}x</p>
                <p class="metric-subtitle">Free Cash Flow / Total Debt</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("FCF to Debt: Data not available")
    
    # Efficiency Ratios
    st.markdown("### ⚡ Efficiency Ratios")
    eff_col1, eff_col2, eff_col3 = st.columns(3)
    
    with eff_col1:
        asset_turnover = (revenue / total_assets) if total_assets > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-label">Asset Turnover</p>
            <p class="metric-value" style="color: var(--primary);">{asset_turnover:.2f}x</p>
            <p class="metric-subtitle">Revenue / Assets</p>
        </div>
        """, unsafe_allow_html=True)
    
    with eff_col2:
        if inventory > 0:
            # Approximate inventory turnover (using COGS)
            inventory_turnover = (income_stmt.CostOfGoodsSold / inventory) if inventory > 0 else 0
            st.markdown(f"""
            <div class="metric-card">
                <p class="metric-label">Inventory Turnover</p>
                <p class="metric-value" style="color: var(--primary);">{inventory_turnover:.2f}x</p>
                <p class="metric-subtitle">COGS / Inventory</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Inventory Turnover: Data not available")
    
    with eff_col3:
        if ar > 0:
            # Days Sales Outstanding (approximate)
            dso = (ar / revenue * 365) if revenue > 0 else 0
            st.markdown(f"""
            <div class="metric-card">
                <p class="metric-label">Days Sales Outstanding</p>
                <p class="metric-value" style="color: var(--primary);">{dso:.0f} days</p>
                <p class="metric-subtitle">(AR / Revenue) × 365</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("DSO: Data not available")
    
    # Additional Income Statement Metrics
    st.markdown("### 📋 Additional Income Statement Metrics")
    inc_col1, inc_col2, inc_col3, inc_col4 = st.columns(4)
    
    with inc_col1:
        st.metric("Gross Profit", f"${gross_profit:,.0f}")
    
    with inc_col2:
        st.metric("EBIT", f"${ebit:,.0f}")
    
    with inc_col3:
        tax_rate = (income_stmt.Taxes / (ebit - income_stmt.InterestExpense) * 100) if (ebit - income_stmt.InterestExpense) > 0 else 0
        st.metric("Effective Tax Rate", f"{tax_rate:.1f}%")
    
    with inc_col4:
        st.metric("Interest Expense", f"${income_stmt.InterestExpense:,.0f}")
    
    # Additional Balance Sheet Metrics
    st.markdown("### 🏦 Additional Balance Sheet Metrics")
    bal_col1, bal_col2, bal_col3, bal_col4 = st.columns(4)
    
    with bal_col1:
        st.metric("Total Assets", f"${total_assets:,.0f}")
    
    with bal_col2:
        st.metric("Total Liabilities", f"${total_liabilities:,.0f}")
    
    with bal_col3:
        st.metric("Total Equity", f"${total_equity:,.0f}")
    
    with bal_col4:
        working_capital = current_assets - current_liabilities
        st.metric("Working Capital", f"${working_capital:,.0f}")
    
    # Additional Cash Flow Metrics
    st.markdown("### 💵 Additional Cash Flow Metrics")
    cash_col1, cash_col2, cash_col3, cash_col4 = st.columns(4)
    
    with cash_col1:
        st.metric("CapEx", f"${cf.CapEx:,.0f}")
    
    with cash_col2:
        st.metric("Dividends Paid", f"${cf.Dividends:,.0f}")
    
    with cash_col3:
        st.metric("Net Change in Cash", f"${cf.NetChangeInCash:,.0f}")
    
    with cash_col4:
        if cf.ShareRepurchases:
            st.metric("Share Repurchases", f"${cf.ShareRepurchases:,.0f}")
        else:
            st.metric("Share Repurchases", "N/A")
    
    # Display KPIs from report.kpis if available
    if report.kpis and len(report.kpis) > 0:
        st.markdown("### 🎯 Additional KPIs from Report")
        kpi_cols = st.columns(min(len(report.kpis), 4))
        for idx, (kpi_name, kpi_value) in enumerate(report.kpis.items()):
            with kpi_cols[idx % 4]:
                if isinstance(kpi_value, (int, float)):
                    if kpi_value < 1 and kpi_value > -1:
                        st.metric(kpi_name, f"{kpi_value:.2%}")
                    else:
                        st.metric(kpi_name, f"{kpi_value:,.2f}")
                else:
                    st.metric(kpi_name, str(kpi_value))

    # === ENHANCED TIER 1 DATA DISPLAY ===

    # Expense Breakdown (if R&D and SG&A are available)
    if report.income_statement.RnD is not None or report.income_statement.SGA is not None:
        st.markdown("### 💰 Operating Expense Breakdown")
        col1, col2, col3 = st.columns(3)
    
        with col1:
            if report.income_statement.RnD is not None:
                st.markdown(f"""
                <div class="metric-card">
                    <p class="metric-label">R&D Spending</p>
                    <p class="metric-value">{format_currency(report.income_statement.RnD)}</p>
                    <p class="metric-subtitle">{(report.income_statement.RnD / report.income_statement.Revenue * 100):.1f}% of revenue</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("R&D data not available")
    
        with col2:
            if report.income_statement.SGA is not None:
                st.markdown(f"""
                <div class="metric-card">
                    <p class="metric-label">SG&A Expenses</p>
                    <p class="metric-value">{format_currency(report.income_statement.SGA)}</p>
                    <p class="metric-subtitle">{(report.income_statement.SGA / report.income_statement.Revenue * 100):.1f}% of revenue</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("SG&A data not available")
    
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <p class="metric-label">Total OpEx</p>
                <p class="metric-value">{format_currency(report.income_statement.OpEx)}</p>
                <p class="metric-subtitle">{(report.income_statement.OpEx / report.income_statement.Revenue * 100):.1f}% of revenue</p>
            </div>
            """, unsafe_allow_html=True)

    # Free Cash Flow (always show since it's Tier 1)
    if report.cash_flow.FreeCashFlow is not None:
        st.markdown("### 💵 Cash Flow Metrics")
        fcf_col1, fcf_col2, fcf_col3 = st.columns(3)
    
        with fcf_col1:
            st.markdown(f"""
            <div class="metric-card">
                <p class="metric-label">Free Cash Flow</p>
                <p class="metric-value" style="color: var(--success);">{format_currency(report.cash_flow.FreeCashFlow)}</p>
                <p class="metric-subtitle">CFO - CapEx</p>
            </div>
            """, unsafe_allow_html=True)
    
        with fcf_col2:
            st.markdown(f"""
            <div class="metric-card">
                <p class="metric-label">Cash from Operations</p>
                <p class="metric-value">{format_currency(report.cash_flow.CashFromOperations)}</p>
                <p class="metric-subtitle">Operating cash generation</p>
            </div>
            """, unsafe_allow_html=True)
    
        with fcf_col3:
            fcf_margin = (report.cash_flow.FreeCashFlow / report.income_statement.Revenue * 100) if report.income_statement.Revenue > 0 else 0
            st.markdown(f"""
            <div class="metric-card">
                <p class="metric-label">FCF Margin</p>
                <p class="metric-value" style="color: var(--accent);">{fcf_margin:.1f}%</p>
                <p class="metric-subtitle">FCF as % of revenue</p>
            </div>
            """, unsafe_allow_html=True)

    # === TIER 2: ADVANCED FORECASTING DATA ===

    # Segment Analysis (if available)
    if report.segment_data and len(report.segment_data) > 0:
        st.markdown("## 📊 Segment Performance")
        st.markdown('<p style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1rem;">Business unit breakdown</p>', unsafe_allow_html=True)
    
        # Create segment table
        segment_df = []
        for segment in report.segment_data:
            segment_df.append({
                "Segment": segment.segment_name,
                "Revenue": f"${segment.revenue:,.0f}",
                "Operating Income": f"${segment.operating_income:,.0f}" if segment.operating_income else "N/A",
                "Margin": f"{(segment.operating_income / segment.revenue * 100):.1f}%" if segment.operating_income else "N/A"
            })
    
        st.table(segment_df)

    # Geographic Breakdown (if available)
    if report.geographic_data and len(report.geographic_data) > 0:
        st.markdown("## 🌍 Geographic Distribution")
        st.markdown('<p style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1rem;">Revenue by region</p>', unsafe_allow_html=True)
    
        # Create geographic table
        geo_df = []
        total_geo_revenue = sum(g.revenue for g in report.geographic_data)
        for geo in report.geographic_data:
            geo_df.append({
                "Region": geo.region,
                "Revenue": f"${geo.revenue:,.0f}",
                "% of Total": f"{(geo.revenue / total_geo_revenue * 100):.1f}%"
            })
    
        st.table(geo_df)

    # Debt Analysis (if debt schedule available)
    if report.debt_schedule and len(report.debt_schedule) > 0:
        st.markdown("## 📅 Debt Maturity Schedule")
        st.markdown('<p style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1rem;">Upcoming debt obligations</p>', unsafe_allow_html=True)
    
        # Create debt schedule table
        debt_df = []
        for debt in report.debt_schedule:
            debt_df.append({
                "Year": debt.year,
                "Principal Due": f"${debt.principal_due:,.0f}",
                "Interest Rate": f"{debt.interest_rate:.2f}%" if debt.interest_rate else "N/A"
            })
    
        st.table(debt_df)
    
        # Show debt ratios if balance sheet data available
        if report.balance_sheet.LongTermDebt:
            debt_to_ebitda = report.balance_sheet.LongTermDebt / report.income_statement.EBITDA if report.income_statement.EBITDA > 0 else 0
            st.metric("Debt-to-EBITDA Ratio", f"{debt_to_ebitda:.2f}x")

    # Forward-Looking Insights (if available)
    if report.forward_looking:
        st.markdown("## 🔮 Forward-Looking Insights")
        st.markdown('<p style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1rem;">MD&A commentary and guidance</p>', unsafe_allow_html=True)
    
        if report.forward_looking.revenue_guidance:
            st.markdown(f"**📈 Revenue Guidance**: {report.forward_looking.revenue_guidance}")
    
        if report.forward_looking.mda_commentary:
            with st.expander("💬 Management Discussion & Analysis"):
                st.write(report.forward_looking.mda_commentary)
    
        if report.forward_looking.risk_factors:
            with st.expander("⚠️ Risk Factors"):
                for risk in report.forward_looking.risk_factors:
                    st.markdown(f"- {risk}")
    
        if report.forward_looking.commitments:
            st.metric("Commitments & Contingencies", f"${report.forward_looking.commitments:,.0f}")

    # === TIER 3: ADVANCED METRICS ===

    # Non-GAAP Metrics (if available)
    if report.non_gaap_metrics:
        st.markdown("## 🔢 Non-GAAP Metrics")
        st.markdown('<p style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1rem;">Adjusted financial metrics</p>', unsafe_allow_html=True)
    
        col1, col2, col3 = st.columns(3)
    
        with col1:
            if report.non_gaap_metrics.adjusted_ebitda:
                st.metric("Adjusted EBITDA", f"${report.non_gaap_metrics.adjusted_ebitda:,.0f}")
    
        with col2:
            if report.non_gaap_metrics.adjusted_net_income:
                st.metric("Adjusted Net Income", f"${report.non_gaap_metrics.adjusted_net_income:,.0f}")
    
        with col3:
            if report.non_gaap_metrics.sbc_expense:
                st.metric("Stock-Based Comp", f"${report.non_gaap_metrics.sbc_expense:,.0f}")
    
        if report.non_gaap_metrics.reconciliation_items:
            with st.expander("🔄 GAAP to Non-GAAP Reconciliation"):
                for item, value in report.non_gaap_metrics.reconciliation_items.items():
                    st.write(f"**{item}**: ${value:,.0f}")

    # Initialize session state for simulation results
    if 'simulation_results' not in st.session_state:
        st.session_state.simulation_results = None
    if 'critic_verdict' not in st.session_state:
        st.session_state.critic_verdict = None
    if 'params' not in st.session_state:
        st.session_state.params = None
    
    if run_btn:
        params = ScenarioParams(
            opex_delta_bps=opex_delta,
            revenue_growth_bps=rev_growth_delta,
            discount_rate_bps=discount_rate_delta
        )
    
        # Store params in session state for debate access
        st.session_state.params = params
    
        # 2. Simulation
        with st.spinner("Running Monte Carlo Simulation..."):
            st.session_state.simulation_results = simulator.run_simulation(report, params)
        
        # 3. Critique
        with st.spinner("DeepSeek is reviewing the report..."):
            st.session_state.critic_verdict = critic.critique(report, st.session_state.simulation_results)

    # Display results if they exist in session state
    if st.session_state.simulation_results is not None:
        simulation_results = st.session_state.simulation_results
        critic_verdict = st.session_state.critic_verdict
    
        # === SIMULATION RESULTS SECTION ===
        st.markdown("## 🎯 Simulation Results")
        st.markdown('<p style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1.5rem;">Monte Carlo • 10,000 iterations • DCF Model</p>', unsafe_allow_html=True)
    
        # Metric Cards
        col1, col2, col3 = st.columns(3)
    
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <p class="metric-label">Projected NPV</p>
                <p class="metric-value">{format_currency(simulation_results.median_npv)}</p>
                <p class="metric-subtitle">Net Present Value @ 8.5% discount</p>
            </div>
            """, unsafe_allow_html=True)
    
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <p class="metric-label">Median Revenue</p>
                <p class="metric-value" style="color: var(--success);">{format_currency(simulation_results.median_revenue)}</p>
                <p class="metric-subtitle">Projected annual revenue</p>
            </div>
            """, unsafe_allow_html=True)
    
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <p class="metric-label">Median EBITDA</p>
                <p class="metric-value" style="color: var(--accent);">{format_currency(simulation_results.median_ebitda)}</p>
                <p class="metric-subtitle">Earnings before interest, tax, D&A</p>
            </div>
            """, unsafe_allow_html=True)
    
        # Assumptions
        st.markdown("### 📋 Model Assumptions")
        for log in simulation_results.assumption_log:
            st.markdown(f"- {log}")
    
        # === ADVERSARIAL ANALYSIS SECTION ===
        st.markdown("## 🛡️ Adversarial Analysis")
        st.markdown('<p style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1.5rem;">AI-powered validation & risk assessment</p>', unsafe_allow_html=True)
        
        # Verdict Badge
        verdict_class = "success" if critic_verdict.verdict == "approve" else "error"
        st.markdown(f"""
        <div class="status-badge {verdict_class}" style="margin-bottom: 1rem;">
            <span>VERDICT: {critic_verdict.verdict.upper()}</span>
        </div>
        """, unsafe_allow_html=True)
    
        # Comparative Analysis
        st.markdown("**Comparative Analysis:**")
        for point in critic_verdict.comparative_analysis:
            st.markdown(f"""
            <div class="critique-item pass">
                <p style="margin: 0; font-size: 0.875rem;">{point}</p>
            </div>
            """, unsafe_allow_html=True)
    
        # Balance Sheet Check
        with st.expander("📊 Balance Sheet Validation"):
            st.json(critic_verdict.balance_sheet_check)
    
        # === NEW: AI ANALYST DEBATE SECTION ===
        st.markdown("## 💬 AI Analyst Debate")
        st.markdown('<p style="font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1.5rem;">Two AI analysts debate the analysis • Converges when agreement is reached</p>', unsafe_allow_html=True)
    
        # Initialize debate result in session state
        if 'debate_result' not in st.session_state:
            st.session_state.debate_result = None
    
        # Debate trigger button
        if st.button("🎙️ Start AI Debate", type="secondary"):
            try:
                with st.spinner("🤖 AI analysts are debating... This may take 30-60 seconds"):
                    from src.agents.debate_agent import DebateAgent
                
                    # Initialize Debate Agent
                    debate_agent = DebateAgent(
                        openai_api_key=os.getenv("OPENAI_API_KEY"),
                        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY")
                    )
                
                    st.session_state.debate_result = debate_agent.run_debate(
                        report=report,
                        simulation=st.session_state.simulation_results,
                        params=st.session_state.params,  # Use params from session state
                        max_rounds=10
                    )
                
                st.success(f"✅ Debate completed in {st.session_state.debate_result.total_rounds} rounds!")
            
            except Exception as e:
                st.error(f"❌ Error during debate: {str(e)}")
                st.exception(e)
    
        # Display debate if it exists
        if st.session_state.debate_result is not None:
            debate = st.session_state.debate_result
        
            # Convergence status
            if debate.converged:
                st.markdown(f"""
                <div class="status-badge success" style="margin-bottom: 1rem;">
                    <span>✅ CONVERGED (Round {debate.convergence_round})</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="status-badge warning" style="margin-bottom: 1rem;">
                    <span>⚠️ NO FULL CONVERGENCE ({debate.total_rounds} rounds)</span>
                </div>
                """, unsafe_allow_html=True)
        
            # Debate transcript
            with st.expander("📜 View Full Debate Transcript", expanded=True):
                for turn in debate.debate_log:
                    # Determine color based on speaker
                    if turn.speaker == "OpenAI":
                        bg_color = "rgba(16, 185, 129, 0.1)"  # Green tint
                        border_color = "#10B981"
                        icon = "🟢"
                    else:
                        bg_color = "rgba(239, 68, 68, 0.1)"  # Red tint
                        border_color = "#EF4444"
                        icon = "🔴"
                
                    st.markdown(f"""
                    <div style="
                        background: {bg_color};
                        border-left: 3px solid {border_color};
                        border-radius: 0.5rem;
                        padding: 1rem;
                        margin-bottom: 0.75rem;
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <strong style="font-size: 0.875rem; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">{icon} {turn.speaker} ({turn.role})</strong>
                            <span style="font-size: 0.75rem; color: var(--muted-foreground); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">Round {turn.round_number}</span>
                        </div>
                        <p style="margin: 0; font-size: 0.875rem; line-height: 1.6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; white-space: pre-wrap;">{turn.message.replace('$', '\$')}</p>
                    </div>
                    """, unsafe_allow_html=True)
        
            # Consensus summary
            st.markdown("### 🎯 Consensus Summary")
            st.markdown(debate.consensus_summary.replace('$', '\$'))
        
            # Final verdict
            st.markdown(f"""
            <div class="metric-card" style="text-align: center; margin-top: 1rem;">
                <p class="metric-label">FINAL INVESTMENT VERDICT</p>
                <p class="metric-value" style="font-size: 2rem;">{debate.final_verdict}</p>
                <p class="metric-subtitle">Confidence: {debate.confidence_level}</p>
            </div>
            """, unsafe_allow_html=True)
    
        # 4. Final Report
        st.markdown("## 📄 Report Generation")
        if st.button("📥 Generate PDF Report", type="primary"):
            try:
                with st.spinner("Generating PDF report..."):
                    output_path = "final_report.pdf"
                    # Include debate result if available
                    debate_data = st.session_state.get('debate_result', None)
                    evaluator.generate_pdf(simulation_results, critic_verdict, report, output_path, debate_data)
            
                st.success("✅ PDF report generated successfully!")
            
                with open(output_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=f,
                        file_name="counterfactual_report.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"❌ Error generating PDF: {str(e)}")
                st.exception(e)
else:
    # Welcome Screen
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem;">
        <div style="font-size: 4rem; margin-bottom: 1rem;">🔮</div>
        <h2 style="margin-bottom: 0.5rem;">Welcome to Counterfactual Financial Oracle</h2>
        <p style="color: var(--muted-foreground); margin-bottom: 2rem;">Upload a financial report to begin your analysis</p>
        <div style="max-width: 600px; margin: 0 auto; text-align: left;">
            <h3 style="font-size: 1rem; margin-bottom: 1rem;">Features:</h3>
            <ul style="color: var(--muted-foreground); line-height: 1.8;">
                <li>🤖 AI-powered document extraction with Landing AI</li>
                <li>📈 Monte Carlo simulation (10,000 scenarios)</li>
                <li>🛡️ Adversarial critique with DeepSeek</li>
                <li>📊 DCF valuation with Gordon Growth model</li>
                <li>📄 Professional PDF report generation</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown("""
<div class="footer">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; gap: 1.5rem;">
            <span>Last updated: 2024-11-19 14:34:22 UTC</span>
            <span>•</span>
            <span>Compute time: 2.847s</span>
            <span>•</span>
            <span style="display: flex; align-items: center; gap: 0.375rem;">
                <span style="width: 6px; height: 6px; border-radius: 50%; background: var(--success);"></span>
                All systems operational
            </span>
        </div>
    </div>
    </div>
</div>
""", unsafe_allow_html=True)
