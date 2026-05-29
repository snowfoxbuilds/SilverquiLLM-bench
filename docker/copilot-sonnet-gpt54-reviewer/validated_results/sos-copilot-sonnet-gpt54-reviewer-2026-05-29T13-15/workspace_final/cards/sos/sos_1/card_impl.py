"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Avatar 7/7.

    This spell costs {1} less to cast for each instant and sorcery card in your graveyard.
    Reach.
    Whenever The Dawning Archaic attacks, you may cast target instant or sorcery card
    from your graveyard without paying its mana cost. If that spell would be put into
    your graveyard, exile it instead.

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
            "This spell costs {1} less to cast for each instant and sorcery card in "
            "your graveyard.\nReach\nWhenever The Dawning Archaic attacks, you may "
            "cast target instant or sorcery card from your graveyard without paying "
            "its mana cost. If that spell would be put into your graveyard, exile it "
            "instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Return the number of instant and sorcery cards in controller's graveyard."""
        controller = getattr(self, "controller", None)
        if controller is None:
            return 0
        gy = controller.zones[Zone.GRAVEYARD]
        count = 0
        for card in gy.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger to cast instant/sorcery from graveyard for free."""
        from engine.events import AttacksTriggeredEvent
        from engine.stack import StackObject
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return

            gy = controller.zones[Zone.GRAVEYARD]
            candidates = [
                c for c in gy.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not candidates:
                return

            # "You may" — player can decline
            if not controller.choose_yes_no(
                "Cast target instant or sorcery from your graveyard for free?"
            ):
                return

            # Choose the card to cast
            chosen = controller.choose_card(
                candidates,
                "Choose instant or sorcery card to cast from graveyard",
            )
            if chosen is None:
                return

            # Move card from graveyard to stack zone
            gy.remove(chosen)
            stack_zone = controller.zones[Zone.STACK]
            stack_zone.add(chosen)
            chosen.controller = controller
            if chosen.owner is None:
                chosen.owner = controller

            # Call on_cast hook (no mana paid)
            chosen.on_cast(game)

            # Build a custom on_resolve that exiles instead of graveyarding
            def _resolve_exile(g: "GameState") -> None:
                chosen.on_resolve(g)
                # Move from stack zone to exile (not graveyard)
                if stack_zone.contains(chosen):
                    stack_zone.remove(chosen)
                owner = getattr(chosen, "owner", controller)
                owner.zones[Zone.EXILE].add(chosen)

            stack_obj = StackObject(
                source=chosen,
                controller=controller,
                targets=[],
                on_resolve=_resolve_exile,
            )
            game.stack.push(stack_obj)

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
