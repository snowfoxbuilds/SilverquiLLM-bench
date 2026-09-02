"""Card implementation for Macabre Waltz."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.card_queries import choose_object
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class MacabreWaltz(Sorcery):
    """Macabre Waltz — {1}{B} — Sorcery.

    Return up to two target creature cards from your graveyard to your
    hand, then discard a card.

    FDN collector number 177.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Macabre Waltz")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Return up to two target creature cards from your graveyard to "
            "your hand, then discard a card.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Up to two target creature cards in your graveyard.

        "Up to two target" → two optional requirements, targeted at cast. The
        engine picks distinct cards (rule 601.2c) and the spell stays castable
        with one or zero creature cards in the graveyard; ``chosen_targets`` then
        holds 0, 1, or 2 cards.
        """
        controller = self.controller

        def _filter(obj: Any) -> bool:
            return (
                CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "owner", None) is controller
            )

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="first of up to two target creature cards in your graveyard",
                zone=Zone.GRAVEYARD,
                optional=True,
            ),
            TargetRequirement(
                filter_fn=_filter,
                description="second of up to two target creature cards in your graveyard",
                zone=Zone.GRAVEYARD,
                optional=True,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Return targets to hand, then discard a card."""
        from engine.game import discard
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        chosen = getattr(self, "chosen_targets", [])
        for target in chosen:
            if target is None:
                continue
            # Verify still a creature card in graveyard
            gy = getattr(target, "owner", controller).zones[Zone.GRAVEYARD]
            if gy.contains(target) and CardType.CREATURE in getattr(target, "card_types", set()):
                move_to_zone(game, target, Zone.GRAVEYARD, Zone.HAND)

        # Then discard a card
        hand = game.get_hand(controller)
        hand_cards = hand.get_all()
        if hand_cards:
            to_discard = choose_object(game, controller, hand_cards, "Choose a card to discard", source_card=self)
            discard(game, controller, to_discard)
