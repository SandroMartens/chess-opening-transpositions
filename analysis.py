# %%
from typing import Iterator, Optional
import pandas as pd
import chess.pgn
from tqdm import tqdm
from numpy import int32
import io


# %%
def load_opening_data() -> pd.DataFrame:
    """Return a dataframe with the opening data. All openings have a position and a name. Data is downloaded from https://github.com/lichess-org/chess-openings."""
    ECO_A = pd.read_csv("files/a.tsv", sep="\t", index_col="epd")
    ECO_B = pd.read_csv("files/b.tsv", sep="\t", index_col="epd")
    ECO_C = pd.read_csv("files/c.tsv", sep="\t", index_col="epd")
    ECO_D = pd.read_csv("files/d.tsv", sep="\t", index_col="epd")
    ECO_E = pd.read_csv("files/e.tsv", sep="\t", index_col="epd")
    STARTING_POSITION = pd.DataFrame.from_dict(
        data={
            "name": ["Start"],
            "epd": ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"],
            "pgn": None,
            "eco": None,
        },
        orient="columns",
    ).set_index("epd")

    OPENINGS = pd.concat([ECO_A, ECO_B, ECO_C, ECO_D, ECO_E, STARTING_POSITION]).drop(
        columns=["uci"]
    )

    # Rename position after 1. d4 d5 to get some differentiating to other 1. d4 openings
    OPENINGS.loc[
        "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq -", "name"
    ] = "Closed Game"

    OPENINGS = shorten_names(OPENINGS)

    return OPENINGS


def shorten_names(openings: pd.DataFrame) -> pd.DataFrame:
    """Replace opening names with their abbreviations and delete "opening", "variation" and "game" and "defense" from the end of the name"""
    ABBREVIATIONS = {
        "King's Indian Attack": "KIA",
        "King's Indian Defense": "KID",
        "Queen's Gambit": "QG",
        "Queen's Gambit Declined": "QGD",
        "Queen's Gambit Accepted": "QGA",
        "King's Gambit": "KG",
        "King's Gambit Declined": "KGD",
        "King's Gambit Accepted": "KGA",
        "Ruy Lopez": "RL",
    }
    for i in range(openings.shape[0]):
        name = openings.name[i]
        for abbreviation in ABBREVIATIONS:
            if abbreviation in name:
                name = name.replace(abbreviation, ABBREVIATIONS[abbreviation])
        name = (
            name.replace(" Opening", "")
            .replace(" Variation", "")
            .replace(" Game", "")
            .replace(" Defense", "")
        )
        openings.name[i] = name

    return openings


# %%
def load_games(filename: str) -> Iterator[chess.pgn.Game]:
    """Load n games from the pgn file and return them as a list"""
    with open(filename, encoding="utf8") as pgn_file:
        #  Downloaded from: https://database.nikonoel.fr/
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is not None:
                # Game == None when the end of the file is reached
                yield game

            else:
                break


def get_positions(games: Iterator[chess.pgn.Game], n_games: int) -> pd.DataFrame:
    """Get epd positions from the first 15 moves of a given number of games."""
    games_positions = []
    for i in tqdm(range(n_games), desc="Extracting positions", unit=" games"):
        try:
            game = next(games)
        except StopIteration:
            break
        positions = []
        main_line = list(game.mainline())
        for ply in range(36):
            # Get first 18 Moves = 36 half moves
            try:
                move = main_line[ply]
            except:
                break
            board = move.board()
            positions.append(board.epd())
        games_positions.append(positions)
    return pd.DataFrame(games_positions)


# %%
def get_opening_name(epd: str, openings) -> Optional[str]:
    """Return opening name from epd, if exists."""
    if epd in openings.index:
        return openings.loc[epd, "name"]
    else:
        return None


def get_adjacency_matrix(
    positions: pd.DataFrame, openings: pd.DataFrame
) -> pd.DataFrame:
    """Iterate over all moves in all games. If a transposition of named openings is found, add 1 to the adjacency matrix between the two openings"""
    unique_names = openings.name.drop_duplicates()
    adjacency_matrix = pd.DataFrame(
        data=0, index=unique_names, columns=unique_names, dtype=int32
    )

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
    """Remove variations that were not reached. An opening was not reached if it has no incoming edges."""
    # axis=1 for outgoing edges
    # axis=0 for incoming edges
    connected_nodes = adjacency_matrix.loc[(adjacency_matrix != 0).any(axis=0)].index
    adjacency_matrix = adjacency_matrix.loc[connected_nodes, connected_nodes]
    return adjacency_matrix


def find_longest_variation(openings) -> int:
    """Find longest named opening variation"""
    len_max = 0
    for pgn in openings.pgn:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is not None:
            len_mainline = len(list(game.mainline_moves()))
            if len_mainline > len_max:
                len_max = len_mainline
    return len_max


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
    FILENAME = "files/lichess_elite_2022-04.pgn"
    OPENINGS = load_opening_data()
    print(f"Longest line: {find_longest_variation(OPENINGS)} halfmoves")
    games = load_games(FILENAME)
    positions = get_positions(games, N_GAMES)
    adjacency_matrix = get_adjacency_matrix(positions, OPENINGS)
    save_results(adjacency_matrix, N_GAMES)


main()
