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
    −7: Flip five coins. Target opponent skips their next X turns, where
        X is the number of coins that came up heads.

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
            "+1: Surveil 2.\n−1: Any number of target players each discard "
            "a card.\n−2: Return target creature card with mana value 3 or "
            "less from your graveyard to the battlefield.\n−7: Flip five "
            "coins. Target opponent skips their next X turns, where X is "
            "the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def _targets(self) -> list[Any]:
        """Targets of the current activation (set via chosen_targets)."""
        return list(getattr(self, "chosen_targets", None) or [])

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1_surveil(game: "GameState") -> None:
            """Surveil 2 — look at the top 2; any number to the graveyard.

            Deliberate limitation: cards kept on top stay in their
            original order (no reorder choice).
            """
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            library = game.get_library(controller)
            # top(2) returns bottom→top; look at the top card first.
            looked = list(reversed(library.top(2)))
            for card in looked:
                if controller.choose_yes_no(
                    f"Surveil: put {getattr(card, 'name', 'card')} into "
                    "your graveyard?"
                ):
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        def _minus1_discard(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            for target in pw._targets():
                if target is None or not hasattr(target, "life"):
                    continue
                hand_cards = game.get_hand(target).get_all()
                if not hand_cards:
                    continue
                chosen = target.choose_card(hand_cards, "Discard a card")
                if chosen is None or chosen not in hand_cards:
                    chosen = hand_cards[-1]
                discard(game, target, chosen)

        def _minus2_reanimate(game: "GameState") -> None:
            """Return target creature card (MV ≤ 3) from your graveyard."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            targets = pw._targets()
            target = targets[0] if targets else None
            if target is None:
                return
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            cost = getattr(target, "mana_cost", None)
            if cost is not None and cost.cmc > 3:
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7_coins(game: "GameState") -> None:
            """Flip five coins; target opponent skips their next X turns."""
            import random

            targets = pw._targets()
            target = targets[0] if targets else None
            if target is None or not hasattr(target, "life"):
                return
            rng = getattr(game, "rng", None)
            if rng is None:
                rng = random.Random()
                game.rng = rng
            heads = sum(rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                target.skip_turns = getattr(target, "skip_turns", 0) + heads

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1_surveil,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1_discard,
                description="−1: Any number of target players each discard "
                            "a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2_reanimate,
                description="−2: Return target creature card with mana "
                            "value 3 or less from your graveyard to the "
                            "battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7_coins,
                description="−7: Flip five coins. Target opponent skips "
                            "their next X turns, where X is the number of "
                            "coins that came up heads.",
            ),
        ]
