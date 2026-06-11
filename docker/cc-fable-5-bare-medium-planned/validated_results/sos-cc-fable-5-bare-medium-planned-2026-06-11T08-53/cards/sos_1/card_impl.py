"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {"Legendary"})
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
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(1 for c in graveyard.get_all() if _is_instant_or_sorcery(c))

    def register_triggers(self, game: GameState) -> None:
        from engine.events import (
            AttacksTriggeredEvent,
            SpellGoesToGraveyardReplacementEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free
            from engine.replacement_effects import ReplacementEffect

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            graveyard = game.get_graveyard(ctrl)
            candidates = [
                c for c in graveyard.get_all() if _is_instant_or_sorcery(c)
            ]
            if not candidates:
                return
            if len(candidates) == 1:
                # Single legal target — auto-select instead of prompting.
                chosen = candidates[0]
            else:
                try:
                    chosen = ctrl.choose_card(
                        candidates,
                        "Cast an instant or sorcery from your graveyard "
                        "without paying its mana cost? (None to decline)",
                    )
                except Exception:
                    chosen = None
            if chosen is None:
                return

            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except CastingError:
                return

            # If that spell would go to the graveyard, exile it instead
            # (one-shot — applies only to this casting of the spell).
            def _replace(g: Any, event: Any) -> Any:
                event.destination = "exile"
                g.replacement_manager.unregister(chosen)
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=SpellGoesToGraveyardReplacementEvent,
                    source=chosen,
                    condition=lambda g, ev: ev.card is chosen,
                    replacement=_replace,
                    controller=ctrl,
                )
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
