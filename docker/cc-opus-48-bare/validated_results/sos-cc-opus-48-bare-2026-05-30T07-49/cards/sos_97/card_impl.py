"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    mc = getattr(card, "mana_cost", None)
    if mc is None:
        return 0
    return getattr(mc, "cmc", 0)


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is
        the number of coins that came up heads.

    Starting loyalty 3.  SOS collector number 97.
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
            "−2: Return target creature card with mana value 3 or less from "
            "your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, "
            "where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Surveil helper
    # ------------------------------------------------------------------

    def _surveil(self, game: "GameState", controller: Any, n: int) -> None:
        library = controller.zones[Zone.LIBRARY]
        graveyard = controller.zones[Zone.GRAVEYARD]

        look = list(reversed(library.top(n)))  # top card first
        for card in look:
            library.remove(card)

        kept: list = []  # top-first order of cards that stay on the library
        for card in look:
            if controller.choose_yes_no(
                f"Surveil — put {getattr(card, 'name', 'card')} into your graveyard?"
            ):
                graveyard.add(card)
            else:
                kept.append(card)

        # Put the kept cards back, preserving their original top-first order.
        for card in reversed(kept):
            library.add(card, "top")

    # ------------------------------------------------------------------
    # Loyalty abilities
    # ------------------------------------------------------------------

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            controller = pw.controller
            if controller is None:
                return
            pw._surveil(game, controller, 2)

        def _minus1(game: "GameState") -> None:
            from engine.game import discard

            targets = getattr(pw, "_resolve_targets", None)
            if not targets:
                single = getattr(pw, "_resolve_target", None)
                targets = [single] if single is not None else []
            for player in targets:
                if player is None:
                    continue
                hand = game.get_hand(player).get_all()
                if not hand:
                    continue
                chosen = player.choose_card(list(hand), "card to discard")
                if chosen is not None and game.get_hand(player).contains(chosen):
                    discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if _mana_value(target) > 3:
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            controller = pw.controller
            if controller is None:
                return

            target = getattr(pw, "_resolve_target", None)
            if target not in game.players or target is controller:
                target = next(
                    (p for p in game.players if p is not controller), None
                )
            if target is None:
                return

            # Five coin flips.  ``_forced_heads`` makes the count deterministic
            # for testing; otherwise flip fairly.
            forced = getattr(pw, "_forced_heads", None)
            if forced is not None:
                heads = max(0, min(5, int(forced)))
            else:
                heads = sum(1 for _ in range(5) if random.random() < 0.5)

            opp_index = game.players.index(target)
            game.skip_turns[opp_index] = game.skip_turns.get(opp_index, 0) + heads

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
                    "−2: Return target creature card with mana value 3 or less "
                    "from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description=(
                    "−7: Flip five coins. Target opponent skips their next X "
                    "turns, where X is the number of heads."
                ),
            ),
        ]
