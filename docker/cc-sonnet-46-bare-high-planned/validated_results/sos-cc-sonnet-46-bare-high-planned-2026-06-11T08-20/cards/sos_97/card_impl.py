"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_targets(pw: Any) -> list[Any]:
    """Read chosen targets from chosen_targets or _resolve_targets."""
    ct = getattr(pw, "chosen_targets", None)
    if ct:
        return list(ct)
    rt = getattr(pw, "_resolve_targets", None)
    if rt:
        return list(rt)
    single = getattr(pw, "_resolve_target", None)
    if single is not None:
        return [single]
    return []


def _get_target(pw: Any) -> Any:
    targets = _get_targets(pw)
    return targets[0] if targets else None


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral, starting loyalty 3.

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
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
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

        def _plus1(game: Any) -> None:
            """Surveil 2: look at top 2 cards; send any to graveyard, rest on top."""
            ctrl = pw.controller
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            top_cards = library.top(2)
            if not top_cards:
                return
            # top_cards is ordered bottom→top; reverse to process top first
            to_process = list(reversed(top_cards))
            kept: list[Any] = []
            for card in to_process:
                try:
                    if ctrl.choose_yes_no(f"Put {card.name} in graveyard?"):
                        library.remove(card)
                        ctrl.zones[Zone.GRAVEYARD].add(card)
                    else:
                        kept.append(card)
                except Exception:
                    kept.append(card)
            # Put kept cards back on top (they were already in library; just remove/re-add in order)
            # kept is ordered from top-card-first; re-add bottom-first to maintain top order
            for card in reversed(kept):
                library.remove(card)
            for card in kept:
                library.add(card)

        def _minus1(game: Any) -> None:
            """Each targeted player discards a card."""
            from engine.game import discard

            targets = _get_targets(pw)
            for player in targets:
                if not hasattr(player, "zones"):
                    continue
                hand_cards = player.zones[Zone.HAND].get_all()
                if not hand_cards:
                    continue
                try:
                    chosen = player.choose_card(hand_cards, "Discard a card")
                except Exception:
                    chosen = hand_cards[0] if hand_cards else None
                if chosen is not None:
                    discard(game, player, chosen)

        def _minus2(game: Any) -> None:
            """Reanimate target creature with MV ≤ 3 from graveyard."""
            from engine.zones import move_to_zone

            ctrl = pw.controller
            if ctrl is None:
                return
            target = _get_target(pw)
            if target is None:
                return
            # Validate: must be a creature card in controller's graveyard with MV ≤ 3
            gy = ctrl.zones[Zone.GRAVEYARD]
            if not gy.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            mc = getattr(target, "mana_cost", None)
            if mc is not None and mc.cmc > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: Any) -> None:
            """Flip 5 coins; target opponent skips next X turns (X = heads)."""
            target = _get_target(pw)
            if target is None or not hasattr(target, "life"):
                return  # target must be a player

            rng = getattr(game, "rng", None)
            if rng is None:
                rng = random.Random()

            heads = sum(rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                current_skips = getattr(target, "skip_turns", 0)
                target.skip_turns = current_skips + heads  # type: ignore[attr-defined]

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1, description="−1: Target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description="−2: Reanimate creature with MV ≤ 3 from graveyard."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="−7: Flip 5 coins; opponent skips X turns (heads)."),
        ]
