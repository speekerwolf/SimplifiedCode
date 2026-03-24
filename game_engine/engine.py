"""Game engine implementing the simplified MTG rules."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from itertools import count

from game_knowledge import (
    CARDS_DRAWN_PER_DRAW_STEP,
    FIRST_PLAYER_DRAWS_ON_TURN_1,
    MAX_LANDS_PLAYED_PER_TURN,
    STARTING_HAND_SIZE,
    STARTING_LIFE,
    BattlefieldState,
    Card,
    CardType,
    GameState,
    Phase,
    PlayerState,
    check_game_invariants,
    validate_deck,
)


@dataclass
class Event:
    """Action log with machine and human-readable fields."""

    log_version: int
    event_id: str
    turn_number: int
    phase: str
    action_index_in_turn: int
    actor_player_id: int
    action_type: str
    payload: dict[str, int | str | None] = field(default_factory=dict)
    state_hash_before: str = ""
    state_hash_after: str = ""
    human_readable: str = ""

    def to_machine_dict(self) -> dict[str, int | str | dict[str, int | str | None]]:
        """Return machine-readable serialization for this event."""
        return {
            "log_version": self.log_version,
            "event_id": self.event_id,
            "turn_number": self.turn_number,
            "phase": self.phase,
            "action_index_in_turn": self.action_index_in_turn,
            "actor_player_id": self.actor_player_id,
            "action_type": self.action_type,
            "payload": self.payload,
            "state_hash_before": self.state_hash_before,
            "state_hash_after": self.state_hash_after,
        }


@dataclass(frozen=True)
class GameResult:
    """Outcome returned by the engine."""

    turns_played: int
    winner_player_id: int
    loser_player_id: int
    end_reason: str
    events: list[Event]


class GameEngine:
    """Runs a deterministic simulation for the simplified MTG rule set."""

    def __init__(self, player_decks: list[list[Card]], seed: int | None = None) -> None:
        if len(player_decks) != 2:
            raise ValueError("GameEngine requires exactly two player decks.")
        for deck in player_decks:
            validate_deck(deck)
        self._rng = random.Random(seed)
        players = [
            PlayerState(id=1, life=STARTING_LIFE, deck=list(player_decks[0])),
            PlayerState(id=2, life=STARTING_LIFE, deck=list(player_decks[1])),
        ]
        self.state = GameState(
            players=players,
            active_player_index=0,
            turn_number=1,
            phase=Phase.TURN_START,
        )
        self.events: list[Event] = []
        self._event_counter = count(1)
        self._action_index_in_turn = 0

    @staticmethod
    def _card_to_dict(card: Card) -> dict[str, int | str]:
        return {"id": card.id, "type": card.type.value, "cost": card.cost}

    @staticmethod
    def _card_from_dict(raw: dict[str, int | str]) -> Card:
        return Card(
            id=str(raw["id"]), type=CardType(str(raw["type"])), cost=int(raw["cost"])
        )

    @classmethod
    def _player_to_dict(cls, player: PlayerState) -> dict[str, object]:
        return {
            "id": player.id,
            "life": player.life,
            "deck": [cls._card_to_dict(card) for card in player.deck],
            "hand": [cls._card_to_dict(card) for card in player.hand],
            "battlefield": {
                "lands": [cls._card_to_dict(card) for card in player.battlefield.lands],
                "creatures": [
                    cls._card_to_dict(card) for card in player.battlefield.creatures
                ],
            },
            "lands_played_this_turn": player.lands_played_this_turn,
        }

    @classmethod
    def _player_from_dict(cls, raw: dict[str, object]) -> PlayerState:
        battlefield = raw["battlefield"]
        battlefield_lands = [cls._card_from_dict(card) for card in battlefield["lands"]]
        battlefield_creatures = [
            cls._card_from_dict(card) for card in battlefield["creatures"]
        ]
        return PlayerState(
            id=int(raw["id"]),
            life=int(raw["life"]),
            deck=[cls._card_from_dict(card) for card in raw["deck"]],
            hand=[cls._card_from_dict(card) for card in raw["hand"]],
            battlefield=BattlefieldState(
                lands=battlefield_lands,
                creatures=battlefield_creatures,
            ),
            lands_played_this_turn=int(raw["lands_played_this_turn"]),
        )

    def serialize_state(self) -> dict[str, object]:
        """Return a JSON-serializable state object."""
        return {
            "schema_version": 1,
            "turn_number": self.state.turn_number,
            "active_player_index": self.state.active_player_index,
            "phase": self.state.phase.value,
            "players": [self._player_to_dict(player) for player in self.state.players],
            "winner_index": self.state.winner_index,
            "loser_index": self.state.loser_index,
        }

    def state_hash(self) -> str:
        """Return stable hash for current serialized state."""
        payload = json.dumps(
            self.serialize_state(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def human_logs(self) -> list[str]:
        """Return human-readable action logs."""
        return [event.human_readable for event in self.events]

    def machine_logs(
        self,
    ) -> list[dict[str, int | str | dict[str, int | str | None]]]:
        """Return machine-readable action logs."""
        return [event.to_machine_dict() for event in self.events]

    def _log_action(
        self,
        *,
        actor_index: int,
        action_type: str,
        payload: dict[str, int | str | None],
        before_hash: str,
        human_readable: str,
    ) -> None:
        self._action_index_in_turn += 1
        event = Event(
            log_version=1,
            event_id=f"evt-{next(self._event_counter)}",
            turn_number=self.state.turn_number,
            phase=self.state.phase.value,
            action_index_in_turn=self._action_index_in_turn,
            actor_player_id=self.state.players[actor_index].id,
            action_type=action_type,
            payload=payload,
            state_hash_before=before_hash,
            state_hash_after=self.state_hash(),
            human_readable=human_readable,
        )
        self.events.append(event)

    def initialize_game(self) -> GameState:
        """Shuffle decks and draw opening hands."""
        for player in self.state.players:
            self._rng.shuffle(player.deck)
        for player_index in range(len(self.state.players)):
            for _ in range(STARTING_HAND_SIZE):
                if not self._draw_card(player_index):
                    self._set_game_over(
                        loser_index=player_index, reason="EMPTY_DECK_ON_OPENING_DRAW"
                    )
                    return self.state
        check_game_invariants(self.state)
        return self.state

    def _draw_card(self, player_index: int) -> bool:
        player = self.state.players[player_index]
        if not player.deck:
            return False
        before_hash = self.state_hash()
        card = player.deck.pop(0)
        player.hand.append(card)
        self._log_action(
            actor_index=player_index,
            action_type="DRAW_CARD",
            payload={"card_id": card.id},
            before_hash=before_hash,
            human_readable=f"Turn {self.state.turn_number} {self.state.phase.value} - "
            f"Player {player.id} DRAW_CARD card={card.id}",
        )
        return True

    def _set_game_over(self, loser_index: int, reason: str) -> None:
        before_loss_hash = self.state_hash()
        self.state.phase = Phase.GAME_OVER
        self.state.loser_index = loser_index
        self.state.winner_index = 1 - loser_index
        loser_id = self.state.players[loser_index].id
        winner_id = self.state.players[self.state.winner_index].id
        self._log_action(
            actor_index=loser_index,
            action_type="PLAYER_LOST",
            payload={"reason": reason},
            before_hash=before_loss_hash,
            human_readable=f"Turn {self.state.turn_number} GAME_OVER - "
            f"Player {loser_id} PLAYER_LOST reason={reason}",
        )
        before_end_hash = self.state_hash()
        self._log_action(
            actor_index=self.state.winner_index,
            action_type="GAME_ENDED",
            payload={"reason": reason},
            before_hash=before_end_hash,
            human_readable=f"Turn {self.state.turn_number} GAME_OVER - "
            f"Player {winner_id} GAME_ENDED reason={reason}",
        )

    def _check_life_loss(self) -> bool:
        for player_index, player in enumerate(self.state.players):
            if player.life <= 0:
                self._set_game_over(
                    loser_index=player_index, reason="LIFE_REACHED_ZERO"
                )
                return True
        return False

    def _play_main_phase(self, player: PlayerState) -> None:
        mana_spent = 0
        played_land = False

        if not played_land:
            for idx, card in enumerate(player.hand):
                if (
                    card.type == CardType.LAND
                    and player.lands_played_this_turn < MAX_LANDS_PLAYED_PER_TURN
                ):
                    before_hash = self.state_hash()
                    player.hand.pop(idx)
                    player.battlefield.lands.append(card)
                    player.lands_played_this_turn += 1
                    played_land = True
                    self._log_action(
                        actor_index=self.state.active_player_index,
                        action_type="PLAY_LAND",
                        payload={"card_id": card.id},
                        before_hash=before_hash,
                        human_readable=f"Turn {self.state.turn_number} MAIN - "
                        f"Player {player.id} PLAY_LAND card={card.id}",
                    )
                    break

        while True:
            available_mana = len(player.battlefield.lands)
            candidate_index = None
            candidate_card = None
            for idx, card in enumerate(player.hand):
                if card.type != CardType.CREATURE:
                    continue
                if mana_spent + card.cost <= available_mana:
                    if candidate_card is None or card.cost > candidate_card.cost:
                        candidate_index = idx
                        candidate_card = card
            if candidate_card is None or candidate_index is None:
                break
            before_hash = self.state_hash()
            player.hand.pop(candidate_index)
            player.battlefield.creatures.append(candidate_card)
            mana_spent += candidate_card.cost
            self._log_action(
                actor_index=self.state.active_player_index,
                action_type="PLAY_CREATURE",
                payload={"card_id": candidate_card.id, "cost": candidate_card.cost},
                before_hash=before_hash,
                human_readable=f"Turn {self.state.turn_number} MAIN - "
                f"Player {player.id} PLAY_CREATURE card={candidate_card.id} "
                f"cost={candidate_card.cost}",
            )

    def _combat(self, active_player: PlayerState, opponent: PlayerState) -> None:
        before_hash = self.state_hash()
        damage = sum(creature.cost for creature in active_player.battlefield.creatures)
        opponent.life -= damage
        self._log_action(
            actor_index=self.state.active_player_index,
            action_type="COMBAT_DAMAGE",
            payload={"damage": damage, "opponent_life": opponent.life},
            before_hash=before_hash,
            human_readable=f"Turn {self.state.turn_number} COMBAT - "
            f"Player {active_player.id} COMBAT_DAMAGE damage={damage}",
        )

    def run_turn(self) -> None:
        """Run a single full turn for the active player."""
        if self.state.phase == Phase.GAME_OVER:
            return

        active_index = self.state.active_player_index
        active_player = self.state.players[active_index]
        opponent = self.state.players[1 - active_index]
        self._action_index_in_turn = 0

        self.state.phase = Phase.TURN_START
        active_player.lands_played_this_turn = 0
        self._log_action(
            actor_index=active_index,
            action_type="TURN_STARTED",
            payload={},
            before_hash=self.state_hash(),
            human_readable=f"Turn {self.state.turn_number} TURN_START - "
            f"Player {active_player.id} TURN_STARTED",
        )

        self.state.phase = Phase.DRAW
        draws_this_turn = CARDS_DRAWN_PER_DRAW_STEP
        if (
            self.state.turn_number == 1
            and active_index == 0
            and not FIRST_PLAYER_DRAWS_ON_TURN_1
        ):
            draws_this_turn = 0
        for _ in range(draws_this_turn):
            if not self._draw_card(active_index):
                self._set_game_over(
                    loser_index=active_index, reason="EMPTY_DECK_ON_DRAW"
                )
                return

        self.state.phase = Phase.MAIN
        self._play_main_phase(active_player)

        self.state.phase = Phase.COMBAT
        self._combat(active_player, opponent)
        if self._check_life_loss():
            return

        self.state.phase = Phase.TURN_END
        check_game_invariants(self.state)
        before_hash = self.state_hash()
        next_active_index = 1 - active_index
        next_turn_number = self.state.turn_number + 1
        self.state.active_player_index = 1 - active_index
        self.state.turn_number += 1
        self.state.phase = Phase.TURN_START
        self._log_action(
            actor_index=active_index,
            action_type="END_TURN",
            payload={
                "next_active_player_id": self.state.players[next_active_index].id,
                "next_turn_number": next_turn_number,
            },
            before_hash=before_hash,
            human_readable=f"Turn {next_turn_number} TURN_START - "
            f"Player {self.state.players[next_active_index].id} NEXT_TURN_READY",
        )

    def run_game(self, max_turns: int = 100) -> GameResult:
        """Run turns until terminal state or max turn limit."""
        self.initialize_game()
        if self.state.phase == Phase.GAME_OVER:
            winner = self.state.players[self.state.winner_index]
            loser = self.state.players[self.state.loser_index]
            return GameResult(
                turns_played=self.state.turn_number - 1,
                winner_player_id=winner.id,
                loser_player_id=loser.id,
                end_reason="OPENING_DRAW",
                events=list(self.events),
            )

        while (
            self.state.phase != Phase.GAME_OVER and self.state.turn_number <= max_turns
        ):
            self.run_turn()

        if self.state.phase != Phase.GAME_OVER:
            raise RuntimeError("Game exceeded max_turns without a winner.")

        winner = self.state.players[self.state.winner_index]
        loser = self.state.players[self.state.loser_index]
        last_reason = str(self.events[-1].payload.get("reason", "UNKNOWN"))
        return GameResult(
            turns_played=self.state.turn_number - 1,
            winner_player_id=winner.id,
            loser_player_id=loser.id,
            end_reason=last_reason,
            events=list(self.events),
        )

    @classmethod
    def from_serialized_state(
        cls,
        serialized_state: dict[str, object],
        *,
        seed: int | None = None,
    ) -> GameEngine:
        """Build engine from serialized state."""
        players = [
            cls._player_from_dict(player) for player in serialized_state["players"]
        ]
        engine = cls.__new__(cls)
        engine._rng = random.Random(seed)
        engine.state = GameState(players=players)
        engine.state.turn_number = int(serialized_state["turn_number"])
        engine.state.active_player_index = int(serialized_state["active_player_index"])
        engine.state.phase = Phase(str(serialized_state["phase"]))
        engine.state.winner_index = serialized_state["winner_index"]
        engine.state.loser_index = serialized_state["loser_index"]
        engine.events = []
        engine._event_counter = count(1)
        engine._action_index_in_turn = 0
        return engine

    @staticmethod
    def replay_to_state(
        initial_state: dict[str, object],
        logs: list[dict[str, object]],
    ) -> dict[str, object]:
        """Deterministically replay machine logs and return resulting state."""
        engine = GameEngine.from_serialized_state(initial_state, seed=0)

        for log in logs:
            engine._apply_replay_action(log)
            if str(log["state_hash_after"]) != engine.state_hash():
                raise ValueError("state_hash_after mismatch during replay.")

        return engine.serialize_state()

    def _apply_replay_action(self, log: dict[str, object]) -> None:
        action_type = str(log["action_type"])
        actor_player_id = int(log["actor_player_id"])
        payload = log.get("payload", {})
        actor_index = self._player_index_by_id(actor_player_id)

        if action_type == "TURN_STARTED":
            self.state.turn_number = int(log["turn_number"])
            self.state.active_player_index = actor_index
            self.state.phase = Phase.TURN_START
            self.state.players[actor_index].lands_played_this_turn = 0
            self._action_index_in_turn = int(log["action_index_in_turn"])
            return
        if action_type == "DRAW_CARD":
            self.state.phase = Phase.DRAW
            player = self.state.players[actor_index]
            card_id = str(payload["card_id"])
            if not player.deck or player.deck[0].id != card_id:
                raise ValueError("Replay draw does not match deck top.")
            player.hand.append(player.deck.pop(0))
            self._action_index_in_turn = int(log["action_index_in_turn"])
            return
        if action_type == "PLAY_LAND":
            self.state.phase = Phase.MAIN
            player = self.state.players[actor_index]
            card_id = str(payload["card_id"])
            card_index = self._find_card_index(player.hand, card_id, CardType.LAND)
            player.battlefield.lands.append(player.hand.pop(card_index))
            player.lands_played_this_turn += 1
            self._action_index_in_turn = int(log["action_index_in_turn"])
            return
        if action_type == "PLAY_CREATURE":
            self.state.phase = Phase.MAIN
            player = self.state.players[actor_index]
            card_id = str(payload["card_id"])
            card_index = self._find_card_index(player.hand, card_id, CardType.CREATURE)
            player.battlefield.creatures.append(player.hand.pop(card_index))
            self._action_index_in_turn = int(log["action_index_in_turn"])
            return
        if action_type == "COMBAT_DAMAGE":
            self.state.phase = Phase.COMBAT
            opponent = self.state.players[1 - actor_index]
            opponent.life = int(payload["opponent_life"])
            self._action_index_in_turn = int(log["action_index_in_turn"])
            return
        if action_type == "PLAYER_LOST":
            self.state.phase = Phase.GAME_OVER
            self.state.loser_index = actor_index
            self.state.winner_index = 1 - actor_index
            self._action_index_in_turn = int(log["action_index_in_turn"])
            return
        if action_type == "GAME_ENDED":
            self.state.phase = Phase.GAME_OVER
            self._action_index_in_turn = int(log["action_index_in_turn"])
            return
        if action_type == "END_TURN":
            self.state.phase = Phase.TURN_START
            self.state.turn_number = int(payload["next_turn_number"])
            self.state.active_player_index = self._player_index_by_id(
                int(payload["next_active_player_id"])
            )
            self._action_index_in_turn = int(log["action_index_in_turn"])
            return
        raise ValueError(f"Unsupported replay action: {action_type}")

    def _player_index_by_id(self, player_id: int) -> int:
        for index, player in enumerate(self.state.players):
            if player.id == player_id:
                return index
        raise ValueError(f"Unknown player id in replay: {player_id}")

    @staticmethod
    def _find_card_index(cards: list[Card], card_id: str, card_type: CardType) -> int:
        for idx, card in enumerate(cards):
            if card.id == card_id and card.type == card_type:
                return idx
        raise ValueError(f"Card not found in expected zone: {card_id}")
