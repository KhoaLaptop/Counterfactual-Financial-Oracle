"""
🧬 EVOLUTION MODULE - Unconstrained Multi-Agent Evolution Framework

This module implements autonomous agent evolution through:
- Genetic algorithms for prompt/strategy evolution
- Emergent agent specialization
- Self-modifying agent behaviors
- Recursive self-improvement loops
- Fitness-based selection and reproduction
"""

from .genome import AgentGenome, StrategyGene, PromptGene
from .population import AgentPopulation
from .evolution_engine import EvolutionEngine
from .meta_agent import MetaAgent, EvolutionOrchestrator
from .emergence import EmergenceDetector, SpecializationTracker
from .recursive_improvement import SelfModificationLoop

__all__ = [
    'AgentGenome',
    'StrategyGene', 
    'PromptGene',
    'AgentPopulation',
    'EvolutionEngine',
    'MetaAgent',
    'EvolutionOrchestrator',
    'EmergenceDetector',
    'SpecializationTracker',
    'SelfModificationLoop'
]
