"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

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
        self.last_coin_flip_results: list[bool] = []
        self.last_coin_flip_heads: int = 0

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        walker = self

        def _plus_one(game: "GameState") -> None:
            from engine.game import surveil

            controller = walker.controller or walker.owner
            if controller is None:
                return
            surveil(game, controller, 2)

        def _minus_one(game: "GameState") -> None:
            from engine.game import discard

            unique_players: list[Any] = []
            for player in list(getattr(walker, "chosen_targets", []) or []):
                if any(existing is player for existing in unique_players):
                    continue
                unique_players.append(player)

            for player in unique_players:
                hand = game.get_hand(player)
                cards = hand.get_all()
                if not cards:
                    continue
                chosen = player.choose_card(cards, "Choose a card to discard")
                if chosen is None or not hand.contains(chosen):
                    chosen = cards[-1]
                discard(game, player, chosen)

        def _minus_two(game: "GameState") -> None:
            from engine.zones import move_to_zone

            controller = walker.controller or walker.owner
            if controller is None:
                return
            targets = getattr(walker, "chosen_targets", []) or []
            target = targets[0] if targets else None
            if target is None:
                return
            if not game.get_graveyard(controller).contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            mana_value = getattr(getattr(target, "mana_cost", None), "cmc", 0)
            if mana_value > 3:
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: "GameState") -> None:
            from engine.game import flip_coin

            controller = walker.controller or walker.owner
            targets = getattr(walker, "chosen_targets", []) or []
            target_player = targets[0] if targets else None
            if controller is None or target_player is None or target_player is controller:
                return
            results = [flip_coin(game, controller, walker) for _ in range(5)]
            walker.last_coin_flip_results = list(results)
            walker.last_coin_flip_heads = sum(1 for result in results if result)
            if walker.last_coin_flip_heads > 0 and hasattr(game, "schedule_skip_next_turns"):
                game.schedule_skip_next_turns(target_player, walker.last_coin_flip_heads)

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
