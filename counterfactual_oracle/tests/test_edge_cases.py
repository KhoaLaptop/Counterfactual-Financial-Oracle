"""
Edge Case Tests

Tests handling of zero/negative values and other edge cases.
"""

import pytest
from counterfactual_oracle.src.models import (
    FinancialReport, IncomeStatement, BalanceSheet, CashFlow, ScenarioParams
)
from counterfactual_oracle.src.logic import run_monte_carlo
from counterfactual_oracle.src.validators import FinancialValidator

def test_zero_revenue():
    """Test that zero revenue is handled gracefully"""
    report = FinancialReport(
        income_statement=IncomeStatement(
            Revenue=0, CostOfGoodsSold=0, GrossProfit=0, OpEx=0,
            EBITDA=0, DepreciationAndAmortization=0, EBIT=0,
            InterestExpense=0, Taxes=0, NetIncome=0
        ),
        balance_sheet=BalanceSheet(
            Assets={"TotalAssets": 0},
            Liabilities={"TotalLiabilities": 0},
            Equity={"TotalEquity": 0}
        ),
        cash_flow=CashFlow(
            NetIncome=0, Depreciation=0, ChangeInWorkingCapital=0,
            CashFromOperations=0, CapEx=0, CashFromInvesting=0,
            DebtRepayment=0, Dividends=0, CashFromFinancing=0,
            NetChangeInCash=0
        ),
        kpis={"TaxRate": 0.25},
        notes={},
        index={}
    )
    
    params = ScenarioParams()
    
    # Should raise ValueError for zero revenue
    with pytest.raises(ValueError, match="Base revenue must be positive"):
        run_monte_carlo(report, params, num_simulations=10)

def test_negative_margin():
    """Test that negative margins are detected"""
    income = IncomeStatement(
        Revenue=100000,
        CostOfGoodsSold=120000,  # COGS > Revenue
        GrossProfit=-20000,
        OpEx=10000,
        EBITDA=-30000,
        DepreciationAndAmortization=0,
        EBIT=-30000,
        InterestExpense=0,
        Taxes=0,
        NetIncome=-30000
    )
    
    validator = FinancialValidator()
    errors = validator.validate_income_statement(income)
    
    # Should detect negative gross margin
    assert any("Negative gross margin" in e.message for e in errors)

def test_opex_exceeds_revenue():
    """Test that OpEx > Revenue is flagged"""
    income = IncomeStatement(
        Revenue=100000,
        CostOfGoodsSold=40000,
        GrossProfit=60000,
        OpEx=150000,  # OpEx > Revenue
        EBITDA=-90000,
        DepreciationAndAmortization=0,
        EBIT=-90000,
        InterestExpense=0,
        Taxes=0,
        NetIncome=-90000
    )
    
    validator = FinancialValidator()
    errors = validator.validate_income_statement(income)
    
    # Should detect OpEx > Revenue
    assert any("exceed revenue" in e.message.lower() for e in errors)

def test_margin_over_100_percent():
    """Test that margins > 100% are flagged"""
    income = IncomeStatement(
        Revenue=100000,
        CostOfGoodsSold=-20000,  # Negative COGS creates >100% margin
        GrossProfit=120000,
        OpEx=10000,
        EBITDA=110000,
        DepreciationAndAmortization=0,
        EBIT=110000,
        InterestExpense=0,
        Taxes=0,
        NetIncome=110000
    )
    
    validator = FinancialValidator()
    errors = validator.validate_income_statement(income)
    
    # Should detect margin > 100%
    assert any("exceeds 100%" in e.message for e in errors)

def test_balance_sheet_imbalance():
    """Test that balance sheet imbalance is detected"""
    bs = BalanceSheet(
        Assets={"TotalAssets": 100000},
        Liabilities={"TotalLiabilities": 40000},
        Equity={"TotalEquity": 50000}  # Should be 60000 to balance
    )
    
    validator = FinancialValidator()
    errors = validator.validate_balance_sheet(bs)
    
    # Should detect imbalance
    assert any("doesn't balance" in e.message for e in errors)

def test_extreme_scenario_params():
    """Test that extreme scenario parameters are flagged"""
    validator = FinancialValidator()
    errors = validator.validate_scenario_params(
        opex_delta_bps=10000,  # 100% change
        rev_growth_bps=10000,
        discount_rate_bps=0
    )
    
    # Should warn about extreme deltas
    assert any("very large" in e.message for e in errors)

def test_negative_discount_rate():
    """Test that negative discount rates are prevented"""
    validator = FinancialValidator()
    errors = validator.validate_scenario_params(
        opex_delta_bps=0,
        rev_growth_bps=0,
        discount_rate_bps=-1000  # Would make rate negative
    )
    
    # Should error on negative rate
    assert any(e.severity == "ERROR" and "negative" in e.message.lower() for e in errors)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
