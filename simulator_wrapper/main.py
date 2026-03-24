"""Main entrypoint for running the game simulator."""

from game_engine import GameEngine
from game_knowledge import DECK_SIZE, GAME_DESCRIPTION, Card, CardType


def build_demo_decks() -> list[list[Card]]:
    """Create deterministic demo decks with lands and creatures."""
    player_one_deck = [
        Card(id=f"p1-land-{idx}", type=CardType.LAND) for idx in range(10)
    ] + [
        Card(id=f"p1-creature-{idx}", type=CardType.CREATURE, cost=(idx % 5) + 1)
        for idx in range(10)
    ]
    player_two_deck = [
        Card(id=f"p2-land-{idx}", type=CardType.LAND) for idx in range(10)
    ] + [
        Card(id=f"p2-creature-{idx}", type=CardType.CREATURE, cost=((idx + 2) % 5) + 1)
        for idx in range(10)
    ]
    assert len(player_one_deck) == DECK_SIZE
    assert len(player_two_deck) == DECK_SIZE
    return [player_one_deck, player_two_deck]


def main() -> None:
    """Run the simulator and print the result."""
    decks = build_demo_decks()
    engine = GameEngine(decks, seed=7)
    result = engine.run_game(max_turns=200)

    print("Game description:")
    print(GAME_DESCRIPTION)
    print()
    print(f"Turns played: {result.turns_played}")
    print(f"Winner: Player {result.winner_player_id}")
    print(f"Loser: Player {result.loser_player_id}")
    print(f"End reason: {result.end_reason}")


if __name__ == "__main__":
    main()
