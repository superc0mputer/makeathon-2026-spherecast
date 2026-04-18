"""
Phase 1 · Substitution Visualization
────────────────────────────────────
Generates an interactive HTML Network Graph showing ingredient
substitution opportunities based on contextual Cosine Similarity.

Dependencies:
    pip install pandas scikit-learn plotly networkx

Usage:
    python ingredient_clustering_visualize_subs.py --db path/to/db.sqlite
"""

import argparse
import networkx as nx
import plotly.graph_objects as go

# Import the logic from your substitution script
from ingredient_clustering import load_data, calculate_substitutes

# Only draw lines between ingredients if they are a strong match (>80% similarity)
# Lowering this will create a messier graph; raising it will isolate exact matches.
EDGE_THRESHOLD = 0.50

def visualize_network(sub_map: dict, out_path: str):
    print(f"[1/3] Building Network Graph (Threshold: {EDGE_THRESHOLD})...")

    G = nx.Graph()

    # 1. Add nodes and edges from the substitution map
    for ingredient, data in sub_map.items():
        # Ensure the node exists even if it has no edges
        G.add_node(ingredient)

        for sub in data["substitutes"]:
            if sub["similarity_score"] >= EDGE_THRESHOLD:
                G.add_edge(ingredient, sub["sku"], weight=sub["similarity_score"])

    # 2. Remove isolated nodes (ingredients with no strong substitutes) to keep the graph clean
    isolated = list(nx.isolates(G))
    G.remove_nodes_from(isolated)

    print(f"      Graph contains {G.number_of_nodes()} ingredients and {G.number_of_edges()} strong substitution links.")

    if G.number_of_nodes() == 0:
        print("❌ No strong substitutes found at this threshold. Lower EDGE_THRESHOLD.")
        return

    print("[2/3] Calculating graph physics (Force-Directed Layout)...")
    # This determines the X/Y coordinates to naturally push/pull related nodes
    pos = nx.spring_layout(G, k=0.5, iterations=50)

    # 3. Create Edges (Lines) for Plotly
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1.5, color='#888'),
        hoverinfo='none',
        mode='lines'
    )

    # 4. Create Nodes (Dots) for Plotly
    node_x = []
    node_y = []
    node_text = []
    node_adjacencies = []

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)

        # Count connections to color code by "hub" importance
        adjacencies = len(list(G.neighbors(node)))
        node_adjacencies.append(adjacencies)

        # Clean up text for hover (e.g., "RM-C43-sucralose-1234" -> "sucralose")
        clean_name = "-".join(node.split("-")[2:-1]).replace("-", " ").title()
        if not clean_name: clean_name = node

        hover_text = f"<b>{clean_name}</b><br>Strong Substitutes: {adjacencies}<br>SKU: {node}"
        node_text.append(hover_text)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        text=node_text,
        marker=dict(
            showscale=True,
            colorscale='YlGnBu',
            reversescale=True,
            color=node_adjacencies,
            size=15,
            colorbar=dict(
                thickness=15,
                title=dict(
                    text='Substitutes',
                    side='right'
                ),
                xanchor='left'
            ),
            line_width=2
        )
    )

    print(f"[3/3] Generating interactive HTML plot -> {out_path}")

    # 5. Render the Figure
    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        # Corrected: title is now a dictionary
                        title=dict(
                            text=f'Ingredient Substitution Network (Similarity > {EDGE_THRESHOLD})',
                            font=dict(size=16)
                        ),
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        plot_bgcolor="white",
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                    )

    fig.write_html(out_path)
    print(f"\n✅ Done! Open '{out_path}' in your web browser.")

def main():
    parser = argparse.ArgumentParser(description="Visualize Ingredient Substitutions")
    parser.add_argument("--db", default="../db.sqlite", help="Path to db.sqlite")
    parser.add_argument("--out", default="substitution_network.html", help="Output HTML file name")
    args = parser.parse_args()

    # Run the substitution math
    components = load_data(args.db)
    substitution_map = calculate_substitutes(components)

    # Visualize
    visualize_network(substitution_map, args.out)

if __name__ == "__main__":
    main()