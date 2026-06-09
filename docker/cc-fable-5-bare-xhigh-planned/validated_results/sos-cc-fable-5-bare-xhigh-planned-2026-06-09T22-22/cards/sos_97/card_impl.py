"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


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

        # +1: Surveil 2.
        def _plus1(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            library = game.get_library(ctrl)
            graveyard = game.get_graveyard(ctrl)
            # Look at the top 2 cards (top-most first).
            top = list(reversed(library.top(2)))
            for card in top:
                if not library.contains(card):
                    continue
                if ctrl.choose_yes_no(
                    f"Surveil: put {getattr(card, 'name', 'card')} into graveyard?"
                ):
                    library.remove(card)
                    graveyard.add(card)
                # else: keep on top (left in place).

        # −1: Any number of target players each discard a card.
        def _minus1(game: "GameState") -> None:
            from engine.game import discard

            targets = getattr(pw, "_resolve_targets", None) or []
            for player in targets:
                hand = game.get_hand(player)
                cards = hand.get_all()
                if not cards:
                    continue
                chosen = player.choose_card(cards, "Discard a card")
                if chosen is not None and hand.contains(chosen):
                    discard(game, player, chosen)

        # −2: Reanimate a creature with mana value <= 3 from your graveyard.
        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone

            ctrl = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if ctrl is None or target is None:
                return
            if not game.get_graveyard(ctrl).contains(target):
                return
            if not _is_creature(target):
                return
            cost = getattr(target, "mana_cost", None)
            if cost is not None and cost.cmc > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        # −7: Flip five coins; target opponent skips their next X turns.
        def _minus7(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            rng = getattr(game, "rng", None)
            if rng is None:
                import random
                game.rng = random.Random()
                rng = game.rng
            heads = sum(1 for _ in range(5) if rng.randint(0, 1) == 1)

            target = getattr(pw, "_resolve_target", None)
            if target is None:
                # Default to an opponent of the controller.
                target = next((p for p in game.players if p is not ctrl), None)
            if target is None or target is ctrl:
                return
            seat = game.players.index(target)
            game._skip_turns[seat] = game._skip_turns.get(seat, 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(
                loyalty_cost=-1, effect=_minus1,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2, effect=_minus2,
                description="−2: Return target creature (mv ≤ 3) from your "
                "graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7, effect=_minus7,
                description="−7: Flip five coins; target opponent skips their "
                "next X turns (X = heads).",
            ),
        ]
