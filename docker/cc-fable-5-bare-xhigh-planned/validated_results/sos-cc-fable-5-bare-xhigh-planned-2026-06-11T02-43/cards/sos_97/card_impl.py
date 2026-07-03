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
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n−1: Any number of target players each discard "
            "a card.\n−2: Return target creature card with mana value 3 or "
            "less from your graveyard to the battlefield.\n−7: Flip five "
            "coins. Target opponent skips their next X turns, where X is "
            "the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _targets(game: "GameState") -> list[Any]:
            return list(getattr(pw, "chosen_targets", None) or [])

        def _plus1(game: "GameState") -> None:
            """Surveil 2 — look at top 2; bin any; rest stay on top.

            Deliberate simplification: kept cards stay in their original
            relative order (no reorder choice).
            """
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            for card in reversed(library.top(2)):  # top card first
                if controller.choose_yes_no(
                    f"Surveil: put {card.name} into your graveyard?"
                ):
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            for target in _targets(game):
                if target not in game.players:
                    continue
                hand_cards = game.get_hand(target).get_all()
                if not hand_cards:
                    continue
                chosen = target.choose_card(hand_cards, "Discard a card")
                if chosen is None or chosen not in hand_cards:
                    chosen = hand_cards[-1]
                discard(game, target, chosen)

        def _minus2(game: "GameState") -> None:
            """Return target creature card (MV <= 3) from your graveyard."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            targets = _targets(game)
            card = targets[0] if targets else None
            if card is None:
                return
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(card):
                return
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                return
            if getattr(card, "mana_cost", ManaCost()).cmc > 3:
                return
            card.controller = controller
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """Flip five coins; target opponent skips their next X turns."""
            controller = pw.controller
            targets = _targets(game)
            target = targets[0] if targets else None
            if target is None or target not in game.players:
                return
            if controller is not None and target is controller:
                return  # must be an opponent
            heads = sum(game.rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                target.skip_turns = getattr(target, "skip_turns", 0) + heads

        return [
            LoyaltyAbility(
                loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description=(
                    "−2: Return target creature card with mana value 3 or "
                    "less from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description=(
                    "−7: Flip five coins. Target opponent skips their next "
                    "X turns, where X is the number of heads."
                ),
            ),
        ]
