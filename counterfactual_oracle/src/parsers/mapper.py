"""
Maps extracted financial data to FinancialReport models.
"""

from typing import Dict, Any, List, Optional
from html.parser import HTMLParser
import re

from ..models import (
    FinancialReport, IncomeStatement, BalanceSheet, CashFlow,
    SegmentData, GeographicData, PDFMetadata
)
from ..infrastructure.logging import get_logger
from .normalizer import FinancialNormalizer

logger = get_logger(__name__)


class TableHTMLParser(HTMLParser):
    """Parser for extracting data from HTML tables."""
    
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = ''
        self.in_table = False
        self.in_row = False
        self.in_cell = False
    
    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current_table = []
        elif tag == 'tr' and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag == 'td' and self.in_row:
            self.in_cell = True
            self.current_cell = ''
    
    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
            if self.current_table:
                self.tables.append(self.current_table)
        elif tag == 'tr' and self.in_row:
            self.in_row = False
            if self.current_row:
                self.current_table.append(self.current_row)
        elif tag == 'td' and self.in_cell:
            self.in_cell = False
            self.current_row.append(self.current_cell.strip())
    
    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


class FinancialMapper:
    """Maps extracted document data to FinancialReport models."""
    
    # Section detection patterns
    SECTION_PATTERNS = {
        'income_statement': r"(?:CONDENSED\s+)?CONSOLIDATED\s+STATEMENTS\s+OF\s+(?:OPERATIONS|INCOME|EARNINGS)",
        'balance_sheet': r"(?:CONDENSED\s+)?CONSOLIDATED\s+BALANCE\s+SHEETS",
        'cash_flow': r"(?:CONDENSED\s+)?CONSOLIDATED\s+STATEMENTS\s+OF\s+CASH\s+FLOWS"
    }
    
    def parse_raw_response(self, raw_data: Dict[str, Any]) -> FinancialReport:
        """
        Parse raw Landing AI response into FinancialReport.
        
        Args:
            raw_data: Raw JSON from Landing AI
            
        Returns:
            FinancialReport model
        """
        markdown_content = raw_data.get('markdown', '')
        
        # Detect if quarterly
        is_quarterly = FinancialNormalizer.detect_quarterly_data(markdown_content)
        if is_quarterly:
            logger.info("annualizing_quarterly_data")
        
        # Extract section data
        section_data = self._extract_sections(markdown_content)
        
        # Build financial report
        income_stmt = self._build_income_statement(
            section_data.get('income_statement', {}),
            is_quarterly
        )
        balance_sheet = self._build_balance_sheet(
            section_data.get('balance_sheet', {})
        )
        cash_flow = self._build_cash_flow(
            section_data.get('cash_flow', {}),
            income_stmt.NetIncome
        )
        
        # Build metadata
        metadata = raw_data.get('metadata', {})
        pdf_metadata = PDFMetadata(
            page_count=metadata.get('page_count', 0),
            duration_ms=metadata.get('duration_ms', 0.0),
            credit_usage=metadata.get('credit_usage', 0.0),
            job_id=metadata.get('job_id', 'unknown'),
            filename=metadata.get('filename')
        )
        
        # Calculate KPIs
        kpis = self._calculate_kpis(income_stmt, cash_flow)
        
        return FinancialReport(
            income_statement=income_stmt,
            balance_sheet=balance_sheet,
            cash_flow=cash_flow,
            segment_data=[],  # TODO: Implement Tier 2 extraction
            geographic_data=[],
            debt_schedule=[],
            forward_looking=None,
            non_gaap_metrics=None,
            legal_regulatory=None,
            kpis=kpis,
            notes={},
            index=self._build_source_index(),
            source_metadata=[],
            pdf_metadata=pdf_metadata
        )
    
    def _extract_sections(self, markdown_content: str) -> Dict[str, Dict[str, str]]:
        """Extract data by financial statement section."""
        sections = {
            'income_statement': {},
            'balance_sheet': {},
            'cash_flow': {}
        }
        
        # Find section headers and their positions
        items = []
        for section, pattern in self.SECTION_PATTERNS.items():
            for match in re.finditer(pattern, markdown_content, re.IGNORECASE):
                items.append({
                    'type': 'header',
                    'section': section,
                    'start': match.start()
                })
        
        # Find tables
        html_table_pattern = r"<table[^>]*>.*?</table>"
        for match in re.finditer(html_table_pattern, markdown_content, re.DOTALL | re.IGNORECASE):
            items.append({
                'type': 'html_table',
                'content': match.group(0),
                'start': match.start()
            })
        
        md_table_pattern = r"(?:^\|.*$(?:\n|$))+"
        for match in re.finditer(md_table_pattern, markdown_content, re.MULTILINE):
            items.append({
                'type': 'md_table',
                'content': match.group(0),
                'start': match.start()
            })
        
        # Sort by position
        items.sort(key=lambda x: x['start'])
        
        # Assign tables to sections
        current_section = None
        for item in items:
            if item['type'] == 'header':
                current_section = item['section']
            elif item['type'] in ['html_table', 'md_table'] and current_section:
                table_data = self._parse_table(item['content'], item['type'])
                sections[current_section].update(table_data)
        
        # Fallback: if no sections found, use all data for all
        if all(not v for v in sections.values()):
            all_data = {}
            for item in items:
                if item['type'] in ['html_table', 'md_table']:
                    all_data.update(self._parse_table(item['content'], item['type']))
            for section in sections:
                sections[section] = all_data
        
        return sections
    
    def _parse_table(self, content: str, table_type: str) -> Dict[str, str]:
        """Parse table content into key-value pairs."""
        rows = []
        
        if table_type == 'html_table':
            parser = TableHTMLParser()
            parser.feed(content)
            if parser.tables:
                rows = parser.tables[0]
        elif table_type == 'md_table':
            lines = content.strip().split('\n')
            for line in lines:
                cells = [c.strip() for c in line.split('|')]
                if len(cells) > 2:
                    if cells[0] == '':
                        cells.pop(0)
                    if cells[-1] == '':
                        cells.pop(-1)
                    rows.append(cells)
        
        # Convert to map
        result = {}
        for row in rows:
            if len(row) >= 2:
                key = row[0].strip().lower()
                # Find first valid number in remaining cells
                for cell in row[1:]:
                    if FinancialNormalizer.clean_number(cell) is not None:
                        result[key] = cell
                        break
        
        return result
    
    def _build_income_statement(
        self,
        data: Dict[str, str],
        is_quarterly: bool
    ) -> IncomeStatement:
        """Build IncomeStatement from extracted data."""
        n = FinancialNormalizer
        
        revenue = n.annualize(
            n.find_field_value(data, 'revenue', 0.0) or 0.0,
            is_quarterly
        )
        cogs = n.annualize(
            n.find_field_value(data, 'cogs', 0.0) or 0.0,
            is_quarterly
        )
        gross_profit = n.annualize(
            n.find_field_value(data, 'gross_profit', 0.0) or 0.0,
            is_quarterly
        )
        if gross_profit == 0 and revenue != 0 and cogs != 0:
            gross_profit = revenue - cogs
        
        opex = n.annualize(
            n.find_field_value(data, 'opex', 0.0) or 0.0,
            is_quarterly
        )
        
        rnd = n.find_field_value(data, 'rnd')
        if rnd is not None:
            rnd = n.annualize(rnd, is_quarterly)
        
        sga = n.find_field_value(data, 'sga')
        if sga is not None:
            sga = n.annualize(sga, is_quarterly)
        
        if opex == 0 and (rnd or sga):
            opex = (rnd or 0) + (sga or 0)
        
        operating_income = n.annualize(
            n.find_field_value(data, 'operating_income', 0.0) or 0.0,
            is_quarterly
        )
        if operating_income == 0 and gross_profit != 0 and opex != 0:
            operating_income = gross_profit - opex
        
        da = n.annualize(
            n.find_field_value(data, 'depreciation', 0.0) or 0.0,
            is_quarterly
        )
        ebitda = operating_income + da
        
        interest = n.annualize(
            n.find_field_value(data, 'interest_expense', 0.0) or 0.0,
            is_quarterly
        )
        taxes = n.annualize(
            n.find_field_value(data, 'taxes', 0.0) or 0.0,
            is_quarterly
        )
        net_income = n.annualize(
            n.find_field_value(data, 'net_income', 0.0) or 0.0,
            is_quarterly
        )
        
        return IncomeStatement(
            Revenue=revenue,
            CostOfGoodsSold=cogs,
            GrossProfit=gross_profit,
            OpEx=opex,
            EBITDA=ebitda,
            DepreciationAndAmortization=da,
            EBIT=operating_income,
            InterestExpense=interest,
            Taxes=taxes,
            NetIncome=net_income,
            RnD=rnd,
            SGA=sga,
            segment_revenue=None
        )
    
    def _build_balance_sheet(self, data: Dict[str, str]) -> BalanceSheet:
        """Build BalanceSheet from extracted data."""
        n = FinancialNormalizer
        
        total_assets = n.find_field_value(data, 'total_assets', 0.0) or 0.0
        total_liabilities = n.find_field_value(data, 'total_liabilities', 0.0) or 0.0
        total_equity = n.find_field_value(data, 'total_equity', 0.0) or 0.0
        
        # Calculate equity if not found
        if total_equity == 0 and total_assets != 0 and total_liabilities != 0:
            total_equity = total_assets - total_liabilities
        
        return BalanceSheet(
            Assets={'TotalAssets': total_assets},
            Liabilities={'TotalLiabilities': total_liabilities},
            Equity={'TotalEquity': total_equity},
            Cash=n.find_field_value(data, 'cash'),
            ShortTermDebt=n.find_field_value(data, 'short_term_debt'),
            LongTermDebt=n.find_field_value(data, 'long_term_debt'),
            AccountsReceivable=n.find_field_value(data, 'accounts_receivable'),
            Inventory=n.find_field_value(data, 'inventory'),
            AccountsPayable=n.find_field_value(data, 'accounts_payable')
        )
    
    def _build_cash_flow(
        self,
        data: Dict[str, str],
        net_income: float
    ) -> CashFlow:
        """Build CashFlow from extracted data."""
        n = FinancialNormalizer
        
        cfo = n.find_field_value(data, 'cfo', 0.0) or 0.0
        capex = abs(n.find_field_value(data, 'capex', 0.0) or 0.0)
        fcf = cfo - capex if cfo != 0 else 0.0
        
        dividends = n.find_field_value(data, 'dividends')
        if dividends:
            dividends = abs(dividends)
        
        share_repurchases = n.find_field_value(data, 'share_repurchases')
        if share_repurchases:
            share_repurchases = abs(share_repurchases)
        
        return CashFlow(
            NetIncome=net_income,
            Depreciation=n.find_field_value(data, 'depreciation', 0.0) or 0.0,
            ChangeInWorkingCapital=0.0,  # TODO: Calculate from components
            CashFromOperations=cfo,
            CapEx=capex,
            CashFromInvesting=0.0,
            DebtRepayment=0.0,
            Dividends=dividends or 0.0,
            CashFromFinancing=0.0,
            NetChangeInCash=0.0,
            FreeCashFlow=fcf,
            ShareRepurchases=share_repurchases
        )
    
    def _calculate_kpis(
        self,
        income_stmt: IncomeStatement,
        cash_flow: CashFlow
    ) -> Dict[str, float]:
        """Calculate key performance indicators."""
        kpis = {}
        
        if income_stmt.Revenue > 0:
            kpis['Revenue Growth'] = 0.0  # Would need historical data
            kpis['EBITDA Margin'] = income_stmt.EBITDA / income_stmt.Revenue
            
            if cash_flow.FreeCashFlow:
                kpis['FCF Margin'] = cash_flow.FreeCashFlow / income_stmt.Revenue
        
        return kpis
    
    def _build_source_index(self) -> Dict[str, str]:
        """Build source index for extracted data."""
        return {
            "Revenue": "Landing AI ADE",
            "OpEx": "Landing AI ADE",
            "EBITDA": "Calculated",
            "Total Assets": "Landing AI ADE"
        }
