"""Analyze transposition in chess openings"""


# %%
import networkx as nx
import pandas as pd

from opening_data import (
    find_longest_variation,
    get_positions,
    load_games,
    load_opening_data,
)


# %%
def analyze_games(positions: pd.DataFrame, openings: pd.DataFrame) -> nx.Graph:
    """Iterate over all positions in all games and build a graph where each position is connected to positions that followed in the next move"""
    G = nx.Graph()
    for i, positions in enumerate(positions.values):
        for j, position in enumerate(positions):
            if j == 0:
                continue
            if position is not None and j < 40:
                G.add_edge(position, positions[j - 1])
    return G


# %%
def main():
    """Main function"""
    N_GAMES = 10000
    FILENAME = "files/lichess_elite_2022-04.pgn"
    #  Downloaded from: https://database.nikonoel.fr/
    OPENINGS = load_opening_data()
    print(f"Longest line: {find_longest_variation(OPENINGS)} halfmoves")
    games = load_games(FILENAME)
    positions = get_positions(games, N_GAMES)
    graph = analyze_games(positions, OPENINGS)
    nx.write_gml(graph, "results/graph.gml")


if __name__ == "__main__":
    main()
