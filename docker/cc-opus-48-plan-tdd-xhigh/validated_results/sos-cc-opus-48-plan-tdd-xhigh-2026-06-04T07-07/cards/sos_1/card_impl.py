"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return bool(types & {CardType.INSTANT, CardType.SORCERY})


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 Legendary Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.  Reach.  Whenever The Dawning Archaic attacks, you may
    cast target instant or sorcery card from your graveyard without paying
    its mana cost.  If that spell would be put into your graveyard, exile it
    instead.

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
            "card in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant "
            "or sorcery card from your graveyard without paying its mana cost. "
            "If that spell would be put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        controller = self.controller
        if controller is None:
            return 0
        return sum(
            1
            for card in controller.zones[Zone.GRAVEYARD].get_all()
            if _instant_or_sorcery(card)
        )

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free
        from engine.events import (
            AttacksTriggeredEvent,
            MoveToGraveyardReplacementEvent,
        )
        from engine.replacement_effects import ReplacementEffect
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            candidates = [
                c
                for c in controller.zones[Zone.GRAVEYARD].get_all()
                if _instant_or_sorcery(c)
            ]
            if not candidates:
                return
            if not controller.choose_yes_no(
                "Cast an instant or sorcery from your graveyard for free?"
            ):
                return
            chosen = controller.choose_card(
                candidates, "Choose an instant or sorcery to cast"
            )
            if chosen is None:
                return

            # "If that spell would be put into your graveyard, exile it
            # instead." — a one-shot, identity-scoped redirect on the chosen
            # spell's resolution.
            marker = type(
                "ArchaicExileRedirect", (), {"name": "Dawning Archaic exile redirect"}
            )()

            def _exile_condition(game: Any, event: Any) -> bool:
                return event.card is chosen

            def _exile_replacement(game: Any, event: Any) -> Any:
                event.destination = "exile"
                game.replacement_manager.unregister(marker)
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=marker,
                    condition=_exile_condition,
                    replacement=_exile_replacement,
                    controller=controller,
                )
            )

            cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)

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
