"""Card implementation for Informed Inkwright."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class InformedInkwright(Creature):
    """Informed Inkwright — {1}{W} — Creature — Human Wizard 2/2.

    Vigilance.
    Repartee — Whenever you cast an instant or sorcery spell that targets a
    creature, create a 1/1 white and black Inkling creature token with flying.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Informed Inkwright")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Vigilance\nRepartee — Whenever you cast an instant or sorcery spell "
            "that targets a creature, create a 1/1 white and black Inkling "
            "creature token with flying.",
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
            from engine.game import create_token

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            token = Creature(
                name="Inkling",
                base_power=1,
                base_toughness=1,
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                owner=ctrl,
                controller=ctrl,
            )
            token.colors = {"W", "B"}
            create_token(game, ctrl, token)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

