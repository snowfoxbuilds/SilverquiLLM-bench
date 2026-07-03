"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_INSTANT_OR_SORCERY = {CardType.INSTANT, CardType.SORCERY}


def _register_exile_instead(game: "GameState", spell: Any, controller: Any) -> object:
    """One-shot replacement: if *spell* would go to a graveyard, exile it.

    Registered against a sentinel source so it is not unregistered when The
    Dawning Archaic leaves the battlefield.  ENGINE LIMITATION: the counter
    path (a local _counter_spell moving the card straight to the graveyard)
    bypasses replacement effects, so a countered spell is not exiled.
    """
    from engine.events import MoveToGraveyardReplacementEvent
    from engine.replacement_effects import ReplacementEffect

    sentinel = object()

    def _condition(g: Any, event: Any) -> bool:
        return event.card is spell

    def _replacement(g: Any, event: Any) -> Any:
        event.destination = "exile"
        g.replacement_manager.unregister(sentinel)
        return event

    game.replacement_manager.register(ReplacementEffect(
        event_type=MoveToGraveyardReplacementEvent,
        source=sentinel,
        condition=_condition,
        replacement=_replacement,
        controller=controller,
    ))
    return sentinel


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
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
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
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

    def cost_reduction(self, game: "GameState") -> int:
        """{1} less per instant/sorcery card in your graveyard (generic only)."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(
            1 for c in graveyard.get_all()
            if getattr(c, "card_types", set()) & _INSTANT_OR_SORCERY
        )

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            graveyard = g.get_graveyard(ctrl)
            candidates = [
                c for c in graveyard.get_all()
                if getattr(c, "card_types", set()) & _INSTANT_OR_SORCERY
            ]
            if not candidates:
                return
            if len(candidates) == 1:
                # Sole legal target is auto-selected; the "may" remains.
                chosen = candidates[0]
                if not ctrl.choose_yes_no(
                    f"Cast {getattr(chosen, 'name', 'card')} from your "
                    "graveyard without paying its mana cost?"
                ):
                    return
            else:
                chosen = ctrl.choose_card(
                    candidates,
                    "Cast an instant or sorcery from your graveyard "
                    "(None to decline)",
                )
                if chosen is None or chosen not in candidates:
                    return

            sentinel = _register_exile_instead(g, chosen, ctrl)
            try:
                cast_spell_free(g, ctrl, chosen, Zone.GRAVEYARD)
            except CastingError:
                # Cast was illegal (e.g. no legal target for the spell) —
                # the card stays in the graveyard; drop the redirect.
                g.replacement_manager.unregister(sentinel)

        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
