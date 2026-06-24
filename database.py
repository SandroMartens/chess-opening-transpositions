"""Store parsed games and positions in SQLite. Mirrors the schema/pipeline shape of
https://github.com/SandroMartens/Lichess-Win-Predictions/blob/master/create_database.py,
adapted to use epd (this project's key into the opening db) instead of fen+engine eval."""

# %%
import io
import sqlite3
from typing import Iterator

import chess.pgn
import pandas as pd
from tqdm import tqdm

from opening_data import get_opening_name, load_games, load_opening_data

DB_PATH = "games.sqlite"


# %%
def write_games(
    games: Iterator[chess.pgn.Game], n_games: int, db_path: str = DB_PATH
) -> None:
    """Read up to n_games from the pgn iterator and store url, pgn, result and elo
    of normally terminated games in the games table."""
    rows = []
    for _ in tqdm(range(n_games), desc="Reading games", unit=" games"):
        try:
            game = next(games)
        except StopIteration:
            break
        if game.headers["Termination"] != "Normal":
            continue
        result = {"1-0": 1, "0-1": -1}.get(game.headers["Result"], 0)
        rows.append(
            (
                game.headers["LichessURL"],
                game.accept(chess.pgn.StringExporter(headers=False)),
                result,
                game.headers["WhiteElo"],
                game.headers["BlackElo"],
            )
        )

    with sqlite3.connect(db_path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS
                games(
                    url TEXT,
                    pgn TEXT,
                    result INTEGER,
                    elo_white INTEGER,
                    elo_black INTEGER,
                    UNIQUE (url)
                )
            """
        )
        con.executemany(
            """
            INSERT OR IGNORE INTO
                games(url, pgn, result, elo_white, elo_black)
            VALUES
                (?, ?, ?, ?, ?)
            """,
            rows,
        )


# %%
def extract_positions(pgn: str) -> list[tuple[int, str]]:
    """Return (ply, epd) for the first 36 half-moves of a game's mainline."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise RuntimeError("could not parse stored pgn")
    return [
        (move.board().ply(), move.board().epd()) for move in list(game.mainline())[:36]
    ]


# %%
def write_positions(db_path: str = DB_PATH) -> None:
    """Extract epd positions for every game not yet in the positions table."""
    with sqlite3.connect(db_path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS
                positions(
                    game_id INTEGER,
                    ply INTEGER NOT NULL,
                    epd TEXT,
                    opening_name TEXT,
                    UNIQUE (game_id, ply)
                )
            """
        )
        unprocessed_games = con.execute(
            """
            SELECT rowid AS game_id, pgn
            FROM games
            WHERE game_id NOT IN (SELECT game_id FROM positions)
            """
        ).fetchall()

        for game_id, pgn in tqdm(
            unprocessed_games, desc="Extracting positions", unit=" games"
        ):
            rows = [(game_id, ply, epd) for ply, epd in extract_positions(pgn)]
            con.executemany(
                """
                INSERT OR IGNORE INTO
                    positions(game_id, ply, epd)
                VALUES
                    (?, ?, ?)
                """,
                rows,
            )


# %%
def annotate_positions(db_path: str = DB_PATH) -> None:
    """Look up the opening name for every position that doesn't have one yet."""
    openings = load_opening_data()
    with sqlite3.connect(db_path) as con:
        unnamed = con.execute(
            "SELECT rowid, epd FROM positions WHERE opening_name IS NULL"
        ).fetchall()
        for rowid, epd in tqdm(unnamed, desc="Annotating positions", unit=" positions"):
            name = get_opening_name(epd, openings)
            if name is not None:
                con.execute(
                    "UPDATE positions SET opening_name = ? WHERE rowid = ?",
                    (name, rowid),
                )


# %%
def load_positions(db_path: str = DB_PATH, n_games: int | None = None) -> pd.DataFrame:
    """Load the positions table shaped like opening_data.get_positions(): rows=games,
    columns=ply, values=epd. Pass n_games to limit to the first n games."""
    query = "SELECT game_id, ply, epd FROM positions"
    params: tuple = ()
    if n_games is not None:
        query += " WHERE game_id IN (SELECT rowid FROM games LIMIT ?)"
        params = (n_games,)
    with sqlite3.connect(db_path) as con:
        long = pd.read_sql(query, con, params=params)
    return long.pivot(index="game_id", columns="ply", values="epd")


# %%
def main():
    """Main function"""
    N_GAMES = 50000
    FILENAME = "../lichess_elite_2022-04.pgn"
    games = load_games(FILENAME)
    write_games(games, N_GAMES)
    write_positions()
    annotate_positions()


if __name__ == "__main__":
    main()
