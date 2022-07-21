
# Chess openings

## Idea

The opening of a chess game is the initial stage of the game. Both players develop their pieces and try to prepare their middle game. Many openings have standard names, such as _Sicilian Defence_. Opening positions are defined by a given _position_ on the board. A game _transposes_ to a different opening, if it reaches a position which is normally reached by a different move order.

For example, there are two move orders to reach the Queen's Gambit:

Move | Name
--- | ---
d4 | Queen's Pawn game
d5 | Closed Game
c4 | Queen's Gambit

Move | Name
--- | ---
c4 | English Opening
d5 | Anglo-Scandinavian Defense
c4 | Queen's Gambit

We transposed from the English Opening to a Queen's Pawn Game. If we analyze many chess games, we can build a graph, were each node is a known opening position and edges are transpositions between openings (or variants).


## Methology


## Results

## Data

I used the opening data from [Lichess](https://github.com/lichess-org/chess-openings). Each named opening (variant) has a `name` and a `epd` (unique position of the pieces on the board).

The games are downloaded from the [Lichess Elite Database](https://database.nikonoel.fr/). I used the file from April 2022. The file is in `pgn` format. PGN files contain headers with metadata and the list of the moves in the game in Short Algebraic Notation.
