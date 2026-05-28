"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer -- {1}{B}{B} -- 3 loyalty.

    +1: Surveil 2.
    -1: Any number of target players each discard a card.
    -2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    -7: Flip five coins. Target opponent skips their next X turns, where X
        is the number of coins that came up heads.
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

    def get_targets(self, game: GameState) -> list[TargetRequirement]:
        """Return targeting requirements (includes graveyard filter for -2)."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(getattr(obj, "mana_cost", None), "cmc", 99) <= 3
                ),
                description="target creature card with mana value 3 or less in your graveyard",
                zone=Zone.GRAVEYARD,
            ),
        ]

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        # ---------------------------------------------------------------
        # +1: Surveil 2
        # ---------------------------------------------------------------
        def _plus1(game: Any) -> None:
            """Surveil 2: look at top 2 cards, put any number into graveyard."""
            controller = pw.controller
            if controller is None:
                return

            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]

            count = min(2, len(library))
            if count == 0:
                return

            # Get top N cards (top = end of internal list)
            top_cards = library.top(count)

            # For each card in the top set, the controller chooses which
            # go to the graveyard.  Each scripted choice that matches a
            # card from the top set sends that card to the graveyard.
            to_graveyard: list[Any] = []
            for _ in range(count):
                try:
                    chosen = controller.choose_card(
                        top_cards, "Surveil: choose a card to put into graveyard"
                    )
                except Exception:
                    break
                if chosen is not None and any(c is chosen for c in top_cards):
                    to_graveyard.append(chosen)
                    top_cards = [c for c in top_cards if c is not chosen]
                else:
                    # Player declined or chose something not in the set
                    break

            # Move chosen cards to graveyard
            for card in to_graveyard:
                if library.contains(card):
                    library.remove(card)
                    graveyard.add(card)

            # Remaining cards stay on top of the library (already there)

        # ---------------------------------------------------------------
        # -1: Any number of target players each discard a card
        # ---------------------------------------------------------------
        def _minus1(game: Any) -> None:
            """Each targeted player discards a card."""
            targets = getattr(pw, "chosen_targets", [])
            if not targets:
                return

            for player in targets:
                hand = game.get_hand(player)
                hand_cards = hand.get_all()
                if not hand_cards:
                    continue  # empty hand, skip

                # The targeted player chooses which card to discard
                try:
                    chosen = player.choose_card(
                        hand_cards, "Choose a card to discard"
                    )
                except Exception:
                    chosen = hand_cards[0]

                if chosen is not None and hand.contains(chosen):
                    hand.remove(chosen)
                    player.zones[Zone.GRAVEYARD].add(chosen)

        # ---------------------------------------------------------------
        # -2: Return target creature with MV <= 3 from graveyard to BF
        # ---------------------------------------------------------------
        def _minus2(game: Any) -> None:
            """Return target creature card with MV <= 3 from graveyard to battlefield."""
            targets = getattr(pw, "chosen_targets", [])
            if not targets:
                return

            target = targets[0]
            controller = pw.controller
            if controller is None:
                return

            owner = getattr(target, "owner", controller)

            # Find the graveyard that actually contains the target
            graveyard = None
            for player in game.players:
                gy = game.get_graveyard(player)
                if gy.contains(target):
                    graveyard = gy
                    break

            if graveyard is None:
                return

            # Move from graveyard to controller's battlefield
            graveyard.remove(target)
            target.controller = controller
            game.get_battlefield(controller).add(target)

        # ---------------------------------------------------------------
        # -7: Flip five coins, opponent skips X turns (X = heads)
        # ---------------------------------------------------------------
        def _minus7(game: Any) -> None:
            """Flip 5 coins. Target opponent skips X turns (X = heads count)."""
            targets = getattr(pw, "chosen_targets", [])
            if not targets:
                return

            opponent = targets[0]

            # Flip five coins using random.randint(0, 1); 1 = heads
            heads_count = 0
            for _ in range(5):
                result = random.randint(0, 1)
                if result == 1:
                    heads_count += 1

            # Record skip turns on the opponent
            current_skips = getattr(opponent, "skip_turns", 0)
            opponent.skip_turns = current_skips + heads_count

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="−2: Return target creature with MV ≤ 3 from graveyard to battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip 5 coins. Target opponent skips X turns (X = heads).",
            ),
        ]
