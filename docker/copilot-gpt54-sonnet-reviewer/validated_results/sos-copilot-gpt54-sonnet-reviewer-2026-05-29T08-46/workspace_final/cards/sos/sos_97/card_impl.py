"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.game import discard, flip_coin, skip_next_turn
from engine.player import ScriptExhaustedError
from engine.types import CardType, ManaCost, Supertype, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _mana_value(card: Any) -> int:
    """Return *card*'s mana value."""
    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is None:
        return 0
    return mana_cost.cmc


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
        self.chosen_targets: list[Any] = []
        self.last_coin_flip_results: list[bool] = []
        self.last_skipped_turns: int = 0

    def _controller(self) -> Player | None:
        return self.controller if self.controller is not None else self.owner

    def _surveil(self, game: "GameState", count: int) -> None:
        controller = self._controller()
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]
        top_cards = list(library.top(count))
        for card in reversed(top_cards):
            if controller.choose_yes_no(
                f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
            ):
                library.remove(card)
                controller.zones[Zone.GRAVEYARD].add(card)

    def _minus_one_targets(self, game: "GameState", _source: Any | None = None) -> list[Any]:
        return list(game.players)

    def _minus_two_targets(self, game: "GameState", _source: Any | None = None) -> list[Any]:
        controller = self._controller()
        if controller is None:
            return []
        graveyard = controller.zones[Zone.GRAVEYARD]
        return [
            card
            for card in graveyard.get_all()
            if CardType.CREATURE in getattr(card, "card_types", set()) and _mana_value(card) <= 3
        ]

    def _minus_seven_targets(self, game: "GameState", _source: Any | None = None) -> list[Any]:
        controller = self._controller()
        if controller is None:
            return []
        return [player for player in game.players if player is not controller]

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        walker = self

        def _plus_one(game: "GameState") -> None:
            walker._surveil(game, 2)

        def _minus_one(game: "GameState") -> None:
            targets = list(getattr(walker, "chosen_targets", []) or [])
            for player in targets:
                hand = game.get_hand(player)
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                try:
                    chosen_card = player.choose_card(cards_in_hand, "discard a card")
                except (ScriptExhaustedError, NotImplementedError):
                    chosen_card = cards_in_hand[0]
                if chosen_card is None or not hand.contains(chosen_card):
                    chosen_card = cards_in_hand[0]
                discard(game, player, chosen_card)

        def _minus_two(game: "GameState") -> None:
            controller = walker._controller()
            if controller is None:
                return

            targets = list(getattr(walker, "chosen_targets", []) or [])
            if not targets:
                return

            target = targets[0]
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if _mana_value(target) > 3:
                return
            if not game.get_graveyard(controller).contains(target):
                return

            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: "GameState") -> None:
            controller = walker._controller()
            targets = list(getattr(walker, "chosen_targets", []) or [])
            if controller is None or not targets:
                walker.last_coin_flip_results = []
                walker.last_skipped_turns = 0
                return

            target_player = targets[0]
            results = [flip_coin(game, controller) for _ in range(5)]
            heads = sum(1 for result in results if result)
            walker.last_coin_flip_results = results
            walker.last_skipped_turns = heads
            skip_next_turn(game, target_player, heads)

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
                min_targets=0,
                max_targets=None,
                target_type="player",
                target_selector=self._minus_one_targets,
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus_two,
                description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
                min_targets=1,
                max_targets=1,
                target_type="creature card",
                target_selector=self._minus_two_targets,
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus_seven,
                description="−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
                min_targets=1,
                max_targets=1,
                target_type="opponent",
                target_selector=self._minus_seven_targets,
            ),
        ]
