"""
Smoke tests for the evolution package: every module must import, and the
code paths that previously referenced un-imported names must run.
"""

import importlib

import pytest

EVOLUTION_MODULES = [
    "genome",
    "population",
    "evolution_engine",
    "meta_agent",
    "emergence",
    "recursive_improvement",
    "unconstrained_system",
]


@pytest.mark.parametrize("module", EVOLUTION_MODULES)
def test_evolution_module_imports(module):
    importlib.import_module(f"counterfactual_oracle.src.evolution.{module}")


def test_meta_agent_selects_strategy():
    from counterfactual_oracle.src.evolution.meta_agent import MetaAgent, MetaStrategy

    agent = MetaAgent()
    agent._select_new_strategy({"niche_coverage": {"a": 0.1}, "best_fitness": 0.9})

    assert isinstance(agent.current_strategy, MetaStrategy)


def test_self_modification_loop_initializes():
    from counterfactual_oracle.src.evolution.recursive_improvement import SelfModificationLoop

    loop = SelfModificationLoop()

    assert loop.mechanism_variants["anything"] == []
