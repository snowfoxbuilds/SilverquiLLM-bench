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
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
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

        def _chosen(index: int = 0) -> Any:
            targets = getattr(pw, "chosen_targets", None) or []
            return targets[index] if len(targets) > index else None

        # ------------------------------------------------------------------
        # +1: Surveil 2
        # ------------------------------------------------------------------

        def _plus1(game: GameState) -> None:
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            looked = list(reversed(library.top(2)))  # topmost first
            remaining = list(looked)
            while remaining:
                chosen = controller.choose_card(
                    remaining,
                    "Surveil 2: choose a card to put into your graveyard "
                    "(None to keep the rest on top)",
                )
                if chosen is None or chosen not in remaining:
                    break
                remaining.remove(chosen)
                move_to_zone(game, chosen, Zone.LIBRARY, Zone.GRAVEYARD)
            # Cards not binned stay on top of the library in their original
            # order (reordering the kept cards is not supported — limitation).

        # ------------------------------------------------------------------
        # −1: Any number of target players each discard a card
        # ------------------------------------------------------------------

        def _minus1(game: GameState) -> None:
            from engine.game import discard

            targets = getattr(pw, "chosen_targets", None) or []
            for player in targets:
                if player is None or not hasattr(player, "zones"):
                    continue
                hand_cards = player.zones[Zone.HAND].get_all()
                if not hand_cards:
                    continue
                chosen = player.choose_card(hand_cards, "Choose a card to discard")
                if chosen is None or chosen not in hand_cards:
                    chosen = hand_cards[-1]
                discard(game, player, chosen)

        # ------------------------------------------------------------------
        # −2: Reanimate a creature card with mana value <= 3
        # ------------------------------------------------------------------

        def _is_valid_reanimation(card: Any) -> bool:
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                return False
            cost = getattr(card, "mana_cost", None)
            return (cost.cmc if cost is not None else 0) <= 3

        def _minus2(game: GameState) -> None:
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            graveyard = game.get_graveyard(controller)
            candidates = [c for c in graveyard.get_all() if _is_valid_reanimation(c)]
            if not candidates:
                return
            target = _chosen()
            if target is None:
                # No activation target supplied: auto-select a lone
                # candidate, otherwise ask.
                if len(candidates) == 1:
                    target = candidates[0]
                else:
                    target = controller.choose_card(
                        candidates,
                        "Return a creature card with mana value 3 or less "
                        "to the battlefield (None to decline)",
                    )
            if target is None or target not in candidates:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        # ------------------------------------------------------------------
        # −7: Flip five coins; target opponent skips their next X turns
        # ------------------------------------------------------------------

        def _minus7(game: GameState) -> None:
            import random

            controller = pw.controller
            if controller is None:
                return
            rng = getattr(game, "rng", None)
            if rng is None:
                rng = game.rng = random.Random()
            heads = sum(rng.randint(0, 1) for _ in range(5))

            target = _chosen()
            if target is None or not hasattr(target, "life") or target is controller:
                # Default to the lone opponent (2-player engine).
                target = next(
                    (p for p in game.players if p is not controller), None
                )
            if target is None:
                return
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
