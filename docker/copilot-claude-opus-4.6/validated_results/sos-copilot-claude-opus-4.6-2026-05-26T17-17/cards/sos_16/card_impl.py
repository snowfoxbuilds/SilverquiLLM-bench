"""Card implementation for Graduation Day."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment, Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class GraduationDay(Enchantment):
    """Graduation Day — {W} — Enchantment.

    Repartee — Whenever you cast an instant or sorcery spell that targets
    a creature, put a +1/+1 counter on target creature you control.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Graduation Day")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Repartee — Whenever you cast an instant or sorcery spell that "
            "targets a creature, put a +1/+1 counter on target creature you control.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the Repartee trigger."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: SpellCastTriggeredEvent) -> bool:
            spell = event.spell
            caster = event.player
            ctrl = getattr(source, "controller", None)
            if caster is not ctrl:
                return False
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Check if any target is a creature
            targets = getattr(event, "targets", None) or []
            for t in targets:
                if CardType.CREATURE in getattr(t, "card_types", set()):
                    return True
            return False

        def _effect(game: "GameState") -> None:
            from engine.game import add_counter

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Put a +1/+1 counter on target creature you control
            bf = game.get_battlefield(ctrl).get_all()
            for obj in bf:
                if isinstance(obj, Creature) or CardType.CREATURE in getattr(obj, "card_types", set()):
                    add_counter(game, obj, "+1/+1", 1)
                    if hasattr(obj, "_base_plus_one_counters"):
                        obj._base_plus_one_counters = obj.plus_one_counters
                    break

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

