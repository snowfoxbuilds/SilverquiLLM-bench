"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Avatar — Legendary.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost.  If that
    spell would be put into your graveyard, exile it instead.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
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
        self.colors = []

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce cost by {1} for each instant/sorcery in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        return sum(
            1
            for card in controller.zones[Zone.GRAVEYARD].get_all()
            if _is_instant_or_sorcery(card)
        )

    def register_triggers(self, game: "GameState") -> None:
        """Attack trigger: free-cast an instant/sorcery from the graveyard."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _attack_condition(game: Any, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source

        def _attack_effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            candidates = [
                c
                for c in ctrl.zones[Zone.GRAVEYARD].get_all()
                if _is_instant_or_sorcery(c)
            ]
            if not candidates:
                return

            if not ctrl.choose_yes_no(
                "Cast an instant or sorcery from your graveyard for free?"
            ):
                return

            chosen = ctrl.choose(candidates, "Choose a card to cast from your graveyard")
            if chosen is None or chosen not in candidates:
                return

            # The cast spell is exiled instead of going to the graveyard.
            chosen._exile_instead_of_graveyard = True  # type: ignore[attr-defined]
            cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_attack_condition,
                effect=_attack_effect,
                source=self,
                controller=controller,
            )
        )
