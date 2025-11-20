import google.generativeai as genai
import json
import os
from ..models import FinancialReport, ScenarioParams, AggregatedSimulation
from ..logic import run_monte_carlo

class SimulatorAgent:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def run_simulation(self, report: FinancialReport, params: ScenarioParams) -> AggregatedSimulation:
        """
        Runs the simulation pipeline.
        1. Uses Python logic for Monte Carlo (more reliable for math than LLM).
        2. Uses LLM to generate the qualitative "Assumption Log" and "Traceability" based on the results.
        """
        
        # 1. Run Math
        agg_results = run_monte_carlo(report, params)
        
        # 2. Generate Qualitative Analysis via LLM
        prompt = f"""
        You are a professional financial analyst.
        
        I have run a Monte Carlo simulation with the following parameters:
        - OpEx Delta: {params.opex_delta_bps} bps
        - Revenue Growth Delta: {params.revenue_growth_bps} bps
        - Discount Rate Delta: {params.discount_rate_bps} bps
        
        The results are:
        - Median NPV: ${agg_results.median_npv:,.2f}
        - Median Revenue: ${agg_results.median_revenue:,.2f}
        - Median EBITDA: ${agg_results.median_ebitda:,.2f}
        
        Report Context:
        - Revenue: ${report.income_statement.Revenue:,.2f}
        - OpEx: ${report.income_statement.OpEx:,.2f}
        - Net Income: ${report.income_statement.NetIncome:,.2f}
        
        Please generate a structured 'assumption_log' and 'traceability' explanation.
        
        **CRITICAL INSTRUCTIONS:**
        1. **STRICT GROUNDING**: You must ONLY use drivers present in the provided Report Context or Simulation Results. Do NOT invent "new product launches", "marketing efficiency", or "customer retention programs" unless they are explicitly in the data.
        2. **CITE NUMBERS**: You must cite specific numbers from the report to support your arguments (e.g., "Given R&D of $7.7B...", "With OpEx at 12% of revenue...").
        3. **CONSISTENCY**: If the simulation shows 0% growth, do NOT argue for growth. Explain the result based on the inputs (e.g., "Revenue remained flat due to the 0 bps growth assumption").
        
        For 'assumption_log', describe the transformations based on the actual simulation parameters.
        For 'traceability', explain where the base numbers came from (refer to the report structure).
        
        Return ONLY valid JSON in this format:
        {{
            "assumption_log": ["log entry 1", "log entry 2"],
            "traceability": {{"Metric": "Source"}}
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            content = response.text
            
            # Clean up markdown code blocks if present
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            llm_data = json.loads(content)
            
            # Merge LLM insights
            agg_results.assumption_log = llm_data.get("assumption_log", agg_results.assumption_log)
            agg_results.traceability = llm_data.get("traceability", agg_results.traceability)
            
        except Exception as e:
            print(f"LLM generation failed, using default logs: {e}")
            
        return agg_results

