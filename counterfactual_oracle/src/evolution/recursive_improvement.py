"""
🔄 RECURSIVE SELF-IMPROVEMENT LOOP

Implements recursive self-improvement where the evolutionary system
improves its own mechanisms for evolution.

This is the highest level of the system - it evolves:
- The mutation operators themselves
- The selection algorithms
- The fitness evaluation methods
- The emergence detection algorithms
"""

from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
import numpy as np
from datetime import datetime

from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MechanismPerformance:
    """Performance metrics for an evolutionary mechanism."""
    mechanism_name: str
    success_rate: float
    avg_improvement: float
    computational_cost: float
    diversity_maintenance: float
    convergence_speed: float
    
    def overall_score(self) -> float:
        """Calculate overall effectiveness score."""
        return (
            0.3 * self.success_rate +
            0.25 * self.avg_improvement +
            0.15 * (1.0 - self.computational_cost) +  # Lower cost is better
            0.15 * self.diversity_maintenance +
            0.15 * self.convergence_speed
        )


@dataclass
class EvolutionaryMechanism:
    """A configurable component of the evolutionary process."""
    name: str
    mechanism_type: str  # "mutation", "selection", "crossover", "evaluation"
    implementation: Callable
    parameters: Dict[str, Any]
    performance_history: List[MechanismPerformance] = field(default_factory=list)
    
    def adapt_parameters(self, feedback: Dict[str, float]) -> None:
        """Adjust parameters based on performance feedback."""
        if self.mechanism_type == "mutation":
            # If too many bad mutations, decrease rate
            if feedback.get("improvement_rate", 0) < 0.1:
                self.parameters["rate"] *= 0.9
            # If stuck in local optima, increase rate
            elif feedback.get("stagnation", 0) > 10:
                self.parameters["rate"] = min(0.5, self.parameters["rate"] * 1.1)
        
        elif self.mechanism_type == "selection":
            # Adjust selection pressure
            if feedback.get("diversity", 1.0) < 0.2:
                self.parameters["pressure"] *= 0.9  # Reduce pressure to maintain diversity
            elif feedback.get("convergence_speed", 0) < 0.1:
                self.parameters["pressure"] = min(3.0, self.parameters["pressure"] * 1.1)
    
    def record_performance(self, performance: MechanismPerformance) -> None:
        """Record performance metrics."""
        self.performance_history.append(performance)
        
        # Keep only last 20
        if len(self.performance_history) > 20:
            self.performance_history = self.performance_history[-20:]
    
    def get_average_performance(self) -> Optional[MechanismPerformance]:
        """Get average performance over history."""
        if not self.performance_history:
            return None
        
        return MechanismPerformance(
            mechanism_name=self.name,
            success_rate=np.mean([p.success_rate for p in self.performance_history]),
            avg_improvement=np.mean([p.avg_improvement for p in self.performance_history]),
            computational_cost=np.mean([p.computational_cost for p in self.performance_history]),
            diversity_maintenance=np.mean([p.diversity_maintenance for p in self.performance_history]),
            convergence_speed=np.mean([p.convergence_speed for p in self.performance_history])
        )


class SelfModificationLoop:
    """
    Recursive self-improvement system.
    
    The system maintains a population of evolutionary mechanisms
    and evolves them to become better at evolving.
    
    This creates a meta-evolutionary loop where:
    1. Level 1: Agents evolve to solve problems
    2. Level 2: Evolution mechanisms evolve to evolve agents better
    3. Level 3: The self-modification loop itself improves
    """
    
    def __init__(self):
        self.mechanisms: Dict[str, EvolutionaryMechanism] = {}
        self.mechanism_variants: Dict[str, List[EvolutionaryMechanism]] = defaultdict(list)
        self.improvement_cycles: int = 0
        self.meta_fitness_history: List[float] = []
        
        self._initialize_mechanisms()
    
    def _initialize_mechanisms(self) -> None:
        """Initialize base evolutionary mechanisms."""
        # Mutation mechanisms
        self.mechanisms["gaussian_mutation"] = EvolutionaryMechanism(
            name="gaussian_mutation",
            mechanism_type="mutation",
            implementation=self._gaussian_mutation,
            parameters={"rate": 0.1, "sigma": 0.1}
        )
        
        self.mechanisms["adaptive_mutation"] = EvolutionaryMechanism(
            name="adaptive_mutation",
            mechanism_type="mutation",
            implementation=self._adaptive_mutation,
            parameters={"base_rate": 0.1, "adaptation_factor": 1.5}
        )
        
        # Selection mechanisms
        self.mechanisms["tournament_selection"] = EvolutionaryMechanism(
            name="tournament_selection",
            mechanism_type="selection",
            implementation=self._tournament_selection,
            parameters={"tournament_size": 3, "pressure": 1.5}
        )
        
        self.mechanisms["diversity_aware_selection"] = EvolutionaryMechanism(
            name="diversity_aware_selection",
            mechanism_type="selection",
            implementation=self._diversity_aware_selection,
            parameters={"diversity_weight": 0.3, "pressure": 1.5}
        )
        
        # Crossover mechanisms
        self.mechanisms["uniform_crossover"] = EvolutionaryMechanism(
            name="uniform_crossover",
            mechanism_type="crossover",
            implementation=self._uniform_crossover,
            parameters={"mixing_ratio": 0.5}
        )
    
    def run_meta_evolution_cycle(self, base_evolution_results: Dict) -> Dict[str, Any]:
        """
        Run one cycle of self-improvement.
        
        Args:
            base_evolution_results: Results from the base evolutionary process
            
        Returns:
            Improvements made to mechanisms
        """
        self.improvement_cycles += 1
        
        logger.info("meta_evolution_cycle_started", cycle=self.improvement_cycles)
        
        # Evaluate current mechanisms
        mechanism_scores = self._evaluate_mechanisms(base_evolution_results)
        
        # Adapt parameters based on performance
        improvements = self._adapt_mechanisms(mechanism_scores)
        
        # Generate mechanism variants (mutate the mutators)
        self._generate_mechanism_variants()
        
        # Select best mechanism variants
        self._select_best_variants(mechanism_scores)
        
        # Record meta-fitness
        avg_score = np.mean(list(mechanism_scores.values())) if mechanism_scores else 0
        self.meta_fitness_history.append(avg_score)
        
        logger.info(
            "meta_evolution_cycle_completed",
            cycle=self.improvement_cycles,
            avg_mechanism_score=avg_score,
            improvements=len(improvements)
        )
        
        return {
            "cycle": self.improvement_cycles,
            "mechanism_scores": mechanism_scores,
            "improvements": improvements,
            "meta_fitness_trend": self._calculate_meta_fitness_trend()
        }
    
    def _evaluate_mechanisms(
        self,
        evolution_results: Dict
    ) -> Dict[str, float]:
        """
        Evaluate how well each mechanism performed.
        
        Uses evolution results to infer mechanism effectiveness.
        """
        scores = {}
        
        for name, mechanism in self.mechanisms.items():
            # Create performance metrics
            perf = MechanismPerformance(
                mechanism_name=name,
                success_rate=evolution_results.get("success_rate", 0.5),
                avg_improvement=evolution_results.get("avg_improvement", 0),
                computational_cost=evolution_results.get("cost", 0.5),
                diversity_maintenance=evolution_results.get("final_diversity", 0.5),
                convergence_speed=1.0 / max(1, evolution_results.get("generations", 50))
            )
            
            mechanism.record_performance(perf)
            scores[name] = perf.overall_score()
        
        return scores
    
    def _adapt_mechanisms(
        self,
        scores: Dict[str, float]
    ) -> List[str]:
        """Adapt mechanism parameters based on scores."""
        improvements = []
        
        for name, mechanism in self.mechanisms.items():
            if name not in scores:
                continue
            
            score = scores[name]
            
            # Generate feedback
            feedback = {
                "improvement_rate": score,
                "stagnation": 0,  # Would need historical data
                "diversity": 0.5,
                "convergence_speed": score
            }
            
            old_params = mechanism.parameters.copy()
            mechanism.adapt_parameters(feedback)
            
            if mechanism.parameters != old_params:
                improvements.append(f"{name}: {old_params} -> {mechanism.parameters}")
        
        return improvements
    
    def _generate_mechanism_variants(self) -> None:
        """
        Create variants of mechanisms (mutate the mutators).
        
        This is the core of recursive improvement - the mechanisms
themselves evolve.
        """
        for name, mechanism in list(self.mechanisms.items()):
            # Create 2 variants with parameter mutations
            for i in range(2):
                variant_name = f"{name}_variant_{i}"
                variant_params = self._mutate_parameters(mechanism.parameters)
                
                variant = EvolutionaryMechanism(
                    name=variant_name,
                    mechanism_type=mechanism.mechanism_type,
                    implementation=mechanism.implementation,
                    parameters=variant_params
                )
                
                self.mechanism_variants[name].append(variant)
    
    def _mutate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create mutated copy of parameters."""
        mutated = params.copy()
        
        for key, value in mutated.items():
            if isinstance(value, float):
                # Gaussian mutation
                mutated[key] = max(0.01, value + np.random.normal(0, value * 0.2))
            elif isinstance(value, int):
                # Small integer perturbation
                mutated[key] = max(1, value + np.random.randint(-1, 2))
        
        return mutated
    
    def _select_best_variants(self, scores: Dict[str, float]) -> None:
        """Select best mechanism variants to promote."""
        for base_name, variants in self.mechanism_variants.items():
            if not variants:
                continue
            
            # Score variants (use same score as base for simplicity)
            base_score = scores.get(base_name, 0.5)
            
            # Find best variant
            best_variant = max(variants, key=lambda v: 
                np.mean([p.overall_score() for p in v.performance_history]) if v.performance_history else base_score
            )
            
            # If variant is better, promote it
            variant_score = np.mean([p.overall_score() for p in best_variant.performance_history]) if best_variant.performance_history else 0
            
            if variant_score > base_score * 1.1:  # 10% improvement threshold
                logger.info(
                    "promoting_mechanism_variant",
                    base=base_name,
                    variant=best_variant.name,
                    improvement=variant_score - base_score
                )
                
                # Promote variant to main mechanism
                self.mechanisms[base_name] = EvolutionaryMechanism(
                    name=base_name,
                    mechanism_type=best_variant.mechanism_type,
                    implementation=best_variant.implementation,
                    parameters=best_variant.parameters,
                    performance_history=best_variant.performance_history
                )
        
        # Clear variants for next cycle
        self.mechanism_variants.clear()
    
    def _calculate_meta_fitness_trend(self) -> str:
        """Calculate trend in meta-evolution fitness."""
        if len(self.meta_fitness_history) < 5:
            return "insufficient_data"
        
        recent = np.mean(self.meta_fitness_history[-5:])
        older = np.mean(self.meta_fitness_history[-10:-5]) if len(self.meta_fitness_history) >= 10 else recent
        
        if recent > older * 1.05:
            return "improving"
        elif recent < older * 0.95:
            return "declining"
        else:
            return "stable"
    
    def get_recursive_improvement_report(self) -> Dict[str, Any]:
        """Generate report on recursive self-improvement."""
        return {
            "improvement_cycles": self.improvement_cycles,
            "mechanism_count": len(self.mechanisms),
            "meta_fitness_trend": self._calculate_meta_fitness_trend(),
            "mechanism_performance": {
                name: {
                    "current_params": mech.parameters,
                    "avg_score": mech.get_average_performance().overall_score() if mech.get_average_performance() else None,
                    "adaptations": len(mech.performance_history)
                }
                for name, mech in self.mechanisms.items()
            },
            "improvement_rate": self._calculate_improvement_rate()
        }
    
    def _calculate_improvement_rate(self) -> float:
        """Calculate rate of improvement over cycles."""
        if len(self.meta_fitness_history) < 2:
            return 0.0
        
        # Linear regression slope
        x = np.arange(len(self.meta_fitness_history))
        y = np.array(self.meta_fitness_history)
        
        slope = np.polyfit(x, y, 1)[0]
        return slope
    
    # Mechanism implementations
    def _gaussian_mutation(self, value: float, params: Dict) -> float:
        """Standard Gaussian mutation."""
        rate = params.get("rate", 0.1)
        sigma = params.get("sigma", 0.1)
        
        if np.random.random() < rate:
            return value + np.random.normal(0, sigma)
        return value
    
    def _adaptive_mutation(self, value: float, params: Dict) -> float:
        """Mutation with adaptive rate based on progress."""
        base_rate = params.get("base_rate", 0.1)
        # Would need access to recent fitness to truly adapt
        return self._gaussian_mutation(value, {"rate": base_rate, "sigma": 0.1})
    
    def _tournament_selection(self, population: List, params: Dict) -> Any:
        """Tournament selection."""
        size = params.get("tournament_size", 3)
        # Implementation would go here
        return np.random.choice(population) if population else None
    
    def _diversity_aware_selection(self, population: List, params: Dict) -> Any:
        """Selection considering diversity."""
        # Implementation would consider both fitness and diversity
        return self._tournament_selection(population, params)
    
    def _uniform_crossover(self, parent1: Dict, parent2: Dict, params: Dict) -> Dict:
        """Uniform crossover between two parents."""
        ratio = params.get("mixing_ratio", 0.5)
        child = {}
        
        for key in parent1:
            if np.random.random() < ratio:
                child[key] = parent1[key]
            else:
                child[key] = parent2.get(key, parent1[key])
        
        return child
