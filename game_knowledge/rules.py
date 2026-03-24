"""Rules, constants, and state models for the simplified MTG simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

PLAYER_COUNT = 2
STARTING_LIFE = 20
DECK_SIZE = 20
STARTING_HAND_SIZE = 7
CARDS_DRAWN_PER_DRAW_STEP = 1
MAX_LANDS_PLAYED_PER_TURN = 1
FIRST_PLAYER_DRAWS_ON_TURN_1 = True


class CardType(str, Enum):
    """Card types supported by the rules."""

    LAND = "LAND"
    CREATURE = "CREATURE"


class Phase(str, Enum):
    """Deterministic game phases."""

    TURN_START = "TURN_START"
    DRAW = "DRAW"
    MAIN = "MAIN"
    COMBAT = "COMBAT"
    TURN_END = "TURN_END"
    GAME_OVER = "GAME_OVER"


@dataclass(frozen=True)
class Card:
    """Single card instance in the game."""

    id: str
    type: CardType
    cost: int = 0


@dataclass
class BattlefieldState:
    """Cards currently in play."""

    lands: list[Card] = field(default_factory=list)
    creatures: list[Card] = field(default_factory=list)


@dataclass
class PlayerState:
    """Mutable player state for simulation."""

    id: int
    life: int
    deck: list[Card]
    hand: list[Card] = field(default_factory=list)
    battlefield: BattlefieldState = field(default_factory=BattlefieldState)
    lands_played_this_turn: int = 0


@dataclass
class GameState:
    """Mutable game state for deterministic progression."""

    players: list[PlayerState]
    active_player_index: int = 0
    turn_number: int = 1
    phase: Phase = Phase.TURN_START
    winner_index: int | None = None
    loser_index: int | None = None


GAME_DESCRIPTION = (
    "Two-player simplified MTG simulation. "
    "Each player starts at 20 life with a 20-card deck and draws 7 cards. "
    "A player draws at the start of each turn, may play at most one land, "
    "and may play creatures using land-based mana. "
    "Creatures persist and automatically deal damage equal to their cost each combat. "
    "A player loses at 0 life or when required to draw from an empty deck."
)


def validate_card(card: Card) -> None:
    """Validate a single card against game rules."""
    if card.type == CardType.CREATURE and card.cost < 0:
        raise ValueError("Creature card cost must be >= 0.")


def validate_deck(deck: list[Card]) -> None:
    """Validate deck size and card legality."""
    if len(deck) != DECK_SIZE:
        raise ValueError(f"Deck must contain exactly {DECK_SIZE} cards.")
    for card in deck:
        validate_card(card)


def check_player_invariants(player: PlayerState) -> None:
    """Validate per-player invariants for debugging/tests."""
    zone_total = (
        len(player.deck)
        + len(player.hand)
        + len(player.battlefield.lands)
        + len(player.battlefield.creatures)
    )
    if zone_total != DECK_SIZE:
        raise ValueError("Player zones must always contain exactly 20 cards total.")
    if player.lands_played_this_turn not in (0, 1):
        raise ValueError("lands_played_this_turn must be 0 or 1.")


def check_game_invariants(state: GameState) -> None:
    """Validate global game invariants for debugging/tests."""
    if len(state.players) != PLAYER_COUNT:
        raise ValueError("Game must have exactly two players.")
    for player in state.players:
        check_player_invariants(player)
    if state.phase != Phase.GAME_OVER and (
        state.winner_index is not None or state.loser_index is not None
    ):
        raise ValueError("winner_index and loser_index must be None before GAME_OVER.")
    if state.phase == Phase.GAME_OVER and (
        state.winner_index is None or state.loser_index is None
    ):
        raise ValueError("winner_index and loser_index must be set at GAME_OVER.")
