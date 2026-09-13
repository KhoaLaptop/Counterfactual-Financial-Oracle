"""
🌟 EMERGENCE DETECTION SYSTEM

Detects and analyzes emergent behaviors, patterns, and capabilities that arise
spontaneously from the multi-agent evolutionary system.

Tracks:
- Novel strategies that weren't explicitly programmed
- Self-organization patterns
- Collective intelligence phenomena
- Unexpected agent collaborations
- Phase transitions in system behavior
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np
from datetime import datetime

from .genome import AgentGenome
from .population import AgentPopulation, AgentInstance
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EmergentPattern:
    """A detected emergent pattern in the system."""
    pattern_id: str
    pattern_type: str
    description: str
    first_observed: str
    agents_involved: Set[str]
    metrics: Dict[str, float]
    stability_score: float  # How consistently it appears (0-1)
    significance_score: float  # Impact on system performance (0-1)
    
    def is_stable(self) -> bool:
        return self.stability_score > 0.7
    
    def is_significant(self) -> bool:
        return self.significance_score > 0.6


@dataclass
class PhaseTransition:
    """Detected phase transition in system behavior."""
    transition_id: str
    from_state: str
    to_state: str
    timestamp: str
    trigger: str
    order_parameter: float  # Value that changed to cause transition
    hysteresis: bool  # Whether transition is reversible


class EmergenceDetector:
    """
    Detects emergent phenomena in the multi-agent system.
    
    Uses multiple detection methods:
    1. Statistical anomaly detection
    2. Network analysis of agent interactions
    3. Complexity metrics (entropy, mutual information)
    4. Behavioral clustering
    """
    
    def __init__(self):
        self.detected_patterns: Dict[str, EmergentPattern] = {}
        self.phase_transitions: List[PhaseTransition] = []
        self.history_buffer: List[Dict] = []
        self.max_history = 1000
        
        # Detection thresholds
        self.novelty_threshold = 0.3
        self.stability_threshold = 0.7
        
        # Pattern tracking
        self.behavioral_clusters: Dict[str, List[str]] = defaultdict(list)
        self.interaction_network: Dict[str, Set[str]] = defaultdict(set)
    
    def analyze_population(
        self,
        population: AgentPopulation,
        generation: int
    ) -> List[EmergentPattern]:
        """
        Analyze a population for emergent patterns.
        
        Returns:
            List of newly detected patterns
        """
        new_patterns = []
        
        # Collect current state
        state = self._capture_state(population, generation)
        self.history_buffer.append(state)
        
        if len(self.history_buffer) > self.max_history:
            self.history_buffer.pop(0)
        
        # Run detection algorithms
        new_patterns.extend(self._detect_self_organization(population))
        new_patterns.extend(self._detect_collective_intelligence(population))
        new_patterns.extend(self._detect_novel_strategies(population))
        new_patterns.extend(self._detect_symbiotic_relationships(population))
        
        # Check for phase transitions
        transition = self._detect_phase_transition()
        if transition:
            self.phase_transitions.append(transition)
        
        # Update pattern stability
        self._update_pattern_stability()
        
        return new_patterns
    
    def _capture_state(
        self,
        population: AgentPopulation,
        generation: int
    ) -> Dict:
        """Capture current system state for analysis."""
        return {
            "generation": generation,
            "timestamp": datetime.now().isoformat(),
            "population_size": len(population.agents),
            "num_species": len(population.species),
            "diversity": population._calculate_diversity_index(),
            "fitness_dist": [a.average_fitness for a in population.agents],
            "strategy_dist": self._get_strategy_distribution(population),
            "species_breakdown": population.get_species_stats()
        }
    
    def _get_strategy_distribution(
        self,
        population: AgentPopulation
    ) -> Dict[str, int]:
        """Get distribution of strategies in population."""
        dist = defaultdict(int)
        for agent in population.agents:
            dist[agent.genome.strategy_gene.value] += 1
        return dict(dist)
    
    def _detect_self_organization(
        self,
        population: AgentPopulation
    ) -> List[EmergentPattern]:
        """
        Detect spontaneous self-organization patterns.
        
        Looks for:
        - Unexpected clustering of similar agents
        - Spatial/temporal organization
        - Hierarchy formation
        """
        patterns = []
        
        # Check for strategy clustering (not random)
        strategy_dist = self._get_strategy_distribution(population)
        total = sum(strategy_dist.values())
        
        if total > 0:
            # Calculate entropy
            probs = [c / total for c in strategy_dist.values()]
            entropy = -sum(p * np.log2(p) for p in probs if p > 0)
            max_entropy = np.log2(len(strategy_dist))
            
            # Low entropy indicates organization (not random)
            if max_entropy > 0 and entropy / max_entropy < 0.5:
                # Find dominant strategy cluster
                dominant_strategy = max(strategy_dist.items(), key=lambda x: x[1])
                
                if dominant_strategy[1] / total > 0.4:  # >40% adoption
                    pattern = EmergentPattern(
                        pattern_id=f"self_org_{datetime.now().timestamp()}",
                        pattern_type="self_organization",
                        description=f"Spontaneous organization around {dominant_strategy[0]} strategy",
                        first_observed=datetime.now().isoformat(),
                        agents_involved={a.agent_id for a in population.agents 
                                        if a.genome.strategy_gene.value == dominant_strategy[0]},
                        metrics={
                            "entropy": entropy,
                            "max_entropy": max_entropy,
                            "dominance": dominant_strategy[1] / total
                        },
                        stability_score=0.5,  # Initial observation
                        significance_score=dominant_strategy[1] / total
                    )
                    
                    patterns.append(pattern)
                    self.detected_patterns[pattern.pattern_id] = pattern
                    
                    logger.info(
                        "self_organization_detected",
                        strategy=dominant_strategy[0],
                        dominance=dominant_strategy[1] / total
                    )
        
        return patterns
    
    def _detect_collective_intelligence(
        self,
        population: AgentPopulation
    ) -> List[EmergentPattern]:
        """
        Detect collective intelligence phenomena.
        
        Looks for:
        - Group performance exceeding individual capabilities
        - Wisdom of crowds effects
        - Distributed problem solving
        """
        patterns = []
        
        if len(population.agents) < 5:
            return patterns
        
        # Check if population fitness > best individual (synergy)
        fitnesses = [a.average_fitness for a in population.agents]
        best_individual = max(fitnesses)
        population_mean = np.mean(fitnesses)
        
        # If mean is close to max, suggests collective convergence on good solution
        if population_mean > best_individual * 0.9 and np.std(fitnesses) < 0.1:
            pattern = EmergentPattern(
                pattern_id=f"coll_intel_{datetime.now().timestamp()}",
                pattern_type="collective_intelligence",
                description="Population converged on high-quality consensus solution",
                first_observed=datetime.now().isoformat(),
                agents_involved={a.agent_id for a in population.agents},
                metrics={
                    "best_individual": best_individual,
                    "population_mean": population_mean,
                    "convergence": 1.0 - (np.std(fitnesses) / max(0.001, population_mean))
                },
                stability_score=0.8,
                significance_score=population_mean
            )
            
            patterns.append(pattern)
            self.detected_patterns[pattern.pattern_id] = pattern
        
        return patterns
    
    def _detect_novel_strategies(
        self,
        population: AgentPopulation
    ) -> List[EmergentPattern]:
        """
        Detect novel strategies not present in initial population.
        
        Tracks emergence of hybrid strategies and novel combinations.
        """
        patterns = []
        
        # Check for hybrid strategies (contain '+')
        hybrid_agents = [
            a for a in population.agents
            if '+' in str(a.genome.strategy_gene.value)
        ]
        
        if len(hybrid_agents) >= 3:  # Significant number
            # Group by hybrid type
            hybrid_types = defaultdict(list)
            for agent in hybrid_agents:
                hybrid_types[agent.genome.strategy_gene.value].append(agent)
            
            # Report each significant hybrid type
            for hybrid_type, agents in hybrid_types.items():
                if len(agents) >= 2:
                    pattern = EmergentPattern(
                        pattern_id=f"novel_strat_{hash(hybrid_type) % 10000}",
                        pattern_type="novel_strategy",
                        description=f"Emergence of hybrid strategy: {hybrid_type}",
                        first_observed=datetime.now().isoformat(),
                        agents_involved={a.agent_id for a in agents},
                        metrics={
                            "adoption_rate": len(agents) / len(population.agents),
                            "avg_fitness": np.mean([a.average_fitness for a in agents])
                        },
                        stability_score=0.4,
                        significance_score=min(1.0, len(agents) / 10)
                    )
                    
                    # Only add if not already tracked
                    if pattern.pattern_id not in self.detected_patterns:
                        patterns.append(pattern)
                        self.detected_patterns[pattern.pattern_id] = pattern
                        
                        logger.info(
                            "novel_strategy_detected",
                            strategy=hybrid_type,
                            adopters=len(agents)
                        )
        
        return patterns
    
    def _detect_symbiotic_relationships(
        self,
        population: AgentPopulation
    ) -> List[EmergentPattern]:
        """
        Detect symbiotic relationships between different agent types.
        
        Looks for:
        - Complementary strategies that improve together
        - Mutualistic interactions
        - Division of labor
        """
        patterns = []
        
        # Need species data
        if not population.species:
            return patterns
        
        # Check for co-evolution between species
        for sp1_name, sp1_members in population.species.items():
            for sp2_name, sp2_members in population.species.items():
                if sp1_name >= sp2_name:
                    continue
                
                if len(sp1_members) >= 3 and len(sp2_members) >= 3:
                    # Check if they have complementary fitness trajectories
                    sp1_fitness = [m.average_fitness for m in sp1_members]
                    sp2_fitness = [m.average_fitness for m in sp2_members]
                    
                    # Both doing well suggests possible symbiosis
                    if np.mean(sp1_fitness) > 0.6 and np.mean(sp2_fitness) > 0.6:
                        pattern = EmergentPattern(
                            pattern_id=f"symbiosis_{sp1_name}_{sp2_name}",
                            pattern_type="symbiotic_relationship",
                            description=f"Cooperative relationship between {sp1_name} and {sp2_name}",
                            first_observed=datetime.now().isoformat(),
                            agents_involved={a.agent_id for a in sp1_members + sp2_members},
                            metrics={
                                "species_1_fitness": np.mean(sp1_fitness),
                                "species_2_fitness": np.mean(sp2_fitness),
                                "combined_population": len(sp1_members) + len(sp2_members)
                            },
                            stability_score=0.6,
                            significance_score=(np.mean(sp1_fitness) + np.mean(sp2_fitness)) / 2
                        )
                        
                        patterns.append(pattern)
                        self.detected_patterns[pattern.pattern_id] = pattern
        
        return patterns
    
    def _detect_phase_transition(self) -> Optional[PhaseTransition]:
        """Detect phase transitions in system behavior."""
        if len(self.history_buffer) < 10:
            return None
        
        # Look for sudden changes in order parameters
        recent = self.history_buffer[-10:]
        older = self.history_buffer[-20:-10]
        
        # Check diversity phase transition
        recent_diversity = np.mean([s["diversity"] for s in recent])
        older_diversity = np.mean([s["diversity"] for s in older])
        
        if abs(recent_diversity - older_diversity) > 0.3:
            # Phase transition detected
            return PhaseTransition(
                transition_id=f"phase_{datetime.now().timestamp()}",
                from_state="high_diversity" if older_diversity > recent_diversity else "low_diversity",
                to_state="low_diversity" if older_diversity > recent_diversity else "high_diversity",
                timestamp=datetime.now().isoformat(),
                trigger="diversity_collapse" if older_diversity > recent_diversity else "diversity_explosion",
                order_parameter=recent_diversity,
                hysteresis=False
            )
        
        return None
    
    def _update_pattern_stability(self) -> None:
        """Update stability scores based on persistence."""
        # Simple heuristic: patterns observed more recently are more stable
        for pattern_id, pattern in self.detected_patterns.items():
            # Increase stability slightly with each observation
            pattern.stability_score = min(1.0, pattern.stability_score + 0.05)
    
    def get_emergence_report(self) -> Dict[str, Any]:
        """Generate comprehensive emergence report."""
        stable_patterns = [p for p in self.detected_patterns.values() if p.is_stable()]
        significant_patterns = [p for p in self.detected_patterns.values() if p.is_significant()]
        
        return {
            "total_patterns_detected": len(self.detected_patterns),
            "stable_patterns": len(stable_patterns),
            "significant_patterns": len(significant_patterns),
            "phase_transitions": len(self.phase_transitions),
            "patterns_by_type": self._count_patterns_by_type(),
            "most_significant": [
                {
                    "id": p.pattern_id,
                    "type": p.pattern_type,
                    "description": p.description,
                    "significance": p.significance_score
                }
                for p in sorted(
                    self.detected_patterns.values(),
                    key=lambda x: x.significance_score,
                    reverse=True
                )[:5]
            ],
            "phase_history": [
                {
                    "from": t.from_state,
                    "to": t.to_state,
                    "trigger": t.trigger,
                    "timestamp": t.timestamp
                }
                for t in self.phase_transitions[-5:]  # Last 5 transitions
            ]
        }
    
    def _count_patterns_by_type(self) -> Dict[str, int]:
        """Count patterns by their type."""
        counts = defaultdict(int)
        for pattern in self.detected_patterns.values():
            counts[pattern.pattern_type] += 1
        return dict(counts)


class SpecializationTracker:
    """
    Tracks how agents specialize into different ecological roles over time.
    
    Monitors:
    - Niche occupation dynamics
    - Division of labor emergence
    - Expertise development
    - Role transitions
    """
    
    def __init__(self):
        self.specialization_history: List[Dict] = []
        self.expertise_tracking: Dict[str, Dict[str, float]] = defaultdict(dict)
    
    def track_specialization(
        self,
        agent: AgentInstance,
        performance_by_task: Dict[str, float]
    ) -> None:
        """
        Track an agent's specialization development.
        
        Args:
            agent: The agent to track
            performance_by_task: Performance metrics for different task types
        """
        agent_id = agent.agent_id
        
        # Update expertise tracking
        for task_type, performance in performance_by_task.items():
            # Exponential moving average
            old_score = self.expertise_tracking[agent_id].get(task_type, 0)
            new_score = 0.7 * old_score + 0.3 * performance
            self.expertise_tracking[agent_id][task_type] = new_score
        
        # Determine primary specialization
        if self.expertise_tracking[agent_id]:
            primary = max(
                self.expertise_tracking[agent_id].items(),
                key=lambda x: x[1]
            )
            
            agent.niche = primary[0]
    
    def get_specialization_report(self) -> Dict[str, Any]:
        """Generate specialization report."""
        # Group agents by specialization
        by_specialization = defaultdict(list)
        for agent_id, expertise in self.expertise_tracking.items():
            if expertise:
                primary = max(expertise.items(), key=lambda x: x[1])
                by_specialization[primary[0]].append({
                    "agent_id": agent_id,
                    "expertise_score": primary[1],
                    "breadth": len(expertise)
                })
        
        return {
            "specialization_distribution": {
                task: len(agents) for task, agents in by_specialization.items()
            },
            "specialist_depth": {
                task: np.mean([a["expertise_score"] for a in agents])
                for task, agents in by_specialization.items()
            },
            "generalists_vs_specialists": self._calculate_generalist_ratio()
        }
    
    def _calculate_generalist_ratio(self) -> float:
        """Calculate ratio of generalists to specialists."""
        generalists = 0
        specialists = 0
        
        for expertise in self.expertise_tracking.values():
            if len(expertise) > 3:  # Good at many things
                generalists += 1
            elif len(expertise) == 1:  # Specialist
                specialists += 1
        
        total = generalists + specialists
        if total == 0:
            return 0.5
        
        return generalists / total
