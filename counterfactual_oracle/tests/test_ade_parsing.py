"""
ADE Parsing Unit Tests

Tests the Landing AI parser with fixed JSON samples to ensure correct extraction.
"""

import pytest
from counterfactual_oracle.src.agents.landing_ai import LandingAIClient
from counterfactual_oracle.src.models import FinancialReport

# Sample ADE response (simplified)
SAMPLE_ADE_RESPONSE = {
    "markdown": """
<table>
<tr><td>Total net sales</td><td>119,575</td></tr>
<tr><td>Total cost of sales</td><td>64,720</td></tr>
<tr><td>Gross margin</td><td>54,855</td></tr>
<tr><td>Total operating expenses</td><td>14,482</td></tr>
<tr><td>Operating income</td><td>40,373</td></tr>
</table>
""",
    "chunks": [],
    "metadata": {}
}

def test_parse_revenue():
    """Test that revenue is correctly extracted"""
    client = LandingAIClient(api_key="test")
    report = client._parse_landing_ai_response(SAMPLE_ADE_RESPONSE)
    
    assert report.income_statement.Revenue == 119575.0, "Revenue should be 119,575"

def test_parse_cogs():
    """Test that COGS is correctly extracted"""
    client = LandingAIClient(api_key="test")
    report = client._parse_landing_ai_response(SAMPLE_ADE_RESPONSE)
    
    assert report.income_statement.CostOfGoodsSold == 64720.0, "COGS should be 64,720"

def test_parse_opex():
    """Test that OpEx is correctly extracted"""
    client = LandingAIClient(api_key="test")
    report = client._parse_landing_ai_response(SAMPLE_ADE_RESPONSE)
    
    assert report.income_statement.OpEx == 14482.0, "OpEx should be 14,482"

def test_parse_ebit():
    """Test that EBIT is correctly extracted"""
    client = LandingAIClient(api_key="test")
    report = client._parse_landing_ai_response(SAMPLE_ADE_RESPONSE)
    
    assert report.income_statement.EBIT == 40373.0, "EBIT should be 40,373"

def test_missing_fields_handled():
    """Test that missing fields don't crash the parser"""
    minimal_response = {
        "markdown": "<table><tr><td>Total net sales</td><td>100,000</td></tr></table>",
        "chunks": []
    }
    
    client = LandingAIClient(api_key="test")
    report = client._parse_landing_ai_response(minimal_response)
    
    # Should not crash, should have revenue
    assert report.income_statement.Revenue == 100000.0
    # Other fields should default to 0
    assert report.income_statement.OpEx >= 0

def test_malformed_numbers():
    """Test handling of malformed number strings"""
    malformed_response = {
        "markdown": """
<table>
<tr><td>Total net sales</td><td>$1,234,567.89</td></tr>
<tr><td>Operating income</td><td>(50,000)</td></tr>
</table>
""",
        "chunks": []
    }
    
    client = LandingAIClient(api_key="test")
    report = client._parse_landing_ai_response(malformed_response)
    
    # Should handle $ and commas
    assert report.income_statement.Revenue == 1234567.89
    # Should handle parentheses as negative
    assert report.income_statement.EBIT == -50000.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
