"""Analyze transposition in chess openings"""

# %%
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from numpy import int32
from tqdm import tqdm

from database import load_positions
from opening_data import (
    find_longest_variation,
    get_opening_name,
    load_opening_data,
    load_opening_data_from_parquet,
)

MIN_OCCURRENCES = 10  # also used by notebooks/node2vec_umap_embedding.ipynb
N_GAMES = 10000


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
def build_filtered_graph(
    adjacency_matrix: pd.DataFrame, min_occurrences: int
) -> tuple[nx.DiGraph, nx.Graph, pd.Series]:
    """Build the self-loop-free directed graph and its undirected view, both
    dropping openings reached by fewer than min_occurrences games. Shared by
    plot_graph() and notebooks/node2vec_umap_embedding.ipynb."""
    graph = nx.from_pandas_adjacency(adjacency_matrix, create_using=nx.DiGraph)
    graph.remove_edges_from(nx.selfloop_edges(graph))
    occurrences = adjacency_matrix.sum(axis=0)
    # Start's only incoming edge is the artificial self-loop (see get_adjacency_matrix) -
    # use its outgoing transitions instead, the real "games reaching Start" count
    occurrences["Start"] = adjacency_matrix.loc["Start"].sum()
    graph = graph.subgraph([n for n in graph if occurrences[n] >= min_occurrences])
    # forceatlas2's attraction force only looks at outgoing edges (A[i, :]) - on a
    # directed graph, nodes with little outgoing weight lose their pull and collapse
    # into the center under gravity alone. Layout/communities need the symmetric view.
    undirected = graph.to_undirected()
    return graph, undirected, occurrences


# %%
def get_communities(undirected: nx.Graph) -> dict[str, int]:
    """Louvain community id per node. Shared by plot_graph() and
    notebooks/node2vec_umap_embedding.ipynb so both color by the same groups."""
    communities = nx.community.louvain_communities(undirected, weight="weight", seed=0)
    return {n: i for i, c in enumerate(communities) for n in c}


# %%
def draw_graph(
    graph: nx.DiGraph,
    undirected: nx.Graph,
    occurrences: pd.Series,
    max_occurrences: float,
    community_of: dict[str, int],
    filename: str,
    show_labels: bool = True,
) -> None:
    """Forceatlas2 layout + louvain-colored draw of graph/undirected, sized
    relative to max_occurrences. Shared by plot_graph() and
    plot_top_communities(). community_of comes from the caller (not
    recomputed here) so coloring stays consistent with whatever partition
    the caller used to pick/rank this graph in the first place."""
    # forceatlas2's node_size is a layout-space halo radius, not a pixel size -
    # passing raw occurrence counts (up to 1000s) wrecks the physics and yields NaN positions.
    # sqrt scale matches node_size_draw's shape below, else halo underestimates
    # mid/small nodes' drawn footprint and they overlap.
    node_size_layout = {
        n: 0.4 * np.sqrt(occurrences[n] / max_occurrences) for n in graph
    }
    # Gephi "Edge Weight Influence" 0.5 dampens high-count edges' pull on layout -
    # networkx has no such exponent param, so pre-transform weight for this call only
    nx.set_edge_attributes(
        undirected,
        {(u, v): w**0.5 for u, v, w in undirected.edges(data="weight")},
        "weight_sqrt",
    )
    pos = nx.forceatlas2_layout(
        undirected,
        max_iter=10_000,
        node_size=node_size_layout,
        weight="weight_sqrt",
        seed=0,
    )
    node_size_draw = 1000 * np.sqrt([occurrences[n] / max_occurrences for n in graph])

    node_color = [community_of[n] for n in graph]

    edge_width = [
        0.1 + 10 * graph[u][v]["weight"] / max_occurrences for u, v in graph.edges()
    ]

    plt.figure(figsize=(20, 20))  # figsize * dpi = output pixels
    nx.draw_networkx_edges(
        graph,
        pos,
        alpha=1,
        arrows=True,
        arrowsize=5,
        connectionstyle="arc3,rad=0.1",
        width=edge_width,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        node_color=node_color,
        cmap=plt.cm.tab20,
        vmin=0,
        vmax=max(community_of.values()),
        node_size=node_size_draw,
    )
    if show_labels:
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
    plt.savefig(filename, dpi=200)
    plt.close()


# %%
def plot_graph(
    adjacency_matrix: pd.DataFrame,
    n_games: int,
    min_occurrences: int = 5,
    show_labels: bool = True,
) -> None:
    """Draw opening transposition graph: forceatlas2 layout, louvain community
    colors, occurrence-based node/font size. Drops openings reached by fewer
    than min_occurrences games. Self-contained convenience wrapper around
    draw_graph() -- main() builds the graph itself and calls draw_graph()
    directly instead, to share it with plot_top_communities() without
    building twice."""
    graph, undirected, occurrences = build_filtered_graph(
        adjacency_matrix, min_occurrences
    )
    max_occurrences = occurrences.max()
    community_of = get_communities(undirected)
    suffix = "" if show_labels else "_no_labels"
    draw_graph(
        graph,
        undirected,
        occurrences,
        max_occurrences,
        community_of,
        f"images/graph_{n_games}{suffix}.png",
        show_labels,
    )


# %%
def plot_top_communities(
    graph: nx.DiGraph,
    undirected: nx.Graph,
    occurrences: pd.Series,
    community_of: dict[str, int],
    n_games: int,
    top_n: int = 8,
    show_labels: bool = True,
) -> None:
    """Zoom into the top_n largest Louvain communities (ranked by total
    occurrences of their member nodes) and re-layout/draw each individually --
    mirrors the manual per-color Gephi workflow in README.md's 'Detail view'.
    Takes the same graph/community_of as plot_graph() (see its docstring) so
    every zoomed community comes out colored consistently with the partition
    that ranked/selected it, and main() doesn't rebuild the graph twice."""
    max_occurrences = occurrences.max()
    members_by_community = pd.Series(community_of).groupby(community_of).groups

    ranked = sorted(
        members_by_community.values(),
        key=lambda members: occurrences[members].sum(),
        reverse=True,
    )

    for rank, members in enumerate(ranked[:top_n], start=1):
        sub_graph = graph.subgraph(members)
        # .copy(): draw_graph() mutates edge attrs (weight_sqrt) on `undirected` -
        # a bare subgraph() view would write those back into the shared parent graph
        sub_undirected = undirected.subgraph(members).copy()
        draw_graph(
            sub_graph,
            sub_undirected,
            occurrences,
            max_occurrences,
            community_of,
            f"images/graph_{n_games}_community_{rank}.png",
            show_labels,
        )


# %%
def main():
    """Main function"""
    # Positions come from games.sqlite (see database.py), not a live pgn parse
    try:
        OPENINGS = load_opening_data_from_parquet()
    except Exception as e:
        # Network down, HF schema drift, or a corrupt local cache - all unrelated to
        # whether the pipeline can run at all, so fall back to the offline tsv source.
        print(f"load_opening_data_from_parquet() failed ({e}), falling back to tsv")
        OPENINGS = load_opening_data()
    print(f"Longest line: {find_longest_variation(OPENINGS)} halfmoves")
    positions = load_positions(n_games=N_GAMES)
    n_games = positions.shape[0]
    adjacency_matrix = get_adjacency_matrix(positions, OPENINGS)
    save_results(adjacency_matrix, n_games)

    # built once, shared below - avoids rebuilding the graph and re-running
    # Louvain twice for the same adjacency_matrix (draw_graph() called
    # directly here instead of via plot_graph(), which would rebuild again)
    graph, undirected, occurrences = build_filtered_graph(
        adjacency_matrix, MIN_OCCURRENCES
    )
    community_of = get_communities(undirected)
    max_occurrences = occurrences.max()

    draw_graph(
        graph,
        undirected,
        occurrences,
        max_occurrences,
        community_of,
        f"images/graph_{n_games}_no_labels.png",
        show_labels=False,
    )

    draw_graph(
        graph,
        undirected,
        occurrences,
        max_occurrences,
        community_of,
        f"images/graph_{n_games}_labels.png",
    )
    plot_top_communities(
        graph, undirected, occurrences, community_of, n_games, show_labels=True
    )


if __name__ == "__main__":
    main()
