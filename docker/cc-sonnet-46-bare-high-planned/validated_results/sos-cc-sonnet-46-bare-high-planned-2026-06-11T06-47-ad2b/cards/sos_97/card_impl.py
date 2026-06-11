"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# Module-level coin flip function — replace in tests for determinism.
_coin_flip_fn = lambda: random.random() < 0.5  # noqa: E731


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty: 3.
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
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less "
            "from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X "
            "turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        # +1: Surveil 2
        def _plus1(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            all_cards = list(library.get_all())
            top_cards = all_cards[-min(2, len(all_cards)):]
            for card in reversed(top_cards):
                try:
                    put_in_gy = ctrl.choose_yes_no(
                        f"Surveil: Put {getattr(card, 'name', 'card')} into graveyard?"
                    )
                except Exception:
                    put_in_gy = False
                if put_in_gy:
                    library.remove(card)
                    ctrl.zones[Zone.GRAVEYARD].add(card)

        # -1: Any number of target players each discard a card
        def _minus1(game: "GameState") -> None:
            from engine.game import discard as _discard
            ctrl = pw.controller
            if ctrl is None:
                return
            for player in game.players:
                try:
                    target_this = ctrl.choose_yes_no(f"Target {player.name}?")
                except Exception:
                    target_this = False
                if not target_this:
                    continue
                hand = game.get_hand(player)
                hand_cards = hand.get_all()
                if not hand_cards:
                    continue
                try:
                    chosen = player.choose_card(hand_cards, "discard a card")
                except Exception:
                    chosen = hand_cards[-1]
                if chosen is not None and hand.contains(chosen):
                    _discard(game, player, chosen)

        # -2: Return target creature card with MV ≤ 3 from graveyard to battlefield
        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone
            ctrl = pw.controller
            if ctrl is None:
                return
            gy = game.get_graveyard(ctrl)
            eligible = [
                c for c in gy.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(getattr(c, "mana_cost", None), "cmc", 0) <= 3
            ]
            if not eligible:
                return
            try:
                target = ctrl.choose_card(eligible, "return from graveyard")
            except Exception:
                target = eligible[0]
            if target is None or not gy.contains(target):
                return
            target.controller = ctrl
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        # -7: Flip five coins; target opponent skips X turns (where X = heads)
        def _minus7(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            opponents = [p for p in game.players if p is not ctrl]
            if not opponents:
                return
            try:
                target_opp = ctrl.choose(opponents, "choose target opponent")
            except Exception:
                target_opp = opponents[0]
            heads = sum(1 for _ in range(5) if _coin_flip_fn())
            if heads > 0:
                current = getattr(target_opp, "turns_to_skip", 0)
                target_opp.turns_to_skip = current + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1,
                           description="-1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2,
                           description="-2: Return target creature card with MV 3 or less "
                                       "from your graveyard to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7,
                           description="-7: Flip five coins. Target opponent skips X turns."),
        ]
