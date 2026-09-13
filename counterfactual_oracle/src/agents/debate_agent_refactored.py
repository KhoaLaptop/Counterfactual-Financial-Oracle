"""
Refactored Debate Agent with async support, caching, and proper telemetry.
"""

import asyncio
import time
import json
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI, AsyncOpenAI
import google.generativeai as genai

from ..models import FinancialReport, AggregatedSimulation, ScenarioParams, DebateTurn, DebateResult
from ..config import settings
from ..infrastructure.logging import get_logger
from ..infrastructure.cache import cache
from ..infrastructure.telemetry import (
    record_debate_metrics, APICostTracker, tracer
)
from ..infrastructure.retry import (
    ResilientAPIClient, create_retry_config_for_provider, CircuitBreaker
)
from .validator import RealismValidatorAgent
from ..debate_prompts import (
    get_gemini_opening_prompt,
    get_deepseek_challenge_prompt,
    get_gemini_response_prompt,
    get_deepseek_counter_prompt,
    get_consensus_prompt,
    CONVERGENCE_ANALYSIS_PROMPT
)

logger = get_logger(__name__)


class DebateAgent:
    """
    Orchestrates multi-round debates between AI analysts with resilience and caching.
    """
    
    def __init__(self, openai_api_key: str = None, deepseek_api_key: str = None):
        """Initialize debate agent with API clients."""
        
        # API Keys
        openai_key = openai_api_key or settings.openai_api_key
        deepseek_key = deepseek_api_key or settings.deepseek_api_key
        
        # Determine optimist provider
        self.optimist_provider = "openai"
        if openai_key and openai_key.startswith("AIza"):
            self.optimist_provider = "google"
            genai.configure(api_key=openai_key)
            self.optimist_model = genai.GenerativeModel(settings.gemini_model)
        else:
            self.openai_client = OpenAI(api_key=openai_key)
            self.async_openai = AsyncOpenAI(api_key=openai_key)
        
        # DeepSeek client
        self.deepseek_client = OpenAI(
            api_key=deepseek_key,
            base_url=settings.deepseek_base_url
        )
        self.async_deepseek = AsyncOpenAI(
            api_key=deepseek_key,
            base_url=settings.deepseek_base_url
        )
        
        # Resilient clients
        self.optimist_resilient = ResilientAPIClient(
            provider=self.optimist_provider,
            model=settings.openai_model if self.optimist_provider == "openai" else settings.gemini_model,
            circuit_breaker=CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        )
        
        self.deepseek_resilient = ResilientAPIClient(
            provider="deepseek",
            model=settings.deepseek_model,
            circuit_breaker=CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        )
        
        # Validator
        self.validator = RealismValidatorAgent(api_key=openai_key)
        
        # Thread pool for sync operations
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    @cache.cached(
        ttl=3600,
        key_builder=lambda self, report, simulation, params, **kwargs: 
            f"debate:{hash(report.income_statement.Revenue)}:{hash(simulation.median_npv)}:{params.opex_delta_bps}"
    )
    def run_debate(
        self,
        report: FinancialReport,
        simulation: AggregatedSimulation,
        params: ScenarioParams,
        max_rounds: int = None,
        convergence_threshold: int = None
    ) -> DebateResult:
        """
        Run a structured debate between AI analysts.
        
        Args:
            report: Financial report data
            simulation: Simulation results
            params: Scenario parameters
            max_rounds: Maximum debate rounds
            convergence_threshold: Rounds without new objections for convergence
            
        Returns:
            DebateResult with complete transcript and consensus
        """
        max_rounds = max_rounds or settings.max_debate_rounds
        convergence_threshold = convergence_threshold or settings.convergence_threshold
        
        start_time = time.time()
        debate_log: List[DebateTurn] = []
        convergence_counter = 0
        converged = False
        convergence_round = None
        
        logger.info(
            "debate_started",
            max_rounds=max_rounds,
            revenue=report.income_statement.Revenue,
            npv=simulation.median_npv
        )
        
        with tracer.start_as_current_span("debate") as span:
            span.set_attribute("max_rounds", max_rounds)
            span.set_attribute("revenue", report.income_statement.Revenue)
            
            # Round 1: Optimist opens
            optimist_opening = self._get_validated_optimist_position(report, simulation, params, debate_log)
            debate_log.append(DebateTurn(
                round_number=1,
                speaker="OpenAI" if self.optimist_provider == "openai" else "Gemini",
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
            
            # Continue debate
            for round_num in range(2, max_rounds + 1):
                # Optimist responds
                optimist_response = self._get_validated_optimist_response(
                    deepseek_challenge, round_num, debate_log, report, simulation, params
                )
                debate_log.append(DebateTurn(
                    round_number=round_num,
                    speaker="OpenAI" if self.optimist_provider == "openai" else "Gemini",
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
                        logger.info("debate_converged", round=round_num)
                        break
                else:
                    convergence_counter = 0
                
                # Rate limiting
                time.sleep(settings.debate_rate_limit_delay)
                
                # DeepSeek counters
                deepseek_counter = self._get_deepseek_counter(
                    optimist_response, round_num, debate_log, report, simulation, params
                )
                debate_log.append(DebateTurn(
                    round_number=round_num,
                    speaker="DeepSeek",
                    role="Skeptic",
                    message=deepseek_counter,
                    timestamp=time.time(),
                    topic_focus=f"Round {round_num} Counter"
                ))
                
                deepseek_challenge = deepseek_counter
                
                # Rate limiting
                time.sleep(settings.debate_rate_limit_delay * 2)
            
            # Synthesize consensus
            consensus = self._synthesize_consensus(debate_log, converged)
            
            duration = time.time() - start_time
            
            result = DebateResult(
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
            
            # Record metrics
            record_debate_metrics(converged, result.total_rounds, duration)
            
            return result
    
    async def run_debate_async(
        self,
        report: FinancialReport,
        simulation: AggregatedSimulation,
        params: ScenarioParams,
        max_rounds: int = None
    ) -> DebateResult:
        """Async version of run_debate for parallel processing."""
        # For now, delegate to sync version with thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.run_debate,
            report, simulation, params, max_rounds
        )
    
    def _get_validated_optimist_position(
        self,
        report: FinancialReport,
        simulation: AggregatedSimulation,
        params: ScenarioParams,
        debate_log: List[DebateTurn]
    ) -> str:
        """Get Optimist's opening position with validation retry loop."""
        prompt = get_gemini_opening_prompt(report, simulation, params)
        
        for attempt in range(3):
            try:
                text = self._call_optimist(prompt)
                
                # Validate
                validation = self.validator.validate_statement(text, report, simulation)
                
                if validation['is_valid']:
                    return text
                else:
                    prompt += f"\n\n[SYSTEM FEEDBACK]: Previous response rejected. Issues: {validation['issues']}.\n"
                    logger.warning("optimist_validation_failed", attempt=attempt, issues=validation['issues'])
                    
            except Exception as e:
                logger.error("optimist_api_error", attempt=attempt, error=str(e))
                if attempt == 2:
                    raise
                time.sleep(2)
        
        return text
    
    def _get_validated_optimist_response(
        self,
        deepseek_challenge: str,
        round_num: int,
        debate_log: List[DebateTurn],
        report: FinancialReport,
        simulation: AggregatedSimulation,
        params: ScenarioParams
    ) -> str:
        """Get Optimist's response with validation."""
        optimist_summary = " ".join([
            t.message[:100] for t in debate_log
            if t.speaker in ["OpenAI", "Gemini"]
        ])
        
        context = {'gemini_summary': optimist_summary}
        prompt = get_gemini_response_prompt(deepseek_challenge, round_num, context, report, simulation, params)
        
        for attempt in range(3):
            try:
                text = self._call_optimist(prompt)
                
                validation = self.validator.validate_statement(text, report, simulation)
                
                if validation['is_valid']:
                    return text
                else:
                    prompt += f"\n\n[SYSTEM FEEDBACK]: Previous response rejected. Issues: {validation['issues']}.\n"
                    logger.warning("optimist_validation_failed", attempt=attempt, issues=validation['issues'])
                    
            except Exception as e:
                logger.error("optimist_api_error", attempt=attempt, error=str(e))
                if attempt == 2:
                    raise
                time.sleep(2)
        
        return text
    
    def _get_deepseek_challenge(
        self,
        gemini_position: str,
        report: FinancialReport,
        simulation: AggregatedSimulation,
        params: ScenarioParams,
        debate_log: List[DebateTurn]
    ) -> str:
        """Get DeepSeek's challenge."""
        prompt = get_deepseek_challenge_prompt(gemini_position, report, simulation, params)
        
        def _call():
            response = self.deepseek_client.chat.completions.create(
                model=settings.deepseek_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            return response.choices[0].message.content
        
        return self.deepseek_resilient.execute_with_resilience(_call)
    
    def _get_deepseek_counter(
        self,
        gemini_response: str,
        round_num: int,
        debate_log: List[DebateTurn],
        report: FinancialReport,
        simulation: AggregatedSimulation,
        params: ScenarioParams
    ) -> str:
        """Get DeepSeek's counter-argument."""
        deepseek_summary = " ".join([
            t.message[:100] for t in debate_log
            if t.speaker == "DeepSeek"
        ])
        
        context = {'deepseek_summary': deepseek_summary}
        prompt = get_deepseek_counter_prompt(gemini_response, round_num, context, report, simulation, params)
        
        def _call():
            response = self.deepseek_client.chat.completions.create(
                model=settings.deepseek_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            return response.choices[0].message.content
        
        return self.deepseek_resilient.execute_with_resilience(_call)
    
    def _call_optimist(self, prompt: str) -> str:
        """Call the optimist LLM."""
        def _call():
            if self.optimist_provider == "google":
                response = self.optimist_model.generate_content(prompt)
                return response.text
            else:
                response = self.openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                return response.choices[0].message.content
        
        return self.optimist_resilient.execute_with_resilience(_call)
    
    def _check_convergence(self, debate_log: List[DebateTurn]) -> bool:
        """Check if debate has converged using LLM analysis."""
        if len(debate_log) < 4:
            return False
        
        transcript = "\n\n".join([
            f"{t.speaker} ({t.role}): {t.message}"
            for t in debate_log[-4:]
        ])
        
        prompt = CONVERGENCE_ANALYSIS_PROMPT.format(debate_transcript=transcript)
        
        try:
            def _call():
                if self.optimist_provider == "google":
                    response = self.optimist_model.generate_content(prompt)
                    return response.text.strip().upper()
                else:
                    response = self.openai_client.chat.completions.create(
                        model=settings.openai_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1
                    )
                    return response.choices[0].message.content.strip().upper()
            
            result = self.optimist_resilient.execute_with_resilience(_call)
            
            logger.debug("convergence_check", result=result)
            
            if "CONVERGED" in result:
                return True
            elif "PARTIAL" in result and len(debate_log) >= 8:
                return True
            else:
                return False
                
        except Exception as e:
            logger.error("convergence_check_failed", error=str(e))
            return False
    
    def _synthesize_consensus(self, debate_log: List[DebateTurn], converged: bool) -> dict:
        """Synthesize final consensus from debate."""
        debate_history = "\n\n".join([
            f"ROUND {t.round_number} - {t.speaker} ({t.role}):\n{t.message}"
            for t in debate_log
        ])
        
        prompt = get_consensus_prompt(debate_history, final_round=True)
        
        try:
            def _call():
                if self.optimist_provider == "google":
                    response = self.optimist_model.generate_content(prompt)
                    return response.text
                else:
                    response = self.openai_client.chat.completions.create(
                        model=settings.openai_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.5
                    )
                    return response.choices[0].message.content
            
            text = self.optimist_resilient.execute_with_resilience(_call)
            
            # Clean up markdown
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
            logger.error("consensus_synthesis_failed", error=str(e))
            return {
                'summary': "Debate completed but consensus synthesis failed.",
                'agreements': ["Debate completed"],
                'disagreements': ["See transcript for details"],
                'verdict': "Hold",
                'confidence': "Low"
            }
