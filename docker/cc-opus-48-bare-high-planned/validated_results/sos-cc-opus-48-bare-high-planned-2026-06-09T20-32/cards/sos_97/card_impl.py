"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _cmc(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
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
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
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

        def _plus1_surveil2(game: "GameState") -> None:
            from engine.zones import move_to_zone

            ctrl = pw.controller
            if ctrl is None:
                return
            lib = ctrl.zones[Zone.LIBRARY]
            # Look at the top 2; for each (from the very top), the controller
            # may put it into the graveyard.  The rest stay on top.
            for card in reversed(list(lib.top(2))):
                if not lib.contains(card):
                    continue
                if ctrl.choose_yes_no(f"Surveil: put {card.name} into your graveyard?"):
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        def _minus1_discard(game: "GameState") -> None:
            from engine.game import discard

            targets = getattr(pw, "_resolve_targets", None) or []
            for player in targets:
                if player is None:
                    continue
                hand = player.zones[Zone.HAND]
                cards = hand.get_all()
                if not cards:
                    continue
                chosen = player.choose_card(cards, "discard a card")
                if chosen is not None and hand.contains(chosen):
                    discard(game, player, chosen)

        def _minus2_reanimate(game: "GameState") -> None:
            from engine.zones import move_to_zone

            ctrl = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if ctrl is None or target is None:
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if _cmc(target) > 3:
                return
            if not ctrl.zones[Zone.GRAVEYARD].contains(target):
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7_coinflips(game: "GameState") -> None:
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                return
            rng = getattr(game, "rng", None)
            if rng is None:
                import random
                rng = game.rng = random.Random()
            heads = sum(1 for _ in range(5) if rng.randint(0, 1) == 1)
            if heads <= 0:
                return
            seat = game.players.index(target)
            game.skip_turns[seat] = game.skip_turns.get(seat, 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_surveil2,
                           description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1_discard,
                           description="−1: Any number of target players each "
                                       "discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2_reanimate,
                           description="−2: Return target creature card with "
                                       "mana value 3 or less from your "
                                       "graveyard to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7_coinflips,
                           description="−7: Flip five coins. Target opponent "
                                       "skips their next X turns (X = heads)."),
        ]
