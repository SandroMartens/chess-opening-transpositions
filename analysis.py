"""Analyze transposition in chess openings"""

# %%
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from numpy import int32
from tqdm import tqdm

from opening_data import (
    find_longest_variation,
    get_opening_name,
    get_positions,
    load_games,
    load_opening_data,
)


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
def main():
    """Main function"""
    N_GAMES = 100
    FILENAME = "../lichess_elite_2022-04.pgn"
    #  Downloaded from: https://database.nikonoel.fr/
    OPENINGS = load_opening_data()
    print(f"Longest line: {find_longest_variation(OPENINGS)} halfmoves")
    games = load_games(FILENAME)
    positions = get_positions(games, N_GAMES)
    adjacency_matrix = get_adjacency_matrix(positions, OPENINGS)
    save_results(adjacency_matrix, N_GAMES)

    graph = nx.from_pandas_adjacency(adjacency_matrix)
    nx.draw(graph, with_labels=True, node_size=200, font_size=6)
    plt.savefig(f"results/graph_{N_GAMES}.png", dpi=200)


if __name__ == "__main__":
    main()
