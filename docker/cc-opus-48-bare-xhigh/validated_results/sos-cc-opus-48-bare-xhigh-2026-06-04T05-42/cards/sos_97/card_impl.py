"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

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
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("starting_loyalty", 3)
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
        self.colors = ["B"]

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            from engine.player import ScriptExhaustedError

            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            cards = list(library.get_all())
            if not cards:
                return
            top_cards = cards[-min(2, len(cards)):]
            for card in reversed(top_cards):
                try:
                    put_in_gy = controller.choose_yes_no(
                        f"Surveil: put {getattr(card, 'name', 'card')} into graveyard?"
                    )
                except (ScriptExhaustedError, NotImplementedError):
                    put_in_gy = False
                if put_in_gy:
                    library.remove(card)
                    controller.zones[Zone.GRAVEYARD].add(card)

        def _minus1(game: "GameState") -> None:
            from engine.game import discard
            from engine.player import ScriptExhaustedError

            targets = getattr(pw, "_resolve_targets", None)
            if not targets:
                single = getattr(pw, "_resolve_target", None)
                targets = [single] if single is not None else []
            for player in targets:
                if player is None:
                    continue
                hand = player.zones[Zone.HAND].get_all()
                if not hand:
                    continue
                try:
                    chosen = player.choose_card(hand, "discard a card")
                except (ScriptExhaustedError, NotImplementedError):
                    chosen = hand[-1]
                if chosen is None or not player.zones[Zone.HAND].contains(chosen):
                    chosen = hand[-1]
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
            mana_cost = getattr(target, "mana_cost", None)
            cmc = mana_cost.cmc if mana_cost is not None else 0
            if cmc > 3:
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            controller = pw.controller
            if controller is None:
                return
            forced = getattr(pw, "_forced_heads", None)
            if forced is not None:
                heads = int(forced)
            else:
                heads = sum(1 for _ in range(5) if random.random() < 0.5)

            target = getattr(pw, "_resolve_target", None)
            if target is None or not hasattr(target, "zones"):
                opponents = [p for p in game.players if p is not controller]
                target = opponents[0] if opponents else None
            if target is None or heads <= 0:
                return
            seat = game.players.index(target)
            game.skip_turns[seat] = game.skip_turns.get(seat, 0) + heads

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
                description="−2: Return target creature card with mana value 3 or "
                "less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins. Target opponent skips their next "
                "X turns, where X is the number of heads.",
            ),
        ]
