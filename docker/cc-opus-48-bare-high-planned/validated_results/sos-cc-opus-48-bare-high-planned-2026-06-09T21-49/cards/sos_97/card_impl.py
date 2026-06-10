"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature_card(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _mana_value(obj: Any) -> int:
    cost = getattr(obj, "mana_cost", None)
    return cost.cmc if cost is not None else 0


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.
    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is
        the number of coins that came up heads.

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
            "+1: Surveil 2.\n−1: Any number of target players each discard a "
            "card.\n−2: Return target creature card with mana value 3 or less "
            "from your graveyard to the battlefield.\n−7: Flip five coins. "
            "Target opponent skips their next X turns, where X is the number of "
            "coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1_surveil(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            # Look at the top 2; for each (from the top down) the player may
            # put it into the graveyard, otherwise it stays on top.
            top_cards = list(library.top(2))
            for card in reversed(top_cards):
                try:
                    to_gy = ctrl.choose_yes_no(
                        f"Surveil: put {getattr(card, 'name', 'card')} into your graveyard?"
                    )
                except Exception:
                    to_gy = False
                if to_gy:
                    library.remove(card)
                    graveyard.add(card)

        def _minus1_discard(game: "GameState") -> None:
            from engine.game import discard

            targets = getattr(pw, "_resolve_targets", None) or []
            for tp in targets:
                if tp is None or not hasattr(tp, "zones"):
                    continue
                hand_cards = tp.zones[Zone.HAND].get_all()
                if not hand_cards:
                    continue
                try:
                    chosen = tp.choose_card(hand_cards, "Discard a card")
                except Exception:
                    chosen = hand_cards[0]
                if chosen is not None:
                    discard(game, tp, chosen)

        def _minus2_reanimate(game: "GameState") -> None:
            from engine.zones import move_to_zone

            ctrl = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if ctrl is None or target is None:
                return
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            if not _is_creature_card(target) or _mana_value(target) > 3:
                return
            target.controller = ctrl
            target.owner = getattr(target, "owner", ctrl) or ctrl
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7_coins(game: "GameState") -> None:
            ctrl = pw.controller
            rng = getattr(game, "rng", None)
            if rng is None:
                import random
                rng = random.Random()
                game.rng = rng
            heads = sum(1 for _ in range(5) if rng.randint(0, 1) == 1)

            # Target opponent (a player that isn't the controller).
            opp = getattr(pw, "_resolve_target", None)
            if opp is None or not hasattr(opp, "zones") or opp is ctrl:
                opp = next((p for p in game.players if p is not ctrl), None)
            if opp is None or heads <= 0:
                return
            idx = game.players.index(opp)
            game.skip_turns[idx] = game.skip_turns.get(idx, 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_surveil,
                           description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1_discard,
                           description="−1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2_reanimate,
                           description="−2: Return a creature card with mana value 3 or less "
                                       "from your graveyard to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7_coins,
                           description="−7: Flip five coins. Target opponent skips their next "
                                       "X turns (X = heads)."),
        ]
