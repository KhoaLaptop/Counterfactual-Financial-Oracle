export interface SimulationResults {
    median_npv: number;
    median_revenue: number;
    median_ebitda: number;
    assumption_log: string[];
    revenue_growth_dist?: number[];
    cash_flow_dist?: number[];
    npv_dist?: number[];
}

export interface CriticVerdict {
    verdict: 'approve' | 'reject';
    comparative_analysis: string[];
}

export interface DebateResult {
    confidence_level: string;
    rounds: any[];
}

export interface Scenario {
    id: string;
    name: string;
    status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
    progress: number;
    error_message?: string;
    simulation_results?: SimulationResults;
    critic_verdict?: CriticVerdict;
    debate_result?: DebateResult;
    final_verdict?: string;
    created_at: string;
}

export interface ScenarioStatus {
    status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
    progress: number;
    error_message?: string;
}

export interface IncomeStatement {
    Revenue: number;
    CostOfGoodsSold: number;
    GrossProfit: number;
    OpEx: number;
    EBITDA: number;
    DepreciationAndAmortization: number;
    EBIT: number;
    InterestExpense: number;
    Taxes: number;
    NetIncome: number;
}

export interface BalanceSheet {
    Assets: { [key: string]: number };
    Liabilities: { [key: string]: number };
    Equity: { [key: string]: number };
    Cash?: number;
    ShortTermDebt?: number;
    LongTermDebt?: number;
}

export interface CashFlow {
    NetIncome: number;
    Depreciation: number;
    ChangeInWorkingCapital: number;
    CashFromOperations: number;
    CapEx: number;
    CashFromInvesting: number;
    CashFromFinancing: number;
    NetChangeInCash: number;
    FreeCashFlow?: number;
}

export interface FinancialReportData {
    income_statement: IncomeStatement;
    balance_sheet: BalanceSheet;
    cash_flow: CashFlow;
    kpis: { [key: string]: number };
}

export interface ReportSummary {
    id: string;
    company_name: string | null;
    fiscal_year: number | null;
    created_at: string;
    pdf_metadata?: any;
}

export interface Report {
    id: string;
    company_name: string | null;
    fiscal_year: number | null;
    report_data: FinancialReportData;
    pdf_metadata: any;
    created_at: string;
}

export interface CreateScenarioRequest {
    report_id: string;
    revenue_growth_delta_bps: number;
    opex_delta_bps: number;
    discount_rate_delta_bps: number;
}
