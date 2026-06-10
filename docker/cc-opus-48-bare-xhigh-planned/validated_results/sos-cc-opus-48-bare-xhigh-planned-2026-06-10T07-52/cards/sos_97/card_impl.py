"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.
    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is
        the number of coins that came up heads.

    SOS collector number 97.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n−1: Any number of target players each discard a "
            "card.\n−2: Return target creature card with mana value 3 or less "
            "from your graveyard to the battlefield.\n−7: Flip five coins. "
            "Target opponent skips their next X turns, where X is the number "
            "of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            """Surveil 2 — look at the top 2 cards; bin any number, keep the
            rest on top."""
            from engine.zones import move_to_zone

            ctrl = pw.controller
            if ctrl is None:
                return
            library = game.get_library(ctrl)
            # top(2) is bottom-to-top; process from the top card downward.
            top_cards = list(reversed(library.top(2)))
            for card in top_cards:
                if ctrl.choose_yes_no(
                    f"Surveil: put {getattr(card, 'name', 'card')} into your "
                    f"graveyard? (No keeps it on top)"
                ):
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            targets = getattr(pw, "chosen_targets", []) or []
            for player in targets:
                if player is None:
                    continue
                hand = game.get_hand(player)
                cards = hand.get_all()
                if not cards:
                    continue
                chosen = player.choose_card(cards, "Discard a card")
                if chosen is not None and hand.contains(chosen):
                    discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            """Return target creature card (MV <= 3) from your graveyard to the
            battlefield."""
            from engine.zones import move_to_zone

            ctrl = pw.controller
            target = (getattr(pw, "chosen_targets", []) or [None])[0]
            if ctrl is None or target is None:
                return
            # Validate: a creature card with mana value <= 3 in your graveyard.
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            cost = getattr(target, "mana_cost", None)
            if cost is not None and cost.cmc > 3:
                return
            if not game.get_graveyard(ctrl).contains(target):
                return
            target.controller = ctrl
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """Flip five coins; target opponent skips their next X turns."""
            target = (getattr(pw, "chosen_targets", []) or [None])[0]
            if target is None:
                return
            heads = sum(game.rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                target.skip_turns = getattr(target, "skip_turns", 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="−2: Return target creature card (MV ≤ 3) from your "
                "graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins. Target opponent skips their "
                "next X turns (X = heads).",
            ),
        ]
