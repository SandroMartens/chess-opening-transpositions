"""Regression test: draw_graph() must color a single-community subgraph
with the SAME tab20 color that community has in the full graph, not the
colormap's fixed first color. See docs/superpowers/specs/
2026-06-24-community-graph-coloring-design.md for the root cause."""

import os
import sys
import tempfile

# Add parent directory to sys.path to import analysis module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from analysis import draw_graph


def test_single_community_subgraph_keeps_global_color():
    graph = nx.DiGraph()
    graph.add_weighted_edges_from([("a", "b", 1), ("b", "c", 1)])
    undirected = graph.to_undirected()
    occurrences = pd.Series({"a": 1, "b": 1, "c": 1})
    # a, b, c all sit in community 5; "phantom" (not in this subgraph) is
    # community 9 -- mirrors plot_top_communities()'s real call shape:
    # community_of always covers the full graph's partition even when
    # graph/undirected here are just one community's subgraph
    community_of = {"a": 5, "b": 5, "c": 5, "phantom": 9}

    real_close = plt.close
    plt.close = lambda *args, **kwargs: None  # keep figure alive past draw_graph()'s plt.close()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test_color.png")
            draw_graph(
                graph, undirected, occurrences, occurrences.max(), community_of,
                filename, show_labels=False,
            )
            collection = plt.gca().collections[-1]
            node_order = list(graph.nodes())
            actual = tuple(collection.get_facecolor()[node_order.index("a")])
    finally:
        plt.close = real_close
        plt.close("all")

    expected = plt.cm.tab20(5 / 9)  # community 5 of global max 9
    assert actual == expected, (
        f"node 'a' (community 5/9) rendered {actual}, expected {expected} -- "
        "draw_graph() is not using a fixed global vmin/vmax scale"
    )
    print("OK: single-community subgraph keeps its global tab20 color")


if __name__ == "__main__":
    test_single_community_subgraph_keeps_global_color()
