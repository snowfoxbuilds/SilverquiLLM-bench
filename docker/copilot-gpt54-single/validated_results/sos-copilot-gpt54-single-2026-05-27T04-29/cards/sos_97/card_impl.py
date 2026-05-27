"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from itertools import permutations
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.game import discard
from engine.types import CardType, Color, ManaCost, Supertype, TargetRequirement, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_first_target(source: Any) -> Any:
    chosen_targets = getattr(source, "chosen_targets", None)
    if chosen_targets:
        return chosen_targets[0]
    return getattr(source, "_resolve_target", None)


def _get_all_targets(source: Any) -> list[Any]:
    chosen_targets = getattr(source, "chosen_targets", None)
    if chosen_targets is not None:
        return list(chosen_targets)
    resolve_targets = getattr(source, "_resolve_targets", None)
    if resolve_targets is not None:
        return list(resolve_targets)
    target = getattr(source, "_resolve_target", None)
    if target is not None:
        return [target]
    return []


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and hasattr(obj, "zones")


def _is_creature_card(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _same_objects(left: list[Any], right: list[Any]) -> bool:
    return len(left) == len(right) and all(
        any(candidate is obj for candidate in right) for obj in left
    )


def _normalize_selected_cards(options: list[Any], selected: Any) -> list[Any] | None:
    if selected is None:
        return []
    if not isinstance(selected, (list, tuple, set)):
        return None
    normalized = list(selected)
    if len({id(card) for card in normalized}) != len(normalized):
        return None
    if not all(any(choice is card for choice in options) for card in normalized):
        return None
    return normalized


def _choose_cards_to_surveil(controller: Any, top_cards: list[Any]) -> list[Any]:
    if hasattr(controller, "choose_cards"):
        try:
            chosen = controller.choose_cards(
                list(reversed(top_cards)),
                min_count=0,
                max_count=len(top_cards),
                prompt="Choose cards to put into your graveyard with surveil.",
            )
            normalized = _normalize_selected_cards(top_cards, chosen)
            if normalized is not None:
                return normalized
        except Exception:
            pass

    graveyard_cards: list[Any] = []
    for card in reversed(top_cards):
        if controller.choose_yes_no(
            f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
        ):
            graveyard_cards.append(card)
    return graveyard_cards


def _choose_library_order(controller: Any, kept_cards: list[Any]) -> list[Any]:
    if len(kept_cards) <= 1:
        return list(kept_cards)

    if hasattr(controller, "choose"):
        try:
            options = [list(order) for order in permutations(kept_cards)]
            chosen_order = controller.choose(
                options,
                "Choose the bottom-to-top order for the cards remaining on top of your library.",
            )
            normalized = _normalize_selected_cards(kept_cards, chosen_order)
            if normalized is not None and _same_objects(normalized, kept_cards):
                return normalized
        except Exception:
            pass

    ordered_top_to_bottom: list[Any] = []
    remaining = list(kept_cards)
    while len(remaining) > 1 and hasattr(controller, "choose_card"):
        try:
            choice = controller.choose_card(
                remaining,
                "Choose the next card to remain on top of your library.",
            )
        except Exception:
            break
        if not any(choice is candidate for candidate in remaining):
            break
        ordered_top_to_bottom.append(choice)
        remaining = [candidate for candidate in remaining if candidate is not choice]

    if len(ordered_top_to_bottom) == len(kept_cards) - 1:
        ordered_top_to_bottom.extend(remaining)
        return list(reversed(ordered_top_to_bottom))

    return list(kept_cards)


def _surveil(game: "GameState", controller: Any, count: int) -> None:
    del game
    library = controller.zones[Zone.LIBRARY]
    cards = list(library.get_all())
    if not cards:
        return

    top_cards = cards[-min(count, len(cards)) :]
    graveyard_cards = _choose_cards_to_surveil(controller, top_cards)
    kept_cards = [card for card in top_cards if not any(card is chosen for chosen in graveyard_cards)]
    ordered_kept_cards = _choose_library_order(controller, kept_cards)

    for card in top_cards:
        if library.contains(card):
            library.remove(card)
    for card in graveyard_cards:
        controller.zones[Zone.GRAVEYARD].add(card)
    for card in ordered_kept_cards:
        library.add(card)


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("colors", {Color.BLACK})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard "
            "to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is "
            "the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_target_requirements(
        self,
        game: "GameState",
        ability_index: int,
    ) -> list[TargetRequirement]:
        """Expose target requirements for tests and higher-level callers."""
        controller = self.controller
        if ability_index == 1:
            return [
                TargetRequirement(
                    filter_fn=_is_player,
                    description="target player",
                    zone=Zone.BATTLEFIELD,
                    min_targets=0,
                    max_targets=None,
                )
            ]
        if ability_index == 2 and controller is not None:
            return [
                TargetRequirement(
                    filter_fn=lambda obj, ctrl=controller: (
                        _is_creature_card(obj)
                        and getattr(obj, "owner", None) is ctrl
                        and getattr(obj, "mana_cost", ManaCost()).cmc <= 3
                    ),
                    description="target creature card with mana value 3 or less from your graveyard",
                    zone=Zone.GRAVEYARD,
                )
            ]
        if ability_index == 3 and controller is not None:
            return [
                TargetRequirement(
                    filter_fn=lambda obj, ctrl=controller: _is_player(obj) and obj is not ctrl,
                    description="target opponent",
                    zone=Zone.BATTLEFIELD,
                )
            ]
        return []

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        source = self

        def _plus_one(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            _surveil(game, controller, 2)

        def _minus_one(game: "GameState") -> None:
            for player in _get_all_targets(source):
                if not _is_player(player):
                    continue
                hand = game.get_hand(player)
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                chosen_card = player.choose_card(cards_in_hand, "discard a card")
                if chosen_card not in cards_in_hand:
                    chosen_card = cards_in_hand[0]
                discard(game, player, chosen_card)

        def _minus_two(game: "GameState") -> None:
            controller = source.controller
            target = _get_first_target(source)
            if controller is None or target is None:
                return
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(target):
                return
            if not _is_creature_card(target):
                return
            if getattr(target, "mana_cost", ManaCost()).cmc > 3:
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: "GameState") -> None:
            controller = source.controller
            target = _get_first_target(source)
            if controller is None or not _is_player(target) or target is controller:
                return
            results = game.flip_coins(5, player=controller, source=source)
            heads = sum(1 for result in results if result)
            if heads > 0:
                game.schedule_skip_next_turns(target, heads)

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
                description=(
                    "−2: Return target creature card with mana value 3 or less from your "
                    "graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus_seven,
                description=(
                    "−7: Flip five coins. Target opponent skips their next X turns, where X "
                    "is the number of coins that came up heads."
                ),
            ),
        ]
