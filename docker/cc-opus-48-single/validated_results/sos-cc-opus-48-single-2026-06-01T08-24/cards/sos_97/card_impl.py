"""Card implementation for Ral Zarek, Guest Lecturer (SOS 97)."""

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
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "-1: Any number of target players each discard a card.\n"
            "-2: Return target creature card with mana value 3 or less from "
            "your graveyard to the battlefield.\n"
            "-7: Flip five coins. Target opponent skips their next X turns, "
            "where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)
        # Set by the resolution pipeline / tests to supply the ability's target.
        self.chosen_targets: list[Any] = []
        self._resolve_target: Any = None

    # ------------------------------------------------------------------
    # Loyalty abilities
    # ------------------------------------------------------------------

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            """+1: Surveil 2."""
            controller = pw.controller
            if controller is None:
                return
            library = game.get_library(controller)
            graveyard = game.get_graveyard(controller)
            # Top of the library is the END of the internal list. Surveil 2
            # examines the top two cards one at a time (topmost first).
            for _ in range(2):
                cards = library.get_all()
                if not cards:
                    break
                top_card = cards[-1]
                to_graveyard = controller.choose_yes_no(
                    f"Surveil: put {getattr(top_card, 'name', 'card')} into "
                    "your graveyard?"
                )
                if to_graveyard:
                    library.remove(top_card)
                    graveyard.add(top_card)
                # If kept on top, leave it where it is; the next iteration
                # would re-examine the same card, so stop after a kept card to
                # honour Surveil's "rest back on top in any order" semantics.
                else:
                    break

        def _minus1(game: "GameState") -> None:
            """−1: Any number of target players each discard a card."""
            from engine.game import discard

            targets = list(getattr(pw, "chosen_targets", []) or [])
            for player in targets:
                hand = game.get_hand(player)
                cards = hand.get_all()
                if not cards:
                    continue
                chosen = player.choose_card(cards, "Choose a card to discard")
                if chosen is None:
                    continue
                discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            """−2: Reanimate a creature card with mana value 3 or less from
            your graveyard."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            target = pw._chosen_single_target()
            if target is None:
                return
            # Must be a creature card.
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            # Mana value must be 3 or less.
            mana_cost = getattr(target, "mana_cost", None)
            mana_value = getattr(mana_cost, "cmc", 0) if mana_cost is not None else 0
            if mana_value > 3:
                return
            # Must be in YOUR (the controller's) graveyard.
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(target):
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """−7: Flip five coins. Target opponent skips their next X turns,
            where X is the number of coins that came up heads."""
            target = pw._chosen_single_target()
            heads = 0
            flipper = pw.controller
            for _ in range(5):
                if game.flip_coin(flipper):
                    heads += 1
            if target is None:
                return
            # Target opponent skips their next X turns.
            if hasattr(target, "skipped_turns"):
                target.skipped_turns += heads

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="-1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="-2: Return target creature card with mana value 3 "
                "or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="-7: Flip five coins. Target opponent skips their "
                "next X turns, where X is the number of coins that came up heads.",
            ),
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _chosen_single_target(self) -> Any:
        """Return the single chosen target for an ability, if any."""
        chosen = getattr(self, "chosen_targets", None)
        if chosen:
            return chosen[0]
        return getattr(self, "_resolve_target", None)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Loyalty-ability targets are chosen by the ability, not the card.

        Returning ``[]`` keeps the casting pipeline from requiring a target
        for the planeswalker itself (cf. KEY_DECISIONS get_targets convention).
        """
        return []
