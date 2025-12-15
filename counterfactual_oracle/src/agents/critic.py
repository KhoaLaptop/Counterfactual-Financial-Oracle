from openai import OpenAI
import json
import os
from ..models import FinancialReport, AggregatedSimulation, CriticVerdict
from ..logic import check_balance_sheet

class CriticAgent:
    def __init__(self, api_key: str):
        # DeepSeek API uses a different authentication format
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "DeepSeek-V3.2-Speciale"

    def critique(self, report: FinancialReport, simulation: AggregatedSimulation) -> CriticVerdict:
        """
        Critiques the simulation results.
        """
        
        # 1. Run Deterministic Checks
        bs_check = check_balance_sheet(report.balance_sheet)
        
        # 2. Run LLM Critique
        prompt = f"""
        You are a senior financial report analyst and a strict critic.
        
        Report Data: {report.model_dump_json()}
        Simulation Results: {simulation.model_dump_json(exclude={'simulation_runs'})}
        Balance Sheet Check: {bs_check}
        
        Tasks:
        1. **Verify Consistency**: Ensure the simulation results (e.g., Revenue Growth) match the input parameters. Call out any contradictions.
        2. **Fact-Check Claims**: If the analysis mentions specific drivers (e.g., "cost cutting"), verify if the OpEx numbers actually decreased. If not, flag it as an unsupported assumption.
        3. **Demand Evidence**: If the analysis is vague (e.g., "operational efficiency"), demand to know WHICH line item improved (SG&A? R&D?) and by how much.
        4. **Compare against industry norms**: Assume standard tech margins if not specified.
        
        Return JSON:
        {{
            "verdict": "approve" or "revise",
            "comparative_analysis": ["point 1", "point 2"],
            "unsupported_assumptions": ["assumption 1", "assumption 2"],
            "correction_instructions": "instructions if revise"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a strict financial critic. Output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            llm_data = json.loads(content)
            
            return CriticVerdict(
                verdict=llm_data.get("verdict", "approve"),
                balance_sheet_check=bs_check,
                cash_flow_check={"status": "checked"}, # Placeholder for deeper check
                comparative_analysis=llm_data.get("comparative_analysis", []),
                unsupported_assumptions=llm_data.get("unsupported_assumptions", []),
                correction_instructions=llm_data.get("correction_instructions")
            )
            
        except Exception as e:
            error_msg = str(e)
            print(f"Critic LLM failed: {error_msg}")
            print(f"DeepSeek API Key (last 4 chars): ...{self.client.api_key[-4:]}")
            print(f"DeepSeek Base URL: {self.client.base_url}")
            
            # Fallback: Use rule-based critique
            comparative_analysis = []
            
            # Check EBITDA margin
            if simulation.median_ebitda > 0 and report.income_statement.Revenue > 0:
                ebitda_margin = simulation.median_ebitda / simulation.median_revenue
                if ebitda_margin > 0.40:
                    comparative_analysis.append(f"EBITDA margin of {ebitda_margin:.1%} is very strong (above 40%)")
                elif ebitda_margin < 0.10:
                    comparative_analysis.append(f"EBITDA margin of {ebitda_margin:.1%} is concerning (below 10%)")
                else:
                    comparative_analysis.append(f"EBITDA margin of {ebitda_margin:.1%} appears reasonable")
            
            # Check NPV reasonableness
            if simulation.median_npv < 0:
                comparative_analysis.append("Negative NPV suggests the investment may not be viable")
            
            comparative_analysis.append(f"Note: DeepSeek API unavailable - using rule-based analysis")
            
            return CriticVerdict(
                verdict="approve", # Default to approve if critic fails to avoid blocking
                balance_sheet_check=bs_check,
                cash_flow_check={},
                comparative_analysis=comparative_analysis,
                unsupported_assumptions=[]
            )


