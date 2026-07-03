"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    return bool(
        getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}
    )


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar — 7/7.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If
    that spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: GameState) -> int:
        """{1} less per instant/sorcery card in your graveyard (generic only)."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(1 for c in graveyard.get_all() if _is_instant_or_sorcery(c))

    def register_triggers(self, game: GameState) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.events import (
            AttacksTriggeredEvent,
            MoveToGraveyardReplacementEvent,
        )
        from engine.replacement_effects import ReplacementEffect
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: GameState, event: Any) -> bool:
            return getattr(event, "creature", None) is source

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            graveyard = game.get_graveyard(controller)
            candidates = [
                c for c in graveyard.get_all() if _is_instant_or_sorcery(c)
            ]
            if not candidates:
                return
            if len(candidates) == 1:
                # Single legal target: auto-select instead of prompting.
                chosen = candidates[0]
            else:
                chosen = controller.choose_card(
                    candidates,
                    "cast an instant or sorcery from your graveyard "
                    "without paying its mana cost (None to decline)",
                )
            if chosen is None or not graveyard.contains(chosen):
                return

            try:
                cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)
            except CastingError:
                return

            def _exile_instead(g: GameState, event: Any) -> Any:
                event.destination = "exile"
                # One-shot: the effect applies to this cast only.
                g.replacement_manager.unregister(chosen)
                return event

            game.replacement_manager.register(ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=chosen,
                condition=lambda g, e: getattr(e, "card", None) is chosen,
                replacement=_exile_instead,
                controller=controller,
            ))

        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=self.controller,
        ))
