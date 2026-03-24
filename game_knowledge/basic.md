# Simplified MTG Engine Specification

## 1) Core Constants

- `PLAYER_COUNT = 2`
- `STARTING_LIFE = 20`
- `DECK_SIZE = 20`
- `STARTING_HAND_SIZE = 7`
- `CARDS_DRAWN_PER_DRAW_STEP = 1`
- `MAX_LANDS_PLAYED_PER_TURN = 1`
- `FIRST_PLAYER_DRAWS_ON_TURN_1 = True`

## 2) Card Model

Each card has:

- `id: str` (unique per physical card instance)
- `type: "LAND" | "CREATURE"`
- `cost: int >= 0` (required for `CREATURE`, ignored for `LAND`)

Validation rules:

- `LAND`: `cost` may be absent or ignored.
- `CREATURE`: `cost` is required and must be `>= 0`.
- Any 20-card deck composition is valid.

## 3) Player State

Each player state contains:

- `id: str`
- `life: int`
- `deck: list[Card]` (deck top position must be defined consistently)
- `hand: list[Card]`
- `battlefield.lands: list[Card]`
- `battlefield.creatures: list[Card]`
- `lands_played_this_turn: int`

## 4) Game State

Game state contains:

- `players: [PlayerState, PlayerState]`
- `active_player_index: 0 | 1`
- `turn_number: int >= 1`
- `phase: "TURN_START" | "DRAW" | "MAIN" | "COMBAT" | "TURN_END" | "GAME_OVER"`
- `winner_index: 0 | 1 | None`
- `loser_index: 0 | 1 | None`

## 5) Initialization Procedure

1. Create 2 players with `life = 20`.
2. Each player provides a valid 20-card deck.
3. Shuffle each deck.
4. Each player draws 7 cards from their own deck.
   - If any required draw cannot be completed (deck empty), that player loses immediately.
5. Set initial turn values:
   - `active_player_index = 0` (or randomize if desired, but use one deterministic policy)
   - `turn_number = 1`
   - `phase = "TURN_START"`
   - `winner_index = None`
   - `loser_index = None`

## 6) Turn Structure (Deterministic Order)

For active player `P`, non-active player `O`:

1. `TURN_START`
   - Set `P.lands_played_this_turn = 0`.

2. `DRAW`
   - `P` attempts to draw 1 card.
   - If `P.deck` is empty before draw, `P` loses immediately and game ends.

3. `MAIN`
   - `P` may play cards from hand in any chosen order, subject to constraints.
   - Track `mana_spent_this_main_phase` (starts at 0 each main phase).
   - Available mana for this main phase is:
     - `available_mana = len(P.battlefield.lands)`
   - Land play rule:
     - At most one land can be played in this turn.
     - On play: move card from hand to `battlefield.lands`, increment `lands_played_this_turn`.
     - This immediately increases the mana ceiling for later creature plays in the same main phase.
   - Creature play rule:
     - Can play if `mana_spent_this_main_phase + creature.cost <= available_mana`.
     - On play: move card from hand to `battlefield.creatures`, increase `mana_spent_this_main_phase` by `creature.cost`.
   - Player may choose to stop and pass out of main phase.

4. `COMBAT` (automatic damage)
   - Total damage dealt by `P` to `O`:
     - `sum(creature.cost for creature in P.battlefield.creatures)`
   - Apply damage immediately to `O.life`.
   - No summoning sickness: creatures played this turn do deal damage this combat.
   - Creatures are persistent: once played, they remain in play.

5. `TURN_END`
   - Check loss conditions.
   - If game is not over:
     - `active_player_index = 1 - active_player_index`
     - `turn_number += 1`
     - `phase = "TURN_START"`

## 7) Loss and Win Conditions

A player loses if:

1. Their `life <= 0`, or
2. They are required to draw but their deck is empty.

Deterministic resolution behavior:

- When a loss condition occurs, game ends immediately (`phase = "GAME_OVER"`).
- `winner_index` is the other player.
- Empty-deck loss is checked only when a draw is attempted.

## 8) Legal Actions API

During `MAIN`, active player actions:

- `PlayLand(card_id)`
  - Preconditions:
    - Card is in hand and type is `LAND`
    - `lands_played_this_turn < 1`
- `PlayCreature(card_id)`
  - Preconditions:
    - Card is in hand and type is `CREATURE`
    - `mana_spent_this_main_phase + card.cost <= len(battlefield.lands)`
- `PassMain()`
  - Ends `MAIN` and advances to `COMBAT`

No player actions are required in other phases (they auto-resolve).

## 9) Engine Invariants

For each player, always enforce:

- `len(deck) + len(hand) + len(battlefield.lands) + len(battlefield.creatures) == 20`
- `lands_played_this_turn in {0, 1}` during a turn
- `mana_spent_this_main_phase <= len(battlefield.lands)` during main phase
- `winner_index` and `loser_index` are both `None` unless phase is `GAME_OVER`
- Once `phase == "GAME_OVER"`, no further state mutation occurs

## 10) Minimal Event Log Schema (Recommended)

Event record fields:

- `type` in:
  - `TURN_STARTED`
  - `CARD_DRAWN`
  - `LAND_PLAYED`
  - `CREATURE_PLAYED`
  - `COMBAT_DAMAGE_APPLIED`
  - `PLAYER_LOST`
  - `GAME_ENDED`
- `turn_number: int`
- `player_index: 0 | 1`
- `payload: dict`

This event model is sufficient for deterministic replay and debugging.
