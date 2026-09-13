"""
🌍 AGENT POPULATION DYNAMICS

Manages populations of agents with genetic diversity, natural selection,
and ecological niches. Implements various selection algorithms.
"""

import random
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass, field
import numpy as np
from collections import defaultdict

from .genome import AgentGenome


@dataclass
class PopulationConfig:
    """Configuration for population dynamics."""
    population_size: int = 50
    elite_ratio: float = 0.1          # Top % that always survives
    mutation_rate: float = 0.2
    crossover_rate: float = 0.6
    diversity_pressure: float = 0.3    # Preference for genetic diversity
    selection_pressure: float = 1.5    # How strongly fitness affects selection
    max_generations: int = 100
    convergence_threshold: float = 0.95


@dataclass
class AgentInstance:
    """An agent with a genome and runtime state."""
    genome: AgentGenome
    agent_id: str
    age: int = 0
    total_fitness: float = 0.0
    evaluations: int = 0
    niche: Optional[str] = None
    
    @property
    def average_fitness(self) -> float:
        return self.total_fitness / max(1, self.evaluations)
    
    def evaluate(self, fitness: float) -> None:
        """Record a fitness evaluation."""
        self.total_fitness += fitness
        self.evaluations += 1
        self.genome.record_fitness(fitness)


class AgentPopulation:
    """
    Manages a population of evolving agents.
    
    Implements:
    - Natural selection based on fitness
    - Sexual and asexual reproduction
    - Speciation (niche specialization)
    - Population dynamics (carrying capacity, competition)
    """
    
    def __init__(self, config: PopulationConfig = None):
        self.config = config or PopulationConfig()
        self.agents: List[AgentInstance] = []
        self.generation = 0
        self.history: List[Dict] = []
        
        # Track speciation
        self.species: Dict[str, List[AgentInstance]] = defaultdict(list)
        self.species_threshold = 0.3  # Genetic distance for new species
        
        # Selection algorithm (can be swapped)
        self.selection_strategy: Callable = self._tournament_selection
        
        self._initialize_population()
    
    def _initialize_population(self) -> None:
        """Create initial random population."""
        for i in range(self.config.population_size):
            genome = AgentGenome(generation=0)
            # Slight randomization of initial personalities
            for trait in genome.personality_gene.traits:
                genome.personality_gene.traits[trait] = random.uniform(0.3, 0.7)
            
            agent = AgentInstance(
                genome=genome,
                agent_id=f"gen0_{i}"
            )
            self.agents.append(agent)
        
        self._classify_species()
    
    def evolve_generation(self) -> Dict[str, Any]:
        """
        Evolve the population one generation.
        
        1. Evaluate fitness (must be done before calling)
        2. Select parents
        3. Reproduce (crossover + mutation)
        4. Replace least fit
        5. Update species
        """
        self.generation += 1
        
        # Sort by fitness
        sorted_agents = sorted(
            self.agents,
            key=lambda a: a.average_fitness,
            reverse=True
        )
        
        # Keep elite
        elite_count = int(self.config.population_size * self.config.elite_ratio)
        new_population = sorted_agents[:elite_count]
        
        # Fill rest with offspring
        offspring_needed = self.config.population_size - elite_count
        offspring = self._generate_offspring(offspring_needed, sorted_agents)
        
        new_population.extend(offspring)
        
        # Age surviving agents
        for agent in new_population[:elite_count]:
            agent.age += 1
        
        self.agents = new_population
        
        # Update species classification
        self._classify_species()
        
        # Record statistics
        stats = self._record_generation_stats()
        
        return stats
    
    def _generate_offspring(
        self,
        count: int,
        sorted_agents: List[AgentInstance]
    ) -> List[AgentInstance]:
        """Generate new agents through reproduction."""
        offspring = []
        
        for i in range(count):
            # Select parents
            parent1 = self.selection_strategy(sorted_agents)
            
            if random.random() < self.config.crossover_rate:
                # Sexual reproduction
                parent2 = self.selection_strategy(sorted_agents)
                # Ensure different parents for diversity
                while parent2 == parent1 and len(sorted_agents) > 1:
                    parent2 = self.selection_strategy(sorted_agents)
                
                child_genome = parent1.genome.crossover(parent2.genome)
            else:
                # Asexual reproduction (cloning with mutation)
                child_genome = parent1.genome.mutate(
                    self.config.mutation_rate
                )
            
            # Create child agent
            child = AgentInstance(
                genome=child_genome,
                agent_id=f"gen{self.generation}_{i}",
                age=0
            )
            
            offspring.append(child)
        
        return offspring
    
    def _tournament_selection(
        self,
        candidates: List[AgentInstance],
        tournament_size: int = 3
    ) -> AgentInstance:
        """
        Tournament selection: pick best from random subset.
        Balances exploration and exploitation.
        """
        tournament = random.sample(
            candidates,
            min(tournament_size, len(candidates))
        )
        return max(tournament, key=lambda a: a.average_fitness)
    
    def _fitness_proportionate_selection(
        self,
        candidates: List[AgentInstance]
    ) -> AgentInstance:
        """
        Roulette wheel selection: probability proportional to fitness.
        Strong selection pressure.
        """
        fitnesses = [a.average_fitness ** self.config.selection_pressure 
                     for a in candidates]
        total_fitness = sum(fitnesses)
        
        if total_fitness == 0:
            return random.choice(candidates)
        
        pick = random.uniform(0, total_fitness)
        current = 0
        
        for agent, fitness in zip(candidates, fitnesses):
            current += fitness
            if current >= pick:
                return agent
        
        return candidates[-1]
    
    def _diversity_aware_selection(
        self,
        candidates: List[AgentInstance]
    ) -> AgentInstance:
        """
        Select agent that balances fitness AND genetic diversity.
        Prevents premature convergence.
        """
        # Base fitness
        fitnesses = np.array([a.average_fitness for a in candidates])
        
        # Calculate diversity contribution
        diversity_scores = []
        for i, agent in enumerate(candidates):
            # Average distance to other candidates
            distances = [
                agent.genome.calculate_diversity(other.genome)
                for j, other in enumerate(candidates) if i != j
            ]
            diversity_scores.append(np.mean(distances) if distances else 0)
        
        # Combined score: fitness + diversity bonus
        combined = (
            fitnesses * (1 - self.config.diversity_pressure) +
            np.array(diversity_scores) * self.config.diversity_pressure
        )
        
        # Select proportional to combined score
        total = combined.sum()
        if total == 0:
            return random.choice(candidates)
        
        probs = combined / total
        return np.random.choice(candidates, p=probs)
    
    def _classify_species(self) -> None:
        """Group agents into species based on genetic similarity."""
        self.species.clear()
        
        for agent in self.agents:
            assigned = False
            
            # Try to assign to existing species
            for species_name, members in self.species.items():
                if members:
                    # Compare to species representative (first member)
                    distance = agent.genome.calculate_diversity(members[0].genome)
                    if distance < self.species_threshold:
                        members.append(agent)
                        agent.niche = species_name
                        assigned = True
                        break
            
            if not assigned:
                # Create new species
                new_species = f"species_{len(self.species)}"
                self.species[new_species].append(agent)
                agent.niche = new_species
    
    def get_species_stats(self) -> Dict[str, Dict]:
        """Get statistics for each species."""
        stats = {}
        for species_name, members in self.species.items():
            if members:
                avg_fitness = np.mean([m.average_fitness for m in members])
                dominant_strategy = self._get_dominant_strategy(members)
                
                stats[species_name] = {
                    "population": len(members),
                    "average_fitness": avg_fitness,
                    "dominant_strategy": dominant_strategy,
                    "avg_age": np.mean([m.age for m in members])
                }
        return stats
    
    def _get_dominant_strategy(self, members: List[AgentInstance]) -> str:
        """Find most common strategy in a species."""
        strategies = defaultdict(int)
        for m in members:
            strategies[m.genome.strategy_gene.value] += 1
        return max(strategies.items(), key=lambda x: x[1])[0]
    
    def _record_generation_stats(self) -> Dict[str, Any]:
        """Record statistics for this generation."""
        fitnesses = [a.average_fitness for a in self.agents]
        
        stats = {
            "generation": self.generation,
            "population_size": len(self.agents),
            "num_species": len(self.species),
            "best_fitness": max(fitnesses),
            "worst_fitness": min(fitnesses),
            "mean_fitness": np.mean(fitnesses),
            "fitness_std": np.std(fitnesses),
            "species_breakdown": self.get_species_stats(),
            "diversity_index": self._calculate_diversity_index()
        }
        
        self.history.append(stats)
        return stats
    
    def _calculate_diversity_index(self) -> float:
        """Calculate population genetic diversity (0-1)."""
        if len(self.agents) < 2:
            return 0.0
        
        # Sample pairwise distances
        distances = []
        sample_size = min(100, len(self.agents) * (len(self.agents) - 1) // 2)
        
        for _ in range(sample_size):
            a1, a2 = random.sample(self.agents, 2)
            distances.append(a1.genome.calculate_diversity(a2.genome))
        
        return np.mean(distances)
    
    def get_best_agent(self) -> AgentInstance:
        """Return the highest fitness agent."""
        return max(self.agents, key=lambda a: a.average_fitness)
    
    def get_specialists(self, niche: str) -> List[AgentInstance]:
        """Get agents specialized for a particular niche."""
        return [a for a in self.agents if a.niche == niche]
    
    def introduce_immigrants(self, num_immigrants: int) -> None:
        """
        Introduce random immigrants to maintain diversity.
        Prevents local optima stagnation.
        """
        for i in range(num_immigrants):
            genome = AgentGenome(generation=self.generation)
            # More extreme randomization for immigrants
            for trait in genome.personality_gene.traits:
                genome.personality_gene.traits[trait] = random.random()
            
            immigrant = AgentInstance(
                genome=genome,
                agent_id=f"immigrant_gen{self.generation}_{i}",
                age=0
            )
            
            # Replace random low-fitness agent
            sorted_agents = sorted(self.agents, key=lambda a: a.average_fitness)
            replace_idx = random.randint(0, len(sorted_agents) // 3)
            self.agents[sorted_agents[replace_idx]] = immigrant
    
    def has_converged(self) -> bool:
        """Check if population has converged on a solution."""
        if len(self.history) < 5:
            return False
        
        recent = self.history[-5:]
        fitnesses = [r["mean_fitness"] for r in recent]
        
        # Check if fitness has plateaued
        if max(fitnesses) - min(fitnesses) < 0.01:
            return True
        
        # Check if diversity has collapsed
        if recent[-1]["diversity_index"] < 0.05:
            return True
        
        return False
