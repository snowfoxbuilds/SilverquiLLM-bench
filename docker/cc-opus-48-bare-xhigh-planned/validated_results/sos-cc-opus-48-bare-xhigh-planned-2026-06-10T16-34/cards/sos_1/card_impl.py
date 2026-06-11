"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}


def _is_instant_or_sorcery(card: Any) -> bool:
    return bool(getattr(card, "card_types", set()) & _INSTANT_SORCERY)


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach.
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
        graveyard = controller.zones[Zone.GRAVEYARD]
        return sum(1 for c in graveyard.get_all() if _is_instant_or_sorcery(c))

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            candidates = [c for c in graveyard.get_all() if _is_instant_or_sorcery(c)]
            if not candidates:
                return  # "may" with no legal target — nothing happens.

            if len(candidates) == 1:
                # Exactly one legal target → auto-select it (per plan).
                chosen = candidates[0]
            else:
                chosen = ctrl.choose_card(
                    candidates,
                    "Cast which instant/sorcery from your graveyard for free? "
                    "(or decline)",
                )
            if chosen is None or chosen not in candidates:
                return

            # "If that spell would be put into your graveyard, exile it
            # instead." Redirect this spell's resolve-time zone move to exile.
            chosen._resolve_to_zone = Zone.EXILE
            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except Exception:
                # Casting failed (e.g. no legal targets for the spell) — clear
                # the redirect so the card is unaffected later.
                if hasattr(chosen, "_resolve_to_zone"):
                    del chosen._resolve_to_zone

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
