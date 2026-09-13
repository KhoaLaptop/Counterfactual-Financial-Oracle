"""
🎭 META-AGENT & EVOLUTION ORCHESTRATOR

The Meta-Agent sits above the evolving population, making strategic decisions
about evolution, resource allocation, and system architecture. It can:
- Spawn new agent species for specific niches
- Allocate compute resources dynamically
- Decide when to evolve vs when to exploit
- Meta-learn about what evolution strategies work best
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import numpy as np

from .genome import AgentGenome, StrategyGene, PromptGene, PersonalityGene, GeneType
from .population import AgentPopulation, AgentInstance, PopulationConfig
from .evolution_engine import EvolutionEngine, EvolutionPhase, FitnessLandscape
from ..infrastructure.logging import get_logger
from ..infrastructure.cache import cache

logger = get_logger(__name__)


class MetaStrategy(Enum):
    """High-level strategies the meta-agent can employ."""
    EXPLORE_NEW_ARCHITECTURES = "explore"      # Try new agent designs
    EXPLOIT_CURRENT_BEST = "exploit"           # Scale up best performers
    DIVERSIFY_NICHES = "diversify"             # Fill ecological niches
    COORDINATE_SPECIALISTS = "coordinate"      # Orchestrate collaboration
    PRUNE_INEFFECTIVE = "prune"                # Remove poor performers
    META_EVOLVE = "meta_evolve"                # Evolve the evolution itself


@dataclass
class ResourceAllocation:
    """Resource budget for evolution."""
    compute_budget: int = 1000          # API calls/generations
    memory_budget: int = 10000          # Cache/storage
    parallel_agents: int = 10           # Concurrent evaluations
    
    def allocate(self, task_priority: float) -> Dict[str, int]:
        """Allocate resources based on task priority."""
        return {
            "compute": int(self.compute_budget * task_priority),
            "memory": int(self.memory_budget * task_priority),
            "parallel": int(self.parallel_agents * task_priority)
        }


@dataclass
class Niche:
    """An ecological niche that agents can specialize in."""
    name: str
    description: str
    required_traits: Dict[str, float]
    current_occupants: List[str] = field(default_factory=list)
    fitness_threshold: float = 0.7
    
    def is_suitable(self, genome: AgentGenome) -> float:
        """Calculate suitability score for this niche (0-1)."""
        matches = []
        for trait, required_level in self.required_traits.items():
            actual_level = genome.personality_gene.traits.get(trait, 0.5)
            # Score based on how close to required level
            match = 1.0 - abs(actual_level - required_level)
            matches.append(match)
        
        return np.mean(matches) if matches else 0.0


@dataclass
class MetaLearningRecord:
    """Record of a meta-learning experiment."""
    timestamp: str
    strategy: MetaStrategy
    parameters: Dict[str, Any]
    outcome: float
    context: Dict[str, Any]


class MetaAgent:
    """
    The Meta-Agent orchestrates the entire evolutionary ecosystem.
    
    Responsibilities:
    1. Monitor population dynamics
    2. Decide when to intervene
    3. Allocate resources
    4. Maintain diversity
    5. Coordinate multi-species interactions
    6. Meta-learn about effective strategies
    """
    
    def __init__(self):
        self.populations: Dict[str, AgentPopulation] = {}
        self.engines: Dict[str, EvolutionEngine] = {}
        self.niches: Dict[str, Niche] = {}
        self.resources = ResourceAllocation()
        
        # Meta-learning
        self.meta_learning_history: List[MetaLearningRecord] = []
        self.strategy_effectiveness: Dict[MetaStrategy, List[float]] = {
            s: [] for s in MetaStrategy
        }
        
        # Active strategies
        self.current_strategy: MetaStrategy = MetaStrategy.EXPLORE_NEW_ARCHITECTURES
        self.strategy_duration: int = 0
        
        # Callbacks for system integration
        self.intervention_callbacks: List[Callable] = []
        
        self._initialize_niches()
    
    def _initialize_niches(self) -> None:
        """Define ecological niches for specialization."""
        self.niches = {
            "bullish_analyst": Niche(
                name="bullish_analyst",
                description="Optimistic financial analyst focusing on growth",
                required_traits={
                    "optimism": 0.8,
                    "risk_tolerance": 0.7,
                    "big_picture_thinking": 0.7
                }
            ),
            "bearish_critic": Niche(
                name="bearish_critic",
                description="Skeptical analyst identifying risks",
                required_traits={
                    "aggression": 0.6,
                    "detail_orientation": 0.8,
                    "risk_tolerance": 0.3
                }
            ),
            "quantitative_modeler": Niche(
                name="quantitative_modeler",
                description="Data-driven analyst using statistical methods",
                required_traits={
                    "detail_orientation": 0.9,
                    "adaptability": 0.5,
                    "patience": 0.7
                }
            ),
            "synthesizer": Niche(
                name="synthesizer",
                description="Agent that combines multiple perspectives",
                required_traits={
                    "cooperation": 0.9,
                    "big_picture_thinking": 0.8,
                    "adaptability": 0.7
                }
            ),
            "contrarian": Niche(
                name="contrarian",
                description="Challenges consensus views",
                required_traits={
                    "aggression": 0.8,
                    "adaptability": 0.6,
                    "cooperation": 0.3
                }
            )
        }
    
    async def orchestrate(
        self,
        problem_space: FitnessLandscape,
        max_meta_iterations: int = 100
    ) -> Dict[str, Any]:
        """
        Main orchestration loop for the evolutionary ecosystem.
        
        Args:
            problem_space: The problem to evolve solutions for
            max_meta_iterations: How many meta-level decisions to make
            
        Returns:
            Final ecosystem state and best solutions
        """
        logger.info(
            "meta_orchestration_started",
            niches=len(self.niches),
            max_iterations=max_meta_iterations
        )
        
        # Initialize primary population
        await self._initialize_population("primary", problem_space)
        
        for iteration in range(max_meta_iterations):
            self.strategy_duration += 1
            
            # Monitor ecosystem
            ecosystem_state = self._assess_ecosystem()
            
            # Decide on strategy
            if self._should_change_strategy(ecosystem_state):
                self._select_new_strategy(ecosystem_state)
            
            # Execute current strategy
            await self._execute_strategy(self.current_strategy, ecosystem_state)
            
            # Meta-learning
            self._update_meta_learning(iteration, ecosystem_state)
            
            # Check convergence
            if self._ecosystem_converged():
                logger.info("ecosystem_converged", iteration=iteration)
                break
            
            if iteration % 10 == 0:
                logger.info(
                    "orchestration_progress",
                    iteration=iteration,
                    strategy=self.current_strategy.value,
                    populations=len(self.populations)
                )
        
        return self._compile_final_report()
    
    async def _initialize_population(
        self,
        name: str,
        problem_space: FitnessLandscape
    ) -> None:
        """Initialize a new evolving population."""
        config = PopulationConfig(
            population_size=50,
            elite_ratio=0.1,
            mutation_rate=0.2,
            diversity_pressure=0.3
        )
        
        engine = EvolutionEngine(config, problem_space)
        
        # Add monitoring callbacks
        engine.generation_callbacks.append(self._on_generation_complete)
        engine.innovation_callbacks.append(self._on_innovation)
        
        self.populations[name] = engine.population
        self.engines[name] = engine
        
        logger.info("population_initialized", name=name)
    
    def _assess_ecosystem(self) -> Dict[str, Any]:
        """Assess the current state of the entire ecosystem."""
        assessment = {
            "populations": {},
            "niche_coverage": {},
            "overall_diversity": 0.0,
            "best_fitness": 0.0,
            "resource_usage": 0.0
        }
        
        total_agents = 0
        all_fitnesses = []
        
        for name, population in self.populations.items():
            stats = population.get_species_stats()
            best = population.get_best_agent()
            
            assessment["populations"][name] = {
                "size": len(population.agents),
                "species": len(population.species),
                "best_fitness": best.average_fitness if best else 0,
                "diversity": population._calculate_diversity_index()
            }
            
            total_agents += len(population.agents)
            all_fitnesses.append(best.average_fitness if best else 0)
        
        # Check niche coverage
        for niche_name, niche in self.niches.items():
            coverage = self._assess_niche_coverage(niche)
            assessment["niche_coverage"][niche_name] = coverage
        
        assessment["overall_diversity"] = np.mean([
            p._calculate_diversity_index() for p in self.populations.values()
        ]) if self.populations else 0
        
        assessment["best_fitness"] = max(all_fitnesses) if all_fitnesses else 0
        
        return assessment
    
    def _assess_niche_coverage(self, niche: Niche) -> float:
        """Calculate how well a niche is covered by current populations."""
        suitable_agents = 0
        
        for population in self.populations.values():
            for agent in population.agents:
                suitability = niche.is_suitable(agent.genome)
                if suitability > 0.7:
                    suitable_agents += 1
        
        # Coverage is 1.0 if we have 3+ suitable agents
        return min(1.0, suitable_agents / 3)
    
    def _should_change_strategy(self, state: Dict) -> bool:
        """Decide if we should switch meta-strategies."""
        # Change strategy if current one isn't working
        if self.strategy_duration > 20:
            recent_effectiveness = np.mean(
                self.strategy_effectiveness[self.current_strategy][-5:]
            ) if self.strategy_effectiveness[self.current_strategy] else 0
            
            if recent_effectiveness < 0.3:
                return True
        
        # Change if ecosystem is unbalanced
        niche_coverage = state.get("niche_coverage", {})
        if any(c < 0.3 for c in niche_coverage.values()):
            return True
        
        return False
    
    def _select_new_strategy(self, state: Dict) -> None:
        """Select the most promising meta-strategy."""
        # Score each strategy based on predicted effectiveness
        scores = {}
        
        for strategy in MetaStrategy:
            base_score = np.mean(
                self.strategy_effectiveness[strategy][-10:]
            ) if self.strategy_effectiveness[strategy] else 0.5
            
            # Adjust based on current state
            if strategy == MetaStrategy.DIVERSIFY_NICHES:
                niche_gaps = sum(1 for c in state.get("niche_coverage", {}).values() if c < 0.5)
                base_score += niche_gaps * 0.1
            
            elif strategy == MetaStrategy.EXPLOIT_CURRENT_BEST:
                if state.get("best_fitness", 0) > 0.8:
                    base_score += 0.2
            
            scores[strategy] = base_score
        
        # Select best strategy (with some exploration)
        if random.random() < 0.1:  # 10% exploration
            self.current_strategy = random.choice(list(MetaStrategy))
        else:
            self.current_strategy = max(scores.items(), key=lambda x: x[1])[0]
        
        self.strategy_duration = 0
        
        logger.info(
            "strategy_changed",
            new_strategy=self.current_strategy.value,
            scores={k.value: round(v, 3) for k, v in scores.items()}
        )
    
    async def _execute_strategy(
        self,
        strategy: MetaStrategy,
        state: Dict
    ) -> None:
        """Execute the selected meta-strategy."""
        if strategy == MetaStrategy.EXPLORE_NEW_ARCHITECTURES:
            await self._explore_new_architectures()
        
        elif strategy == MetaStrategy.EXPLOIT_CURRENT_BEST:
            self._exploit_best_solutions()
        
        elif strategy == MetaStrategy.DIVERSIFY_NICHES:
            await self._diversify_into_niches()
        
        elif strategy == MetaStrategy.COORDINATE_SPECIALISTS:
            await self._coordinate_specialists()
        
        elif strategy == MetaStrategy.PRUNE_INEFFECTIVE:
            self._prune_ineffective_agents()
        
        elif strategy == MetaStrategy.META_EVOLVE:
            await self._evolve_evolution_parameters()
    
    async def _explore_new_architectures(self) -> None:
        """Spawn new populations with novel architectures."""
        # Create variant population with different config
        config = PopulationConfig(
            population_size=30,
            mutation_rate=0.4,  # High mutation for exploration
            diversity_pressure=0.5
        )
        
        # Use same fitness landscape as primary
        if "primary" in self.engines:
            landscape = self.engines["primary"].fitness_landscape
            await self._initialize_population(f"exploratory_{len(self.populations)}", landscape)
    
    def _exploit_best_solutions(self) -> None:
        """Scale up the best performing agents."""
        # Find best agent across all populations
        best_overall = None
        best_fitness = 0
        
        for population in self.populations.values():
            best = population.get_best_agent()
            if best and best.average_fitness > best_fitness:
                best_fitness = best.average_fitness
                best_overall = best
        
        if best_overall:
            # Spawn elite population from best agent
            elite_pop = AgentPopulation(PopulationConfig(
                population_size=20,
                elite_ratio=0.5,
                mutation_rate=0.05  # Low mutation to preserve good solution
            ))
            
            # Seed with variants of best agent
            for i, agent in enumerate(elite_pop.agents):
                if i == 0:
                    agent.genome = best_overall.genome
                else:
                    agent.genome = best_overall.genome.mutate(0.1)
            
            self.populations["elite"] = elite_pop
    
    async def _diversify_into_niches(self) -> None:
        """Ensure all ecological niches are occupied."""
        for niche_name, niche in self.niches.items():
            coverage = self._assess_niche_coverage(niche)
            
            if coverage < 0.5:
                # Need to evolve specialists for this niche
                await self._evolve_specialist(niche)
    
    async def _evolve_specialist(self, niche: Niche) -> None:
        """Evolve an agent specialized for a specific niche."""
        # Create targeted fitness function
        def niche_fitness(agent: AgentInstance) -> float:
            base = agent.average_fitness
            suitability = niche.is_suitable(agent.genome)
            return 0.6 * base + 0.4 * suitability
        
        # Initialize if needed
        pop_name = f"specialist_{niche.name}"
        if pop_name not in self.populations:
            config = PopulationConfig(population_size=20)
            self.populations[pop_name] = AgentPopulation(config)
        
        # Run targeted evolution
        population = self.populations[pop_name]
        
        # Evaluate with niche-aware fitness
        for agent in population.agents:
            fitness = niche_fitness(agent)
            agent.evaluate(fitness)
        
        # Evolve one generation
        population.evolve_generation()
    
    async def _coordinate_specialists(self) -> None:
        """Orchestrate collaboration between different specialists."""
        # Find specialists from different niches
        specialists = []
        
        for niche_name in self.niches:
            pop_name = f"specialist_{niche_name}"
            if pop_name in self.populations:
                best = self.populations[pop_name].get_best_agent()
                if best:
                    specialists.append((niche_name, best))
        
        if len(specialists) >= 2:
            # Create hybrid agents that combine specialist traits
            for i in range(min(5, len(specialists) - 1)):
                parent1 = specialists[i][1]
                parent2 = specialists[i + 1][1]
                
                # Crossover between different specialists
                hybrid_genome = parent1.genome.crossover(parent2.genome)
                
                # Add to hybrid population
                if "hybrids" not in self.populations:
                    self.populations["hybrids"] = AgentPopulation(PopulationConfig(population_size=10))
                
                hybrid_agent = AgentInstance(
                    genome=hybrid_genome,
                    agent_id=f"hybrid_{i}"
                )
                self.populations["hybrids"].agents.append(hybrid_agent)
    
    def _prune_ineffective_agents(self) -> None:
        """Remove low-performing agents to free resources."""
        for name, population in list(self.populations.items()):
            if name == "primary":
                continue  # Don't prune primary
            
            # Remove bottom 20%
            sorted_agents = sorted(
                population.agents,
                key=lambda a: a.average_fitness
            )
            
            cutoff = int(len(sorted_agents) * 0.2)
            population.agents = sorted_agents[cutoff:]
            
            # Remove empty populations
            if len(population.agents) < 5:
                del self.populations[name]
                if name in self.engines:
                    del self.engines[name]
    
    async def _evolve_evolution_parameters(self) -> None:
        """Meta-evolve: evolve the evolution parameters themselves."""
        # Try different parameter configurations
        param_variants = [
            {"mutation": 0.1, "crossover": 0.8, "selection": 2.0},
            {"mutation": 0.3, "crossover": 0.5, "selection": 1.5},
            {"mutation": 0.2, "crossover": 0.6, "selection": 1.8, "diversity": 0.4}
        ]
        
        best_config = None
        best_outcome = 0
        
        for params in param_variants:
            # Test this configuration
            test_pop = AgentPopulation(PopulationConfig(
                population_size=20,
                mutation_rate=params["mutation"],
                crossover_rate=params["crossover"]
            ))
            
            # Quick evolution test
            for _ in range(5):
                test_pop.evolve_generation()
            
            outcome = test_pop.get_best_agent().average_fitness if test_pop.agents else 0
            
            if outcome > best_outcome:
                best_outcome = outcome
                best_config = params
        
        # Apply best config to primary population
        if best_config and "primary" in self.populations:
            config = self.populations["primary"].config
            config.mutation_rate = best_config["mutation"]
            config.crossover_rate = best_config["crossover"]
    
    def _update_meta_learning(self, iteration: int, state: Dict) -> None:
        """Learn from the effectiveness of strategies."""
        # Record outcome of current strategy
        outcome = state.get("best_fitness", 0)
        
        record = MetaLearningRecord(
            timestamp=datetime.now().isoformat(),
            strategy=self.current_strategy,
            parameters={
                "populations": len(self.populations),
                "resources": self.resources.compute_budget
            },
            outcome=outcome,
            context=state
        )
        
        self.meta_learning_history.append(record)
        self.strategy_effectiveness[self.current_strategy].append(outcome)
    
    def _on_generation_complete(self, generation: int, stats: Dict, state: Any) -> None:
        """Callback for generation completion."""
        pass  # Could trigger real-time monitoring
    
    def _on_innovation(self, innovation: Dict) -> None:
        """Callback for innovation detection."""
        logger.info(
            "meta_agent_observed_innovation",
            genome_id=innovation.get("genome_id"),
            fitness=innovation.get("fitness")
        )
    
    def _ecosystem_converged(self) -> bool:
        """Check if entire ecosystem has converged."""
        # All populations converged
        for engine in self.engines.values():
            if not engine.population.has_converged():
                return False
        
        # All niches covered
        for niche in self.niches.values():
            if self._assess_niche_coverage(niche) < 0.8:
                return False
        
        return True
    
    def _compile_final_report(self) -> Dict[str, Any]:
        """Compile comprehensive final report."""
        return {
            "meta_iterations": len(self.meta_learning_history),
            "final_strategy": self.current_strategy.value,
            "populations": {
                name: {
                    "size": len(pop.agents),
                    "species": len(pop.species),
                    "best_fitness": pop.get_best_agent().average_fitness if pop.agents else 0
                }
                for name, pop in self.populations.items()
            },
            "niche_coverage": {
                name: self._assess_niche_coverage(niche)
                for name, niche in self.niches.items()
            },
            "strategy_effectiveness": {
                k.value: np.mean(v) if v else 0
                for k, v in self.strategy_effectiveness.items()
            },
            "best_genomes": [
                {
                    "population": name,
                    "fitness": pop.get_best_agent().average_fitness,
                    "phenotype": pop.get_best_agent().genome.get_phenotype()
                }
                for name, pop in self.populations.items()
                if pop.agents
            ]
        }


class EvolutionOrchestrator:
    """
    High-level orchestrator that coordinates multiple MetaAgents
    for different problem domains or time scales.
    """
    
    def __init__(self):
        self.meta_agents: Dict[str, MetaAgent] = {}
        self.global_fitness_history: List[float] = []
    
    async def run_parallel_evolution(
        self,
        problem_spaces: Dict[str, FitnessLandscape]
    ) -> Dict[str, Any]:
        """
        Run multiple evolutionary processes in parallel.
        
        Args:
            problem_spaces: Dict of problem name -> fitness landscape
            
        Returns:
            Combined results from all evolutionary runs
        """
        # Create MetaAgent for each problem
        tasks = []
        for name, landscape in problem_spaces.items():
            meta_agent = MetaAgent()
            self.meta_agents[name] = meta_agent
            tasks.append(meta_agent.orchestrate(landscape))
        
        # Run all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Compile results
        return {
            name: result if not isinstance(result, Exception) else {"error": str(result)}
            for name, result in zip(problem_spaces.keys(), results)
        }
