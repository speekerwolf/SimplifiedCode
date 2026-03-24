# Two-Player Card Game Simulator

Minimal three-module simulator:
- `game_knowledge`: game rules and description
- `game_engine`: deterministic simplified MTG rule engine
- `simulator_wrapper`: executable `main` entrypoint

## Rules Summary

- 2 players, each starts at 20 life
- Each player has a 20-card deck and draws 7 cards to start
- Cards are `LAND` or `CREATURE`
- One land can be played per turn
- Lands provide mana; creatures cost mana to play
- Creatures are persistent and auto-deal damage each combat equal to their cost
- A player loses at 0 life or when required to draw from an empty deck

## Run

```bash
python -m simulator_wrapper.main
```

The run prints turns played, winner/loser, and end reason for one deterministic simulation.

## Implementation Requirements

- The game state must be a fully serializable object (for example JSON-serializable).
- Every player action must produce a log entry in two formats:
  - Human-readable string format (for debugging and audits).
  - Machine-readable structured format (for programmatic replay/analysis).
- The engine must support deterministic replay:
  - Given an initial game state and an ordered list of machine-readable logs,
    replaying those logs must always produce the same resulting game state.

## Suggested Log Schema

Use one log object per action. Keep ordering stable and append-only.

Machine-readable log entry:

```json
{
  "log_version": 1,
  "event_id": "uuid-or-sequential-id",
  "turn_number": 3,
  "phase": "MAIN",
  "action_index_in_turn": 2,
  "actor_player_id": 1,
  "action_type": "PLAY_CREATURE",
  "payload": {
    "card_id": "p1-creature-4",
    "cost": 3
  },
  "state_hash_before": "sha256-hex",
  "state_hash_after": "sha256-hex",
  "timestamp": "2026-03-24T12:34:56Z"
}
```

Human-readable log entry:

```text
Turn 3 MAIN #2 - Player 1 PLAY_CREATURE card=p1-creature-4 cost=3
```

State serialization schema (minimum):

```json
{
  "schema_version": 1,
  "turn_number": 3,
  "active_player_index": 0,
  "phase": "MAIN",
  "players": [
    {
      "id": 1,
      "life": 18,
      "deck": ["card-id-1", "card-id-2"],
      "hand": ["card-id-3"],
      "battlefield": {
        "lands": ["card-id-4"],
        "creatures": ["card-id-5"]
      },
      "lands_played_this_turn": 1
    },
    {
      "id": 2,
      "life": 20,
      "deck": [],
      "hand": [],
      "battlefield": {
        "lands": [],
        "creatures": []
      },
      "lands_played_this_turn": 0
    }
  ],
  "winner_index": null,
  "loser_index": null
}
```

Deterministic replay contract:

- Replay starts from a serialized initial state.
- Logs are applied in ascending order by `(turn_number, action_index_in_turn, event_id)`.
- `state_hash_before` must match current state hash before applying each log.
- After applying a log, computed state hash must equal `state_hash_after`.
- Any mismatch must fail replay immediately with a deterministic error.
