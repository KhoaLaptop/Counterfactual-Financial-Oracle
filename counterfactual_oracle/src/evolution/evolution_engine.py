"""
⚡ EVOLUTION ENGINE

The core engine that drives multi-agent evolution. Handles fitness evaluation,
generation advancement, and adaptive strategies.
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from datetime import datetime

from .genome import AgentGenome
from .population import AgentPopulation, AgentInstance, PopulationConfig
from ..infrastructure.logging import get_logger
from ..infrastructure.telemetry import tracer

logger = get_logger(__name__)


class EvolutionPhase(Enum):
    """Phases of the evolutionary process."""
    EXPLORATION = "exploration"      # High diversity, low selection pressure
    EXPLOITATION = "exploitation"    # Low diversity, high selection pressure  
    ADAPTATION = "adaptation"        # Responding to environmental changes
    STASIS = "stasis"               # Converged, minimal changes
    SPECIATION = "speciation"       # Formation of new species


@dataclass
class FitnessLandscape:
    """Represents the problem space agents are evolving to solve."""
    
    # Fitness function(s)
    primary_fitness_fn: Callable[[AgentInstance], float]
    secondary_fitness_fns: List[Callable[[AgentInstance], float]] = field(default_factory=list)
    
    # Landscape characteristics
    multimodal: bool = True          # Multiple local optima?
    dynamic: bool = False            # Changes over time?
    noisy: bool = True               # Stochastic fitness evaluations?
    
    # Environmental conditions that affect evolution
    current_conditions: Dict[str, Any] = field(default_factory=dict)
    
    def evaluate(self, agent: AgentInstance) -> Dict[str, float]:
        """
        Comprehensive fitness evaluation.
        Returns multiple fitness dimensions.
        """
        with tracer.start_as_current_span("fitness_evaluation"):
            # Primary fitness
            primary = self.primary_fitness_fn(agent)
            
            # Secondary objectives
            secondary = {
                f"objective_{i}": fn(agent)
                for i, fn in enumerate(self.secondary_fitness_fns)
            }
            
            # Add noise if landscape is noisy
            if self.noisy:
                primary += np.random.normal(0, 0.05)
            
            return {
                "primary": primary,
                **secondary,
                "combined": self._combine_fitnesses(primary, secondary)
            }
    
    def _combine_fitnesses(self, primary: float, secondary: Dict) -> float:
        """Combine multiple fitness dimensions into single score."""
        # Pareto frontier approach: prefer agents good at multiple things
        secondary_avg = np.mean(list(secondary.values())) if secondary else 0.5
        
        # Weighted combination with primary dominance
        return 0.7 * primary + 0.3 * secondary_avg
    
    def update_conditions(self, new_conditions: Dict[str, Any]) -> None:
        """Update environmental conditions (for dynamic landscapes)."""
        self.current_conditions.update(new_conditions)
        self.dynamic = True


@dataclass
class EvolutionState:
    """Current state of the evolutionary process."""
    generation: int = 0
    phase: EvolutionPhase = EvolutionPhase.EXPLORATION
    best_fitness_ever: float = 0.0
    best_genome_ever: Optional[AgentGenome] = None
    stagnation_counter: int = 0
    improvement_rate: float = 0.0
    diversity_history: List[float] = field(default_factory=list)
    innovation_events: List[Dict] = field(default_factory=list)


class EvolutionEngine:
    """
    Drives the evolutionary process with adaptive strategies.
    
    Features:
    - Adaptive mutation rates based on progress
    - Phase transitions (exploration → exploitation)
    - Environmental adaptation
    - Innovation tracking
    - Convergence detection with restart capability
    """
    
    def __init__(
        self,
        population_config: PopulationConfig = None,
        fitness_landscape: FitnessLandscape = None
    ):
        self.population = AgentPopulation(population_config)
        self.fitness_landscape = fitness_landscape
        self.state = EvolutionState()
        
        # Adaptive parameters
        self.adaptive_mutation = True
        self.adaptive_selection = True
        self.restart_on_convergence = True
        
        # Callbacks for monitoring
        self.generation_callbacks: List[Callable] = []
        self.innovation_callbacks: List[Callable] = []
    
    async def evolve(
        self,
        max_generations: int = 100,
        target_fitness: float = 0.95,
        async_eval: bool = True
    ) -> EvolutionState:
        """
        Run evolution until convergence or max generations.
        
        Args:
            max_generations: Maximum generations to run
            target_fitness: Stop when best agent reaches this fitness
            async_eval: Evaluate agents asynchronously
            
        Returns:
            Final evolution state
        """
        logger.info(
            "evolution_started",
            max_generations=max_generations,
            target_fitness=target_fitness
        )
        
        for generation in range(max_generations):
            self.state.generation = generation
            
            # Evaluate population
            if async_eval:
                await self._evaluate_population_async()
            else:
                self._evaluate_population_sync()
            
            # Update state
            self._update_evolution_state()
            
            # Check termination conditions
            if self._should_terminate(target_fitness):
                break
            
            # Adaptive parameter adjustment
            if self.adaptive_mutation:
                self._adapt_parameters()
            
            # Phase management
            self._manage_evolution_phase()
            
            # Advance generation
            stats = self.population.evolve_generation()
            
            # Trigger callbacks
            for callback in self.generation_callbacks:
                callback(generation, stats, self.state)
            
            # Log progress
            if generation % 10 == 0:
                logger.info(
                    "evolution_progress",
                    generation=generation,
                    best_fitness=self.state.best_fitness_ever,
                    phase=self.state.phase.value,
                    diversity=stats.get("diversity_index", 0)
                )
        
        logger.info(
            "evolution_completed",
            final_generation=self.state.generation,
            best_fitness=self.state.best_fitness_ever
        )
        
        return self.state
    
    async def _evaluate_population_async(self) -> None:
        """Evaluate all agents asynchronously."""
        tasks = [
            self._evaluate_agent_async(agent)
            for agent in self.population.agents
        ]
        await asyncio.gather(*tasks)
    
    async def _evaluate_agent_async(self, agent: AgentInstance) -> None:
        """Evaluate single agent asynchronously."""
        fitness_scores = self.fitness_landscape.evaluate(agent)
        agent.evaluate(fitness_scores["combined"])
        
        # Update agent genome with epigenetic adaptations
        agent.genome.adapt_to_environment(
            self.fitness_landscape.current_conditions
        )
    
    def _evaluate_population_sync(self) -> None:
        """Evaluate all agents synchronously."""
        for agent in self.population.agents:
            fitness_scores = self.fitness_landscape.evaluate(agent)
            agent.evaluate(fitness_scores["combined"])
    
    def _update_evolution_state(self) -> None:
        """Update evolution state based on current population."""
        best_current = self.population.get_best_agent()
        best_fitness = best_current.average_fitness
        
        # Track best ever
        if best_fitness > self.state.best_fitness_ever:
            improvement = best_fitness - self.state.best_fitness_ever
            self.state.best_fitness_ever = best_fitness
            self.state.best_genome_ever = best_current.genome
            self.state.stagnation_counter = 0
            self.state.improvement_rate = improvement
            
            # Record innovation
            self._record_innovation(best_current, improvement)
        else:
            self.state.stagnation_counter += 1
            self.state.improvement_rate *= 0.9  # Decay
        
        # Track diversity
        current_diversity = self._calculate_population_diversity()
        self.state.diversity_history.append(current_diversity)
    
    def _record_innovation(self, agent: AgentInstance, improvement: float) -> None:
        """Record a significant improvement (innovation event)."""
        innovation = {
            "generation": self.state.generation,
            "fitness": agent.average_fitness,
            "improvement": improvement,
            "genome_id": agent.genome.genome_id,
            "phenotype": agent.genome.get_phenotype(),
            "timestamp": datetime.now().isoformat()
        }
        
        self.state.innovation_events.append(innovation)
        
        # Trigger callbacks
        for callback in self.innovation_callbacks:
            callback(innovation)
        
        logger.info(
            "innovation_detected",
            generation=self.state.generation,
            fitness=agent.average_fitness,
            genome_id=agent.genome.genome_id
        )
    
    def _should_terminate(self, target_fitness: float) -> bool:
        """Check if evolution should stop."""
        # Target reached
        if self.state.best_fitness_ever >= target_fitness:
            logger.info("target_fitness_reached")
            return True
        
        # Stagnation with restart
        if self.state.stagnation_counter > 50:
            if self.restart_on_convergence:
                logger.info("restarting_after_stagnation")
                self._restart_with_diversity_injection()
                return False
            else:
                logger.info("stagnation_detected")
                return True
        
        # Convergence
        if self.population.has_converged() and self.state.generation > 20:
            logger.info("population_converged")
            return True
        
        return False
    
    def _adapt_parameters(self) -> None:
        """Adaptively adjust evolutionary parameters."""
        config = self.population.config
        
        # Adjust mutation rate based on stagnation
        if self.state.stagnation_counter > 10:
            # Increase mutation to escape local optima
            config.mutation_rate = min(0.5, config.mutation_rate * 1.1)
        elif self.state.improvement_rate > 0.1:
            # Decrease mutation when making progress
            config.mutation_rate = max(0.05, config.mutation_rate * 0.95)
        
        # Adjust diversity pressure based on population diversity
        if len(self.state.diversity_history) >= 5:
            recent_diversity = np.mean(self.state.diversity_history[-5:])
            if recent_diversity < 0.1:
                # Low diversity - increase pressure to diversify
                config.diversity_pressure = min(0.8, config.diversity_pressure + 0.05)
            elif recent_diversity > 0.5:
                # High diversity - focus on selection
                config.diversity_pressure = max(0.1, config.diversity_pressure - 0.05)
    
    def _manage_evolution_phase(self) -> None:
        """Manage transitions between evolution phases."""
        current = self.state.phase
        generation = self.state.generation
        stagnation = self.state.stagnation_counter
        diversity = self.state.diversity_history[-1] if self.state.diversity_history else 0.5
        
        # Phase transition logic
        if current == EvolutionPhase.EXPLORATION:
            if generation > 20 and diversity < 0.3:
                # Transition to exploitation after initial exploration
                self.state.phase = EvolutionPhase.EXPLOITATION
                logger.info("phase_transition", from_phase="exploration", to_phase="exploitation")
        
        elif current == EvolutionPhase.EXPLOITATION:
            if stagnation > 15:
                # Stagnated - need more exploration
                self.state.phase = EvolutionPhase.EXPLORATION
                self._increase_exploration()
                logger.info("phase_transition", from_phase="exploitation", to_phase="exploration")
            elif len(self.population.species) > 3:
                # Multiple species forming
                self.state.phase = EvolutionPhase.SPECIATION
        
        elif current == EvolutionPhase.STASIS:
            if self.fitness_landscape.dynamic:
                self.state.phase = EvolutionPhase.ADAPTATION
        
        # Update config based on phase
        self._apply_phase_config(current)
    
    def _apply_phase_config(self, phase: EvolutionPhase) -> None:
        """Apply configuration appropriate for current phase."""
        config = self.population.config
        
        if phase == EvolutionPhase.EXPLORATION:
            config.mutation_rate = 0.25
            config.crossover_rate = 0.5
            config.diversity_pressure = 0.5
            config.selection_pressure = 1.2
        
        elif phase == EvolutionPhase.EXPLOITATION:
            config.mutation_rate = 0.1
            config.crossover_rate = 0.7
            config.diversity_pressure = 0.2
            config.selection_pressure = 2.0
        
        elif phase == EvolutionPhase.SPECIATION:
            config.diversity_pressure = 0.6  # Maintain species separation
    
    def _increase_exploration(self) -> None:
        """Inject diversity to escape local optima."""
        # Introduce immigrants
        immigrant_count = int(self.population.config.population_size * 0.2)
        self.population.introduce_immigrants(immigrant_count)
        
        # Temporarily increase mutation
        self.population.config.mutation_rate = 0.4
        
        logger.info("exploration_boost", immigrants=immigrant_count)
    
    def _restart_with_diversity_injection(self) -> None:
        """Restart evolution while preserving best individual."""
        # Keep elite
        best = self.population.get_best_agent()
        
        # Reset population but keep best
        self.population._initialize_population()
        self.population.agents[0] = best
        
        # Boost diversity
        self._increase_exploration()
        
        self.state.stagnation_counter = 0
    
    def _calculate_population_diversity(self) -> float:
        """Calculate current population diversity."""
        return self.population._calculate_diversity_index()
    
    def get_evolution_report(self) -> Dict[str, Any]:
        """Generate comprehensive evolution report."""
        return {
            "state": {
                "generation": self.state.generation,
                "phase": self.state.phase.value,
                "best_fitness": self.state.best_fitness_ever,
                "stagnation": self.state.stagnation_counter
            },
            "population": {
                "size": len(self.population.agents),
                "species_count": len(self.population.species),
                "diversity": self.state.diversity_history[-1] if self.state.diversity_history else 0
            },
            "innovations": len(self.state.innovation_events),
            "best_genome": self.state.best_genome_ever.get_phenotype() if self.state.best_genome_ever else None,
            "species": self.population.get_species_stats()
        }
