"""
Parser module tests.
"""

import pytest
from counterfactual_oracle.src.parsers.normalizer import FinancialNormalizer
from counterfactual_oracle.src.parsers.mapper import FinancialMapper
from counterfactual_oracle.src.parsers.validator import ExtractionValidator
from counterfactual_oracle.src.models import FinancialReport


class TestFinancialNormalizer:
    """Test data normalization."""
    
    def test_clean_number_basic(self):
        """Test basic number cleaning."""
        assert FinancialNormalizer.clean_number("1234") == 1234.0
        assert FinancialNormalizer.clean_number("1,234") == 1234.0
        assert FinancialNormalizer.clean_number("$1,234") == 1234.0
    
    def test_clean_number_negative(self):
        """Test negative number handling."""
        assert FinancialNormalizer.clean_number("(50,000)") == -50000.0
        assert FinancialNormalizer.clean_number("-1234") == -1234.0
    
    def test_clean_number_abbreviations(self):
        """Test K, M, B abbreviations."""
        assert FinancialNormalizer.clean_number("1.5K") == 1500.0
        assert FinancialNormalizer.clean_number("1.5M") == 1500000.0
        assert FinancialNormalizer.clean_number("1.5B") == 1500000000.0
    
    def test_clean_number_percentage(self):
        """Test percentage conversion."""
        assert FinancialNormalizer.clean_number("15%") == 0.15
        assert FinancialNormalizer.clean_number("15.5%") == 0.155
    
    def test_clean_number_invalid(self):
        """Test invalid input handling."""
        assert FinancialNormalizer.clean_number("") is None
        assert FinancialNormalizer.clean_number("-") is None
        assert FinancialNormalizer.clean_number(None) is None
    
    def test_detect_quarterly_data(self):
        """Test quarterly data detection."""
        quarterly = "Three Months Ended September 30, 2024"
        annual = "Year Ended December 31, 2024"
        
        assert FinancialNormalizer.detect_quarterly_data(quarterly) is True
        assert FinancialNormalizer.detect_quarterly_data(annual) is False
    
    def test_annualize(self):
        """Test annualization."""
        assert FinancialNormalizer.annualize(100, True) == 400
        assert FinancialNormalizer.annualize(100, False) == 100
        assert FinancialNormalizer.annualize(None, True) is None
    
    def test_find_field_value(self):
        """Test field lookup with synonyms."""
        data = {
            "total net sales": "119,575",
            "cost of sales": "64,720"
        }
        
        assert FinancialNormalizer.find_field_value(data, 'revenue') == 119575.0
        assert FinancialNormalizer.find_field_value(data, 'cogs') == 64720.0
        assert FinancialNormalizer.find_field_value(data, 'nonexistent') is None


class TestFinancialMapper:
    """Test financial data mapping."""
    
    @pytest.fixture
    def sample_raw_response(self):
        """Create a sample raw response."""
        return {
            "markdown": """
            <table>
            <tr><td>Total net sales</td><td>119,575</td></tr>
            <tr><td>Cost of sales</td><td>64,720</td></tr>
            <tr><td>Gross profit</td><td>54,855</td></tr>
            <tr><td>Total operating expenses</td><td>14,482</td></tr>
            <tr><td>Operating income</td><td>40,373</td></tr>
            <tr><td>Net income</td><td>30,000</td></tr>
            <tr><td>Total assets</td><td>300,000</td></tr>
            <tr><td>Total liabilities</td><td>100,000</td></tr>
            <tr><td>Total shareholders' equity</td><td>200,000</td></tr>
            </table>
            """,
            "metadata": {
                "page_count": 5,
                "duration_ms": 1500,
                "credit_usage": 1.5,
                "job_id": "test-job-123"
            }
        }
    
    def test_parse_raw_response(self, sample_raw_response):
        """Test parsing raw response to FinancialReport."""
        mapper = FinancialMapper()
        report = mapper.parse_raw_response(sample_raw_response)
        
        assert isinstance(report, FinancialReport)
        assert report.income_statement.Revenue == 119575.0
        assert report.income_statement.CostOfGoodsSold == 64720.0
        assert report.income_statement.GrossProfit == 54855.0
        assert report.balance_sheet.Assets['TotalAssets'] == 300000.0
    
    def test_ebitda_calculation(self, sample_raw_response):
        """Test that EBITDA is calculated correctly."""
        mapper = FinancialMapper()
        report = mapper.parse_raw_response(sample_raw_response)
        
        # EBITDA = EBIT + D&A
        expected_ebitda = 40373.0 + 0  # D&A not provided in sample
        assert report.income_statement.EBITDA == expected_ebitda


class TestExtractionValidator:
    """Test extraction validation."""
    
    @pytest.fixture
    def valid_report(self):
        """Create a valid financial report."""
        from counterfactual_oracle.src.models import IncomeStatement, BalanceSheet, CashFlow
        
        return FinancialReport(
            income_statement=IncomeStatement(
                Revenue=100000,
                CostOfGoodsSold=40000,
                GrossProfit=60000,
                OpEx=20000,
                EBITDA=45000,
                DepreciationAndAmortization=5000,
                EBIT=40000,
                InterestExpense=1000,
                Taxes=8000,
                NetIncome=31000
            ),
            balance_sheet=BalanceSheet(
                Assets={'TotalAssets': 200000},
                Liabilities={'TotalLiabilities': 80000},
                Equity={'TotalEquity': 120000}
            ),
            cash_flow=CashFlow(
                NetIncome=31000,
                Depreciation=5000,
                ChangeInWorkingCapital=-2000,
                CashFromOperations=34000,
                CapEx=10000,
                CashFromInvesting=-10000,
                DebtRepayment=0,
                Dividends=5000,
                CashFromFinancing=-5000,
                NetChangeInCash=19000,
                FreeCashFlow=24000
            )
        )
    
    def test_valid_report(self, valid_report):
        """Test validation of a valid report."""
        validator = ExtractionValidator()
        result = validator.validate(valid_report)
        
        assert result.is_valid is True
        assert len(result.get_errors()) == 0
    
    def test_balance_sheet_imbalance(self, valid_report):
        """Test detection of unbalanced balance sheet."""
        valid_report.balance_sheet.Assets['TotalAssets'] = 100000  # Wrong
        
        validator = ExtractionValidator()
        result = validator.validate(valid_report)
        
        assert result.is_valid is False
        errors = result.get_errors()
        assert any("balance" in e.message.lower() for e in errors)
    
    def test_negative_revenue(self, valid_report):
        """Test detection of negative revenue."""
        valid_report.income_statement.Revenue = -1000
        
        validator = ExtractionValidator()
        result = validator.validate(valid_report)
        
        assert result.is_valid is False
        errors = result.get_errors()
        assert any("revenue" in e.message.lower() for e in errors)
