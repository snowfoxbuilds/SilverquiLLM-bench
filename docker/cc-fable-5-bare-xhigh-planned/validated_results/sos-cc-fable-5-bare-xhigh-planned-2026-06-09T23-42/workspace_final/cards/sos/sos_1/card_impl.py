"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

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
        """{1} less for each instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(
            1
            for card in graveyard.get_all()
            if getattr(card, "card_types", set()) & _SPELL_TYPES
        )

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration
        from engine.zones import move_to_zone

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            candidates = [
                c
                for c in graveyard.get_all()
                if getattr(c, "card_types", set()) & _SPELL_TYPES
            ]
            if not candidates:
                return  # "may" with no legal target — nothing happens
            if not ctrl.choose_yes_no(
                "Cast an instant or sorcery card from your graveyard "
                "without paying its mana cost?"
            ):
                return
            chosen = ctrl.choose_card(
                candidates, "Choose an instant or sorcery card to cast"
            )
            if chosen is None or not graveyard.contains(chosen):
                return
            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except CastingError:
                return

            # "If that spell would be put into your graveyard, exile it
            # instead." — the engine's resolve path moves instants and
            # sorceries stack→graveyard without consulting replacement
            # effects, so redirect at resolution by wrapping the spell's
            # StackObject. Deliberate limitation: a counter that bins the
            # spell directly bypasses this redirect.
            spell_obj = game.stack.peek()
            if spell_obj is None or spell_obj.source is not chosen:
                return
            original_resolve = spell_obj.on_resolve

            def _resolve_then_exile(g: "GameState") -> None:
                original_resolve(g)
                owner = getattr(chosen, "owner", ctrl)
                gy = owner.zones[Zone.GRAVEYARD]
                if gy.contains(chosen):
                    move_to_zone(g, chosen, Zone.GRAVEYARD, Zone.EXILE)

            spell_obj.on_resolve = _resolve_then_exile

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
