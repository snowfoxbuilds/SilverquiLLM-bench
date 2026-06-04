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
    """The Dawning Archaic — {10} — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard. Reach. Whenever The Dawning Archaic attacks, you may cast
    target instant or sorcery card from your graveyard without paying its mana
    cost. If that spell would be put into your graveyard, exile it instead.

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
        """Costs {1} less per instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        gy = controller.zones[Zone.GRAVEYARD]
        return sum(1 for c in gy.get_all() if _is_instant_or_sorcery(c))

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return getattr(event, "creature", None) is source

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            controller = source.controller
            if controller is None:
                return
            gy = controller.zones[Zone.GRAVEYARD]
            candidates = [c for c in gy.get_all() if _is_instant_or_sorcery(c)]
            if not candidates:
                return

            # "you may cast"
            try:
                if not controller.choose_yes_no(
                    "Cast an instant or sorcery from your graveyard for free?"
                ):
                    return
            except Exception:
                return

            try:
                chosen = controller.choose_card(
                    candidates, "Choose an instant or sorcery to cast"
                )
            except Exception:
                chosen = None
            if chosen is None or not gy.contains(chosen):
                return

            # Replacement: if this spell would hit the graveyard, exile instead.
            chosen.replace_graveyard_with_exile = True
            try:
                cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)
            except Exception:
                # Casting failed (e.g. no legal target); revert the flag.
                chosen.replace_graveyard_with_exile = False

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
