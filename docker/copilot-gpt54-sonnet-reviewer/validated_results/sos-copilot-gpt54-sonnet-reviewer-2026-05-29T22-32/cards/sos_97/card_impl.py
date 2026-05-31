"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.game import discard, surveil
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone
from engine.zones import move_to_zone


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer."""

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
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus_one(game: Any) -> None:
            controller = pw.controller
            if controller is None:
                return
            surveil(game, controller, 2)

        def _minus_one(game: Any, *, targets: list[Any] | None = None) -> None:
            chosen_targets = _resolve_targets(pw, targets)
            for player in chosen_targets:
                hand = player.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                chosen_card = player.choose_card(cards_in_hand, "Discard a card")
                if chosen_card is not None and hand.contains(chosen_card):
                    discard(game, player, chosen_card)

        def _minus_two(game: Any, *, targets: list[Any] | None = None) -> None:
            controller = pw.controller
            if controller is None:
                return
            target = _resolve_single_target(pw, targets)
            if target is None:
                return
            if getattr(target, "owner", None) is not controller:
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if getattr(getattr(target, "mana_cost", None), "cmc", 99) > 3:
                return
            if not controller.zones[Zone.GRAVEYARD].contains(target):
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: Any, *, targets: list[Any] | None = None) -> None:
            controller = pw.controller
            if controller is None:
                return
            target_player = _resolve_single_target(pw, targets)
            if target_player is None or target_player is controller:
                return
            heads = 0
            for _ in range(5):
                if game.flip_coin(controller, pw):
                    heads += 1
            game.skip_next_turns(target_player, heads)

        controller = self.controller
        return [
            LoyaltyAbility(
                loyalty_cost=1,
                effect=_plus_one,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus_one,
                description="−1: Any number of target players each discard a card.",
                target_requirements=lambda _game: [
                    TargetRequirement(
                        filter_fn=lambda obj: hasattr(obj, "life"),
                        description="target player",
                        zone=None,
                    )
                ],
                min_targets=0,
                max_targets=None,
                target_description="target players",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus_two,
                description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
                target_requirements=lambda _game, source=pw: [
                    TargetRequirement(
                        filter_fn=lambda obj, _source=source: (
                            CardType.CREATURE in getattr(obj, "card_types", set())
                            and getattr(getattr(obj, "mana_cost", None), "cmc", 99) <= 3
                            and getattr(obj, "owner", None) is getattr(_source, "controller", None)
                        ),
                        description="target creature card with mana value 3 or less from your graveyard",
                        zone=Zone.GRAVEYARD,
                    )
                ],
                min_targets=1,
                max_targets=1,
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus_seven,
                description="−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
                target_requirements=lambda _game, source=pw: [
                    TargetRequirement(
                        filter_fn=lambda obj, _source=source: (
                            hasattr(obj, "life")
                            and obj is not getattr(_source, "controller", None)
                        ),
                        description="target opponent",
                        zone=None,
                    )
                ],
                min_targets=1,
                max_targets=1,
            ),
        ]


def _resolve_targets(source: Any, explicit_targets: list[Any] | None) -> list[Any]:
    """Read chosen targets from the activation wrapper or test shims."""
    if explicit_targets is not None:
        return list(explicit_targets)
    if hasattr(source, "chosen_targets"):
        return list(getattr(source, "chosen_targets") or [])
    if hasattr(source, "_resolve_targets"):
        return list(getattr(source, "_resolve_targets") or [])
    target = getattr(source, "_resolve_target", None)
    return [] if target is None else [target]


def _resolve_single_target(source: Any, explicit_targets: list[Any] | None) -> Any | None:
    """Return the first chosen target, if any."""
    targets = _resolve_targets(source, explicit_targets)
    return targets[0] if targets else None
