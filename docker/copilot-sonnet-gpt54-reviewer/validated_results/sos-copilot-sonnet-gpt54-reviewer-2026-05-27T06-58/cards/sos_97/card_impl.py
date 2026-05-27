"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty: 3
    +1: Surveil 2
    -1: Any number of target players each discard a card
    -2: Return target creature card with mana value ≤ 3 from your graveyard to the battlefield
    -7: Flip five coins. Target opponent skips their next X turns, where X is the number of heads.
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
            "-1: Any number of target players each discard a card.\n"
            "-2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "-7: Flip five coins. Target opponent skips their next X turns, where X is the number of heads.",
        )
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Return the target filter requirements for the -2 loyalty ability.

        NOTE: This method exists so test code can validate the -2 ability's
        graveyard filter function directly (cards/sos/sos_97/tests.py lines 440–461).
        Planeswalkers do not target on cast; per-ability targeting is handled when
        each loyalty ability is activated (chosen_targets is set externally by the
        activation pipeline before the effect is called).
        """
        def _creature_mv_lte3(card: Any) -> bool:
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                return False
            mana_cost = getattr(card, "mana_cost", None)
            if mana_cost is None:
                return True  # zero cost counts as 0
            cmc = getattr(mana_cost, "cmc", 0)
            return cmc <= 3

        return [
            TargetRequirement(
                filter_fn=_creature_mv_lte3,
                description="target creature card with mana value 3 or less in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        """Return all four loyalty abilities."""
        pw = self

        # +1: Surveil 2
        def _plus1(game: "GameState") -> None:
            controller = getattr(pw, "controller", None)
            if controller is None:
                return
            lib = game.get_library(controller)
            all_cards = list(lib.get_all())
            look_count = min(2, len(all_cards))
            if look_count == 0:
                return
            # Top of library is the last element; top N cards are all_cards[-look_count:]
            top_cards = all_cards[-look_count:]
            # Ask player which cards to send to graveyard
            try:
                to_graveyard = controller.choose(top_cards, "surveil: choose cards to put in graveyard")
            except Exception:
                to_graveyard = []
            if to_graveyard is None:
                to_graveyard = []
            # Move chosen cards to graveyard
            graveyard = game.get_graveyard(controller)
            for card in to_graveyard:
                lib.remove(card)
                graveyard.add(card)
            # Build list of kept cards (those in top_cards that were not graveyarded)
            kept = [c for c in top_cards if c not in to_graveyard]
            if len(kept) > 1:
                # Ask the controller to choose the order to put kept cards back on top.
                # The last element in the returned list ends up on top.
                # Gracefully fall back to the original order if the script is exhausted.
                try:
                    ordered = controller.choose(
                        kept,
                        "surveil: choose order of kept cards (last = top of library)",
                    )
                    if ordered is not None and len(ordered) == len(kept):
                        kept = list(ordered)
                except Exception:
                    pass  # keep original order
            # Remove kept cards from their current library positions and re-insert
            # in the chosen order (bottom to top, so the last one ends on top).
            for card in kept:
                lib.remove(card)
            for card in kept:
                lib.add(card)

        # -1: Any number of target players each discard a card
        def _minus1(game: "GameState") -> None:
            targets = getattr(pw, "chosen_targets", [])
            for player in targets:
                hand = game.get_hand(player)
                hand_cards = hand.get_all()
                if not hand_cards:
                    continue
                try:
                    chosen = player.choose_card(hand_cards, "discard a card")
                except Exception:
                    chosen = hand_cards[0] if hand_cards else None
                if chosen is not None:
                    from engine.game import discard
                    discard(game, player, chosen)

        # -2: Return target creature card with MV <= 3 from controller's graveyard to battlefield
        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone as _move_to_zone

            targets = getattr(pw, "chosen_targets", [])
            if not targets:
                return
            creature = targets[0]
            controller = getattr(pw, "controller", None)
            if controller is None:
                return
            # Only return from the controller's own graveyard (oracle text: "your graveyard")
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(creature):
                return
            # Ensure the creature will be placed under the controller's control
            creature.controller = controller
            # Use move_to_zone so ETB triggers and replacement effects fire correctly
            _move_to_zone(game, creature, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        # -7: Flip five coins, target opponent skips X turns (X = heads)
        def _minus7(game: "GameState") -> None:
            targets = getattr(pw, "chosen_targets", [])
            if not targets:
                return
            opponent = targets[0]
            # Flip 5 coins
            heads = sum(1 for _ in range(5) if random.random() < 0.5)
            # Set turns_to_skip on opponent
            if hasattr(opponent, "turns_to_skip"):
                opponent.turns_to_skip += heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1, description="-1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description="-2: Return target creature card with mana value 3 or less from your graveyard to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="-7: Flip five coins. Target opponent skips their next X turns."),
        ]
