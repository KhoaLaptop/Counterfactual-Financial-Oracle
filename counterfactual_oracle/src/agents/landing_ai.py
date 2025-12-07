import json
import os
import requests
from typing import Dict, Any, Optional, List
from ..models import (
    FinancialReport, IncomeStatement, BalanceSheet, CashFlow,
    SegmentData, GeographicData, DebtSchedule, 
    ForwardLookingData, NonGAAPMetrics, LegalAndRegulatory,
    PDFMetadata
)

class LandingAIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.va.landing.ai/v1/ade"

    def extract_data(self, pdf_path: str) -> FinancialReport:
        """
        Extracts data from a PDF using Landing AI ADE API.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        # Upload the PDF and request extraction
        # Increase timeout to 15 minutes for large financial PDFs
        with open(pdf_path, 'rb') as f:
            files = {'document': f}
            response = requests.post(
                f"{self.base_url}/parse",
                headers=headers,
                files=files,
                timeout=900  # 15 minutes timeout for large PDFs
            )
        
        # Only accept 200 OK. 206 (Partial Content) means corrupted data
        if response.status_code != 200:
            error_msg = f"Landing AI API error: {response.status_code}"
            if response.status_code == 206:
                error_msg += " - PDF processing incomplete/corrupted. Try a simpler PDF or fewer pages."
            else:
                error_msg += f" - {response.text[:500]}"  # Limit error text
            raise Exception(error_msg)
        
        raw_data = response.json()
        
        # Debug: Save the raw response to a file for inspection
        debug_file = "/tmp/landing_ai_debug_response.json"
        with open(debug_file, 'w') as f:
            json.dump(raw_data, f, indent=2)
        print(f"Landing AI response saved to: {debug_file}")
        
        # Transform Landing AI response into our FinancialReport structure
        return self.parse_landing_ai_response(raw_data)
    
    def parse_landing_ai_response(self, raw_data: Dict[str, Any]) -> FinancialReport:
        """
        Parses the Landing AI ADE response and transforms it into our FinancialReport model.
        Landing AI returns data in markdown format with HTML tables.
        
        This parser extracts Tier 1-3 data using robust synonym matching and section-aware parsing.
        It handles mixed HTML/Markdown tables and plain text headers.
        """
        import re
        from html.parser import HTMLParser
        
        # Extract the markdown content
        markdown_content = raw_data.get('markdown', '')
        
        # Helper to clean and convert to number
        def clean_number(text: str) -> Optional[float]:
            """Convert text to float, return None if not possible"""
            try:
                text = text.strip()
                if not text or text == '-':
                    return None
                is_negative = '(' in text or ')' in text
                cleaned = re.sub(r'[^0-9.]', '', text)
                if not cleaned:
                    return None
                val = float(cleaned)
                return -val if is_negative else val
            except:
                return None

        # --- 1. Identify Sections and Tables by Position ---
        
        # Regex for headers
        header_patterns = {
            'is': r"(?:CONDENSED\s+)?CONSOLIDATED\s+STATEMENTS\s+OF\s+(?:OPERATIONS|INCOME|EARNINGS)",
            'bs': r"(?:CONDENSED\s+)?CONSOLIDATED\s+BALANCE\s+SHEETS",
            'cf': r"(?:CONDENSED\s+)?CONSOLIDATED\s+STATEMENTS\s+OF\s+CASH\s+FLOWS"
        }
        
        # Find all headers and their positions
        items = []
        for section, pattern in header_patterns.items():
            for match in re.finditer(pattern, markdown_content, re.IGNORECASE):
                items.append({'type': 'header', 'section': section, 'start': match.start()})
        
        # Find all HTML tables
        html_table_pattern = r"<table[^>]*>.*?</table>"
        for match in re.finditer(html_table_pattern, markdown_content, re.DOTALL | re.IGNORECASE):
            items.append({'type': 'html_table', 'content': match.group(0), 'start': match.start()})
            
        # Find all Markdown tables (blocks of lines starting with |)
        # We look for at least 2 consecutive lines starting with |
        md_table_pattern = r"(?:^\|.*$(?:\n|$))+"
        for match in re.finditer(md_table_pattern, markdown_content, re.MULTILINE):
            items.append({'type': 'md_table', 'content': match.group(0), 'start': match.start()})
            
        # Sort items by position
        items.sort(key=lambda x: x['start'])
        
        # --- 2. Process Items and Assign to Sections ---
        
        section_maps = {'is': {}, 'bs': {}, 'cf': {}}
        current_section = None
        
        # HTML Parser Class
        class TableParser(HTMLParser):
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
                    if self.current_table: self.tables.append(self.current_table)
                elif tag == 'tr' and self.in_row:
                    self.in_row = False
                    if self.current_row: self.current_table.append(self.current_row)
                elif tag == 'td' and self.in_cell:
                    self.in_cell = False
                    self.current_row.append(self.current_cell.strip())
            def handle_data(self, data):
                if self.in_cell: self.current_cell += data

        def parse_table_content(content, table_type):
            extracted_map = {}
            rows = []
            
            if table_type == 'html_table':
                parser = TableParser()
                parser.feed(content)
                if parser.tables:
                    rows = parser.tables[0]
            elif table_type == 'md_table':
                lines = content.strip().split('\n')
                for line in lines:
                    cells = [c.strip() for c in line.split('|')]
                    if len(cells) > 2:
                        if cells[0] == '': cells.pop(0)
                        if cells[-1] == '': cells.pop(-1)
                        rows.append(cells)
            
            # Convert rows to map
            for row in rows:
                if len(row) >= 2:
                    key = row[0].strip().lower()
                    # Find first valid number
                    val = None
                    for cell in row[1:]:
                        if clean_number(cell) is not None:
                            val = cell
                            break
                    if val:
                        extracted_map[key] = val
            return extracted_map

        # Iterate and assign
        for item in items:
            if item['type'] == 'header':
                current_section = item['section']
            elif item['type'] in ['html_table', 'md_table']:
                # If we haven't found a header yet, or if we are in a known section
                # Note: If current_section is None, we might want to try to guess or just skip
                # For now, if None, we add to all (fallback) or just skip. 
                # Let's add to all if no section found yet (unlikely with regex), or maybe 'is' as default?
                target_sections = [current_section] if current_section else ['is', 'bs', 'cf']
                
                table_map = parse_table_content(item['content'], item['type'])
                
                for sec in target_sections:
                    section_maps[sec].update(table_map)

        is_map = section_maps['is']
        bs_map = section_maps['bs']
        cf_map = section_maps['cf']
        
        # Fallback: If maps are empty, try to use all data for all sections
        if not is_map and not bs_map and not cf_map:
            # This happens if regex headers failed completely
            # We just merge all tables into all maps
            all_data = {}
            for item in items:
                if item['type'] in ['html_table', 'md_table']:
                    all_data.update(parse_table_content(item['content'], item['type']))
            is_map = all_data
            bs_map = all_data
            cf_map = all_data

        # Helper to find value using synonyms from a specific map
        def get_value(field_map: Dict[str, str], synonyms: List[str], default: Optional[float] = None) -> float:
            for synonym in synonyms:
                term = synonym.lower()
                if term in field_map:
                    val = clean_number(field_map[term])
                    if val is not None:
                        return val
                for key, val_str in field_map.items():
                    if term == key or (len(key) < 100 and term in key):
                        val = clean_number(val_str)
                        if val is not None:
                            return val
            return default if default is not None else 0.0

        def get_optional_value(field_map: Dict[str, str], synonyms: List[str]) -> Optional[float]:
            val = get_value(field_map, synonyms, default=None)
            return val if val != 0.0 else None

        # === TIER 1: Core Financial Statements ===
        
        # --- ANNUALIZATION LOGIC ---
        # Detect if Income Statement data is quarterly based on column header
        # If "Three Months Ended" is found, multiply IS values by 4 to annualize
        is_quarterly = bool(re.search(r'three\s+months\s+ended', markdown_content, re.IGNORECASE))
        annualization_multiplier = 4.0 if is_quarterly else 1.0
        
        if is_quarterly:
            print(f"[ANNUALIZATION] Detected 'Three Months Ended' - applying 4x multiplier to Income Statement")
        
        # Helper to annualize income statement values
        def annualize(value: float) -> float:
            return value * annualization_multiplier if value else 0.0
        
        # Income Statement (Use is_map) - Apply annualization for quarterly data
        revenue_raw = get_value(is_map, ['Net sales', 'Total net sales', 'Revenue', 'Total revenue', 'Sales'])
        revenue = annualize(revenue_raw)
        
        cogs_raw = get_value(is_map, ['Cost of sales', 'Total cost of sales', 'Cost of goods sold', 'Cost of revenue'])
        cogs = annualize(cogs_raw)
        
        # FIX 1: Separate Gross Profit (dollar amount) from Gross Margin (percentage)
        gross_profit_raw = get_value(is_map, ['Gross profit'], default=0.0)
        gross_profit = annualize(gross_profit_raw)
        # If not found, calculate it
        if gross_profit == 0 and revenue != 0 and cogs != 0:
            gross_profit = revenue - cogs
            
        opex_raw = get_value(is_map, ['Total operating expenses', 'Operating expenses', 'Total operating costs'])
        opex = annualize(opex_raw)
        
        operating_income_raw = get_value(is_map, ['Operating income', 'Income from operations', 'Operating profit'])
        operating_income = annualize(operating_income_raw)
        if operating_income == 0 and gross_profit != 0 and opex != 0:
            operating_income = gross_profit - opex
            
        net_income_raw = get_value(is_map, ['Net income', 'Net earnings', 'Net profit', 'Net loss', 'Net income (loss)'])
        net_income = annualize(net_income_raw)
        
        # For Cash Flow, prefer YTD Net Income if available (to align with YTD cash flow)
        net_income_ytd = get_value(cf_map, [
            'Net income (loss)',
            'Net loss',
            'Net income'
        ], default=None)
        cf_net_income = net_income_ytd if net_income_ytd is not None else net_income
        
        # FIX 2: Improve SG&A extraction with better synonyms
        rnd_raw = get_optional_value(is_map, ['Research and development', 'R&D', 'Research & development'])
        rnd = annualize(rnd_raw) if rnd_raw else None
        sga_raw = get_optional_value(is_map, [
            'Sales, general and administrative', 
            'Selling, general and administrative', 
            'SG&A',
            'Sales, general & administrative'
        ])
        sga = annualize(sga_raw) if sga_raw else None
        
        if opex == 0 and (rnd or sga):
            opex = (rnd or 0) + (sga or 0)

        interest_raw = get_value(is_map, ['Interest expense', 'Interest and dividend income'], default=0.0)
        interest = annualize(interest_raw)
        taxes_raw = get_value(is_map, ['Provision for income taxes', 'Income tax expense', 'Income tax'])
        taxes = annualize(taxes_raw)
        
        # Try to find Depreciation in CF if not in IS (common)
        da_raw = get_value(is_map, ['Depreciation and amortization'], default=0.0)
        if da_raw == 0:
            da_raw = get_value(cf_map, ['Depreciation and amortization', 'Depreciation'], default=0.0)
        da = annualize(da_raw)
        
        ebit = operating_income
        ebitda = ebit + da
        
        # Log extracted values for debugging
        if is_quarterly:
            print(f"[ANNUALIZATION] Revenue: ${revenue_raw:,.0f} x4 = ${revenue:,.0f} (annualized)")
            print(f"[ANNUALIZATION] Net Income: ${net_income_raw:,.0f} x4 = ${net_income:,.0f} (annualized)")
        else:
            print(f"[EXTRACTION] Revenue: ${revenue:,.0f}, Net Income: ${net_income:,.0f}")

        income_statement = IncomeStatement(
            Revenue=revenue,
            CostOfGoodsSold=cogs,
            GrossProfit=gross_profit,
            OpEx=opex,
            EBITDA=ebitda,
            DepreciationAndAmortization=da,
            EBIT=ebit,
            InterestExpense=interest,
            Taxes=taxes,
            NetIncome=net_income,
            RnD=rnd,
            SGA=sga,
            segment_revenue=None 
        )



        
        # Balance Sheet (Use bs_map)
        total_assets = get_value(bs_map, ['Total assets'])
        total_liabilities = get_value(bs_map, ['Total liabilities'])
        
        # FIX 3: Better equity extraction
        total_equity = get_value(bs_map, [
            'Shareholders\' equity',
            'Total shareholders\' equity', 
            'Total equity',
            'Stockholders\' equity'
        ], default=0.0)
        # If still 0, calculate from balance sheet equation
        if total_equity == 0 and total_assets != 0 and total_liabilities != 0:
            total_equity = total_assets - total_liabilities
        
        # FIX 4: Better cash extraction with more synonyms
        cash = get_optional_value(bs_map, [
            'Cash, cash equivalents and marketable securities',
            'Cash and cash equivalents', 
            'Cash and cash equivalents, end of period',
            'Cash'
        ])
        
        # FIX 5: Separate short-term and long-term debt properly
        short_term_debt = get_optional_value(bs_map, [
            'Short-term debt',
            'Current portion of long-term debt',
            'Commercial paper',
            'Loans payable, net, current',
            'Loans payable net current',
            'Notes payable, current',
            'Current debt'
        ])
        
        # FIX 6: Better long-term debt extraction
        long_term_debt = get_optional_value(bs_map, [
            'Long-term debt', 
            'Long term debt',
            'Term debt',
            'Loans payable, net, non-current',
            'Loans payable net non-current',
            'Notes payable, non-current',
            'Non-current debt'
        ])
        
        ar = get_optional_value(bs_map, ['Accounts receivable, net', 'Accounts receivable'])
        inventory = get_optional_value(bs_map, ['Inventories', 'Inventory'])
        ap = get_optional_value(bs_map, ['Accounts payable'])
        
        balance_sheet = BalanceSheet(
            Assets={'TotalAssets': total_assets},
            Liabilities={'TotalLiabilities': total_liabilities},
            Equity={'TotalEquity': total_equity},
            Cash=cash,
            ShortTermDebt=short_term_debt,
            LongTermDebt=long_term_debt,
            AccountsReceivable=ar,
            Inventory=inventory,
            AccountsPayable=ap
        )
        
        # Cash Flow (Use cf_map)
        cfo = get_value(cf_map, [
            'Net cash provided by operating activities',
            'Net cash used in operating activities',
            'Cash generated by operating activities', 
            'Cash from operations',
            'Cash flows from operating activities',
            'Net cash from operating activities'
        ], default=0.0)
        # Make absolute value for CFO (used can be negative)
        if cfo < 0:
            cfo = cfo  # Keep negative if cash is used
        
        # FIX 7: Better CapEx extraction
        capex = get_value(cf_map, [
            'Purchases related to property and equipment and intangible assets',
            'Payments for acquisition of property, plant and equipment',
            'Capital expenditures',
            'Purchases of property and equipment',
            'Purchase of property and equipment',
            'Acquisitions of property, plant and equipment',
            'Payments for property and equipment'
        ], default=0.0)
        capex = abs(capex) if capex != 0 else 0.0
        
        # FIX 8: FCF = CFO - CapEx (not just CFO)
        fcf_calc = (cfo - capex) if cfo != 0 else 0.0
        
        share_repurchases = get_optional_value(cf_map, [
            'Payments related to repurchases of common stock',
            'Repurchases of common stock', 
            'Payments for dividends and dividend equivalents'
        ])
        if share_repurchases: share_repurchases = abs(share_repurchases)
        
        dividends = get_optional_value(cf_map, [
            'Dividends paid',
            'Payments for dividends'
        ])
        if dividends: dividends = abs(dividends)
        
        # FIX 9: Better net change in cash extraction
        net_change_cash = get_value(cf_map, [
            'Change in cash and cash equivalents',
            'Increase/(Decrease) in cash, cash equivalents and restricted cash',
            'Increase (decrease) in cash', 
            'Net increase (decrease) in cash', 
            'Net change in cash'
        ], default=0.0)
        
        # FIX 10: Calculate working capital changes from individual components
        ar_change = get_value(cf_map, ['Accounts receivable'], default=0.0)
        inv_change = get_value(cf_map, ['Inventories'], default=0.0)
        ap_change = get_value(cf_map, ['Accounts payable'], default=0.0)
        accrued_change = get_value(cf_map, ['Accrued and other current liabilities'], default=0.0)
        wc_change = ar_change + inv_change + ap_change + accrued_change
        
        cash_flow = CashFlow(
            NetIncome=cf_net_income,  # Use YTD value for cash flow alignment
            Depreciation=da,
            ChangeInWorkingCapital=wc_change,
            CashFromOperations=cfo,
            CapEx=capex,
            CashFromInvesting=get_value(cf_map, [
                'Net cash used in investing activities',
                'Cash generated by/(used in) investing activities', 
                'Cash from investing',
                'Investing activities'
            ], default=0.0),
            DebtRepayment=0.0,
            Dividends=dividends or 0.0,
            CashFromFinancing=get_value(cf_map, [
                'Net cash used in financing activities',
                'Cash used in financing activities',
                'Cash generated by/(used in) financing activities',
                'Cash from financing',
                'Financing activities'
            ], default=0.0),
            NetChangeInCash=net_change_cash,
            FreeCashFlow=fcf_calc,
            ShareRepurchases=share_repurchases
        )
        
        # === TIER 2 & 3 (Empty for now) ===
        segment_data: List[SegmentData] = []
        geographic_data: List[GeographicData] = []
        debt_schedule: List[DebtSchedule] = []
        forward_looking: Optional[ForwardLookingData] = None
        non_gaap_metrics: Optional[NonGAAPMetrics] = None
        legal_regulatory: Optional[LegalAndRegulatory] = None
        
        return FinancialReport(
            income_statement=income_statement,
            balance_sheet=balance_sheet,
            cash_flow=cash_flow,
            segment_data=segment_data,
            geographic_data=geographic_data,
            debt_schedule=debt_schedule,
            forward_looking=forward_looking,
            non_gaap_metrics=non_gaap_metrics,
            legal_regulatory=legal_regulatory,
            kpis={
                "Revenue Growth": 0.0,
                "EBITDA Margin": (ebitda / revenue) if revenue > 0 else 0,
                "FCF Margin": (fcf_calc / revenue) if (revenue > 0 and fcf_calc) else 0
            },
            notes={},
            index={
                "Revenue": "Landing AI ADE",
                "OpEx": "Landing AI ADE",
                "EBITDA": "Calculated"
            },
            source_metadata=[],
            pdf_metadata=PDFMetadata(
                page_count=raw_data.get('metadata', {}).get('page_count', 0),
                duration_ms=raw_data.get('metadata', {}).get('duration_ms', 0.0),
                credit_usage=raw_data.get('metadata', {}).get('credit_usage', 0.0),
                job_id=raw_data.get('metadata', {}).get('job_id', 'unknown'),
                filename=raw_data.get('metadata', {}).get('filename')
            )
        )
