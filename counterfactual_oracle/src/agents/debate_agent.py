"""
Debate Agent: Orchestrates multi-round debates between Gemini (Optimist) and DeepSeek (Skeptic)

This agent manages the debate flow, handles convergence detection, and synthesizes
the final consensus from the debate transcript.
"""

import time
import re
import json
from typing import List, Tuple
from openai import OpenAI

from ..models import FinancialReport, AggregatedSimulation, DebateTurn, DebateResult
from ..debate_prompts import (
    get_gemini_opening_prompt,
    get_deepseek_challenge_prompt,
    get_gemini_response_prompt,
    get_deepseek_counter_prompt,
    get_consensus_prompt,
    CONVERGENCE_ANALYSIS_PROMPT
)


from .validator import RealismValidatorAgent

class DebateAgent:
    def __init__(self, kimi_api_key: str, deepseek_api_key: str):
        """Initialize debate agent with API clients"""
        # Kimi (Optimist) - using moonshot-v1-8k
        self.kimi = OpenAI(
            api_key=kimi_api_key,
            base_url="https://api.moonshot.cn/v1"
        )
        
        # DeepSeek (Skeptic)  
        self.deepseek = OpenAI(
            api_key=deepseek_api_key,
            base_url="https://api.deepseek.com/v1"
        )
        
        # Realism Validator (using Kimi now)
        self.validator = RealismValidatorAgent(api_key=kimi_api_key)
        
    def run_debate(
        self, 
        report: FinancialReport, 
        simulation: AggregatedSimulation,
        params: 'ScenarioParams',  # Add params for grounding
        max_rounds: int = 10,
        convergence_threshold: int = 2
    ) -> DebateResult:
        """
        Run a structured debate between Gemini and DeepSeek until convergence
        
        Args:
            report: Financial report data
            simulation: Simulation results
            params: Scenario parameters (for grounding to actual deltas)
            max_rounds: Maximum debate rounds (safety limit)
            convergence_threshold: Rounds without new objections needed for convergence
            
        Returns:
            DebateResult with complete transcript and consensus
        """
        debate_log = []
        convergence_counter = 0
        converged = False
        convergence_round = None
        
        # Round 1: Optimist (Kimi) opens with optimistic position (Validated)
        optimist_opening = self._get_validated_optimist_position(report, simulation, params, debate_log)
        debate_log.append(DebateTurn(
            round_number=1,
            speaker="Kimi",
            role="Optimist",
            message=optimist_opening,
            timestamp=time.time(),
            topic_focus="Opening Position"
        ))
        
        # Round 1: DeepSeek challenges
        deepseek_challenge = self._get_deepseek_challenge(optimist_opening, report, simulation, params, debate_log)
        debate_log.append(DebateTurn(
            round_number=1,
            speaker="DeepSeek",
            role="Skeptic",
            message=deepseek_challenge,
            timestamp=time.time(),
            topic_focus="Initial Challenge"
        ))
        
        # Continue debate until convergence or max rounds
        for round_num in range(2, max_rounds + 1):
            # RATE LIMITING: Pause before next LLM call (Kimi response)
            # Kimi Tier 0 limit is 3 RPM -> 20s per request. We use 25s to be safe.
            # The sleep is handled inside _get_validated_optimist_response

            # Optimist (Kimi) responds to critique (Validated)
            optimist_response = self._get_validated_optimist_response(
                deepseek_challenge, 
                round_num, 
                debate_log,
                report,
                simulation,
                params
            )
            debate_log.append(DebateTurn(
                round_number=round_num,
                speaker="Kimi",
                role="Optimist",
                message=optimist_response,
                timestamp=time.time(),
                topic_focus=f"Round {round_num} Response"
            ))
            
            # Check for convergence
            if self._check_convergence(debate_log):
                convergence_counter += 1
                if convergence_counter >= convergence_threshold:
                    converged = True
                    convergence_round = round_num
                    break
            else:
                convergence_counter = 0  # Reset if new objections arise
            
            # RATE LIMITING: Pause before next LLM call (DeepSeek counter)
            time.sleep(10)

            # DeepSeek counters - PASS data to prevent amnesia
            deepseek_counter = self._get_deepseek_counter(
                optimist_response,
                round_num,
                debate_log,
                report,
                simulation,
                params
            )
            debate_log.append(DebateTurn(
                round_number=round_num,
                speaker="DeepSeek",
                role="Skeptic",
                message=deepseek_counter,
                timestamp=time.time(),
                topic_focus=f"Round {round_num} Counter"
            ))
            
            # Update for next iteration
            deepseek_challenge = deepseek_counter
        
        # Synthesize consensus
        consensus = self._synthesize_consensus(debate_log, converged)
        
        return DebateResult(
            debate_log=debate_log,
            total_rounds=len(set(t.round_number for t in debate_log)),
            converged=converged,
            convergence_round=convergence_round,
            consensus_summary=consensus['summary'],
            key_agreements=consensus['agreements'],
            key_disagreements=consensus['disagreements'],
            final_verdict=consensus['verdict'],
            confidence_level=consensus['confidence']
        )
    
    def _get_validated_optimist_position(
        self, 
        report: FinancialReport, 
        simulation: AggregatedSimulation,
        params: 'ScenarioParams',
        debate_log: List[DebateTurn]
    ) -> str:
        """Get Optimist's (Kimi) opening position with validation retry loop"""
        prompt = get_gemini_opening_prompt(report, simulation, params)
        
        for attempt in range(3):
            # RATE LIMITING: Strict 25s pause for Kimi Tier 0 (3 RPM)
            time.sleep(25)
            
            try:
                response = self.kimi.chat.completions.create(
                    model="moonshot-v1-8k",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                text = response.choices[0].message.content
                
                # Validate
                validation = self.validator.validate_statement(text, report, simulation)
                
                if validation['is_valid']:
                    return text
                else:
                    # Add feedback to prompt and retry
                    prompt += f"\n\n[SYSTEM FEEDBACK]: Your previous response was rejected. Issues: {validation['issues']}. \nFeedback: {validation['feedback']}\n\nPlease rewrite strictly adhering to the data."
            except Exception as e:
                print(f"Kimi API Error: {e}")
                if attempt == 2: raise e
                time.sleep(5) # Short backoff on error
        
        return text # Return last attempt if all fail

    def _get_validated_optimist_response(
        self,
        deepseek_challenge: str,
        round_num: int,
        debate_log: List[DebateTurn],
        report: FinancialReport,
        simulation: AggregatedSimulation,
        params: 'ScenarioParams'
    ) -> str:
        """Get Optimist's (Kimi) response with validation retry loop"""
        # Summarize previous Optimist statements
        optimist_summary = " ".join([
            t.message[:100] for t in debate_log 
            if t.speaker == "Kimi"
        ])
        
        context = {'gemini_summary': optimist_summary}
        # PASS report, simulation, params to re-inject data
        prompt = get_gemini_response_prompt(deepseek_challenge, round_num, context, report, simulation, params)
        
        for attempt in range(3):
            # RATE LIMITING: Strict 25s pause for Kimi Tier 0 (3 RPM)
            time.sleep(25)
            
            try:
                response = self.kimi.chat.completions.create(
                    model="moonshot-v1-8k",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                text = response.choices[0].message.content
                
                # Validate
                validation = self.validator.validate_statement(text, report, simulation)
                
                if validation['is_valid']:
                    return text
                else:
                    # Add feedback to prompt and retry
                    prompt += f"\n\n[SYSTEM FEEDBACK]: Your previous response was rejected. Issues: {validation['issues']}. \nFeedback: {validation['feedback']}\n\nPlease rewrite strictly adhering to the data."
            except Exception as e:
                print(f"Kimi API Error: {e}")
                if attempt == 2: raise e
                time.sleep(5)
                
        return text
    
    def _get_deepseek_challenge(
        self,
        gemini_position: str,
        report: FinancialReport,
        simulation: AggregatedSimulation,
        params: 'ScenarioParams',
        debate_log: List[DebateTurn]
    ) -> str:
        """Get DeepSeek's challenge"""
        prompt = get_deepseek_challenge_prompt(gemini_position, report, simulation, params)
        response = self.deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    
    def _get_deepseek_counter(
        self,
        gemini_response: str,
        round_num: int,
        debate_log: List[DebateTurn],
        report: FinancialReport,
        simulation: AggregatedSimulation,
        params: 'ScenarioParams'
    ) -> str:
        """Get DeepSeek's counter-argument"""
        # Summarize previous DeepSeek statements
        deepseek_summary = " ".join([
            t.message[:100] for t in debate_log 
            if t.speaker == "DeepSeek"
        ])
        
        context = {'deepseek_summary': deepseek_summary}
        # PASS report, simulation, params to re-inject data
        prompt = get_deepseek_counter_prompt(gemini_response, round_num, context, report, simulation, params)
        
        response = self.deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    
    def _check_convergence(self, debate_log: List[DebateTurn]) -> bool:
        """
        Check if the debate has converged
        
        Convergence indicators:
        - Both agents use agreement language ("I agree", "You're right")
        - No new objections in last 2 turns
        - Similar conclusions being drawn
        """
        if len(debate_log) < 4:
            return False
        
        # Get last 2 messages from each agent
        recent_messages = [t.message.lower() for t in debate_log[-4:]]
        
        # Check for agreement keywords
        agreement_keywords = [
            "i agree", "you're right", "fair point", "i concede",
            "that makes sense", "good point", "i accept", "converge",
            "consensus", "we agree", "aligned"
        ]
        
        agreement_count = sum(
            1 for msg in recent_messages 
            for keyword in agreement_keywords 
            if keyword in msg
        )
        
        # If 2+ agreement statements in last 4 messages, likely converging
        return agreement_count >= 2
    
    def _synthesize_consensus(
        self, 
        debate_log: List[DebateTurn],
        converged: bool
    ) -> dict:
        """Synthesize final consensus from debate using LLM"""
        
        # Construct debate history string
        debate_history = "\n\n".join([
            f"ROUND {t.round_number} - {t.speaker} ({t.role}):\n{t.message}"
            for t in debate_log
        ])
        
        prompt = get_consensus_prompt(debate_history, final_round=True)
        
        try:
            # RATE LIMITING: Strict 25s pause for Kimi
            time.sleep(25)
            
            # Call Kimi to synthesize consensus
            response = self.kimi.chat.completions.create(
                model="moonshot-v1-8k",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            text = response.choices[0].message.content
            
            # Clean up markdown code blocks if present
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
                
            data = json.loads(text)
            
            return {
                'summary': data.get('summary', "Consensus reached."),
                'agreements': data.get('agreements', []),
                'disagreements': data.get('disagreements', []),
                'verdict': data.get('verdict', "Hold"),
                'confidence': data.get('confidence', "Medium")
            }
            
        except Exception as e:
            print(f"Error synthesizing consensus: {e}")
            # Fallback to simple summary if LLM fails
            return {
                'summary': "The analysts discussed the scenario but could not generate a structured consensus summary due to a processing error.",
                'agreements': ["Debate completed"],
                'disagreements': ["See transcript for details"],
                'verdict': "Hold",
                'confidence': "Low"
            }

    def _determine_verdict(self, debate_log: List[DebateTurn], converged: bool) -> str:
        """Determine final investment verdict from debate (Fallback)"""
        # Get all messages
        all_text = " ".join([t.message.lower() for t in debate_log])
        
        # Count positive vs negative sentiment
        positive_keywords = ["growth", "strong", "opportunity", "upside", "buy", "positive", "confident"]
        negative_keywords = ["risk", "concern", "downside", "sell", "negative", "weak", "challenge"]
        
        positive_count = sum(1 for keyword in positive_keywords if keyword in all_text)
        negative_count = sum(1 for keyword in negative_keywords if keyword in all_text)
        
        # Determine verdict based on balance
        if positive_count > negative_count * 1.5:
            return "Buy" if converged else "Cautious Buy"
        elif negative_count > positive_count * 1.5:
            return "Sell" if converged else "Cautious Sell"
        else:
            return "Hold"
