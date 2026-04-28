"""
docs/graph_builder.py
---------------------
Builds a dependency graph from parsed repo data and exports it as:
  - A PNG image (dependency graph)
  - A Mermaid flowchart string (for embedding in README)

Uses networkx for graph construction and matplotlib for rendering.
"""
import logging
from typing import List, Dict, Any
import networkx as nx
import matplotlib
matplotlib.use("Agg")  # non-interactive backend (safe for servers)
import matplotlib.pyplot as plt
from pathlib import Path

logger = logging.getLogger(__name__)


def build_dependency_graph(parsed_files: List[Dict[str, Any]]) -> nx.DiGraph:
    """
    Build a directed dependency graph from parsed file structures.

    Nodes: file paths (short names)
    Edges: file A → file B means A imports something from B
    """
    G = nx.DiGraph()
    # Create a mapping: module_name → file_path
    file_names = {
        f["file"].replace("/", ".").replace("\\", ".").rstrip(".py"): f["file"]
        for f in parsed_files
    }

    for pf in parsed_files:
        source_node = pf["file"]
        G.add_node(source_node)

        for imp in pf.get("imports", []):
            # Check if this import refers to another file in the repo
            for mod_key, target_file in file_names.items():
                if imp.startswith(mod_key) and target_file != source_node:
                    G.add_edge(source_node, target_file, label=imp)
                    break

    return G


def save_graph_image(G: nx.DiGraph, output_path: str) -> str:
    """
    Render the dependency graph as a PNG image.
    Returns the output path.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(14, 10), facecolor="#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    # Use spring layout for readability
    pos = nx.spring_layout(G, seed=42, k=2.5)

    # Shorten node labels for display
    labels = {n: n.split("/")[-1].split("\\")[-1] for n in G.nodes()}

    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=1200, node_color="#e94560", alpha=0.9)
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax, font_size=8, font_color="white")
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edge_color="#00d2ff",
        arrows=True,
        arrowsize=15,
        width=1.5,
        alpha=0.7,
    )
    ax.set_title("Module Dependency Graph", color="white", fontsize=14, pad=15)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    logger.info(f"[GraphBuilder] Dependency graph saved to {output_path}")
    return output_path


def generate_mermaid_flowchart(parsed_files: List[Dict[str, Any]]) -> str:
    """
    Generate a Mermaid flowchart showing module structure.
    Each file is a node; classes and functions are sub-nodes.

    Returns a Mermaid diagram string for embedding in README.md.
    """
    lines = ["```mermaid", "graph TD"]

    for pf in parsed_files:
        file_id = pf["file"].replace("/", "_").replace("\\", "_").replace(".", "_")
        file_label = pf["file"].split("/")[-1].split("\\")[-1]
        lines.append(f'    {file_id}["{file_label}"]')

        for cls in pf.get("classes", []):
            cls_id = f'{file_id}_{cls["name"]}'
            lines.append(f'    {cls_id}["📦 {cls["name"]}"]')
            lines.append(f"    {file_id} --> {cls_id}")
            for method in cls.get("methods", []):
                if method["name"].startswith("_"):
                    continue  # skip private methods
                m_id = f'{cls_id}_{method["name"]}'
                lines.append(f'    {m_id}["⚙ {method["name"]}()"]')
                lines.append(f"    {cls_id} --> {m_id}")

        for fn in pf.get("functions", []):
            fn_id = f'{file_id}_{fn["name"]}'
            lines.append(f'    {fn_id}["🔧 {fn["name"]}()"]')
            lines.append(f"    {file_id} --> {fn_id}")

    lines.append("```")
    return "\n".join(lines)
