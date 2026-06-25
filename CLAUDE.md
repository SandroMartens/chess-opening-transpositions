# CLAUDE.md

Guidance for Claude Code (claude.ai/code) in this repo.

## Project

Analyzes ~340k Lichess elite-player games for transpositions between named chess openings (e.g. English Opening transposing into Queen's Gambit). Output: graph rendered with Gephi (external, not in repo) into `images/`. Full methodology + results in `README.md`.

## Architecture

`opening_data.py` — shared loading logic (`load_opening_data`, `shorten_names`, `load_games`, `get_positions`, `get_opening_name`, `find_longest_variation`), imported by both pipelines and `database.py`. Fix bugs here once, not in pipeline scripts.

`database.py` — caches parsed games/positions in `games.sqlite` (gitignored, local-only) so pgn skips re-parsing each run:

- `write_games(games, n_games)` — pulls games from `load_games` iterator, keeps only `Termination == "Normal"`, stores `url` (unique), re-serialized headerless pgn move text, `result` (1/-1/0), both Elos in `games` table.
- `extract_positions(pgn)` / `write_positions()` — re-parses each stored game's pgn, records `(ply, epd)` for first 36 half-moves into `positions` (unique on `(game_id, ply)`), skips games already processed.
- `annotate_positions()` — fills `positions.opening_name` for rows still `NULL` via `get_opening_name`.
- `load_positions(n_games=None)` — reads `positions` back pivoted into same (rows=games, cols=ply, values=epd) shape `get_positions()` returns; `n_games` limits to first n games by `games.rowid`. How `analysis.py` gets positions now.

Two parallel analysis pipelines:

- `analysis.py` — N×N adjacency matrix keyed by **opening name** (string). Records transition only when opening name differs from previous named position. Loads positions from `games.sqlite` via `database.load_positions()` — **not** live pgn parse. Saves CSV via own `save_results()`.
- `analysis_by_position.py` — newer (current `v2` work). `networkx.Graph` keyed by raw **epd position string**, writes `.gml` via `nx.write_gml`. Less lossy than name-based matrix. Still does live pgn parse (`load_games` → `get_positions`), not yet wired to `database.py`.

Pipeline steps:

1. `load_opening_data()` — reads `files/{a,b,c,d,e}.tsv` (Lichess ECO db, indexed by `epd`), concats, adds synthetic `Start` row for initial position, renames two positions (`Closed Game`, `Open Game`) to disambiguate from generic `Queen's/King's Pawn Game`. `shorten_names()` abbreviates long names (QGD, KID, RL, etc.), strips trailing "Opening"/"Variation"/"Game"/"Defense".
2. Positions in (rows=games, cols=ply, values=`epd`) shape, from one of two sources: `database.load_positions()` (analysis.py, reads sqlite cache) or live `load_games(filename)` + `get_positions(games, n_games)` (analysis_by_position.py, streams pgn via `python-chess` and walks each mainline for first 36 half-moves).
3. Graph build — `get_adjacency_matrix()` (analysis.py) or `analyze_games()` (analysis_by_position.py): edge per opening/position change.
4. Save — `save_results()` (analysis.py only) writes CSV to `results/`, then `analysis.py` also renders PNG via `nx.from_pandas_adjacency` → `nx.draw_networkx_edges/_nodes` (edge width and node/font size scaled by occurrence count) → `plt.savefig` (quick preview; Gephi still does real layout); analysis_by_position.py writes GML directly in `main()`.

## Data dependencies

- `files/*.tsv` — Lichess opening db (committed, from https://github.com/lichess-org/chess-openings).
- `lichess_elite_2022-04.pgn` — game db, **not in repo** (gitignored). Download from https://database.nikonoel.fr/. Path set per script via `FILENAME` (see Running) — place file where each script expects it before running.
- `games.sqlite` — **not in repo** (gitignored), local cache built by `database.py` from pgn (`games` + `positions` tables). `analysis.py` reads from this, not pgn directly.
- `results/`, `images/graph_*.png` — generated CSV/GML/Gephi/preview-PNG output, gitignored; regenerate locally via pipelines.

## Running

uv-managed: `pyproject.toml` + `uv.lock` + `.venv`. Deps: `pandas`, `numpy`, `python-chess` (as `chess.pgn`), `networkx`, `matplotlib`, `tqdm`. `uv add <pkg>` to add, `uv run python <file>` to run inside venv. Scripts use `# %%` cell markers for interactive/Jupyter-style execution (e.g. VS Code), not pure CLI scripts.

Build sqlite cache, then run `analysis.py`:

```sh
uv run python database.py
uv run python analysis.py
```

`analysis_by_position.py` still parses pgn live, no cache step needed:

```sh
uv run python analysis_by_position.py
```

Adjust `N_GAMES` and `FILENAME`/`db_path` constants in each file's `main()` to control games processed. Note: `analysis_by_position.py` and `database.py` currently point `FILENAME` at different paths (`files/lichess_elite_2022-04.pgn` vs `../lichess_elite_2022-04.pgn`).

`test_1.py` — profiling script (`timeit`/`line_profiler`), not test suite. No pytest/unittest setup in repo (plain `assert` files under `tests/`, run directly via `uv run python tests/test_*.py`).

Notebooks under `notebooks/` are stripped of outputs/metadata on commit via `nbstripout` (dev dep, filter declared in `.gitattributes`). The filter itself lives in local `.git/config`, not shared by the clone — run `uv run nbstripout --install --attributes .gitattributes` once per clone after `uv sync`.
