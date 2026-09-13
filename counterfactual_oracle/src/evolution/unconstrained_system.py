"""
🚀 UNCONSTRAINED MULTI-AGENT EVOLUTION SYSTEM

This is the main entry point for the unconstrained evolutionary system.

It combines:
- Genetic evolution of agent behaviors
- Meta-agent orchestration
- Emergence detection
- Recursive self-improvement

This system has no fixed boundaries - it evolves its own evolution,
creates new species, and discovers novel strategies autonomously.
"""

import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import numpy as np

from .genome import AgentGenome, AgentInstance
from .population import AgentPopulation, PopulationConfig
from .evolution_engine import EvolutionEngine, FitnessLandscape, EvolutionPhase
from .meta_agent import MetaAgent, EvolutionOrchestrator
from .emergence import EmergenceDetector, SpecializationTracker
from .recursive_improvement import SelfModificationLoop
from ..infrastructure.logging import get_logger
from ..infrastructure.telemetry import tracer

logger = get_logger(__name__)


@dataclass
class SystemConfiguration:
    """Configuration for the unconstrained evolution system."""
    enable_recursive_improvement: bool = True
    enable_emergence_detection: bool = True
    enable_meta_orchestration: bool = True
    max_generations: int = 200
    target_fitness: float = 0.95
    parallel_populations: int = 3
    
    # Unconstrained parameters
    allow_unbounded_complexity: bool = True
    enable_species_creation: bool = True
    allow_agent_spawning: bool = True
    dynamic_environment: bool = True


class UnconstrainedEvolutionSystem:
    """
    The complete unconstrained multi-agent evolution system.
    
    This system operates with minimal human-imposed constraints:
    - Agents can evolve any viable strategy
    - New species emerge naturally
    - The system improves its own evolution mechanisms
    - Meta-agents coordinate multiple populations
    - Emergent behaviors are detected and amplified
    """
    
    def __init__(self, config: SystemConfiguration = None):
        self.config = config or SystemConfiguration()
        
        # Core components
        self.meta_agent: Optional[MetaAgent] = None
        self.orchestrator = EvolutionOrchestrator()
        
        # Detection and tracking
        self.emergence_detector = EmergenceDetector()
        self.specialization_tracker = SpecializationTracker()
        
        # Self-improvement
        self.self_modification = SelfModificationLoop()
        
        # State
        self.generation = 0
        self.system_history: List[Dict] = []
        self.global_best: Optional[AgentInstance] = None
        
    async def initialize(self, problem_definition: Dict[str, Any]) -> None:
        """
        Initialize the unconstrained system.
        
        Args:
            problem_definition: Definition of the problem to evolve solutions for
        """
        logger.info(
            "unconstrained_system_initializing",
            recursive=self.config.enable_recursive_improvement,
            emergence=self.config.enable_emergence_detection,
            meta=self.config.enable_meta_orchestration
        )
        
        # Create meta-agent
        self.meta_agent = MetaAgent()
        
        # Define fitness landscape
        landscape = self._create_fitness_landscape(problem_definition)
        
        # Initialize primary population
        await self.meta_agent._initialize_population("unconstrained_primary", landscape)
        
        logger.info("unconstrained_system_initialized")
    
    async def evolve(
        self,
        problem_definition: Dict[str, Any],
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Run unconstrained evolution.
        
        This is the main entry point that runs the complete evolutionary system
        with all its meta-capabilities.
        
        Args:
            problem_definition: The problem to solve
            callback: Optional callback for progress updates
            
        Returns:
            Final system state and best evolved solutions
        """
        await self.initialize(problem_definition)
        
        logger.info(
            "unconstrained_evolution_started",
            max_generations=self.config.max_generations
        )
        
        for generation in range(self.config.max_generations):
            self.generation = generation
            
            with tracer.start_as_current_span("evolution_generation") as span:
                span.set_attribute("generation", generation)
                
                # 1. Run base evolution
                await self._run_base_evolution()
                
                # 2. Detect emergent patterns
                if self.config.enable_emergence_detection:
                    await self._detect_emergence()
                
                # 3. Meta-orchestration
                if self.config.enable_meta_orchestration and generation % 10 == 0:
                    await self._run_meta_orchestration()
                
                # 4. Recursive self-improvement
                if self.config.enable_recursive_improvement and generation % 20 == 0:
                    await self._run_recursive_improvement()
                
                # 5. Update global state
                self._update_global_state()
                
                # 6. Record history
                self._record_generation_history()
                
                # Callback
                if callback:
                    callback(generation, self._get_current_state())
                
                # Logging
                if generation % 10 == 0:
                    self._log_progress()
                
                # Check termination
                if self._should_terminate():
                    break
        
        return self._compile_final_report()
    
    async def _run_base_evolution(self) -> None:
        """Run one generation of base evolution for all populations."""
        for name, engine in self.meta_agent.engines.items():
            # Evaluate
            await engine._evaluate_population_async()
            
            # Advance
            stats = engine.population.evolve_generation()
            
            # Update engine state
            engine._update_evolution_state()
    
    async def _detect_emergence(self) -> None:
        """Detect emergent patterns in all populations."""
        for name, population in self.meta_agent.populations.items():
            new_patterns = self.emergence_detector.analyze_population(
                population, self.generation
            )
            
            if new_patterns:
                logger.info(
                    "emergence_detected",
                    population=name,
                    patterns=len(new_patterns),
                    pattern_types=[p.pattern_type for p in new_patterns]
                )
                
                # If significant emergence, boost that population
                for pattern in new_patterns:
                    if pattern.is_significant():
                        self._boost_emergent_pattern(pattern, population)
    
    def _boost_emergent_pattern(
        self,
        pattern: Any,
        population: AgentPopulation
    ) -> None:
        """Amplify significant emergent patterns."""
        # Increase resources to agents showing the pattern
        for agent_id in pattern.agents_involved:
            for agent in population.agents:
                if agent.agent_id == agent_id:
                    # Boost fitness to help pattern spread
                    agent.evaluate(0.1)  # Bonus for innovation
    
    async def _run_meta_orchestration(self) -> None:
        """Run meta-level orchestration."""
        ecosystem_state = self.meta_agent._assess_ecosystem()
        
        # Check for niche gaps and fill them
        await self.meta_agent._diversify_into_niches()
        
        # Coordinate specialists
        if len(self.meta_agent.populations) > 2:
            await self.meta_agent._coordinate_specialists()
    
    async def _run_recursive_improvement(self) -> None:
        """Run recursive self-improvement of evolution mechanisms."""
        # Collect base evolution results
        evolution_results = {
            "success_rate": self._calculate_success_rate(),
            "avg_improvement": self._calculate_avg_improvement(),
            "final_diversity": self._calculate_global_diversity(),
            "generations": self.generation,
            "cost": 0.5  # Would track actual compute cost
        }
        
        # Run meta-evolution
        improvements = self.self_modification.run_meta_evolution_cycle(evolution_results)
        
        logger.info(
            "recursive_improvement_completed",
            cycle=improvements.get("cycle"),
            improvements_count=len(improvements.get("improvements", []))
        )
    
    def _update_global_state(self) -> None:
        """Update global system state."""
        # Find global best across all populations
        for population in self.meta_agent.populations.values():
            best = population.get_best_agent()
            if best:
                if not self.global_best or best.average_fitness > self.global_best.average_fitness:
                    self.global_best = best
    
    def _record_generation_history(self) -> None:
        """Record this generation's state."""
        record = {
            "generation": self.generation,
            "populations": len(self.meta_agent.populations),
            "total_agents": sum(len(p.agents) for p in self.meta_agent.populations.values()),
            "species": sum(len(p.species) for p in self.meta_agent.populations.values()),
            "global_best_fitness": self.global_best.average_fitness if self.global_best else 0,
            "detected_patterns": len(self.emergence_detector.detected_patterns),
            "phase_transitions": len(self.emergence_detector.phase_transitions)
        }
        
        self.system_history.append(record)
    
    def _log_progress(self) -> None:
        """Log current progress."""
        if not self.system_history:
            return
        
        latest = self.system_history[-1]
        
        logger.info(
            "unconstrained_evolution_progress",
            generation=latest["generation"],
            populations=latest["populations"],
            total_agents=latest["total_agents"],
            species=latest["species"],
            best_fitness=round(latest["global_best_fitness"], 4),
            patterns=latest["detected_patterns"]
        )
    
    def _should_terminate(self) -> bool:
        """Check if evolution should terminate."""
        # Target fitness reached
        if self.global_best and self.global_best.average_fitness >= self.config.target_fitness:
            logger.info("target_fitness_reached")
            return True
        
        # All populations converged
        all_converged = all(
            engine.population.has_converged()
            for engine in self.meta_agent.engines.values()
        )
        
        if all_converged and self.generation > 50:
            logger.info("all_populations_converged")
            return True
        
        return False
    
    def _create_fitness_landscape(
        self,
        problem_def: Dict[str, Any]
    ) -> FitnessLandscape:
        """Create fitness landscape from problem definition."""
        def primary_fitness(agent: AgentInstance) -> float:
            # Problem-specific fitness evaluation
            # This would be customized based on the actual problem
            base_fitness = agent.average_fitness
            
            # Bonus for genomic diversity
            diversity_bonus = len(set(agent.genome.strategy_gene.value.split('+'))) * 0.05
            
            return min(1.0, base_fitness + diversity_bonus)
        
        return FitnessLandscape(
            primary_fitness_fn=primary_fitness,
            dynamic=self.config.dynamic_environment
        )
    
    def _calculate_success_rate(self) -> float:
        """Calculate success rate of evolution."""
        if not self.system_history:
            return 0.5
        
        recent = self.system_history[-10:]
        improvements = sum(1 for i in range(1, len(recent)) 
                          if recent[i]["global_best_fitness"] > recent[i-1]["global_best_fitness"])
        
        return improvements / max(1, len(recent) - 1)
    
    def _calculate_avg_improvement(self) -> float:
        """Calculate average fitness improvement."""
        if len(self.system_history) < 2:
            return 0.0
        
        improvements = []
        for i in range(1, len(self.system_history)):
            curr = self.system_history[i]["global_best_fitness"]
            prev = self.system_history[i-1]["global_best_fitness"]
            if curr > prev:
                improvements.append(curr - prev)
        
        return np.mean(improvements) if improvements else 0.0
    
    def _calculate_global_diversity(self) -> float:
        """Calculate global diversity across all populations."""
        diversities = [
            p._calculate_diversity_index()
            for p in self.meta_agent.populations.values()
        ]
        return np.mean(diversities) if diversities else 0.0
    
    def _get_current_state(self) -> Dict[str, Any]:
        """Get current system state."""
        return {
            "generation": self.generation,
            "global_best": {
                "fitness": self.global_best.average_fitness if self.global_best else 0,
                "phenotype": self.global_best.genome.get_phenotype() if self.global_best else None
            },
            "populations": len(self.meta_agent.populations),
            "emergent_patterns": len(self.emergence_detector.detected_patterns),
            "phase": self._get_dominant_phase()
        }
    
    def _get_dominant_phase(self) -> str:
        """Get the dominant evolution phase across populations."""
        phases = [e.state.phase.value for e in self.meta_agent.engines.values()]
        if phases:
            return max(set(phases), key=phases.count)
        return "unknown"
    
    def _compile_final_report(self) -> Dict[str, Any]:
        """Compile comprehensive final report."""
        return {
            "system_summary": {
                "total_generations": self.generation,
                "final_populations": len(self.meta_agent.populations),
                "final_species": sum(len(p.species) for p in self.meta_agent.populations.values()),
                "total_emergent_patterns": len(self.emergence_detector.detected_patterns)
            },
            "best_solution": {
                "fitness": self.global_best.average_fitness if self.global_best else 0,
                "genome": self.global_best.genome.get_phenotype() if self.global_best else None,
                "genome_id": self.global_best.genome.genome_id if self.global_best else None
            },
            "emergence_report": self.emergence_detector.get_emergence_report(),
            "specialization_report": self.specialization_tracker.get_specialization_report(),
            "recursive_improvement_report": self.self_modification.get_recursive_improvement_report(),
            "evolution_history": self.system_history[-20:],  # Last 20 generations
            "meta_strategy_history": [
                {
                    "generation": i * 10,
                    "strategy": self.meta_agent.current_strategy.value if self.meta_agent else "unknown"
                }
                for i in range(len(self.system_history) // 10)
            ]
        }


# Convenience function for running the system
async def run_unconstrained_evolution(
    problem_definition: Dict[str, Any],
    config: SystemConfiguration = None,
    progress_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Run the unconstrained multi-agent evolution system.
    
    Example:
        results = await run_unconstrained_evolution({
            "problem_type": "financial_analysis",
            "objectives": ["maximize_npv", "minimize_risk"],
            "constraints": ["liquidity", "regulatory"]
        })
    """
    system = UnconstrainedEvolutionSystem(config)
    return await system.evolve(problem_definition, progress_callback)
