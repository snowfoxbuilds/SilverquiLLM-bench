"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _surveil(game: "GameState", player: Any, n: int) -> None:
    """Surveil N: look at top N cards, put any into graveyard (rest stay on top)."""
    library = player.zones[Zone.LIBRARY]
    top_cards = library.top(n)
    for card in top_cards:
        put_in_gy = False
        try:
            put_in_gy = player.choose_yes_no(
                f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
            )
        except Exception:
            pass
        if put_in_gy:
            library.remove(card)
            player.zones[Zone.GRAVEYARD].add(card)


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral (3 loyalty).

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your graveyard
        to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is the
        number of coins that came up heads.
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

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        # +1: Surveil 2
        def _plus1(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            _surveil(game, ctrl, 2)

        # −1: Any number of target players each discard a card.
        def _minus1(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            from engine.game import discard

            for player in list(game.players):
                try:
                    include = ctrl.choose_yes_no(
                        f"Make {player.name} discard a card?"
                    )
                except Exception:
                    include = False
                if not include:
                    continue
                hand_cards = player.zones[Zone.HAND].get_all()
                if not hand_cards:
                    continue
                try:
                    card = ctrl.choose_card(hand_cards, f"Choose card for {player.name} to discard")
                except Exception:
                    card = hand_cards[0]
                if card is not None:
                    discard(game, player, card)

        # −2: Return target creature card with MV ≤ 3 from graveyard to battlefield.
        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone

            ctrl = pw.controller
            if ctrl is None:
                return
            gy = ctrl.zones[Zone.GRAVEYARD]
            candidates = [
                c for c in gy.get_all()
                if (CardType.CREATURE in getattr(c, "card_types", set())
                    and _mana_value(c) <= 3)
            ]
            if not candidates:
                return
            try:
                chosen = ctrl.choose_card(candidates, "Return creature with MV ≤ 3 from graveyard")
            except Exception:
                chosen = candidates[0]
            if chosen is None:
                return
            chosen.controller = ctrl
            if chosen.owner is None:
                chosen.owner = ctrl
            move_to_zone(game, chosen, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        # −7: Flip five coins, opponent skips X turns (X = heads).
        def _minus7(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            # Find an opponent.
            opponent = None
            for p in game.players:
                if p is not ctrl:
                    opponent = p
                    break
            if opponent is None:
                return
            # Flip 5 coins.
            heads = sum(1 for _ in range(5) if random.random() < 0.5)
            if heads > 0:
                opponent.skip_turns = getattr(opponent, "skip_turns", 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1, description="-1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description="-2: Return target creature with MV ≤ 3 from graveyard."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="-7: Flip 5 coins, opponent skips X turns."),
        ]


def _mana_value(card: Any) -> int:
    """Return the mana value of a card."""
    cost = getattr(card, "mana_cost", None)
    if cost is None:
        return 0
    return cost.generic + sum(cost.pips.values()) + len(getattr(cost, "hybrid", []))
