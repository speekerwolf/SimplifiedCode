"""Main entrypoint for running the game simulator."""

from game_engine import Card, GameEngine, Player
from game_knowledge import GAME_DESCRIPTION


def build_minimal_players() -> list[Player]:
    """Create two minimal players with tiny card decks."""
    player_one = Player(player_id=1, deck=[Card(name="P1 Card A"), Card(name="P1 Card B")])
    player_two = Player(player_id=2, deck=[Card(name="P2 Card A"), Card(name="P2 Card B")])
    return [player_one, player_two]


def main() -> None:
    """Run the simulator and print the result."""
    players = build_minimal_players()
    engine = GameEngine(players)
    result = engine.run()

    print("Game description:")
    print(GAME_DESCRIPTION)
    print()
    print(f"Turns played: {result.turns_played}")
    print(f"Winner: Player {result.winner_player_id}")


if __name__ == "__main__":
    main()
