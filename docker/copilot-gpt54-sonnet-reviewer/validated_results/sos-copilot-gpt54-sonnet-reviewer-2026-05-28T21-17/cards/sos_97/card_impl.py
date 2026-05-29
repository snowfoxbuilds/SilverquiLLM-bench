"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.game import discard, surveil
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_targets(self, game: "GameState") -> list[list[TargetRequirement]]:
        controller = self.controller

        def _is_player(obj: Any) -> bool:
            return hasattr(obj, "life")

        def _is_small_graveyard_creature(obj: Any) -> bool:
            if CardType.CREATURE not in getattr(obj, "card_types", set()):
                return False
            if getattr(getattr(obj, "mana_cost", None), "cmc", 99) > 3:
                return False
            if controller is None:
                return True
            return controller.zones[Zone.GRAVEYARD].contains(obj)

        def _is_opponent(obj: Any) -> bool:
            return hasattr(obj, "life") and obj is not controller

        return [
            [],
            [
                TargetRequirement(
                    filter_fn=_is_player,
                    description="target player",
                    zone=Zone.BATTLEFIELD,
                    min_targets=0,
                    max_targets=None,
                )
            ],
            [
                TargetRequirement(
                    filter_fn=_is_small_graveyard_creature,
                    description="target creature card with mana value 3 or less from your graveyard",
                    zone=Zone.GRAVEYARD,
                )
            ],
            [
                TargetRequirement(
                    filter_fn=_is_opponent,
                    description="target opponent",
                    zone=Zone.BATTLEFIELD,
                )
            ],
        ]

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus_one(game: "GameState") -> None:
            controller = pw.controller
            if controller is None:
                return
            surveil(game, controller, 2)

        def _minus_one(game: "GameState") -> None:
            for player in list(getattr(pw, "chosen_targets", []) or []):
                hand = game.get_hand(player)
                cards = hand.get_all()
                if not cards:
                    continue
                chosen = player.choose_card(cards, "Choose a card to discard")
                if chosen not in cards:
                    chosen = cards[-1]
                discard(game, player, chosen)

        def _minus_two(game: "GameState") -> None:
            controller = pw.controller
            targets = getattr(pw, "chosen_targets", []) or []
            if controller is None or not targets:
                return
            target = targets[0]
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if getattr(getattr(target, "mana_cost", None), "cmc", 99) > 3:
                return
            if not game.get_graveyard(controller).contains(target):
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: "GameState") -> None:
            targets = getattr(pw, "chosen_targets", []) or []
            if not targets:
                return
            opponent = targets[0]
            if not hasattr(opponent, "life") or opponent is pw.controller:
                return
            heads = sum(1 for _ in range(5) if game.flip_coin())
            game.skip_next_turns(opponent, heads)

        return [
            LoyaltyAbility(loyalty_cost=1, effect=_plus_one, description="+1: Surveil 2."),
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
