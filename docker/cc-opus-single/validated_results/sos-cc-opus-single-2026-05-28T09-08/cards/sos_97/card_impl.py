"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature_mv_le_3(card: Any) -> bool:
    """Return True if *card* is a creature card with mana value 3 or less."""
    card_types = getattr(card, "card_types", set())
    if CardType.CREATURE not in card_types:
        return False
    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is None:
        # No mana cost means MV 0
        return True
    cmc = getattr(mana_cost, "cmc", 0)
    return cmc <= 3


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer -- {1}{B}{B} -- Legendary Planeswalker -- Ral

    Starting loyalty 3.

    +1: Surveil 2.
    -1: Any number of target players each discard a card.
    -2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    -7: Flip five coins. Target opponent skips their next X turns, where
        X is the number of coins that came up heads.

    SOS collector number 97.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less "
            "from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, "
            "where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Targeting (for -2 ability)
    # ------------------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        """Return target requirements.

        The -2 ability targets a creature card with mana value 3 or less
        in the controller's graveyard.
        """
        return [
            TargetRequirement(
                filter_fn=_is_creature_mv_le_3,
                description="target creature card with mana value 3 or less in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    # ------------------------------------------------------------------
    # Loyalty abilities
    # ------------------------------------------------------------------

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1_surveil(game: GameState) -> None:
            """+1: Surveil 2 -- look at top 2 cards, put any number into
            graveyard, rest on top of library in any order.

            Default implementation puts all surveiled cards into the graveyard.
            """
            controller = pw.controller
            if controller is None:
                return

            library = controller.zones[Zone.LIBRARY]
            count = min(2, len(library))
            if count == 0:
                return

            # Get the top N cards (last N in the list)
            surveiled = library.top(count)
            # Move all to graveyard (simplified surveil)
            graveyard = controller.zones[Zone.GRAVEYARD]
            for card in surveiled:
                library.remove(card)
                graveyard.add(card)

        def _minus1_discard(game: GameState) -> None:
            """-1: Any number of target players each discard a card."""
            from engine.game import discard

            targets = getattr(pw, "_resolve_targets", None) or getattr(pw, "chosen_targets", None) or []
            for player in targets:
                if player is None:
                    continue
                hand = player.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if cards_in_hand:
                    # Discard the last card in hand (simplified choice)
                    card_to_discard = cards_in_hand[-1]
                    discard(game, player, card_to_discard)

        def _minus2_reanimate(game: GameState) -> None:
            """-2: Return target creature card with MV <= 3 from graveyard
            to the battlefield."""
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                chosen = getattr(pw, "chosen_targets", None)
                if chosen:
                    target = chosen[0]
            if target is None:
                return

            controller = pw.controller
            if controller is None:
                return

            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return

            # Move from graveyard to battlefield (high-level move fires ETB events)
            from engine.zones import move_to_zone
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

            # Ensure controller is set on the reanimated creature
            target.controller = controller

        def _minus7_ultimate(game: GameState) -> None:
            """-7: Flip five coins. Target opponent skips their next X turns,
            where X is the number of coins that came up heads."""
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                targets = getattr(pw, "_resolve_targets", None) or getattr(pw, "chosen_targets", None) or []
                if targets:
                    target = targets[0]
            if target is None:
                return

            # Determine coin flip results
            coin_results = getattr(pw, "_coin_results", None)
            if coin_results is not None:
                heads_count = sum(1 for r in coin_results if r)
            else:
                heads_count = 0
                for _ in range(5):
                    if random.choice([True, False]):
                        heads_count += 1

            # Apply turn-skipping to the target opponent
            if heads_count > 0:
                if not hasattr(target, "skip_turns"):
                    target.skip_turns = 0
                target.skip_turns += heads_count

        return [
            LoyaltyAbility(
                loyalty_cost=1,
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
                description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7_ultimate,
                description="−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
            ),
        ]
