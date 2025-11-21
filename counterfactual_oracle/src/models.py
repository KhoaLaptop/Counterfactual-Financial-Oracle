from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

# === SOURCE METADATA ===

class SourceMetadata(BaseModel):
    """Tracks the document source of extracted financial data"""
    field_name: str
    value: float
    source_page: Optional[int] = None
    source_text: Optional[str] = None
    bounding_box: Optional[Dict[str, float]] = None
    extraction_confidence: Optional[float] = None

# === TIER 1: MUST-HAVE FINANCIAL STATEMENTS ===

class IncomeStatement(BaseModel):
    """Enhanced Income Statement with segment-level and expense breakdown"""
    # Core metrics (required)
    Revenue: float
    CostOfGoodsSold: float
    GrossProfit: float
    OpEx: float
    EBITDA: float
    DepreciationAndAmortization: float
    EBIT: float
    InterestExpense: float
    Taxes: float
    NetIncome: float
    
    # Tier 1 enhancements (optional but valuable)
    RnD: Optional[float] = None              # R&D expenses (separate from OpEx)
    SGA: Optional[float] = None              # SG&A expenses (separate from OpEx)
    segment_revenue: Optional[Dict[str, float]] = None  # Revenue by business segment

class BalanceSheet(BaseModel):
    """Enhanced Balance Sheet with detailed breakdowns"""
    Assets: Dict[str, float]
    Liabilities: Dict[str, float]
    Equity: Dict[str, float]
    
    # Tier 1 enhancements (optional)
    Cash: Optional[float] = None
    ShortTermDebt: Optional[float] = None
    LongTermDebt: Optional[float] = None
    AccountsReceivable: Optional[float] = None
    Inventory: Optional[float] = None
    AccountsPayable: Optional[float] = None

class CashFlow(BaseModel):
    """Enhanced Cash Flow Statement with FCF"""
    NetIncome: float
    Depreciation: float
    ChangeInWorkingCapital: float
    CashFromOperations: float
    CapEx: float
    CashFromInvesting: float
    DebtRepayment: float
    Dividends: float
    CashFromFinancing: float
    NetChangeInCash: float
    
    # Tier 1 enhancements
    FreeCashFlow: Optional[float] = None     # CFO - CapEx
    ShareRepurchases: Optional[float] = None

# === TIER 2: ADVANCED FORECASTING DATA ===

class SegmentData(BaseModel):
    """Business segment performance data"""
    segment_name: str
    revenue: float
    operating_income: Optional[float] = None
    assets: Optional[float] = None
    
class GeographicData(BaseModel):
    """Geographic breakdown of business"""
    region: str
    revenue: float
    long_lived_assets: Optional[float] = None

class DebtSchedule(BaseModel):
    """Debt maturity schedule"""
    year: int
    principal_due: float
    interest_rate: Optional[float] = None

class ForwardLookingData(BaseModel):
    """MD&A and forward-looking statements"""
    mda_commentary: Optional[str] = None
    revenue_guidance: Optional[str] = None
    risk_factors: List[str] = Field(default_factory=list)
    commitments: Optional[float] = None
    contingencies: Optional[str] = None

# === TIER 3: ADVANCED METRICS ===

class NonGAAPMetrics(BaseModel):
    """Non-GAAP adjustments and reconciliations"""
    adjusted_ebitda: Optional[float] = None
    adjusted_net_income: Optional[float] = None
    sbc_expense: Optional[float] = None  # Stock-based compensation
    reconciliation_items: Dict[str, float] = Field(default_factory=dict)

class LegalAndRegulatory(BaseModel):
    """Legal risks and regulatory disclosures"""
    legal_proceedings: List[str] = Field(default_factory=list)
    regulatory_matters: List[str] = Field(default_factory=list)
    off_balance_sheet: Optional[str] = None

# === COMPLETE FINANCIAL REPORT ===

class FinancialReport(BaseModel):
    """Comprehensive financial report with Tier 1-3 data"""
    # Tier 1: Core statements (required)
    income_statement: IncomeStatement
    balance_sheet: BalanceSheet
    cash_flow: CashFlow
    
    # Tier 2: Advanced forecasting (optional)
    segment_data: List[SegmentData] = Field(default_factory=list)
    geographic_data: List[GeographicData] = Field(default_factory=list)
    debt_schedule: List[DebtSchedule] = Field(default_factory=list)
    forward_looking: Optional[ForwardLookingData] = None
    
    # Tier 3: Optional but powerful (optional)
    non_gaap_metrics: Optional[NonGAAPMetrics] = None
    legal_regulatory: Optional[LegalAndRegulatory] = None
    
    # Metadata
    kpis: Dict[str, float] = Field(default_factory=dict)
    notes: Dict[str, str] = Field(default_factory=dict)
    index: Dict[str, str] = Field(default_factory=dict)
    source_metadata: List[SourceMetadata] = Field(default_factory=list)

# === SCENARIO AND SIMULATION MODELS ===

class ScenarioParams(BaseModel):
    opex_delta_bps: float = 0.0
    revenue_growth_bps: float = 0.0
    discount_rate_bps: float = 0.0
    tax_rate_delta_bps: float = 0.0

class SimulationResult(BaseModel):
    scenario_id: int
    revenue: float
    ebitda: float
    net_income: float
    fcf: float
    npv: float
    key_driver: str
    # Multi-year forecasts (t1 to t5)
    revenue_forecast: List[float] = Field(default_factory=list)
    ebitda_forecast: List[float] = Field(default_factory=list)
    net_income_forecast: List[float] = Field(default_factory=list)
    fcf_forecast: List[float] = Field(default_factory=list)

class AggregatedSimulation(BaseModel):
    median_npv: float
    p10_npv: float
    p90_npv: float
    median_revenue: float
    median_ebitda: float
    median_fcf: float
    # Aggregated multi-year forecasts (P50)
    revenue_forecast_p50: List[float] = Field(default_factory=list)
    ebitda_forecast_p50: List[float] = Field(default_factory=list)
    fcf_forecast_p50: List[float] = Field(default_factory=list)
    assumption_log: List[str]
    traceability: Dict[str, str]
    simulation_runs: List[SimulationResult]

class CriticVerdict(BaseModel):
    verdict: str
    balance_sheet_check: Dict[str, Any]
    cash_flow_check: Dict[str, Any]
    comparative_analysis: List[str]
    unsupported_assumptions: List[str]
    correction_instructions: Optional[str] = None

# === DEBATE MODULE MODELS ===

class DebateTurn(BaseModel):
    """Represents a single turn in the debate"""
    round_number: int
    speaker: str
    role: str
    message: str
    timestamp: float
    topic_focus: str = "General Analysis"

class DebateResult(BaseModel):
    """Complete result of a multi-round debate"""
    debate_log: List[DebateTurn] = Field(default_factory=list)
    total_rounds: int
    converged: bool
    convergence_round: Optional[int] = None
    consensus_summary: str
    key_agreements: List[str] = Field(default_factory=list)
    key_disagreements: List[str] = Field(default_factory=list)
    final_verdict: str
    confidence_level: str = "Medium"
