import pytest

from game_engine import GameEngine
from game_knowledge import (
    DECK_SIZE,
    STARTING_HAND_SIZE,
    Card,
    CardType,
    Phase,
    validate_deck,
)


def make_land(card_id: str) -> Card:
    return Card(id=card_id, type=CardType.LAND, cost=0)


def make_creature(card_id: str, cost: int) -> Card:
    return Card(id=card_id, type=CardType.CREATURE, cost=cost)


def make_deck(land_count: int, creature_costs: list[int]) -> list[Card]:
    cards: list[Card] = []
    cards.extend(make_land(f"land-{idx}") for idx in range(land_count))
    cards.extend(
        make_creature(f"creature-{idx}", cost)
        for idx, cost in enumerate(creature_costs)
    )
    if len(cards) != DECK_SIZE:
        raise ValueError("Test deck must have exactly 20 cards.")
    return cards


def test_validate_deck_requires_exact_size() -> None:
    with pytest.raises(ValueError, match="exactly 20"):
        validate_deck([make_land("x")] * 19)


def test_validate_deck_rejects_negative_creature_cost() -> None:
    bad_deck = [make_land(f"land-{idx}") for idx in range(19)] + [
        make_creature("bad", -1)
    ]
    with pytest.raises(ValueError, match=">= 0"):
        validate_deck(bad_deck)


def test_initialization_draws_opening_hands() -> None:
    deck1 = make_deck(20, [])
    deck2 = make_deck(20, [])
    engine = GameEngine([deck1, deck2], seed=1)
    state = engine.initialize_game()

    assert len(state.players[0].hand) == STARTING_HAND_SIZE
    assert len(state.players[1].hand) == STARTING_HAND_SIZE
    assert len(state.players[0].deck) == DECK_SIZE - STARTING_HAND_SIZE
    assert len(state.players[1].deck) == DECK_SIZE - STARTING_HAND_SIZE
    assert state.phase == Phase.TURN_START


def test_empty_deck_on_draw_causes_loss() -> None:
    deck1 = make_deck(20, [])
    deck2 = make_deck(20, [])
    engine = GameEngine([deck1, deck2], seed=0)
    engine.initialize_game()
    engine.state.players[0].deck = []

    assert len(engine.state.players[0].deck) == 0
    engine.run_turn()

    assert engine.state.phase == Phase.GAME_OVER
    assert engine.state.loser_index == 0
    assert engine.state.winner_index == 1


def test_only_one_land_is_played_per_turn() -> None:
    deck1 = make_deck(20, [])
    deck2 = make_deck(20, [])
    engine = GameEngine([deck1, deck2], seed=0)
    engine.initialize_game()
    player = engine.state.players[0]
    player.deck = [make_land(f"d{idx}") for idx in range(17)]
    player.hand = [make_land("l1"), make_land("l2"), make_land("l3")]
    player.battlefield.lands = []
    player.battlefield.creatures = []

    engine.run_turn()

    assert len(player.battlefield.lands) == 1
    assert player.lands_played_this_turn == 1


def test_creature_play_respects_available_mana() -> None:
    deck1 = make_deck(20, [])
    deck2 = make_deck(20, [])
    engine = GameEngine([deck1, deck2], seed=0)
    engine.initialize_game()
    active = engine.state.players[0]
    active.deck = [make_land(f"d{idx}") for idx in range(14)]
    active.hand = [
        make_land("main-land"),
        make_creature("c3", 3),
        make_creature("c2", 2),
        make_creature("c1", 1),
    ]
    active.battlefield.lands = [make_land("b1"), make_land("b2")]
    active.battlefield.creatures = []

    engine.run_turn()

    creature_costs = sorted(card.cost for card in active.battlefield.creatures)
    assert creature_costs == [3]


def test_no_summoning_sickness_creature_deals_damage_same_turn() -> None:
    deck1 = make_deck(20, [])
    deck2 = make_deck(20, [])
    engine = GameEngine([deck1, deck2], seed=0)
    engine.initialize_game()
    active = engine.state.players[0]
    opponent = engine.state.players[1]
    active.deck = [make_land(f"d{idx}") for idx in range(18)]
    active.hand = [make_land("l1"), make_creature("c1", 1)]
    active.battlefield.lands = []
    active.battlefield.creatures = []
    start_life = opponent.life

    engine.run_turn()

    assert opponent.life == start_life - 1
    assert len(active.battlefield.creatures) == 1


def test_creatures_persist_and_keep_dealing_damage() -> None:
    deck1 = make_deck(20, [])
    deck2 = make_deck(20, [])
    engine = GameEngine([deck1, deck2], seed=0)
    engine.initialize_game()
    p1 = engine.state.players[0]
    p2 = engine.state.players[1]
    p1.deck = [make_land(f"d{idx}") for idx in range(16)]
    p1.hand = [make_land("h1"), make_land("h2")]
    p1.battlefield.lands = [make_land("b1")]
    p1.battlefield.creatures = [make_creature("persist", 2)]
    start_life = p2.life

    engine.run_turn()
    engine.run_turn()
    engine.run_turn()

    assert p2.life == start_life - 4


def test_run_game_ends_by_life_or_empty_deck() -> None:
    deck1 = [make_land("p1-land")] + [
        make_creature(f"p1-c-{idx}", 20) for idx in range(19)
    ]
    deck2 = make_deck(20, [])
    engine = GameEngine([deck1, deck2], seed=0)
    result = engine.run_game(max_turns=40)

    assert result.winner_player_id in (1, 2)
    assert result.loser_player_id in (1, 2)
    assert result.winner_player_id != result.loser_player_id
    assert result.turns_played >= 1


def test_state_is_json_serializable() -> None:
    deck1 = make_deck(20, [])
    deck2 = make_deck(20, [])
    engine = GameEngine([deck1, deck2], seed=3)
    engine.initialize_game()
    engine.run_turn()

    serialized = engine.serialize_state()
    import json

    dumped = json.dumps(serialized, sort_keys=True)
    assert isinstance(dumped, str)
    assert serialized["schema_version"] == 1


def test_events_have_machine_and_human_formats() -> None:
    deck1 = make_deck(20, [])
    deck2 = make_deck(20, [])
    engine = GameEngine([deck1, deck2], seed=5)
    engine.initialize_game()
    engine.run_turn()

    human_logs = engine.human_logs()
    machine_logs = engine.machine_logs()

    assert human_logs
    assert machine_logs
    assert len(human_logs) == len(machine_logs)
    assert all(isinstance(entry, str) and entry for entry in human_logs)
    assert all("action_type" in entry for entry in machine_logs)
    assert all("state_hash_before" in entry for entry in machine_logs)
    assert all("state_hash_after" in entry for entry in machine_logs)


def test_replay_logs_reconstructs_same_state() -> None:
    deck1 = make_deck(20, [])
    deck2 = make_deck(20, [])
    engine = GameEngine([deck1, deck2], seed=9)
    engine.initialize_game()
    initial_state = engine.serialize_state()
    initial_log_count = len(engine.machine_logs())

    engine.run_turn()
    engine.run_turn()

    replayed = GameEngine.replay_to_state(
        initial_state, engine.machine_logs()[initial_log_count:]
    )
    assert replayed == engine.serialize_state()
