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
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
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

    # ------------------------------------------------------------------
    # Loyalty abilities
    # ------------------------------------------------------------------

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _targets(game: Any) -> list[Any]:
            return list(getattr(pw, "chosen_targets", None) or [])

        def _plus1(game: "GameState") -> None:
            """Surveil 2 — look at the top 2 cards; put any number into the
            graveyard, the rest back on top.  LOCAL LIMITATION: kept cards
            stay in their existing order (no reorder choice)."""
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            looked = list(reversed(library.top(2)))  # topmost first
            remaining = list(looked)
            while remaining:
                try:
                    chosen = controller.choose_card(
                        remaining,
                        "surveil: put a card into your graveyard (None to stop)",
                    )
                except Exception:
                    chosen = None
                if chosen is None or chosen not in remaining:
                    break
                remaining.remove(chosen)
                library.remove(chosen)
                graveyard.add(chosen)

        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            for player in _targets(game):
                if player is None or not hasattr(player, "zones"):
                    continue
                hand = player.zones[Zone.HAND].get_all()
                if not hand:
                    continue
                try:
                    chosen = player.choose_card(hand, "choose a card to discard")
                except Exception:
                    chosen = hand[-1]
                if chosen is None or chosen not in hand:
                    chosen = hand[-1]
                discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            """Return target creature card with MV <= 3 from your graveyard
            to the battlefield."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            targets = _targets(game)
            card = targets[0] if targets else None
            if card is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(card):
                return
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                return
            if getattr(card, "mana_cost", ManaCost()).cmc > 3:
                return
            card.controller = controller
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """Flip five coins; target opponent skips their next X turns
            (X = heads)."""
            targets = _targets(game)
            opponent = targets[0] if targets else None
            if opponent is None or not hasattr(opponent, "skip_turns"):
                return
            heads = sum(game.rng.randint(0, 1) for _ in range(5))
            opponent.skip_turns += heads

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
                description="−2: Return target creature card with mana value "
                "3 or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins. Target opponent skips "
                "their next X turns, where X is the number of heads.",
            ),
        ]
