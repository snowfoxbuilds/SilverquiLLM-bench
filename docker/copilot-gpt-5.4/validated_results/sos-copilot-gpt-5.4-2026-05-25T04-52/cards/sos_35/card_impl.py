"""Card implementation for Stirring Hopesinger."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class StirringHopesinger(Creature):
    """Stirring Hopesinger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stirring Hopesinger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Bird", "Bard"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.LIFELINK)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying, lifelink\nRepartee — Whenever you cast an instant or sorcery spell that targets "
            "a creature, put a +1/+1 counter on each creature you control.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
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

        def _effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            for permanent in game.get_battlefield(current_controller).get_all():
                if isinstance(permanent, Creature) and getattr(permanent, "controller", None) is current_controller:
                    permanent.plus_one_counters += 1
                    permanent._base_plus_one_counters = permanent.plus_one_counters

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
