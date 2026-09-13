"""
🚀 DEMONSTRATION: Unconstrained Multi-Agent Evolution

This script demonstrates the unconstrained evolutionary system
running on a sample financial analysis problem.
"""

import asyncio
import json
from datetime import datetime

import sys
sys.path.insert(0, '/Users/khoapc/Counterfactual Financial Oracle/counterfactual_oracle/src')

from evolution import (
    UnconstrainedEvolutionSystem,
    SystemConfiguration,
    run_unconstrained_evolution
)
from infrastructure.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)


async def demo_callback(generation: int, state: dict):
    """Callback for progress updates."""
    if generation % 20 == 0:
        print(f"\n📊 Generation {generation}")
        print(f"   Best Fitness: {state['global_best']['fitness']:.4f}")
        print(f"   Populations: {state['populations']}")
        print(f"   Emergent Patterns: {state['emergent_patterns']}")
        print(f"   Phase: {state['phase']}")


async def main():
    """Run unconstrained evolution demonstration."""
    
    print("🧬 UNCONSTRAINED MULTI-AGENT EVOLUTION")
    print("=" * 60)
    print("\nThis system will:")
    print("  • Evolve agents with genetic algorithms")
    print("  • Detect emergent behaviors automatically")
    print("  • Self-improve its evolution mechanisms")
    print("  • Create new species as needed")
    print("  • Coordinate multiple populations")
    print("=" * 60)
    
    # Define the problem
    problem = {
        "problem_type": "financial_debate_optimization",
        "description": "Evolve optimal debate strategies for financial analysis",
        "objectives": [
            "maximize_consensus_quality",
            "minimize_debate_rounds",
            "maximize_prediction_accuracy"
        ],
        "constraints": [
            "grounding_in_data",
            "no_hallucination",
            "mathematical_correctness"
        ],
        "evaluation_criteria": {
            "consensus_quality": 0.4,
            "efficiency": 0.3,
            "accuracy": 0.3
        }
    }
    
    # Configure the system
    config = SystemConfiguration(
        enable_recursive_improvement=True,
        enable_emergence_detection=True,
        enable_meta_orchestration=True,
        max_generations=100,
        target_fitness=0.90,
        parallel_populations=3,
        allow_unbounded_complexity=True,
        enable_species_creation=True,
        dynamic_environment=True
    )
    
    print("\n⚙️  Configuration:")
    print(f"   Max Generations: {config.max_generations}")
    print(f"   Target Fitness: {config.target_fitness}")
    print(f"   Recursive Improvement: {config.enable_recursive_improvement}")
    print(f"   Emergence Detection: {config.enable_emergence_detection}")
    print(f"   Meta Orchestration: {config.enable_meta_orchestration}")
    
    print("\n🚀 Starting Evolution...")
    print("-" * 60)
    
    start_time = datetime.now()
    
    # Run the evolution
    results = await run_unconstrained_evolution(
        problem_definition=problem,
        config=config,
        progress_callback=demo_callback
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # Display results
    print("\n" + "=" * 60)
    print("✅ EVOLUTION COMPLETE")
    print("=" * 60)
    
    print(f"\n⏱️  Duration: {duration:.1f} seconds")
    print(f"🔄 Total Generations: {results['system_summary']['total_generations']}")
    
    print("\n🏆 BEST EVOLVED SOLUTION:")
    best = results['best_solution']
    print(f"   Fitness: {best['fitness']:.4f}")
    print(f"   Genome ID: {best['genome_id']}")
    if best['genome']:
        print(f"   Strategy: {best['genome'].get('strategy', 'unknown')}")
        print(f"   Communication: {best['genome'].get('communication_style', 'unknown')}")
        print(f"   Dominant Trait: {best['genome'].get('dominant_trait', 'unknown')}")
    
    print("\n🌟 EMERGENT PATTERNS DETECTED:")
    emergence = results['emergence_report']
    print(f"   Total Patterns: {emergence['total_patterns_detected']}")
    print(f"   Stable Patterns: {emergence['stable_patterns']}")
    print(f"   Significant Patterns: {emergence['significant_patterns']}")
    
    if emergence.get('most_significant'):
        print("\n   Top Patterns:")
        for i, pattern in enumerate(emergence['most_significant'][:3], 1):
            print(f"   {i}. {pattern['type']}: {pattern['description'][:60]}...")
    
    print("\n🎯 SPECIALIZATION:")
    spec = results['specialization_report']
    print(f"   Distribution: {spec.get('specialization_distribution', {})}")
    print(f"   Generalist/Specialist Ratio: {spec.get('generalists_vs_specialists', 0):.2f}")
    
    print("\n🔧 RECURSIVE SELF-IMPROVEMENT:")
    recursive = results['recursive_improvement_report']
    print(f"   Improvement Cycles: {recursive['improvement_cycles']}")
    print(f"   Meta-Fitness Trend: {recursive['meta_fitness_trend']}")
    print(f"   Improvement Rate: {recursive['improvement_rate']:.6f}")
    
    print("\n📊 POPULATION STATISTICS:")
    summary = results['system_summary']
    print(f"   Final Populations: {summary['final_populations']}")
    print(f"   Species Count: {summary['final_species']}")
    print(f"   Phase Transitions: {emergence.get('phase_transitions', 0)}")
    
    print("\n" + "=" * 60)
    print("📄 Full results saved to: evolution_results.json")
    print("=" * 60)
    
    # Save full results
    with open('evolution_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
