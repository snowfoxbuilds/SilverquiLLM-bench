"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.game import discard, flip_coins
from engine.types import ManaCost, Supertype, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


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

        def _distinct_targets(targets: list[Player]) -> list[Player]:
            distinct: list[Player] = []
            for player in targets:
                if player is None or player in distinct:
                    continue
                distinct.append(player)
            return distinct

        def _plus_one(game: GameState) -> None:
            controller = pw.controller
            if controller is None:
                return
            library = game.get_library(controller)
            top_cards = list(library.top(2))
            kept_cards: list[Any] = []
            for card in reversed(top_cards):
                if controller.choose_yes_no(
                    f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
                ):
                    library.remove(card)
                    game.get_graveyard(controller).add(card)
                else:
                    kept_cards.append(card)

            if len(kept_cards) >= 2:
                original_order = list(reversed(kept_cards))
                reordered = original_order
                try:
                    chosen_order = controller.choose(
                        [original_order, list(reversed(original_order))],
                        "choose order for cards kept on top after surveil",
                    )
                    chosen_order_list = list(chosen_order)
                    if (
                        len(chosen_order_list) == len(original_order)
                        and sorted(id(card) for card in chosen_order_list)
                        == sorted(id(card) for card in original_order)
                    ):
                        reordered = chosen_order_list
                except Exception:
                    reordered = original_order

                for card in original_order:
                    if library.contains(card):
                        library.remove(card)
                for card in reordered:
                    library.add(card)

        def _minus_one(game: GameState) -> None:
            for player in _distinct_targets(list(getattr(pw, "chosen_targets", []))):
                hand = game.get_hand(player)
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                chosen = player.choose_card(cards_in_hand, "discard a card")
                if chosen is not None and hand.contains(chosen):
                    discard(game, player, chosen)

        def _minus_two(game: GameState) -> None:
            controller = pw.controller
            if controller is None:
                return
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                chosen_targets = list(getattr(pw, "chosen_targets", []))
                target = chosen_targets[0] if chosen_targets else None
            if target is None:
                return
            if not isinstance(target, Creature):
                return
            if target.mana_cost.cmc > 3:
                return
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(target):
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: GameState) -> None:
            controller = pw.controller
            if controller is None:
                return
            chosen_targets = list(getattr(pw, "chosen_targets", []))
            if not chosen_targets:
                return
            target_opponent = chosen_targets[0]
            if (
                target_opponent is None
                or target_opponent is controller
                or target_opponent not in getattr(game, "players", [])
            ):
                return
            results = flip_coins(game, 5)
            heads = sum(1 for result in results if result)
            pw.last_coin_flip_results = results
            pw.last_coin_flip_heads = heads
            if hasattr(game, "schedule_skip_next_turns"):
                game.schedule_skip_next_turns(target_opponent, heads)

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
