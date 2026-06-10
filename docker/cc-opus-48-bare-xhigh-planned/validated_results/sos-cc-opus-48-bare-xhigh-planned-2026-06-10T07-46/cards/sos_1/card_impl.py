"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _instant_or_sorcery(card: Any) -> bool:
    return bool(getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Avatar.

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
        ctrl = self.controller
        if ctrl is None:
            return 0
        return sum(
            1 for c in ctrl.zones[Zone.GRAVEYARD].get_all() if _instant_or_sorcery(c)
        )

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            return getattr(event, "creature", None) is source

        def _effect(g: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            candidates = [
                c for c in ctrl.zones[Zone.GRAVEYARD].get_all() if _instant_or_sorcery(c)
            ]
            if not candidates:
                return
            # "may cast target ..." — if exactly one legal target, auto-select
            # it; otherwise let the controller choose one (or decline with None).
            if len(candidates) == 1:
                chosen = candidates[0]
            else:
                chosen = ctrl.choose_card(
                    candidates,
                    "cast an instant or sorcery from your graveyard without "
                    "paying its mana cost",
                )
            if chosen is None or chosen not in candidates:
                return
            # "If that spell would be put into your graveyard, exile it
            # instead." — handled by the _exile_on_resolve flag read in
            # engine.casting._resolve_spell.
            chosen._exile_on_resolve = True
            try:
                cast_spell_free(g, ctrl, chosen, Zone.GRAVEYARD)
            except Exception:
                # No legal target / cannot be cast — leave it in the graveyard.
                chosen._exile_on_resolve = False

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
