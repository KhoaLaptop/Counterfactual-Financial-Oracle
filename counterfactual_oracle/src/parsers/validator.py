"""
Validation for extracted financial data.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from ..models import FinancialReport
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    field: str
    message: str
    severity: ValidationSeverity
    suggestion: str = ""


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    issues: List[ValidationIssue]
    
    def get_errors(self) -> List[ValidationIssue]:
        """Get only error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]
    
    def get_warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


class ExtractionValidator:
    """Validates extracted financial reports for plausibility."""
    
    # Industry benchmarks for validation
    BENCHMARKS = {
        'ebitda_margin_min': -0.5,  # -50%
        'ebitda_margin_max': 0.7,   # 70%
        'net_margin_min': -0.5,
        'net_margin_max': 0.5,
        'debt_to_ebitda_max': 10.0,
    }
    
    def validate(self, report: FinancialReport) -> ValidationResult:
        """
        Validate a financial report.
        
        Args:
            report: FinancialReport to validate
            
        Returns:
            ValidationResult with issues found
        """
        issues = []
        
        # Run all validation checks
        issues.extend(self._validate_balance_sheet(report))
        issues.extend(self._validate_income_statement(report))
        issues.extend(self._validate_cash_flow(report))
        issues.extend(self._validate_ratios(report))
        issues.extend(self._validate_consistency(report))
        
        # Report is valid if no errors
        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        
        logger.info(
            "validation_completed",
            is_valid=is_valid,
            issue_count=len(issues),
            error_count=len([i for i in issues if i.severity == ValidationSeverity.ERROR])
        )
        
        return ValidationResult(is_valid=is_valid, issues=issues)
    
    def _validate_balance_sheet(self, report: FinancialReport) -> List[ValidationIssue]:
        """Validate balance sheet."""
        issues = []
        bs = report.balance_sheet
        
        # Check accounting equation: Assets = Liabilities + Equity
        assets = bs.Assets.get('TotalAssets', 0)
        liabilities = bs.Liabilities.get('TotalLiabilities', 0)
        equity = bs.Equity.get('TotalEquity', 0)
        
        total_liab_equity = liabilities + equity
        diff = abs(assets - total_liab_equity)
        tolerance = max(assets * 0.01, 1.0)  # 1% or $1 tolerance
        
        if diff > tolerance:
            issues.append(ValidationIssue(
                field="balance_sheet",
                message=f"Balance sheet doesn't balance: Assets (${assets:,.0f}) != "
                       f"Liabilities + Equity (${total_liab_equity:,.0f})",
                severity=ValidationSeverity.ERROR,
                suggestion="Check extraction for missing or incorrect values"
            ))
        
        # Check for negative assets
        if assets < 0:
            issues.append(ValidationIssue(
                field="total_assets",
                message="Total assets is negative",
                severity=ValidationSeverity.ERROR,
                suggestion="Review asset extraction"
            ))
        
        # Check for negative equity (possible but unusual)
        if equity < 0:
            issues.append(ValidationIssue(
                field="total_equity",
                message="Negative equity detected (insolvency risk)",
                severity=ValidationSeverity.WARNING,
                suggestion="Verify equity extraction or confirm company is in distress"
            ))
        
        return issues
    
    def _validate_income_statement(self, report: FinancialReport) -> List[ValidationIssue]:
        """Validate income statement."""
        issues = []
        inc = report.income_statement
        
        # Check for negative revenue
        if inc.Revenue <= 0:
            issues.append(ValidationIssue(
                field="revenue",
                message="Revenue is zero or negative",
                severity=ValidationSeverity.ERROR,
                suggestion="Check revenue extraction"
            ))
        
        # Check COGS <= Revenue
        if inc.CostOfGoodsSold > inc.Revenue:
            issues.append(ValidationIssue(
                field="cogs",
                message="COGS exceeds Revenue (negative gross margin)",
                severity=ValidationSeverity.WARNING,
                suggestion="Verify COGS extraction or confirm company has negative gross margin"
            ))
        
        # Check Gross Profit calculation
        expected_gp = inc.Revenue - inc.CostOfGoodsSold
        gp_diff = abs(inc.GrossProfit - expected_gp)
        if gp_diff > max(inc.Revenue * 0.001, 1.0):
            issues.append(ValidationIssue(
                field="gross_profit",
                message=f"Gross profit ({inc.GrossProfit:,.0f}) doesn't match "
                       f"Revenue - COGS ({expected_gp:,.0f})",
                severity=ValidationSeverity.WARNING,
                suggestion="Verify gross profit extraction"
            ))
        
        # Check EBITDA calculation
        expected_ebitda = inc.EBIT + inc.DepreciationAndAmortization
        ebitda_diff = abs(inc.EBITDA - expected_ebitda)
        if ebitda_diff > max(inc.Revenue * 0.001, 1.0):
            issues.append(ValidationIssue(
                field="ebitda",
                message=f"EBITDA ({inc.EBITDA:,.0f}) doesn't match "
                       f"EBIT + D&A ({expected_ebitda:,.0f})",
                severity=ValidationSeverity.WARNING,
                suggestion="Verify EBITDA calculation"
            ))
        
        return issues
    
    def _validate_cash_flow(self, report: FinancialReport) -> List[ValidationIssue]:
        """Validate cash flow statement."""
        issues = []
        cf = report.cash_flow
        
        # Check FCF calculation
        expected_fcf = cf.CashFromOperations - cf.CapEx
        fcf_diff = abs(cf.FreeCashFlow - expected_fcf)
        if fcf_diff > max(abs(cf.CashFromOperations) * 0.001, 1.0):
            issues.append(ValidationIssue(
                field="free_cash_flow",
                message=f"FCF ({cf.FreeCashFlow:,.0f}) doesn't match "
                       f"CFO - CapEx ({expected_fcf:,.0f})",
                severity=ValidationSeverity.WARNING,
                suggestion="Verify FCF calculation"
            ))
        
        return issues
    
    def _validate_ratios(self, report: FinancialReport) -> List[ValidationIssue]:
        """Validate financial ratios are within reasonable bounds."""
        issues = []
        inc = report.income_statement
        bs = report.balance_sheet
        
        # EBITDA margin
        if inc.Revenue > 0:
            ebitda_margin = inc.EBITDA / inc.Revenue
            
            if ebitda_margin < self.BENCHMARKS['ebitda_margin_min']:
                issues.append(ValidationIssue(
                    field="ebitda_margin",
                    message=f"EBITDA margin ({ebitda_margin:.1%}) is extremely low",
                    severity=ValidationSeverity.WARNING,
                    suggestion="Verify EBITDA extraction"
                ))
            
            if ebitda_margin > self.BENCHMARKS['ebitda_margin_max']:
                issues.append(ValidationIssue(
                    field="ebitda_margin",
                    message=f"EBITDA margin ({ebitda_margin:.1%}) is extremely high",
                    severity=ValidationSeverity.WARNING,
                    suggestion="Verify EBITDA extraction for software/IP companies this may be normal"
                ))
            
            # Net margin
            net_margin = inc.NetIncome / inc.Revenue
            
            if net_margin < self.BENCHMARKS['net_margin_min']:
                issues.append(ValidationIssue(
                    field="net_margin",
                    message=f"Net margin ({net_margin:.1%}) is extremely low",
                    severity=ValidationSeverity.WARNING
                ))
            
            if net_margin > self.BENCHMARKS['net_margin_max']:
                issues.append(ValidationIssue(
                    field="net_margin",
                    message=f"Net margin ({net_margin:.1%}) is extremely high",
                    severity=ValidationSeverity.WARNING
                ))
        
        # Debt to EBITDA
        total_debt = (bs.ShortTermDebt or 0) + (bs.LongTermDebt or 0)
        if inc.EBITDA > 0:
            debt_to_ebitda = total_debt / inc.EBITDA
            if debt_to_ebitda > self.BENCHMARKS['debt_to_ebitda_max']:
                issues.append(ValidationIssue(
                    field="debt_to_ebitda",
                    message=f"Debt/EBITDA ({debt_to_ebitda:.1f}x) is very high",
                    severity=ValidationSeverity.WARNING,
                    suggestion="High leverage detected - verify debt extraction"
                ))
        
        return issues
    
    def _validate_consistency(self, report: FinancialReport) -> List[ValidationIssue]:
        """Validate cross-statement consistency."""
        issues = []
        
        # Net income should match between income statement and cash flow
        inc_net_income = report.income_statement.NetIncome
        cf_net_income = report.cash_flow.NetIncome
        
        diff = abs(inc_net_income - cf_net_income)
        tolerance = max(inc_net_income * 0.001, 1.0) if inc_net_income != 0 else 1.0
        
        if diff > tolerance:
            issues.append(ValidationIssue(
                field="net_income_consistency",
                message=f"Net income mismatch: Income Statement (${inc_net_income:,.0f}) vs "
                       f"Cash Flow (${cf_net_income:,.0f})",
                severity=ValidationSeverity.WARNING,
                suggestion="May be due to annualization - check if periods align"
            ))
        
        return issues
