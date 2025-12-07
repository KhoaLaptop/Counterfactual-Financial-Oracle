from fpdf import FPDF
from ..models import AggregatedSimulation, CriticVerdict, FinancialReport, DebateResult
from typing import Optional

class EvaluatorAgent:
    def __init__(self):
        pass

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text to be compatible with latin-1 encoding for FPDF"""
        if not isinstance(text, str):
            return str(text)
            
        replacements = {
            '\u2018': "'",  # Left single quote
            '\u2019': "'",  # Right single quote
            '\u201c': '"',  # Left double quote
            '\u201d': '"',  # Right double quote
            '\u2013': "-",  # En dash
            '\u2014': "-",  # Em dash
            '\u2026': "...", # Ellipsis
            '\u00a0': " ",  # Non-breaking space
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
            
        # Final fallback: replace any remaining non-latin-1 chars with ?
        return text.encode('latin-1', 'replace').decode('latin-1')

    def generate_pdf(self, simulation: AggregatedSimulation, critic: CriticVerdict, 
                     report: FinancialReport, output_path: str, debate_result: Optional[DebateResult] = None):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="Counterfactual Financial Report", ln=1, align='C')
        pdf.ln(5)
        
        # Results Section
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Simulation Results", ln=1)
        pdf.set_font("Arial", size=11)
        pdf.cell(200, 8, txt=f"Median NPV: ${simulation.median_npv:,.2f}", ln=1)
        pdf.cell(200, 8, txt=f"Median Revenue: ${simulation.median_revenue:,.2f}", ln=1)
        pdf.cell(200, 8, txt=f"Median EBITDA: ${simulation.median_ebitda:,.2f}", ln=1)
        pdf.ln(5)
        
        # Critic Section
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Critic Verdict", ln=1)
        pdf.set_font("Arial", size=11)
        pdf.cell(200, 8, txt=f"Verdict: {critic.verdict.upper()}", ln=1)
        pdf.ln(3)
        
        # Assumptions
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 8, txt="Model Assumptions:", ln=1)
        pdf.set_font("Arial", size=10)
        for log in simulation.assumption_log:
            pdf.multi_cell(0, 6, txt=self._sanitize_text(f"  - {log}"))
        pdf.ln(5)
        
        # Comparative Analysis
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 8, txt="Comparative Analysis:", ln=1)
        pdf.set_font("Arial", size=10)
        for point in critic.comparative_analysis:
            pdf.multi_cell(0, 6, txt=self._sanitize_text(f"  - {point}"))
        pdf.ln(5)
        
        # NEW: AI Debate Transcript (if available)
        if debate_result is not None:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, txt="AI Analyst Debate Transcript", ln=1, align='C')
            pdf.ln(5)
            
            pdf.set_font("Arial", 'I', 10)
            pdf.multi_cell(0, 5, txt=self._sanitize_text(f"Two AI analysts debated the financial analysis for {debate_result.total_rounds} rounds. "
                                     f"{'Consensus was reached.' if debate_result.converged else 'Healthy disagreement remained.'}"))
            pdf.ln(3)
            
            # Convergence status
            pdf.set_font("Arial", 'B', 12)
            status_text = f"Status: {'CONVERGED' if debate_result.converged else 'DIVERGED'}"
            if debate_result.converged:
                status_text += f" (Round {debate_result.convergence_round})"
            pdf.cell(200, 8, txt=status_text, ln=1)
            pdf.ln(3)
            
            # Debate rounds (show first 3 and last 2 to keep PDF concise)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(200, 8, txt="Debate Highlights:", ln=1)
            pdf.ln(2)
            
            # Show selected rounds
            rounds_to_show = []
            total_turns = len(debate_result.debate_log)
            
            if total_turns <= 6:
                rounds_to_show = debate_result.debate_log
            else:
                # First 3 turns
                rounds_to_show.extend(debate_result.debate_log[:3])
                # Add separator
                rounds_to_show.append(None)  # Marker for "..."
                # Last 2 turns
                rounds_to_show.extend(debate_result.debate_log[-2:])
            
            for turn in rounds_to_show:
                if turn is None:
                    pdf.set_font("Arial", 'I', 10)
                    pdf.cell(200, 6, txt="... (additional rounds omitted for brevity) ...", ln=1, align='C')
                    pdf.ln(2)
                    continue
                
                # Speaker header
                pdf.set_font("Arial", 'B', 10)
                speaker_text = f"Round {turn.round_number}: {turn.speaker} ({turn.role})"
                pdf.cell(200, 6, txt=self._sanitize_text(speaker_text), ln=1)
                
                # Message content (truncate if too long)
                pdf.set_font("Arial", size=9)
                message = turn.message[:400] + "..." if len(turn.message) > 400 else turn.message
                pdf.multi_cell(0, 5, txt=self._sanitize_text(message))
                pdf.ln(2)
            
            # Final verdict
            pdf.ln(3)
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(200, 10, txt="Final Investment Verdict", ln=1)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(200, 8, txt=f"{debate_result.final_verdict} (Confidence: {debate_result.confidence_level})", ln=1)
            pdf.ln(3)
            
            # Key agreements
            if debate_result.key_agreements:
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(200, 7, txt="Key Agreements:", ln=1)
                pdf.set_font("Arial", size=9)
                for agreement in debate_result.key_agreements[:3]:
                    pdf.multi_cell(0, 5, txt=self._sanitize_text(f"  + {agreement[:150]}"))
                pdf.ln(2)
            
            # Remaining concerns
            if debate_result.key_disagreements:
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(200, 7, txt="Remaining Concerns:", ln=1)
                pdf.set_font("Arial", size=9)
                for disagreement in debate_result.key_disagreements[:2]:
                    pdf.multi_cell(0, 5, txt=self._sanitize_text(f"  - {disagreement[:150]}"))
                pdf.ln(2)
        
        # NEW: Document Sources Appendix
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="Appendix: Document Sources", ln=1, align='C')
        pdf.ln(5)
        
        pdf.set_font("Arial", 'I', 10)
        pdf.multi_cell(0, 5, txt="This appendix shows the document sources for key financial inputs used in the analysis.")
        pdf.ln(3)
        
        # Table header
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(50, 8, txt="Field", border=1)
        pdf.cell(40, 8, txt="Value", border=1)
        pdf.cell(100, 8, txt="Source", border=1, ln=1)
        
        # Table rows
        pdf.set_font("Arial", size=9)
        sources_data = [
            ("Revenue", f"${report.income_statement.Revenue:,.0f}", report.index.get("Revenue", "Landing AI ADE")),
            ("OpEx", f"${report.income_statement.OpEx:,.0f}", report.index.get("OpEx", "Landing AI ADE")),
            ("EBITDA", f"${report.income_statement.EBITDA:,.0f}", "Calculated: Revenue - COGS - OpEx"),
            ("Total Assets", f"${report.balance_sheet.Assets.get('TotalAssets', 0):,.0f}", 
             report.index.get("Total Assets", "Landing AI ADE")),
        ]
        
        for field, value, source in sources_data:
            pdf.cell(50, 7, txt=field, border=1)
            pdf.cell(40, 7, txt=value, border=1)
            pdf.cell(100, 7, txt=source[:45], border=1, ln=1)  # Truncate long sources
        
        pdf.ln(5)
        pdf.set_font("Arial", 'I', 8)
        pdf.multi_cell(0, 4, txt="Note: All values extracted using Landing AI Advanced Document Extraction (ADE). "
                                  "Source references indicate the document section or calculation method.")
        
        pdf.output(output_path)
        return output_path

