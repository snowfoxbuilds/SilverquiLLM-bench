"""Card implementation for SphinxsTutelage."""

from __future__ import annotations


from engine.card import (
    ActivatedAbility,
    Artifact,
    Creature,
    Enchantment,
    Instant,
    ManaAbility,
    Sorcery,
)
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Color, HybridManaSymbol, Keyword, ManaCost, ManaType, Supertype, Zone
from typing import TYPE_CHECKING, Any


def _get_colors_of_permanent(obj: Any) -> set[Color]:
    """Return the set of MTG colors for a permanent based on its mana cost."""
    from engine.protection import get_colors
    return get_colors(obj)


class SphinxsTutelage(Enchantment):
    """Sphinx's Tutelage — {2}{U} — Enchantment

    Whenever you draw a card, target opponent mills two cards, then if
    two nonland cards that share a color were milled this way, repeat
    this process.

    {5}{U}: Draw a card, then discard a card.

    SPG collector number 75.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sphinx's Tutelage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Whenever you draw a card, target opponent mills two cards, "
            "then if two nonland cards that share a color were milled this "
            "way, repeat this process.\n"
            "{5}{U}: Draw a card, then discard a card.",
        )
        super().__init__(**kwargs)

    @staticmethod
    def _mill(game: Any, player: Any, count: int) -> list[Any]:
        """Mill *count* cards from *player*'s library to graveyard.

        Returns the list of milled cards.
        """
        milled: list[Any] = []
        library = player.zones[Zone.LIBRARY]
        graveyard = player.zones[Zone.GRAVEYARD]
        for _ in range(count):
            if len(library) == 0:
                break
            cards = library.top(1)
            card = cards[0]
            library.remove(card)
            graveyard.add(card)
            milled.append(card)
        return milled

    @staticmethod
    def _shared_color_among_nonlands(cards: list[Any]) -> bool:
        """Return True if two nonland cards in *cards* share a colour."""
        nonlands = [
            c for c in cards
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        if len(nonlands) < 2:
            return False
        # Gather colours per nonland card
        color_sets = [_get_colors_of_permanent(c) for c in nonlands]
        # Check pairwise for shared colour
        for i in range(len(color_sets)):
            for j in range(i + 1, len(color_sets)):
                if color_sets[i] & color_sets[j]:
                    return True
        return False

    def register_triggers(self, game: Any) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(g: Any, data: dict) -> bool:
            """Fire when the controller draws a card."""
            controller = source.controller or source.owner
            return data.get("player") is controller

        def _effect(g: Any) -> None:
            controller = source.controller or source.owner
            if controller is None:
                return
            # Target opponent — pick the first opponent
            opponent = None
            for p in g.players:
                if p is not controller:
                    opponent = p
                    break
            if opponent is None:
                return
            # Mill-repeat loop
            max_iterations = 100  # Safety cap
            for _ in range(max_iterations):
                milled = SphinxsTutelage._mill(g, opponent, 2)
                if len(milled) < 2:
                    break
                if not SphinxsTutelage._shared_color_among_nonlands(milled):
                    break

        reg = TriggerRegistration(
            event_type=EventType.DRAWS_CARD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=source.controller or source.owner,
        )
        game.trigger_manager.register(reg)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            cost = ManaCost.parse("{5}{U}")
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _effect(game: Any) -> None:
            from engine.game import draw_card, discard

            controller = source.controller or source.owner
            if controller is None:
                return
            card_drawn = draw_card(game, controller)
            # Discard: let controller choose, or pick first card in hand
            hand = controller.zones[Zone.HAND]
            cards_in_hand = hand.get_all()
            if cards_in_hand:
                to_discard = cards_in_hand[0]
                discard(game, controller, to_discard)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{5}{U}: Draw a card, then discard a card.",
        )]


__all__ = ["SphinxsTutelage"]
