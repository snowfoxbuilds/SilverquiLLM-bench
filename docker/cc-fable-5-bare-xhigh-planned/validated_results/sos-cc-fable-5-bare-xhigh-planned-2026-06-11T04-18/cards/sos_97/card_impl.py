"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(game: GameState, obj: Any) -> bool:
    return obj in game.players


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.
    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X
        is the number of coins that came up heads.

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

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1_surveil(game: GameState) -> None:
            """Surveil 2: look at the top two cards; bin any number.

            One yes/no per card (top first): True puts it into the
            graveyard. Kept cards stay on top in their original relative
            order (reordering not modelled — deliberate simplification).
            """
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            n = min(2, len(library))
            if n == 0:
                return
            cards = library.top(n)  # bottom-to-top order
            for card in reversed(cards):  # look at the top card first
                try:
                    to_graveyard = controller.choose_yes_no(
                        f"surveil: put {getattr(card, 'name', '?')} into "
                        "your graveyard?"
                    )
                except Exception:
                    to_graveyard = False
                if to_graveyard:
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        def _minus1_discard(game: GameState) -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            targets = getattr(pw, "chosen_targets", None) or []
            for target in targets:
                if not _is_player(game, target):
                    continue
                hand = game.get_hand(target).get_all()
                if not hand:
                    continue
                try:
                    chosen = target.choose_card(hand, "discard a card")
                except Exception:
                    chosen = hand[-1]
                if chosen is None or chosen not in hand:
                    chosen = hand[-1]
                discard(game, target, chosen)

        def _minus2_reanimate(game: GameState) -> None:
            """Return target creature card (mv <= 3) from your graveyard
            to the battlefield."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            targets = getattr(pw, "chosen_targets", None) or []
            target = targets[0] if targets else None
            if target is None:
                return
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if getattr(getattr(target, "mana_cost", None), "cmc", 0) > 3:
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7_coins(game: GameState) -> None:
            """Flip five coins; target opponent skips their next X turns."""
            import random

            controller = pw.controller
            targets = getattr(pw, "chosen_targets", None) or []
            target = targets[0] if targets else None
            if target is None or not _is_player(game, target):
                return
            if controller is not None and target is controller:
                return  # must target an opponent
            rng = getattr(game, "rng", None)
            if rng is None:
                rng = game.rng = random.Random()
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
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2_reanimate,
                description=(
                    "−2: Return target creature card with mana value 3 or "
                    "less from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7_coins,
                description=(
                    "−7: Flip five coins. Target opponent skips their next "
                    "X turns, where X is the number of coins that came up heads."
                ),
            ),
        ]
