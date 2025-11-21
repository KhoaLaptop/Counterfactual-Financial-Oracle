import google.generativeai as genai
import time
import json
from typing import Dict, Any, List, Optional
from ..models import FinancialReport, AggregatedSimulation

class RealismValidatorAgent:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        self.blocklist = [
            "new product", "product launch", "market expansion", 
            "pre-order", "internal projection", "market research",
            "partner demand", "customer retention program", 
            "marketing efficiency", "unspecified cost savings"
        ]

    def validate_statement(
        self, 
        statement: str, 
        report: FinancialReport, 
        simulation: AggregatedSimulation
    ) -> Dict[str, Any]:
        """
        Validates a debate statement for realism, grounding, and math consistency.
        Returns a dict with 'is_valid' (bool), 'issues' (list), and 'corrected_text' (str).
        """
        
        # 1. Quick Keyword Check (Fast Fail)
        found_blocked = [term for term in self.blocklist if term in statement.lower()]
        if found_blocked:
            return {
                "is_valid": False,
                "issues": [f"Used blocked term: '{term}'" for term in found_blocked],
                "feedback": f"You mentioned {found_blocked}. This data does not exist in the report. Remove it and stick to the provided numbers."
            }

        # 2. LLM Validation
        prompt = f"""
        You are a strict Realism Validator for a financial debate.
        
        Your Job: Check if the Analyst's statement contains hallucinations, math errors, or blocked concepts.
        
        CONTEXT (The ONLY truth):
        - Revenue: ${report.income_statement.Revenue:,.0f}
        - OpEx: ${report.income_statement.OpEx:,.0f}
        - EBITDA: ${report.income_statement.EBITDA:,.0f}
        - Net Income: ${report.income_statement.NetIncome:,.0f}
        
        SIMULATION RESULTS (The ONLY future truth):
        - Median NPV: ${simulation.median_npv:,.0f}
        - Median Revenue: ${simulation.median_revenue:,.0f}
        - Median EBITDA: ${simulation.median_ebitda:,.0f}
        
        ANALYST STATEMENT:
        "{statement}"
        
        VALIDATION RULES:
        1. **No Hallucinations**: Reject claims about "new products", "pre-orders", "market expansion", or "internal data" not in Context.
        2. **Math Consistency**: Reject claims like "EBITDA is strong" if it dropped in the simulation. Reject "margin expansion" if OpEx delta is positive (costs rising).
        3. **Strict Grounding**: Every number cited must exist in the Context or be a direct calculation from it.
        
        Return JSON ONLY:
        {{
            "is_valid": boolean,
            "issues": ["list of specific errors"],
            "feedback": "Instructions to the analyst to fix the statement (e.g., 'Remove reference to new product, cite actual OpEx of $14B')"
        }}
        """
        

        
        try:
            # RATE LIMITING: Pause before validation call
            time.sleep(10)
            response = self.model.generate_content(prompt)
            text = response.text
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
                
            result = json.loads(text)
            return result
            
        except Exception as e:
            # Fallback if validation fails
            print(f"Validation failed: {e}")
            return {"is_valid": True, "issues": [], "feedback": ""}
