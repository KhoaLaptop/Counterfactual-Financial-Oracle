import pytest
from counterfactual_oracle.src.models import BalanceSheet
from counterfactual_oracle.src.logic import check_balance_sheet

def test_balance_sheet_balanced():
    bs = BalanceSheet(
        Assets={"TotalAssets": 100.0},
        Liabilities={"TotalLiabilities": 40.0},
        Equity={"TotalEquity": 60.0}
    )
    result = check_balance_sheet(bs)
    assert result["is_balanced"] is True
    assert result["difference"] == 0.0

def test_balance_sheet_imbalanced():
    bs = BalanceSheet(
        Assets={"TotalAssets": 100.0},
        Liabilities={"TotalLiabilities": 40.0},
        Equity={"TotalEquity": 50.0} # Missing 10
    )
    result = check_balance_sheet(bs)
    assert result["is_balanced"] is False
    assert result["difference"] == 10.0
