"""Card implementation for Melancholic Poet."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    GainsLifeTriggeredEvent,
    LosesLifeTriggeredEvent,
    SpellCastTriggeredEvent,
)
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_repartee_spell(game: GameState, source: Creature, event: SpellCastTriggeredEvent) -> bool:
    current_controller = getattr(source, "controller", None)
    if current_controller is None or event.player is not current_controller:
        return False
    spell = event.spell
    if spell is None:
        return False
    card_types = getattr(spell, "card_types", set())
    if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
        return False
    return any(
        isinstance(target, Creature) and target.is_on_battlefield(game)
        for target in getattr(spell, "_casting_targets", [])
    )


class MelancholicPoet(Creature):
    """Melancholic Poet."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Melancholic Poet")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Elf", "Bard"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Repartee — Whenever you cast an instant or sorcery spell that targets a creature, "
            "each opponent loses 1 life and you gain 1 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            return _is_repartee_spell(game, source, event)

        def _effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            for player in game.players:
                if player is current_controller:
                    continue
                player.life -= 1
                game.trigger_manager.fire_event(
                    game,
                    LosesLifeTriggeredEvent(player=player, amount=1),
                )
            current_controller.life += 1
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=current_controller, amount=1),
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
