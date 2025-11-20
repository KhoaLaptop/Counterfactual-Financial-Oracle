"""
Financial Validators and Sanity Checks

This module provides validation and guardrails for financial calculations.
Ensures inputs and outputs remain within physically possible bounds.
"""

from typing import Dict, List, Tuple
from .models import FinancialReport, IncomeStatement, BalanceSheet

class ValidationError:
    def __init__(self, severity: str, field: str, message: str, value: float = None):
        self.severity = severity  # "ERROR", "WARNING", "INFO"
        self.field = field
        self.message = message
        self.value = value
    
    def __repr__(self):
        return f"[{self.severity}] {self.field}: {self.message}"

class FinancialValidator:
    """
    Validates financial data for sanity and physical constraints.
    """
    
    def __init__(self):
        self.errors: List[ValidationError] = []
    
    def validate_income_statement(self, income: IncomeStatement) -> List[ValidationError]:
        """
        Validates income statement for logical consistency.
        
        Checks:
        - OpEx > Revenue (impossible)
        - Gross margin > 100% (impossible)
        - Negative revenue (suspicious)
        - EBITDA margin > 100% (impossible)
        """
        errors = []
        
        # Check: OpEx > Revenue
        if income.OpEx > income.Revenue and income.Revenue > 0:
            errors.append(ValidationError(
                "ERROR",
                "OpEx",
                f"Operating expenses (${income.OpEx:,.0f}) exceed revenue (${income.Revenue:,.0f})",
                income.OpEx / income.Revenue
            ))
        
        # Check: Gross margin > 100%
        if income.Revenue > 0:
            gross_margin = income.GrossProfit / income.Revenue
            if gross_margin > 1.0:
                errors.append(ValidationError(
                    "ERROR",
                    "GrossMargin",
                    f"Gross margin of {gross_margin:.1%} exceeds 100% (impossible)",
                    gross_margin
                ))
            elif gross_margin < 0:
                errors.append(ValidationError(
                    "WARNING",
                    "GrossMargin",
                    f"Negative gross margin of {gross_margin:.1%} indicates COGS > Revenue",
                    gross_margin
                ))
        
        # Check: Negative revenue
        if income.Revenue < 0:
            errors.append(ValidationError(
                "ERROR",
                "Revenue",
                f"Negative revenue (${income.Revenue:,.0f}) is invalid",
                income.Revenue
            ))
        
        # Check: EBITDA margin
        if income.Revenue > 0:
            ebitda_margin = income.EBITDA / income.Revenue
            if ebitda_margin > 1.0:
                errors.append(ValidationError(
                    "ERROR",
                    "EBITDA",
                    f"EBITDA margin of {ebitda_margin:.1%} exceeds 100% (impossible)",
                    ebitda_margin
                ))
            elif ebitda_margin < -0.5:
                errors.append(ValidationError(
                    "WARNING",
                    "EBITDA",
                    f"EBITDA margin of {ebitda_margin:.1%} is extremely negative",
                    ebitda_margin
                ))
        
        # Check: Revenue = 0 but other values exist
        if income.Revenue == 0 and (income.OpEx > 0 or income.COGS > 0):
            errors.append(ValidationError(
                "WARNING",
                "Revenue",
                "Revenue is zero but expenses are recorded",
                0
            ))
        
        return errors
    
    def validate_balance_sheet(self, bs: BalanceSheet) -> List[ValidationError]:
        """
        Validates balance sheet for accounting identity.
        
        Checks:
        - Assets = Liabilities + Equity (fundamental accounting equation)
        - Negative equity (possible but suspicious)
        """
        errors = []
        
        total_assets = bs.Assets.get("TotalAssets", 0)
        total_liabs = bs.Liabilities.get("TotalLiabilities", 0)
        total_equity = bs.Equity.get("TotalEquity", 0)
        
        # Check: Balance sheet equation
        diff = total_assets - (total_liabs + total_equity)
        tolerance = max(total_assets * 0.01, 1.0)  # 1% or $1
        
        if abs(diff) > tolerance:
            errors.append(ValidationError(
                "ERROR",
                "BalanceSheet",
                f"Balance sheet doesn't balance: Assets=${total_assets:,.0f}, Liab+Equity=${total_liabs + total_equity:,.0f}, Diff=${diff:,.0f}",
                diff
            ))
        
        # Check: Negative equity
        if total_equity < 0:
            errors.append(ValidationError(
                "WARNING",
                "Equity",
                f"Negative equity (${total_equity:,.0f}) indicates liabilities exceed assets",
                total_equity
            ))
        
        return errors
    
    def validate_scenario_params(self, opex_delta_bps: float, rev_growth_bps: float, 
                                 discount_rate_bps: float) -> List[ValidationError]:
        """
        Validates scenario parameters are within reasonable bounds.
        
        Checks:
        - Deltas are not extreme (> ±5000 bps = ±50%)
        - Discount rate doesn't go negative
        """
        errors = []
        
        # Check: Extreme deltas
        if abs(opex_delta_bps) > 5000:
            errors.append(ValidationError(
                "WARNING",
                "OpExDelta",
                f"OpEx delta of {opex_delta_bps} bps (±{abs(opex_delta_bps)/100:.0f}%) is very large",
                opex_delta_bps
            ))
        
        if abs(rev_growth_bps) > 5000:
            errors.append(ValidationError(
                "WARNING",
                "RevenueDelta",
                f"Revenue growth delta of {rev_growth_bps} bps (±{abs(rev_growth_bps)/100:.0f}%) is very large",
                rev_growth_bps
            ))
        
        # Check: Discount rate going negative
        base_discount = 0.08  # 8% default
        new_discount = base_discount + (discount_rate_bps / 10000.0)
        if new_discount < 0:
            errors.append(ValidationError(
                "ERROR",
                "DiscountRate",
                f"Discount rate would become negative ({new_discount:.2%})",
                new_discount
            ))
        
        return errors
    
    def clamp_value(self, value: float, min_val: float, max_val: float, field_name: str) -> Tuple[float, List[ValidationError]]:
        """
        Clamps a value to a valid range and returns warnings if clamped.
        """
        errors = []
        original = value
        clamped = max(min_val, min(max_val, value))
        
        if clamped != original:
            errors.append(ValidationError(
                "INFO",
                field_name,
                f"Value {original:.2f} clamped to range [{min_val:.2f}, {max_val:.2f}] → {clamped:.2f}",
                clamped
            ))
        
        return clamped, errors
