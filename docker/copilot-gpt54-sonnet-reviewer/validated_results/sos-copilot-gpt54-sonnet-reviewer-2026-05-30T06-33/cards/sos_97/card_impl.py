"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


ORACLE_TEXT = (
    "+1: Surveil 2.\n"
    "−1: Any number of target players each discard a card.\n"
    "−2: Return target creature card with mana value 3 or less from your "
    "graveyard to the battlefield.\n"
    "−7: Flip five coins. Target opponent skips their next X turns, where X "
    "is the number of coins that came up heads."
)


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
        kwargs.setdefault("rules_text", ORACLE_TEXT)
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        source = self

        def _plus_one(game: "GameState") -> None:
            from engine.game import surveil

            controller = source.controller
            if controller is None:
                return
            source.last_surveil_result = surveil(game, controller, 2)

        def _minus_one(game: "GameState") -> None:
            from engine.game import discard

            for player in self._chosen_targets():
                hand = player.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                try:
                    chosen_card = player.choose_card(cards_in_hand, "Choose a card to discard")
                except Exception:
                    chosen_card = cards_in_hand[0]
                if chosen_card is None or not hand.contains(chosen_card):
                    chosen_card = cards_in_hand[0]
                discard(game, player, chosen_card)

        def _minus_two(game: "GameState") -> None:
            from engine.zones import move_to_zone

            controller = source.controller
            target = self._first_chosen_target()
            if controller is None or target is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            mana_cost = getattr(target, "mana_cost", None)
            mana_value = mana_cost.cmc if mana_cost is not None else 0
            if mana_value > 3:
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: "GameState") -> None:
            from engine.game import flip_coin, schedule_skip_next_turn

            controller = source.controller
            target = self._first_chosen_target()
            if controller is None or target is None or target is controller:
                return
            results = [flip_coin(game, controller, source) for _ in range(5)]
            source.last_coin_flip_results = results
            heads = sum(1 for result in results if result)
            source.last_coin_flip_heads = heads
            if heads > 0:
                schedule_skip_next_turn(game, target, heads)

        return [
            LoyaltyAbility(loyalty_cost=1, effect=_plus_one, description="+1: Surveil 2."),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus_one,
                description="−1: Any number of target players each discard a card.",
                target_requirements=self._minus_one_target_requirements,
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus_two,
                description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
                target_requirements=self._minus_two_target_requirements,
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus_seven,
                description="−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
                target_requirements=self._minus_seven_target_requirements,
            ),
        ]

    def _chosen_targets(self) -> list[Any]:
        chosen = getattr(self, "chosen_targets", None)
        if chosen is not None:
            return list(chosen)
        chosen = getattr(self, "_resolve_targets", None)
        if chosen is not None:
            return list(chosen)
        target = getattr(self, "_resolve_target", None)
        return [] if target is None else [target]

    def _first_chosen_target(self) -> Any | None:
        chosen = self._chosen_targets()
        return chosen[0] if chosen else None

    def _minus_one_target_requirements(
        self,
        game: "GameState",
        source: Any,
    ) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj in game.players,
                description="any number of target players",
                zone=None,
                options_getter=lambda current_game: list(current_game.players),
                min_targets=0,
                max_targets=len(game.players),
            )
        ]

    def _minus_two_target_requirements(
        self,
        game: "GameState",
        source: Any,
    ) -> list[TargetRequirement]:
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj: self._is_small_creature_in_your_graveyard(obj, controller),
                description="target creature card with mana value 3 or less from your graveyard",
                zone=Zone.GRAVEYARD,
                options_getter=lambda _game: [] if controller is None else list(controller.zones[Zone.GRAVEYARD].get_all()),
            )
        ]

    def _minus_seven_target_requirements(
        self,
        game: "GameState",
        source: Any,
    ) -> list[TargetRequirement]:
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj in game.players and obj is not controller,
                description="target opponent",
                zone=None,
                options_getter=lambda current_game: [
                    player for player in current_game.players if player is not controller
                ],
            )
        ]

    @staticmethod
    def _is_small_creature_in_your_graveyard(obj: Any, controller: Any) -> bool:
        if controller is None:
            return False
        if CardType.CREATURE not in getattr(obj, "card_types", set()):
            return False
        if not controller.zones[Zone.GRAVEYARD].contains(obj):
            return False
        mana_cost = getattr(obj, "mana_cost", None)
        mana_value = mana_cost.cmc if mana_cost is not None else 0
        return mana_value <= 3
