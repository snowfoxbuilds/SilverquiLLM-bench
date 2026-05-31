"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Planeswalker — Ral — 3 loyalty.

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
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "\u22121: Any number of target players each discard a card.\n"
            "\u22122: Return target creature card with mana value 3 or less "
            "from your graveyard to the battlefield.\n"
            "\u22127: Flip five coins. Target opponent skips their next X "
            "turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Surveil 2."""
            from engine.game import surveil
            ctrl = pw.controller
            if ctrl is not None:
                surveil(game, ctrl, 2)

        def _minus1(game: Any) -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard as discard_card
            # Targets are set on pw._resolve_targets or chosen_targets.
            targets = getattr(pw, "chosen_targets", None) or []
            if not targets:
                # Try to discard from scripted choice.
                ctrl = pw.controller
                if ctrl is not None:
                    targets = [ctrl]
            for target_player in targets:
                hand = game.get_hand(target_player)
                if len(hand) > 0:
                    cards = hand.get_all()
                    try:
                        card = target_player.choose_card(cards, "Discard a card")
                    except Exception:
                        card = cards[0] if cards else None
                    if card is not None:
                        discard_card(game, target_player, card)

        def _minus2(game: Any) -> None:
            """Return target creature card with MV ≤ 3 from graveyard to battlefield."""
            from engine.zones import move_to_zone
            ctrl = pw.controller
            if ctrl is None:
                return
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                targets = getattr(pw, "chosen_targets", None) or []
                target = targets[0] if targets else None
            if target is None:
                return
            # Validate: creature card in controller's graveyard with MV ≤ 3.
            gy = game.get_graveyard(ctrl)
            if not gy.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            cost = getattr(target, "mana_cost", None)
            mv = cost.cmc if cost else 0
            if mv > 3:
                return
            target.controller = ctrl
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: Any) -> None:
            """Flip five coins. Target opponent skips their next X turns."""
            ctrl = pw.controller
            if ctrl is None:
                return
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                targets = getattr(pw, "chosen_targets", None) or []
                target = targets[0] if targets else None
            if target is None:
                # Default to first opponent.
                for p in game.players:
                    if p is not ctrl:
                        target = p
                        break
            if target is None:
                return
            heads = sum(random.randint(0, 1) for _ in range(5))
            if heads > 0:
                if not hasattr(target, "turns_to_skip"):
                    target.turns_to_skip = 0  # type: ignore[attr-defined]
                target.turns_to_skip += heads  # type: ignore[attr-defined]

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="\u22121: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="\u22122: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="\u22127: Flip five coins. Target opponent skips their next X turns.",
            ),
        ]

