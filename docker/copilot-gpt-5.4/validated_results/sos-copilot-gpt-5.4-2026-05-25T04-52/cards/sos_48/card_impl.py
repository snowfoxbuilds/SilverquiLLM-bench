"""Card implementation for Exhibition Tidecaller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


class ExhibitionTidecaller(Creature):
    """Exhibition Tidecaller."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Exhibition Tidecaller")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("subtypes", {"Djinn", "Wizard"})
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self._pending_opus_targets: list[Player] = []
        self._pending_opus_mill_counts: list[int] = []

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            if (
                current_controller is None
                or event.player is not current_controller
                or spell is None
                or not bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
            ):
                return False

            target_player = current_controller.choose(game.players, "Choose a player to mill")
            if target_player not in game.players:
                target_player = game.players[0]
            source._pending_opus_targets.append(target_player)
            mana_spent = getattr(spell, "mana_spent", 0)
            source._pending_opus_mill_counts.append(10 if mana_spent >= 5 else 3)
            return True

        def _effect(game: GameState) -> None:
            if not source.is_on_battlefield(game):
                if source._pending_opus_targets:
                    source._pending_opus_targets.pop()
                if source._pending_opus_mill_counts:
                    source._pending_opus_mill_counts.pop()
                return

            target_player = source._pending_opus_targets.pop() if source._pending_opus_targets else None
            mill_count = source._pending_opus_mill_counts.pop() if source._pending_opus_mill_counts else 3
            if target_player not in game.players:
                return

            library = game.get_library(target_player)
            for _ in range(mill_count):
                if len(library) == 0:
                    break
                card = library.top(1)[0]
                move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
