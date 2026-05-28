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
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        source = self

        def _plus_one(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return

            library = controller.zones[Zone.LIBRARY]
            top_cards = library.top(2)
            for card in reversed(top_cards):
                if controller.choose_yes_no(
                    f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
                ):
                    library.remove(card)
                    controller.zones[Zone.GRAVEYARD].add(card)

        def _minus_one(game: GameState) -> None:
            for player in _chosen_targets(source):
                hand = player.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                try:
                    chosen_card = player.choose_card(cards_in_hand, "discard a card")
                except Exception:
                    chosen_card = cards_in_hand[-1]
                if chosen_card is not None and hand.contains(chosen_card):
                    from engine.game import discard

                    discard(game, player, chosen_card)

        def _minus_two(game: GameState) -> None:
            controller = source.controller
            target = _first_chosen_target(source)
            if controller is None or target is None:
                return
            if getattr(target, "owner", None) is not controller:
                return
            if not controller.zones[Zone.GRAVEYARD].contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            mana_cost = getattr(target, "mana_cost", None)
            if mana_cost is None or mana_cost.cmc > 3:
                return

            from engine.zones import move_to_zone

            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: GameState) -> None:
            controller = source.controller
            target_opponent = _first_chosen_target(source)
            if controller is None or target_opponent is None or target_opponent is controller:
                return
            results = game.flip_coins(5)
            heads = sum(1 for result in results if result)
            game.queue_skipped_turns(target_opponent, heads)

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


def _chosen_targets(source: Any) -> list[Any]:
    """Return effect targets from the engine's existing planeswalker backdoors."""
    targets = getattr(source, "chosen_targets", None)
    if targets is not None:
        return list(targets)
    targets = getattr(source, "_resolve_targets", None)
    if targets is not None:
        return list(targets)
    target = getattr(source, "_resolve_target", None)
    if target is None:
        return []
    return [target]


def _first_chosen_target(source: Any) -> Any | None:
    """Return the first chosen target, if any."""
    targets = _chosen_targets(source)
    return targets[0] if targets else None
