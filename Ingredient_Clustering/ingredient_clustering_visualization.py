"""
Phase 1 · Targeted Substitution Visualization
─────────────────────────────────────────────
Generates an interactive HTML Network Graph showing ingredient
substitution opportunities for a SINGLE target ingredient based
on contextual Cosine Similarity.

Dependencies:
    pip install pandas scikit-learn plotly networkx

Usage:
    python ingredient_clustering_visualize_subs.py --target "ING-123" --db path/to/db.sqlite
"""

import argparse
import networkx as nx
import plotly.graph_objects as go

# Import the targeted logic from your substitution script
from ingredient_clustering import load_data, calculate_target_substitutes

# Only draw lines between ingredients if they are a strong match
EDGE_THRESHOLD = 0.50

def visualize_network(target_data: dict, out_path: str):
    target_sku = target_data["target_sku"]
    print(f"[1/3] Building Hub-and-Spoke Graph for {target_sku} (Threshold: {EDGE_THRESHOLD})...")

    G = nx.Graph()

    # 1. Add the central target node
    G.add_node(target_sku, is_target=True, score=1.0)

    # 2. Add substitute nodes and connect them to the target
    for sub in target_data["substitutes"]:
        score = sub["similarity_score"]
        if score >= EDGE_THRESHOLD:
            G.add_node(sub["sku"], is_target=False, score=score)
            G.add_edge(target_sku, sub["sku"], weight=score)

    print(f"      Graph contains 1 target and {G.number_of_nodes() - 1} valid substitutes.")

    if G.number_of_nodes() <= 1:
        print(f"❌ No strong substitutes found for {target_sku} at this threshold. Lower EDGE_THRESHOLD.")
        return

    print("[2/3] Calculating graph physics (Force-Directed Layout)...")
    # spring_layout naturally pushes the spokes out from the center hub
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
    node_colors = []
    node_sizes = []

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)

        # Clean up text for hover (e.g., "RM-C43-sucralose-1234" -> "sucralose")
        clean_name = "-".join(node.split("-")[2:-1]).replace("-", " ").title()
        if not clean_name: clean_name = node

        if node == target_sku:
            # Highlight the central target node
            hover_text = f"<b>{clean_name} (TARGET)</b><br>SKU: {node}"
            node_colors.append(1.0) # Force highest color map value
            node_sizes.append(25)   # Make it larger
        else:
            # Format the spoke nodes
            score = G.nodes[node]['score']
            hover_text = f"<b>{clean_name}</b><br>Similarity: {score:.3f}<br>SKU: {node}"
            node_colors.append(score)
            node_sizes.append(15)

        node_text.append(hover_text)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        text=node_text,
        marker=dict(
            showscale=True,
            colorscale='YlGnBu', # Yellow -> Green -> Blue
            reversescale=True,
            color=node_colors,
            size=node_sizes,
            colorbar=dict(
                thickness=15,
                title=dict(
                    text='Similarity Score',
                    side='right'
                ),
                xanchor='left'
            ),
            line_width=2,
            line_color='white'
        )
    )

    print(f"[3/3] Generating interactive HTML plot -> {out_path}")

    # 5. Render the Figure
    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        title=dict(
                            text=f'Substitutes for {target_sku} (Similarity > {EDGE_THRESHOLD})',
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
    parser = argparse.ArgumentParser(description="Visualize Ingredient Substitutions for a Target")
    parser.add_argument("--target", required=True, help="The SKU of the ingredient to analyze (e.g. 'ING-123')")
    parser.add_argument("--db", default="../db.sqlite", help="Path to db.sqlite")
    parser.add_argument("--out-dir", default=".", help="Directory to write HTML output")
    args = parser.parse_args()

    # 1. Run the substitution math
    components = load_data(args.db)
    try:
        target_data = calculate_target_substitutes(components, args.target)
    except ValueError as e:
        print(f"\n[!] {e}")
        return

    # 2. Clean the filename in case the SKU has weird characters
    import os
    safe_target = "".join(c for c in args.target if c.isalnum() or c in ('-', '_'))
    out_path = os.path.join(args.out_dir, f"network_{safe_target}.html")

    # 3. Visualize
    visualize_network(target_data, out_path)

if __name__ == "__main__":
    main()