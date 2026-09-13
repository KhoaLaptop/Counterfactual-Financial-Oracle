"""
🧬 AGENT GENOME SYSTEM

Implements a genetic representation of agent capabilities, strategies, and behaviors.
Agents have genomes that can mutate, crossover, and evolve over generations.
"""

import random
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class GeneType(Enum):
    """Types of genes in the agent genome."""
    STRATEGY = "strategy"           # How the agent approaches problems
    PERSONALITY = "personality"     # Behavioral tendencies
    PROMPT_STYLE = "prompt_style"   # Communication patterns
    REASONING = "reasoning"         # Logic and analysis style
    MEMORY = "memory"               # How agent uses context
    CREATIVITY = "creativity"       # Divergent thinking
    SKEPTICISM = "skepticism"       # Critical analysis tendency
    OPTIMISM = "optimism"           # Positive bias


@dataclass
class Gene:
    """Base class for genes."""
    gene_type: GeneType
    value: Any
    mutation_rate: float = 0.1
    dominance: float = 1.0  # How strongly this gene expresses
    
    def mutate(self, intensity: float = 1.0) -> 'Gene':
        """Create a mutated copy of this gene."""
        if random.random() > self.mutation_rate * intensity:
            return self
        
        # Apply mutation
        new_value = self._mutate_value(intensity)
        return Gene(
            gene_type=self.gene_type,
            value=new_value,
            mutation_rate=self.mutation_rate,
            dominance=self.dominance
        )
    
    def _mutate_value(self, intensity: float) -> Any:
        """Override in subclasses for specific mutation logic."""
        return self.value


@dataclass
class StrategyGene(Gene):
    """Gene controlling debate/financial analysis strategies."""
    
    STRATEGIES = [
        "fundamental_analysis",
        "technical_analysis", 
        "contrarian",
        "momentum",
        "value_investing",
        "growth_focused",
        "risk_parity",
        "macro_economic",
        "micro_structural",
        "behavioral",
        "quantitative",
        "qualitative_deep"
    ]
    
    def __post_init__(self):
        if isinstance(self.value, str) and self.value not in self.STRATEGIES:
            self.value = random.choice(self.STRATEGIES)
    
    def _mutate_value(self, intensity: float) -> str:
        """Strategy can switch or hybridize."""
        if random.random() < 0.3 * intensity:
            # Switch to different strategy
            return random.choice(self.STRATEGIES)
        elif random.random() < 0.2 * intensity:
            # Hybrid strategy
            primary = self.value
            secondary = random.choice([s for s in self.STRATEGIES if s != primary])
            return f"{primary}+{secondary}"
        return self.value


@dataclass
class PromptGene(Gene):
    """Gene controlling prompt engineering style."""
    
    STYLES = {
        "analytical": "Focus on data-driven analysis with clear reasoning chains",
        "intuitive": "Use pattern recognition and holistic understanding",
        "socratic": "Ask probing questions to uncover truth",
        "adversarial": "Challenge assumptions aggressively",
        "collaborative": "Build on other's ideas constructively",
        "first_principles": "Break down to fundamental truths and rebuild",
        "systems_thinking": "Consider interconnectedness and emergent properties",
        "probabilistic": "Think in distributions and confidence intervals",
        "narrative": "Construct compelling stories from data",
        "mathematical": "Express concepts in formal mathematical terms"
    }
    
    def _mutate_value(self, intensity: float) -> str:
        """Prompt style can shift or combine."""
        if random.random() < 0.25 * intensity:
            return random.choice(list(self.STYLES.keys()))
        return self.value
    
    def get_full_prompt(self) -> str:
        """Generate complete prompt from gene."""
        return self.STYLES.get(self.value, self.STYLES["analytical"])


@dataclass
class PersonalityGene(Gene):
    """Gene controlling agent personality traits (0-1 scale)."""
    
    traits: Dict[str, float] = field(default_factory=lambda: {
        "aggression": 0.5,
        "cooperation": 0.5,
        "risk_tolerance": 0.5,
        "detail_orientation": 0.5,
        "big_picture_thinking": 0.5,
        "patience": 0.5,
        "adaptability": 0.5
    })
    
    def _mutate_value(self, intensity: float) -> Dict[str, float]:
        """Mutate personality traits."""
        new_traits = self.traits.copy()
        
        for trait in new_traits:
            if random.random() < 0.3 * intensity:
                # Gaussian mutation around current value
                delta = random.gauss(0, 0.1 * intensity)
                new_traits[trait] = np.clip(new_traits[trait] + delta, 0.0, 1.0)
        
        return new_traits
    
    def get_dominant_trait(self) -> Tuple[str, float]:
        """Get the strongest personality trait."""
        return max(self.traits.items(), key=lambda x: x[1])


@dataclass
class AgentGenome:
    """
    Complete genetic blueprint for an agent.
    
    Contains all genes that determine:
    - How the agent thinks (reasoning)
    - How the agent communicates (prompts)
    - How the agent behaves (personality)
    - What strategies the agent employs
    """
    
    genome_id: str = field(default_factory=lambda: 
        hashlib.md5(str(random.random()).encode()).hexdigest()[:12]
    )
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)
    
    # Core genes
    strategy_gene: StrategyGene = field(default_factory=lambda:
        StrategyGene(GeneType.STRATEGY, random.choice(StrategyGene.STRATEGIES))
    )
    
    prompt_gene: PromptGene = field(default_factory=lambda:
        PromptGene(GeneType.PROMPT_STYLE, "analytical")
    )
    
    personality_gene: PersonalityGene = field(default_factory=lambda:
        PersonalityGene(GeneType.PERSONALITY, {})
    )
    
    # Epigenetic factors (environmental adaptations)
    epigenetic_markers: Dict[str, float] = field(default_factory=dict)
    
    # Fitness history
    fitness_history: List[float] = field(default_factory=list)
    
    def mutate(self, mutation_intensity: float = 1.0) -> 'AgentGenome':
        """Create a mutated copy of this genome."""
        return AgentGenome(
            generation=self.generation + 1,
            parent_ids=[self.genome_id],
            strategy_gene=self.strategy_gene.mutate(mutation_intensity),
            prompt_gene=self.prompt_gene.mutate(mutation_intensity),
            personality_gene=self.personality_gene.mutate(mutation_intensity),
            epigenetic_markers=self.epigenetic_markers.copy()
        )
    
    def crossover(self, other: 'AgentGenome') -> 'AgentGenome':
        """
        Sexual reproduction - combine with another genome.
        Creates novel combinations of traits.
        """
        child = AgentGenome(
            generation=max(self.generation, other.generation) + 1,
            parent_ids=[self.genome_id, other.genome_id]
        )
        
        # Randomly inherit genes from parents
        child.strategy_gene = random.choice([self.strategy_gene, other.strategy_gene])
        child.prompt_gene = random.choice([self.prompt_gene, other.prompt_gene])
        
        # Blend personality traits
        child.personality_gene = PersonalityGene(
            GeneType.PERSONALITY,
            self._blend_traits(
                self.personality_gene.traits,
                other.personality_gene.traits
            )
        )
        
        return child
    
    def _blend_traits(self, traits1: Dict, traits2: Dict) -> Dict:
        """Blend personality traits from two parents."""
        blended = {}
        for key in traits1:
            # Weighted average with some noise
            weight = random.uniform(0.3, 0.7)
            noise = random.gauss(0, 0.05)
            blended[key] = np.clip(
                weight * traits1[key] + (1 - weight) * traits2[key] + noise,
                0.0, 1.0
            )
        return blended
    
    def adapt_to_environment(self, environment: Dict[str, Any]) -> None:
        """
        Epigenetic adaptation - modify gene expression based on environment
        without changing underlying DNA.
        """
        # Adjust strategies based on market conditions
        if environment.get("market_volatility", 0) > 0.7:
            self.epigenetic_markers["stress_response"] = 1.0
            self.epigenetic_markers["risk_aversion"] = 0.8
        
        if environment.get("debaters_converged", False):
            self.epigenetic_markers["consensus_seeking"] = 0.9
        
        if environment.get("fitness_trend", 0) > 0:
            self.epigenetic_markers["reinforce_success"] = 1.0
    
    def calculate_diversity(self, other: 'AgentGenome') -> float:
        """Calculate genetic distance from another genome (0-1)."""
        # Compare strategies
        strategy_diff = 0.0 if self.strategy_gene.value == other.strategy_gene.value else 0.33
        
        # Compare personalities
        personality_diff = np.mean([
            abs(self.personality_gene.traits[t] - other.personality_gene.traits[t])
            for t in self.personality_gene.traits
        ]) * 0.33
        
        # Compare prompts
        prompt_diff = 0.0 if self.prompt_gene.value == other.prompt_gene.value else 0.34
        
        return strategy_diff + personality_diff + prompt_diff
    
    def record_fitness(self, fitness: float) -> None:
        """Record fitness score from evaluation."""
        self.fitness_history.append(fitness)
        
        # Epigenetic adaptation: successful strategies become more dominant
        if len(self.fitness_history) >= 3:
            recent_trend = np.mean(self.fitness_history[-3:])
            if recent_trend > 0.8:
                self.epigenetic_markers["confidence"] = min(
                    1.0, self.epigenetic_markers.get("confidence", 0.5) + 0.1
                )
    
    def get_phenotype(self) -> Dict[str, Any]:
        """
        Express genome as observable characteristics (phenotype).
        This is how the genome manifests as agent behavior.
        """
        return {
            "strategy": self.strategy_gene.value,
            "communication_style": self.prompt_gene.value,
            "dominant_trait": self.personality_gene.get_dominant_trait(),
            "risk_profile": "aggressive" if self.personality_gene.traits["risk_tolerance"] > 0.7 else "conservative",
            "adaptability": self.personality_gene.traits["adaptability"],
            "generation": self.generation,
            "fitness_trend": np.mean(self.fitness_history[-5:]) if self.fitness_history else 0
        }
