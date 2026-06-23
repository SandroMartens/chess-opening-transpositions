"""Analyze transposition in chess openings"""

# %%
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from numpy import int32
from tqdm import tqdm

from database import load_positions
from opening_data import find_longest_variation, get_opening_name, load_opening_data


# %%
def get_adjacency_matrix(
    positions: pd.DataFrame, openings: pd.DataFrame
) -> pd.DataFrame:
    """Iterate over all moves in all games. If a transposition of named openings is
    found, add 1 to the adjacency matrix between the two openings"""
    unique_names = openings.name.drop_duplicates()
    adjacency_matrix = pd.DataFrame(
        data=0, index=unique_names, columns=unique_names, dtype=int32
    )

    # So that we dont delete the Start node later
    adjacency_matrix.loc["Start", "Start"] = 1
    for game in tqdm(range(positions.shape[0]), desc="Analyzing games", unit=" games"):
        last_opening_name = "Start"
        for ply in range(positions.shape[1]):
            epd = positions.iloc[game, ply]
            new_opening_name = get_opening_name(epd, openings)
            if new_opening_name is not None and new_opening_name != last_opening_name:
                adjacency_matrix.loc[last_opening_name, new_opening_name] += 1
                last_opening_name = new_opening_name

    adjacency_matrix = remove_non_reached_nodes(adjacency_matrix)

    return adjacency_matrix


def remove_non_reached_nodes(adjacency_matrix: pd.DataFrame) -> pd.DataFrame:
    """Remove variations that were not reached. An opening was not reached if it has
    no incoming edges."""
    # axis=1 for outgoing edges
    # axis=0 for incoming edges
    connected_nodes = adjacency_matrix.loc[(adjacency_matrix != 0).any(axis=0)].index
    adjacency_matrix = adjacency_matrix.loc[connected_nodes, connected_nodes]
    return adjacency_matrix


def save_results(adjacency_matrix: pd.DataFrame, n_games: int) -> None:
    """Save adjacency matrix and number of occurrences of each position to csv file"""
    adjacency_matrix.to_csv(f"results/adjacency_matrix_{n_games}.csv")
    occurrences = adjacency_matrix.sum(axis=0)
    occurrences.to_csv(
        f"results/occurrences_{n_games}.csv", index_label="Id", header=["Occurrences"]
    )


# %%
def plot_graph(
    adjacency_matrix: pd.DataFrame, n_games: int, min_occurrences: int = 5
) -> None:
    """Draw opening transposition graph: forceatlas2 layout, louvain community
    colors, occurrence-based node/font size. Drops openings reached by fewer
    than min_occurrences games."""
    graph = nx.from_pandas_adjacency(adjacency_matrix)
    graph.remove_edges_from(nx.selfloop_edges(graph))
    occurrences = adjacency_matrix.sum(axis=0)
    # Start's only incoming edge is the artificial self-loop (see get_adjacency_matrix) -
    # use its outgoing transitions instead, the real "games reaching Start" count
    occurrences["Start"] = adjacency_matrix.loc["Start"].sum()
    graph = graph.subgraph([n for n in graph if occurrences[n] >= min_occurrences])
    max_occurrences = occurrences.max()
    # forceatlas2's node_size is a layout-space halo radius, not a pixel size -
    # passing raw occurrence counts (up to 1000s) wrecks the physics and yields NaN positions
    node_size_layout = {n: 0.05 * occurrences[n] / max_occurrences for n in graph}
    pos = nx.forceatlas2_layout(
        graph, max_iter=10_000, node_size=node_size_layout, weight="weight", seed=0
    )
    node_size_draw = np.sqrt([1000 * occurrences[n] / max_occurrences for n in graph])

    communities = nx.community.louvain_communities(graph, weight="weight", seed=0)
    community_of = {n: i for i, c in enumerate(communities) for n in c}
    node_color = [community_of[n] for n in graph]

    edge_width = [
        0.2 + 10 * graph[u][v]["weight"] / max_occurrences for u, v in graph.edges()
    ]

    plt.figure(figsize=(20, 20))  # figsize * dpi = output pixels
    nx.draw_networkx_edges(
        graph,
        pos,
        alpha=1,
        arrows=True,
        connectionstyle="arc3,rad=0.1",
        width=edge_width,
    )
    nx.draw_networkx_nodes(
        graph, pos, node_color=node_color, cmap=plt.cm.tab20, node_size=node_size_draw
    )
    # nx.draw_networkx_labels font_size is a single scalar - loop manually for per-node scaling
    ax = plt.gca()
    for n in graph:
        x, y = pos[n]
        ax.text(
            x,
            y,
            n,
            fontsize=4 + 12 * occurrences[n] / max_occurrences,
            ha="center",
            va="center",
        )
    plt.savefig(f"images/graph_{n_games}.png", dpi=200)


# %%
def main():
    """Main function"""
    MIN_OCCURENCES = 5
    # Positions come from games.sqlite (see database.py), not a live pgn parse
    OPENINGS = load_opening_data()
    print(f"Longest line: {find_longest_variation(OPENINGS)} halfmoves")
    positions = load_positions()
    n_games = positions.shape[0]
    adjacency_matrix = get_adjacency_matrix(positions, OPENINGS)
    save_results(adjacency_matrix, n_games)
    plot_graph(adjacency_matrix, n_games, min_occurrences=MIN_OCCURENCES)


if __name__ == "__main__":
    main()
