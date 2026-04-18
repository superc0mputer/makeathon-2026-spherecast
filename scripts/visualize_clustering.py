"""
Phase 1 · Hybrid Substitution Visualization
────────────────────────────────────────────────────
Generates interactive HTML Network Graphs showing either:
1. Hub-and-Spoke: Substitutes for a SINGLE target ingredient.
2. Global Clusters: A macro-view of all ingredient similarities.

Usage:
    python scripts/visualize_clustering.py --target "ING-123"
    python scripts/visualize_clustering.py --all --threshold 0.75
"""

import argparse
import os
import sys
from collections import Counter

# 🚀 Force Python to look one folder up for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import networkx as nx
import plotly.graph_objects as go
import plotly.colors as pcolors

from src.services.clustering_service import load_data, calculate_target_substitutes, calculate_all_similarities

# This is a fallback, but gets overridden by the terminal argument!
EDGE_THRESHOLD = 0.40

# ==========================================
# 1. SINGLE TARGET VISUALIZATION
# ==========================================
def visualize_network(target_data: dict, out_path: str):
    target_sku = target_data["target_sku"]
    print(f"[1/3] Building Hub-and-Spoke Graph for {target_sku} (Threshold: {EDGE_THRESHOLD})...")

    G = nx.Graph()
    G.add_node(target_sku, is_target=True, score=1.0)

    for sub in target_data["substitutes"]:
        score = sub["similarity_score"]
        if score >= EDGE_THRESHOLD:
            G.add_node(sub["sku"], is_target=False, score=score)
            G.add_edge(target_sku, sub["sku"], weight=score)

    if G.number_of_nodes() <= 1:
        print(f"❌ No strong substitutes found for {target_sku}.")
        return

    print("[2/3] Calculating graph physics...")
    pos = nx.spring_layout(G, k=0.5, iterations=50)

    _render_targeted_graph(G, pos, target_sku, f'Hybrid Substitutes for {target_sku}', out_path)


# ==========================================
# 2. GLOBAL CLUSTER VISUALIZATION
# ==========================================
def visualize_global_clusters(edge_list: list, out_path: str):
    print(f"[1/3] Building Global Cluster Graph (Threshold: {EDGE_THRESHOLD})...")

    G = nx.Graph()
    for source, target, score in edge_list:
        if score >= EDGE_THRESHOLD:
            G.add_edge(source, target, weight=score)

    if G.number_of_nodes() == 0:
        print("❌ No edges meet the threshold.")
        return

    print(f"      Graph contains {G.number_of_nodes()} nodes and {G.number_of_edges()} connections.")
    print("[2/3] Calculating graph physics (This may take a moment)...")

    pos = nx.spring_layout(G, k=0.15, iterations=50)

    print("      Detecting community clusters...")
    communities = nx.community.greedy_modularity_communities(G, weight='weight')

    for cluster_id, community in enumerate(communities):

        # Extract the clean ingredient names for this specific cluster
        names = []
        for node in community:
            clean = "-".join(node.split("-")[2:-1]).replace("-", " ").title()
            if clean:
                names.append(clean)

        # Find the 1 or 2 most common ingredient names to use as the semantic label
        if names:
            top_names = [name for name, count in Counter(names).most_common(2)]
            semantic_name = " & ".join(top_names)
        else:
            semantic_name = f"Cluster {cluster_id}"

        for node in community:
            G.nodes[node]['cluster_id'] = cluster_id
            G.nodes[node]['cluster_name'] = semantic_name

    _render_global_graph(G, pos, 'Global Ingredient Similarity Clusters', out_path)


# ==========================================
# PLOTLY RENDERING: TARGETED
# ==========================================
def _render_targeted_graph(G, pos, target_sku, title, out_path):
    edge_x, edge_y = [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=1.5, color='#888'), hoverinfo='none', mode='lines')

    node_x, node_y, node_text, node_hovertext, node_colors, node_sizes = [], [], [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)

        clean_name = "-".join(node.split("-")[2:-1]).replace("-", " ").title()
        if not clean_name: clean_name = node

        if node == target_sku:
            node_text.append(f"🎯 {clean_name}")
            node_hovertext.append(f"<b>{clean_name} (TARGET)</b><br>SKU: {node}")
            node_colors.append(1.0)
            node_sizes.append(25)
        else:
            score = G.nodes[node]['score']
            node_text.append(f"{clean_name}<br>({score:.2f})")
            node_hovertext.append(f"<b>{clean_name}</b><br>Hybrid Similarity: {score:.3f}<br>SKU: {node}")
            node_colors.append(score)
            node_sizes.append(15)

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode='markers+text', text=node_text, textposition="bottom center",
        hovertext=node_hovertext, hoverinfo='text', textfont=dict(family="sans-serif", size=10, color="#333"),
        marker=dict(showscale=True, colorscale='YlGnBu', reversescale=True, color=node_colors, size=node_sizes,
                    colorbar=dict(thickness=15, title=dict(text='Similarity Score', side='right'), xanchor='left'),
                    line_width=2, line_color='white')
    )

    print(f"[3/3] Generating interactive HTML plot -> {out_path}")
    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(title=dict(text=title, font=dict(size=16)), showlegend=False, hovermode='closest',
                                     margin=dict(b=40, l=40, r=40, t=40), plot_bgcolor="white",
                                     xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                     yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)))
    fig.write_html(out_path)
    print(f"\n✅ Done! Open '{out_path}' in your web browser.")


# ==========================================
# PLOTLY RENDERING: GLOBAL CLUSTERS
# ==========================================
def _render_global_graph(G, pos, title, out_path):
    fig = go.Figure()

    clusters = {}
    for node in G.nodes():
        cid = G.nodes[node].get('cluster_id', 0)
        if cid not in clusters:
            clusters[cid] = []
        clusters[cid].append(node)

    # Cross-Cluster Links (Hidden by Default!)
    cross_edge_x, cross_edge_y = [], []
    for u, v in G.edges():
        if G.nodes[u].get('cluster_id') != G.nodes[v].get('cluster_id'):
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            cross_edge_x.extend([x0, x1, None])
            cross_edge_y.extend([y0, y1, None])

    if cross_edge_x:
        fig.add_trace(go.Scatter(
            x=cross_edge_x, y=cross_edge_y, mode='lines',
            line=dict(width=0.2, color='rgba(200, 200, 200, 0.2)'),
            hoverinfo='none', name='Cross-Cluster Links', showlegend=True,
            visible='legendonly' # Hide the hairball!
        ))

    palette = pcolors.qualitative.Alphabet + pcolors.qualitative.Dark24

    for cid, nodes in sorted(clusters.items()):
        color = palette[cid % len(palette)]

        # Retrieve the generated semantic name and append the cluster size
        semantic_name = G.nodes[nodes[0]].get('cluster_name', f'Cluster {cid}')
        group_name = f"{semantic_name} (n={len(nodes)})"

        # Internal Edges
        edge_x, edge_y = [], []
        for u, v in G.edges():
            if G.nodes[u].get('cluster_id') == cid and G.nodes[v].get('cluster_id') == cid:
                x0, y0 = pos[u]
                x1, y1 = pos[v]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])

        if edge_x:
            fig.add_trace(go.Scatter(
                x=edge_x, y=edge_y, mode='lines',
                line=dict(width=1.0, color=color), opacity=0.5,
                hoverinfo='none', legendgroup=group_name, showlegend=False
            ))

        # Nodes
        node_x, node_y, node_hovertext = [], [], []
        for node in nodes:
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            clean_name = "-".join(node.split("-")[2:-1]).replace("-", " ").title()
            if not clean_name: clean_name = node

            # Update hover text to show the semantic name instead of an integer ID
            node_hovertext.append(f"<b>{clean_name}</b><br>Group: {semantic_name}<br>SKU: {node}")

        fig.add_trace(go.Scatter(
            x=node_x, y=node_y, mode='markers',
            name=group_name, legendgroup=group_name,
            hovertext=node_hovertext, hoverinfo='text',
            marker=dict(color=color, size=10, line_width=1, line_color='white')
        ))

    print(f"[3/3] Generating interactive HTML plot -> {out_path}")
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        legend=dict(title="<b>Clusters</b><br><i>(Double-click to isolate)</i>", itemsizing='constant'),
        hovermode='closest', margin=dict(b=40, l=40, r=40, t=40), plot_bgcolor="white",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    fig.write_html(out_path)
    print(f"\n✅ Done! Open '{out_path}' in your web browser.")


# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Visualize Ingredient Substitutions")
    parser.add_argument("--target", required=False, help="The SKU of the target (e.g. 'ING-123')")
    parser.add_argument("--all", action="store_true", help="Visualize all similarity clusters globally")
    parser.add_argument("--threshold", type=float, default=0.40, help="Minimum similarity score to draw a line")
    parser.add_argument("--db", default="db.sqlite", help="Path to db.sqlite")
    parser.add_argument("--out-dir", default=".", help="Directory to write HTML output")
    args = parser.parse_args()

    # Override the global EDGE_THRESHOLD with the user's input
    global EDGE_THRESHOLD
    EDGE_THRESHOLD = args.threshold

    os.makedirs(args.out_dir, exist_ok=True)
    components = load_data(args.db)

    if args.all:
        real_edges = calculate_all_similarities(components)
        out_path = os.path.join(args.out_dir, "network_global_clusters.html")
        visualize_global_clusters(real_edges, out_path)

    elif args.target:
        try:
            target_data = calculate_target_substitutes(components, args.target)
        except ValueError as e:
            print(f"\n[!] {e}")
            return

        safe_target = "".join(c for c in args.target if c.isalnum() or c in ('-', '_'))
        out_path = os.path.join(args.out_dir, f"network_hybrid_{safe_target}.html")
        visualize_network(target_data, out_path)

    else:
        print("❌ Error: You must provide either --target <SKU> or --all")

if __name__ == "__main__":
    main()