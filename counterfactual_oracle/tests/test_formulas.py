import pytest
from counterfactual_oracle.src.logic import calculate_fcf, calculate_npv

def test_calculate_fcf():
    # FCF = EBIT*(1-t) + D&A + ChangeInWC + CapEx
    # Example: EBIT=100, t=0.25 -> NOPAT=75
    # D&A=10, ChangeWC=-5 (outflow), CapEx=-20 (outflow)
    # FCF = 75 + 10 - 5 - 20 = 60
    
    ebit = 100.0
    tax_rate = 0.25
    dep_amort = 10.0
    change_wc = -5.0
    capex = -20.0
    
    expected_fcf = 60.0
    assert calculate_fcf(ebit, tax_rate, dep_amort, change_wc, capex) == expected_fcf

def test_calculate_npv():
    # FCF stream = [100, 100]
    # r = 0.10
    # NPV = 100/1.1 + 100/1.21 = 90.909 + 82.644 = 173.55
    
    fcf_stream = [100.0, 100.0]
    discount_rate = 0.10
    
    npv = calculate_npv(fcf_stream, discount_rate)
    assert pytest.approx(npv, 0.01) == 173.55
