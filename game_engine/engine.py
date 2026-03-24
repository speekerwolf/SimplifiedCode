"""Minimal game engine implementing the current game rules."""

from dataclasses import dataclass

from game_knowledge import MAX_TURNS, WINNER_PLAYER_ID


@dataclass(frozen=True)
class Card:
    """Minimal card model for player decks."""

    name: str


@dataclass
class Player:
    """Minimal player model with an id and a deck."""

    player_id: int
    deck: list[Card]

    def take_turn(self) -> None:
        """Current rule: players take no action on their turn."""
        return None


@dataclass(frozen=True)
class GameResult:
    """Outcome returned by the engine."""

    turns_played: int
    winner_player_id: int


class GameEngine:
    """Runs a deterministic simulation for the minimal rule set."""

    def __init__(self, players: list[Player]) -> None:
        if len(players) != 2:
            raise ValueError("GameEngine requires exactly two players.")
        self.players = players
        self.turns_played = 0

    def run(self) -> GameResult:
        """Run exactly MAX_TURNS alternating turns and return the winner."""
        for turn_index in range(MAX_TURNS):
            active_player = self.players[turn_index % len(self.players)]
            active_player.take_turn()
            self.turns_played += 1

        return GameResult(turns_played=self.turns_played, winner_player_id=WINNER_PLAYER_ID)
