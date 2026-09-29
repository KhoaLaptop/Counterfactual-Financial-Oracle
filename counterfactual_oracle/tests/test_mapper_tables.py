"""
Table selection in FinancialMapper, reproducing failures seen on real filings
(Apple and NVIDIA 10-Qs, Walmart earnings release; see the extractor benchmark).
"""

import pytest

from counterfactual_oracle.src.parsers.mapper import FinancialMapper

INCOME = """
## Condensed Consolidated Statements of Income (In millions)

|                          | Three Months Ended - Jul 26, 2026 | Three Months Ended - Jul 27, 2025 | Six Months Ended - Jul 26, 2026 |
|--------------------------|-------------|-------------|-------------|
| Revenue                  | $ 96,221    | $ 46,743    | $ 177,837   |
| Cost of revenue          | 24,079      | 12,890      | 44,538      |
| Gross profit             | 72,142      | 33,853      | 133,299     |
| Total operating expenses | 8,408       | 5,413       | 16,029      |
| Operating income         | 63,734      | 28,440      | 117,270     |
| Income tax expense       | 11,000      | 4,000       | 20,000      |
| Net income               | $ 59,688    | $ 26,422    | $ 110,000   |
"""

BALANCE = """
## Condensed Consolidated Balance Sheets (In millions)

|                             | Jul 26, 2026 | Jan 25, 2026 |
|-----------------------------|-------------|-------------|
| Cash and cash equivalents   | $ 22,443    | $ 8,589     |
| Total assets                | $ 320,272   | $ 200,000   |
| Total liabilities           | 91,288      | 60,000      |
| Total shareholders' equity  | 228,984     | 140,000     |
"""

CASH_FLOW = """
## Condensed Consolidated Statements of Cash Flows (In millions)

|                                            | Six Months Ended - Jul 26, 2026 | Six Months Ended - Jul 27, 2025 |
|--------------------------------------------|-------------|-------------|
| Net income                                 | $ 110,000   | $ 50,000    |
| Net cash provided by operating activities  | 74,421      | 40,000      |
| Purchases related to property and equipment and intangible assets | (4,434) | (2,000) |
"""

# MD&A: prose mentioning the income statement, then a percentage-of-revenue table.
MDNA_PERCENT_TABLE = """
The following table sets forth certain items in our Condensed Consolidated Statements of Income
expressed as a percentage of revenue.

|                  | Three Months Ended - Jul 26, 2026 | Three Months Ended - Jul 27, 2025 |
|------------------|------|------|
| Revenue          | 100.0 % | 100.0 % |
| Cost of revenue  | 25.0 %  | 27.6 %  |
| Gross profit     | 75.0 %  | 72.4 %  |
| Operating income | 66.2 %  | 60.8 %  |
| Net income       | 62.0 %  | 56.5 %  |
"""

# Notes: a segment table after an in-text mention of the income statement.
SEGMENT_NOTE = """
Stock-based compensation is included in the Condensed Consolidated Statements of Income as follows.

|                   | Three Months Ended - Jul 26, 2026 |
|-------------------|------|
| Revenue           | 5,000 |
| Operating income  | 1,200 |
"""


def _report(markdown):
    return FinancialMapper().parse_raw_response({"markdown": markdown})


def _quarter(value):
    # "Three Months Ended" -> the mapper annualizes income statement flows x4
    return pytest.approx(value * 4)


def test_later_mentions_and_percentage_tables_do_not_override_the_statement():
    report = _report(INCOME + BALANCE + CASH_FLOW + MDNA_PERCENT_TABLE + SEGMENT_NOTE)

    inc = report.income_statement
    assert inc.Revenue == _quarter(96_221)
    assert inc.CostOfGoodsSold == _quarter(24_079)
    assert inc.GrossProfit == _quarter(72_142)
    assert inc.EBIT == _quarter(63_734)
    assert inc.NetIncome == _quarter(59_688)


def test_statement_tables_are_found_without_headings():
    # Earnings releases often render statement titles as images, leaving bare tables.
    strip = lambda md: "\n".join(line for line in md.splitlines() if not line.startswith("##"))  # noqa: E731
    report = _report(strip(INCOME) + strip(BALANCE) + strip(CASH_FLOW))

    assert report.income_statement.Revenue == _quarter(96_221)
    assert report.balance_sheet.Assets["TotalAssets"] == 320_272
    assert report.cash_flow.CashFromOperations == 74_421


def test_balance_sheet_and_cash_flow_come_from_their_own_tables():
    report = _report(INCOME + BALANCE + CASH_FLOW + MDNA_PERCENT_TABLE)

    bs, cf = report.balance_sheet, report.cash_flow
    assert bs.Cash == 22_443
    assert bs.Liabilities["TotalLiabilities"] == 91_288
    assert bs.Equity["TotalEquity"] == 228_984
    assert cf.CapEx == 4_434


def test_statement_split_across_a_page_break_is_merged():
    assets, liabilities = BALANCE.split("| Total liabilities")
    header = "|                             | Jul 26, 2026 | Jan 25, 2026 |\n|---|---|---|\n"
    split_balance = assets + "\n\n<!-- page break -->\n\n" + header + "| Total liabilities" + liabilities

    report = _report(INCOME + split_balance + CASH_FLOW)

    assert report.balance_sheet.Assets["TotalAssets"] == 320_272
    assert report.balance_sheet.Liabilities["TotalLiabilities"] == 91_288
    assert report.balance_sheet.Equity["TotalEquity"] == 228_984


def test_percentage_cells_are_never_used_as_values():
    report = _report(MDNA_PERCENT_TABLE)

    assert report.income_statement.Revenue == 0.0
    assert report.income_statement.GrossProfit == 0.0


def test_prefers_amounts_attributable_to_the_company_over_consolidated_totals():
    # Walmart-style statements: consolidated totals include noncontrolling interests.
    markdown = """
|                                                        | Three Months Ended - 2026 | Three Months Ended - 2025 |
|--------------------------------------------------------|---------|---------|
| Net sales                                              | $ 186,100 | $ 175,750 |
| Cost of sales                                          | 138,804 | 132,771 |
| Operating income                                       | 9,383   | 7,286   |
| Consolidated net income                                | 6,529   | 7,200   |
| Consolidated net income attributable to noncontrolling interest | (163) | (150) |
| Consolidated net income attributable to Walmart        | $ 6,366 | $ 7,050 |

|                                          | July 31, 2026 | July 31, 2025 |
|------------------------------------------|---------|---------|
| Cash and cash equivalents                | $ 11,529 | $ 9,000 |
| Total assets                             | 293,914 | 280,000 |
| Total liabilities                        | 189,408 | 180,000 |
| Total Walmart shareholders’ equity       | 98,238  | 94,000  |
| Nonredeemable noncontrolling interest    | 6,268   | 6,000   |
| Total equity                             | 104,506 | 100,000 |
"""
    report = _report(markdown)

    assert report.income_statement.NetIncome == _quarter(6_366)
    assert report.balance_sheet.Equity["TotalEquity"] == 98_238


def test_total_liabilities_and_equity_row_is_not_equity():
    markdown = """
|                                             | Jun 27, 2026 | Sep 27, 2025 |
|---------------------------------------------|---------|---------|
| Total liabilities and shareholders' equity  | 383,266 | 360,000 |
| Cash and cash equivalents                   | 39,544  | 30,000  |
| Total assets                                | 383,266 | 360,000 |
| Total liabilities                           | 275,746 | 270,000 |
| Total shareholders' equity                  | 107,520 | 90,000  |
"""
    assert _report(markdown).balance_sheet.Equity["TotalEquity"] == 107_520


# --- label variants seen on held-out filings (Pfizer, Caterpillar, JPMorgan, Exxon, Deckers) ---

def test_revenue_prefers_total_row_and_handles_plurals_and_compound_labels():
    pfizer_style = """
|                    | Three Months Ended - September 28, 2025 | Three Months Ended - September 29, 2024 |
|--------------------|--------|--------|
| Product revenues   | $ 13,920 | $ 15,417 |
| Alliance revenues  | 2,298  | 1,900  |
| Total revenues     | 16,654 | 17,702 |
| Cost of sales      | 4,000  | 3,900  |
| Net income         | 3,500  | 4,470  |
"""
    caterpillar_style = pfizer_style.replace("Product revenues", "Sales of Machinery").replace(
        "Total revenues", "Total sales and revenues")

    assert _report(pfizer_style).income_statement.Revenue == _quarter(16_654)
    assert _report(caterpillar_style).income_statement.Revenue == _quarter(16_654)


def test_net_income_labelled_profit_with_footnote_marker():
    markdown = """
|                                       | Three Months Ended - March 31, 2025 | Three Months Ended - March 31, 2024 |
|---------------------------------------|--------|--------|
| Total sales and revenues              | 14,249 | 15,799 |
| Cost of goods sold                    | 8,965  | 9,662  |
| Gross profit                          | 5,284  | 6,137  |
| Operating profit                      | 2,586  | 3,470  |
| Profit of consolidated companies      | 1,996  | 2,844  |
| Profit attributable to noncontrolling interests | (7) | (2) |
| Profit 1                              | $ 2,003 | 2,856 |
| Profit per common share               | $ 4.22 | 5.78   |
"""
    report = _report(markdown)

    assert report.income_statement.NetIncome == _quarter(2_003)
    assert report.income_statement.GrossProfit == _quarter(5_284)


def test_cash_flow_labels_with_used_in_parentheticals():
    pfizer = "| Net cash provided by/(used in) operating activities | 6,356 | 6,023 |"
    jpmorgan = "| Net cash (used in)/provided by operating activities | (237,044) | 12,000 |"
    caterpillar = "| Net cash provided by (used for) operating activities | 1,289 | 2,052 |"
    jpmorgan_2026 = "| Net cash (used in) operating activities | (237,044) | (222,292) |"
    cases = [(pfizer, 6_356), (jpmorgan, -237_044), (caterpillar, 1_289), (jpmorgan_2026, -237_044)]
    for row, expected in cases:
        markdown = f"""
|                                                | Nine Months Ended - 2025 | Nine Months Ended - 2024 |
|------------------------------------------------|--------|--------|
| Net income                                     | 9,000  | 8,000  |
| Depreciation and amortization                  | 1,000  | 900    |
{row}
| Purchases of property, plant and equipment     | (1,784) | (1,700) |
"""
        cash_flow = _report(markdown).cash_flow
        assert cash_flow.CashFromOperations == expected
        assert cash_flow.CapEx == 1_784


def test_company_share_of_equity_is_preferred_over_total_equity():
    exxon_style = """
|                                    | Dec 31, 2025 | Dec 31, 2024 |
|------------------------------------|---------|---------|
| Cash and cash equivalents          | 10,000  | 23,000  |
| Total assets                       | 448,980 | 453,000 |
| Total liabilities                  | 182,354 | 180,000 |
| ExxonMobil share of equity         | 259,386 | 263,705 |
| Noncontrolling interests           | 7,240   | 7,000   |
| Total equity                       | 266,626 | 270,705 |
| Total liabilities and equity       | 448,980 | 453,000 |
"""
    assert _report(exxon_style).balance_sheet.Equity["TotalEquity"] == 259_386


def test_balance_sheet_continuation_after_a_short_caption_is_merged():
    deckers_style = """
|                                   | June 30, 2026 | March 31, 2026 |
|-----------------------------------|-------------|-------------|
| Cash and cash equivalents         | $ 1,500,000 | $ 1,800,000 |
| Total assets                      | $ 3,868,621 | $ 3,687,765 |
| Trade accounts payable            | $ 700,000   | $ 500,000   |
| Total current liabilities         | 1,060,000   | 900,000     |

Stockholders' equity

Common stock ($0.01 par value per share; 750,000 shares authorized;

| 136,725 shares issued and outstanding) | June 30, 2026 1,367 | March 31, 2026 1,400 |
|----------------------------------------|-----------|-----------|
| Additional paid-in capital             | 298,049   | 287,700   |
| Retained earnings                      | 2,034,898 | 2,246,000 |
| Total stockholders' equity             | 2,301,682 | 2,499,638 |
| Total liabilities and stockholders' equity | $ 3,868,621 | $ 3,687,765 |
"""
    assert _report(deckers_style).balance_sheet.Equity["TotalEquity"] == 2_301_682
