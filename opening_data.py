"""Load Lichess opening data and PGN games, shared by analysis.py and analysis_by_position.py"""

import io
import os
from typing import Iterator, Optional

import chess.pgn
import pandas as pd
from tqdm import tqdm


def _starting_position() -> pd.DataFrame:
    """Synthetic row for the initial position, absent from both raw sources (tsv and the HF
    parquet dataset) but required as the self-loop anchor in analysis.get_adjacency_matrix."""
    return pd.DataFrame.from_dict(
        data={
            "name": ["Start"],
            "epd": ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"],
            "pgn": None,
            "eco": None,
        },
        orient="columns",
    ).set_index("epd")


def _finalize_openings(openings: pd.DataFrame) -> pd.DataFrame:
    """Shared postprocessing for both loaders: add the Start row, disambiguate two
    positions, then abbreviate names. Keeps the two raw sources interchangeable."""
    openings = pd.concat([openings, _starting_position()])

    # Rename position after 1. d4 d5 to get some differentiating to other 1. d4 openings
    openings.loc[
        "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq -", "name"
    ] = "Closed Game"

    # King's Pawn Game -> Open Game, because later we rename King's Pawn Game to King's Pawn Game
    openings.loc[
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -", "name"
    ] = "Open Game"

    return shorten_names(openings)


def load_opening_data() -> pd.DataFrame:
    """Return a dataframe with the opening data. All openings have a position and a name.
    Data is downloaded from https://github.com/lichess-org/chess-openings."""
    eco_a = pd.read_csv("files/a.tsv", sep="\t", index_col="epd")
    ECO_B = pd.read_csv("files/b.tsv", sep="\t", index_col="epd")
    ECO_C = pd.read_csv("files/c.tsv", sep="\t", index_col="epd")
    ECO_D = pd.read_csv("files/d.tsv", sep="\t", index_col="epd")
    ECO_E = pd.read_csv("files/e.tsv", sep="\t", index_col="epd")

    OPENINGS = pd.concat([eco_a, ECO_B, ECO_C, ECO_D, ECO_E]).drop(columns=["uci"])

    return _finalize_openings(OPENINGS)


def load_opening_data_from_parquet(
    cache_path: str = "chess_openings_hf.parquet",
) -> pd.DataFrame:
    """Alternative to load_opening_data(): same epd/name/pgn/eco fields, sourced from
    https://huggingface.co/datasets/Lichess/chess-openings instead of files/*.tsv. That
    dataset is parquet-only and 226MB (includes a 512x512 img column we don't need), so the
    first call downloads it and caches it at cache_path (gitignored); later calls read the
    local cache instead of re-downloading."""
    if os.path.exists(cache_path):
        openings = pd.read_parquet(cache_path)
    else:
        openings = pd.read_parquet(
            "hf://datasets/Lichess/chess-openings/data/train-00000-of-00001.parquet"
        )
        openings.to_parquet(cache_path)

    openings = openings.drop(columns=["img", "uci", "eco-volume"]).set_index("epd")

    return _finalize_openings(openings)


def shorten_names(openings: pd.DataFrame) -> pd.DataFrame:
    """Replace opening names with their abbreviations and delete "opening", "variation"
    and "game" and "defense" from the end of the name"""
    ABBREVIATIONS = {
        "Queen's Gambit Declined": "QGD",
        "Queen's Gambit Accepted": "QGA",
        "Queen's Gambit": "QG",
        "King's Indian Attack": "KIA",
        "King's Indian Defense": "KID",
        "King's Gambit Declined": "KGD",
        "King's Gambit Accepted": "KGA",
        "King's Gambit": "KG",
        "Ruy Lopez": "RL",
    }

    names = openings["name"]
    for long_name, short_name in ABBREVIATIONS.items():
        names = names.str.replace(long_name, short_name, regex=False)
    names = (
        names.str.replace(" Opening", "", regex=False)
        .str.replace(" Variation", "", regex=False)
        .str.replace(" Game", "", regex=False)
        .str.replace(" Defense", "", regex=False)
    )
    openings["name"] = names

    return openings


def load_games(filename: str) -> Iterator[chess.pgn.Game]:
    """Load n games from the pgn file and return them as a list"""
    with open(filename, encoding="utf8") as pgn_file:
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is not None:
                # Game == None when the end of the file is reached
                yield game

            else:
                break


def get_positions(games: Iterator[chess.pgn.Game], n_games: int) -> pd.DataFrame:
    """Get epd positions from the first 18 moves of a given number of games."""
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
            except IndexError:
                break
            board = move.board()
            positions.append(board.epd())
        games_positions.append(positions)
    return pd.DataFrame(games_positions)


def get_opening_name(epd: str, openings) -> Optional[str]:
    """Return opening name from epd, if exists."""
    if epd in openings.index:
        return openings.loc[epd, "name"]
    return None


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
