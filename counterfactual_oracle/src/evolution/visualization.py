"""
📊 Evolution Visualization Module

Tools for visualizing the evolutionary process, emergent patterns,
and system dynamics.
"""

from typing import Dict, List, Any, Optional
import json
from datetime import datetime
import numpy as np

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from .genome import AgentGenome
from .population import AgentPopulation
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


class EvolutionVisualizer:
    """Visualizes evolution dynamics and results."""
    
    def __init__(self):
        if not HAS_MATPLOTLIB:
            logger.warning("matplotlib not available, visualization disabled")
        self.history: List[Dict] = []
    
    def record_generation(self, generation: int, state: Dict) -> None:
        """Record generation state for visualization."""
        self.history.append({
            "generation": generation,
            **state
        })
    
    def plot_fitness_evolution(self, save_path: Optional[str] = None) -> None:
        """Plot fitness over generations."""
        if not HAS_MATPLOTLIB or not self.history:
            return
        
        generations = [h["generation"] for h in self.history]
        fitnesses = [h.get("global_best", {}).get("fitness", 0) for h in self.history]
        
        plt.figure(figsize=(12, 6))
        plt.plot(generations, fitnesses, 'b-', linewidth=2, label='Best Fitness')
        plt.fill_between(generations, fitnesses, alpha=0.3)
        
        plt.xlabel('Generation')
        plt.ylabel('Fitness')
        plt.title('Fitness Evolution Over Time')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()
    
    def plot_diversity(self, save_path: Optional[str] = None) -> None:
        """Plot population diversity over time."""
        if not HAS_MATPLOTLIB or not self.history:
            return
        
        # Extract diversity data if available
        generations = [h["generation"] for h in self.history]
        
        # Placeholder - would need actual diversity tracking
        plt.figure(figsize=(12, 6))
        plt.plot(generations, [0.5] * len(generations), 'g-', label='Diversity')
        
        plt.xlabel('Generation')
        plt.ylabel('Diversity Index')
        plt.title('Population Diversity Over Time')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def plot_species_tree(self, population: AgentPopulation, save_path: Optional[str] = None) -> None:
        """Visualize species phylogenetic tree."""
        if not HAS_MATPLOTLIB:
            return
        
        fig, ax = plt.subplots(figsize=(14, 10))
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(population.species)))
        
        y_offset = 0
        for i, (species_name, members) in enumerate(population.species.items()):
            if not members:
                continue
            
            # Draw species block
            x = [m.genome.generation for m in members]
            y = [y_offset + j for j in range(len(members))]
            
            ax.scatter(x, y, c=[colors[i]], label=species_name, s=100, alpha=0.6)
            
            # Draw connections
            for j in range(len(x) - 1):
                ax.plot([x[j], x[j+1]], [y[j], y[j+1]], 
                       color=colors[i], alpha=0.3, linewidth=1)
            
            y_offset += len(members) + 2
        
        ax.set_xlabel('Generation')
        ax.set_ylabel('Agent Lineage')
        ax.set_title('Species Evolution Tree')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()
    
    def plot_genome_network(self, population: AgentPopulation, save_path: Optional[str] = None) -> None:
        """Visualize genome similarity network."""
        if not HAS_MATPLOTLIB:
            return
        
        try:
            import networkx as nx
        except ImportError:
            logger.warning("networkx not available for network visualization")
            return
        
        # Create graph
        G = nx.Graph()
        
        # Add nodes
        for agent in population.agents:
            G.add_node(agent.agent_id, 
                      fitness=agent.average_fitness,
                      strategy=agent.genome.strategy_gene.value)
        
        # Add edges based on genetic similarity
        for i, a1 in enumerate(population.agents):
            for a2 in population.agents[i+1:]:
                distance = a1.genome.calculate_diversity(a2.genome)
                if distance < 0.3:  # Similar genomes
                    G.add_edge(a1.agent_id, a2.agent_id, weight=1-distance)
        
        # Draw
        fig, ax = plt.subplots(figsize=(12, 12))
        
        pos = nx.spring_layout(G, k=3, iterations=50)
        
        # Color by fitness
        node_colors = [G.nodes[n].get('fitness', 0) for n in G.nodes()]
        
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, 
                              cmap=plt.cm.viridis, node_size=300, ax=ax)
        nx.draw_networkx_edges(G, pos, alpha=0.2, ax=ax)
        
        ax.set_title('Genome Similarity Network')
        plt.colorbar(plt.cm.ScalarMappable(cmap=plt.cm.viridis), ax=ax, label='Fitness')
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()
    
    def create_html_report(self, results: Dict[str, Any], output_path: str = "evolution_report.html") -> None:
        """Create an interactive HTML report of evolution results."""
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Evolution Report - Generation {results['system_summary']['total_generations']}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric {{
            display: inline-block;
            margin: 10px 20px 10px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 6px;
            min-width: 150px;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }}
        .pattern {{
            border-left: 4px solid #667eea;
            padding-left: 15px;
            margin: 10px 0;
        }}
        .pattern-type {{
            font-weight: bold;
            color: #667eea;
        }}
        .genome {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 14px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧬 Unconstrained Multi-Agent Evolution Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="card">
        <h2>📊 System Summary</h2>
        <div class="metric">
            <div class="metric-value">{results['system_summary']['total_generations']}</div>
            <div class="metric-label">Generations</div>
        </div>
        <div class="metric">
            <div class="metric-value">{results['system_summary']['final_populations']}</div>
            <div class="metric-label">Populations</div>
        </div>
        <div class="metric">
            <div class="metric-value">{results['system_summary']['final_species']}</div>
            <div class="metric-label">Species</div>
        </div>
        <div class="metric">
            <div class="metric-value">{results['emergence_report']['total_patterns_detected']}</div>
            <div class="metric-label">Emergent Patterns</div>
        </div>
    </div>
    
    <div class="card">
        <h2>🏆 Best Evolved Solution</h2>
        <p><strong>Fitness:</strong> {results['best_solution']['fitness']:.4f}</p>
        <p><strong>Genome ID:</strong> {results['best_solution']['genome_id']}</p>
        
        <h3>Phenotype:</h3>
        <div class="genome">
            {json.dumps(results['best_solution']['genome'], indent=2) if results['best_solution']['genome'] else 'N/A'}
        </div>
    </div>
    
    <div class="card">
        <h2>🌟 Emergent Patterns</h2>
        <p><strong>Total Detected:</strong> {results['emergence_report']['total_patterns_detected']}</p>
        <p><strong>Stable:</strong> {results['emergence_report']['stable_patterns']}</p>
        <p><strong>Significant:</strong> {results['emergence_report']['significant_patterns']}</p>
        
        <h3>Most Significant:</h3>
        """
        
        for pattern in results['emergence_report'].get('most_significant', [])[:5]:
            html += f"""
        <div class="pattern">
            <div class="pattern-type">{pattern['type']}</div>
            <div>{pattern['description']}</div>
            <small>Significance: {pattern['significance']:.3f}</small>
        </div>
            """
        
        html += """
    </div>
    
    <div class="card">
        <h2>🎯 Specialization</h2>
        <p><strong>Generalist/Specialist Ratio:</strong> {spec_ratio:.2f}</p>
        
        <h3>Distribution:</h3>
        <table>
            <tr>
                <th>Specialization</th>
                <th>Count</th>
            </tr>
        """.format(
            spec_ratio=results['specialization_report'].get('generalists_vs_specialists', 0)
        )
        
        for spec, count in results['specialization_report'].get('specialization_distribution', {}).items():
            html += f"""
            <tr>
                <td>{spec}</td>
                <td>{count}</td>
            </tr>
            """
        
        html += """
        </table>
    </div>
    
    <div class="card">
        <h2>🔧 Recursive Self-Improvement</h2>
        <p><strong>Improvement Cycles:</strong> {cycles}</p>
        <p><strong>Meta-Fitness Trend:</strong> {trend}</p>
        <p><strong>Improvement Rate:</strong> {rate:.6f}</p>
    </div>
</body>
</html>
        """.format(
            cycles=results['recursive_improvement_report']['improvement_cycles'],
            trend=results['recursive_improvement_report']['meta_fitness_trend'],
            rate=results['recursive_improvement_report']['improvement_rate']
        )
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        logger.info("html_report_generated", path=output_path)


def export_to_tensorboard(results: Dict[str, Any], log_dir: str = "runs/evolution") -> None:
    """Export evolution metrics to TensorBoard."""
    try:
        from torch.utils.tensorboard import SummaryWriter
        
        writer = SummaryWriter(log_dir)
        
        # Log evolution history
        for record in results.get('evolution_history', []):
            gen = record['generation']
            writer.add_scalar('Fitness/best', record.get('global_best_fitness', 0), gen)
            writer.add_scalar('Population/agents', record.get('total_agents', 0), gen)
            writer.add_scalar('Population/species', record.get('species', 0), gen)
        
        writer.close()
        logger.info("tensorboard_export_complete", log_dir=log_dir)
        
    except ImportError:
        logger.warning("tensorboard not available for export")
