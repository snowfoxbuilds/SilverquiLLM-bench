"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


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

    def get_loyalty_targets(self, game: "GameState", ability_index: int) -> list[TargetRequirement]:
        """Expose public target requirements for Ral's targeted loyalty abilities."""
        controller = self.controller or self.owner

        if ability_index == 1:
            requirement = TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="any number of target players",
                zone=Zone.BATTLEFIELD,
            )
            requirement.min_targets = 0  # type: ignore[attr-defined]
            requirement.max_targets = None  # type: ignore[attr-defined]
            return [requirement]

        if ability_index == 2:
            return [
                TargetRequirement(
                    filter_fn=lambda obj, _c=controller: (
                        CardType.CREATURE in getattr(obj, "card_types", set())
                        and _c is not None
                        and _c.zones[Zone.GRAVEYARD].contains(obj)
                        and getattr(getattr(obj, "mana_cost", None), "cmc", 0) <= 3
                    ),
                    description="target creature card with mana value 3 or less from your graveyard",
                    zone=Zone.GRAVEYARD,
                )
            ]

        if ability_index == 3:
            return [
                TargetRequirement(
                    filter_fn=lambda obj, _c=controller: hasattr(obj, "life") and obj is not _c,
                    description="target opponent",
                    zone=Zone.BATTLEFIELD,
                )
            ]

        return []

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus_one(game: "GameState") -> None:
            controller = pw.controller or pw.owner
            if controller is None:
                return

            library = controller.zones[Zone.LIBRARY]
            cards = list(library.get_all())
            if not cards:
                return

            top_cards = cards[-min(2, len(cards)):]
            for card in reversed(top_cards):
                if controller.choose_yes_no(
                    f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
                ):
                    library.remove(card)
                    controller.zones[Zone.GRAVEYARD].add(card)

        def _minus_one(game: "GameState") -> None:
            from engine.game import discard

            targets = list(getattr(pw, "_resolve_targets", None) or getattr(pw, "chosen_targets", None) or [])
            for player in targets:
                hand = player.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                chosen = player.choose_card(cards_in_hand, "card to discard")
                if chosen is not None:
                    discard(game, player, chosen)

        def _minus_two(game: "GameState") -> None:
            from engine.zones import move_to_zone

            controller = pw.controller or pw.owner
            target = getattr(pw, "_resolve_target", None)
            if controller is None or target is None:
                return
            if not controller.zones[Zone.GRAVEYARD].contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if getattr(getattr(target, "mana_cost", None), "cmc", 0) > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: "GameState") -> None:
            from engine.game import flip_coins, skip_next_turns

            controller = pw.controller or pw.owner
            target = getattr(pw, "_resolve_target", None)
            results = flip_coins(game, 5, player=controller, source=pw)
            heads = sum(1 for result in results if result)
            if controller is None or target is None or target is controller or heads <= 0:
                return
            skip_next_turns(game, target, heads)

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
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus_two,
                description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus_seven,
                description="−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
            ),
        ]
