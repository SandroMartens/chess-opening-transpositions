# CLAUDE.md

Guidance for Claude Code (claude.ai/code) in this repo.

## Project

Analyzes ~340k Lichess elite-player games for transpositions between named chess openings (e.g. English Opening transposing into Queen's Gambit). Output: graph rendered with Gephi (external, not in repo) into `images/`. Full methodology + results in `README.md`.

## Architecture

`opening_data.py` — shared loading logic (`load_opening_data`, `shorten_names`, `load_games`, `get_positions`, `get_opening_name`, `find_longest_variation`), imported by both pipelines. Fix bugs here once, not in pipeline scripts.

Two parallel pipelines, same load → parse → build graph → save shape:

- `analysis.py` — original. N×N adjacency matrix keyed by **opening name** (string). Records transition only when opening name differs from previous named position. Saves CSV via own `save_results()`.
- `analysis_by_position.py` — newer (current `v2` work). `networkx.Graph` keyed by raw **epd position string**, writes `.gml` via `nx.write_gml`. Less lossy than name-based matrix.

Pipeline steps (same order both files):
1. `load_opening_data()` — reads `files/{a,b,c,d,e}.tsv` (Lichess ECO db, indexed by `epd`), concats, adds synthetic `Start` row for initial position, renames two positions (`Closed Game`, `Open Game`) to disambiguate from generic `Queen's/King's Pawn Game`. `shorten_names()` abbreviates long names (QGD, KID, RL, etc.), strips trailing "Opening"/"Variation"/"Game"/"Defense".
2. `load_games(filename)` — streams games from PGN via `python-chess` (generator, not loaded fully into memory).
3. `get_positions(games, n_games)` — per game, walks mainline, records `epd()` after each of first 36 half-moves (18 full moves) into DataFrame (rows=games, cols=ply).
4. Graph build — `get_adjacency_matrix()` (analysis.py) or `analyze_games()` (analysis_by_position.py): edge per opening/position change.
5. Save — `save_results()` (analysis.py only) writes CSV to `results/`; analysis_by_position.py writes GML directly in `main()`.

## Data dependencies

- `files/*.tsv` — Lichess opening db (committed, from https://github.com/lichess-org/chess-openings).
- `files/lichess_elite_2022-04.pgn` — game db, **not in repo** (gitignored). Download from https://database.nikonoel.fr/, place in `files/` before running either pipeline.
- `results/` — generated CSV/GML/Gephi output, checked in from past runs; large files.

## Running

No package manifest (`requirements.txt`/`pyproject.toml`). Deps: `pandas`, `numpy`, `python-chess` (as `chess.pgn`), `networkx` (analysis_by_position.py only), `tqdm`. Scripts use `# %%` cell markers for interactive/Jupyter-style execution (e.g. VS Code), not pure CLI scripts.

Run a pipeline directly:
```
python analysis_by_position.py
```
Adjust `N_GAMES` and `FILENAME` constants in each file's `main()` to control games processed.

`test_1.py` — profiling script (`timeit`/`line_profiler`), not a test suite. No pytest/unittest setup in repo.
