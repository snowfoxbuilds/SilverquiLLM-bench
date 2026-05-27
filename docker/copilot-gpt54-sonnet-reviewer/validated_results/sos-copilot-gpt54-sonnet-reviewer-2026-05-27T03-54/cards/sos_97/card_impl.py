"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _chosen_targets(source: Any) -> list[Any]:
    """Return the chosen targets recorded on *source*."""
    chosen = getattr(source, "chosen_targets", None)
    if chosen is not None:
        return list(chosen)
    chosen = getattr(source, "_resolve_targets", None)
    if chosen is not None:
        return list(chosen)
    target = getattr(source, "_resolve_target", None)
    return [] if target is None else [target]


def _first_chosen_target(source: Any) -> Any | None:
    """Return the first chosen target recorded on *source*."""
    targets = _chosen_targets(source)
    return targets[0] if targets else None


def _surveil(game: "GameState", player: Any, count: int) -> None:
    """Have *player* surveil *count* cards."""
    if player is None or count <= 0:
        return

    library = game.get_library(player)
    graveyard = game.get_graveyard(player)
    cards = list(library.get_all())
    if not cards:
        return

    top_cards = cards[-min(count, len(cards)) :]
    for card in reversed(top_cards):
        if player.choose_yes_no(
            f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
        ):
            library.remove(card)
            graveyard.add(card)


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

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus_one(game: "GameState") -> None:
            _surveil(game, pw.controller, 2)

        def _minus_one(game: "GameState") -> None:
            from engine.game import discard

            for target_player in _chosen_targets(pw):
                if not hasattr(target_player, "zones"):
                    continue
                hand = game.get_hand(target_player)
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                try:
                    chosen = target_player.choose_card(cards_in_hand, "card to discard")
                except Exception:
                    chosen = cards_in_hand[-1]
                if chosen is not None and hand.contains(chosen):
                    discard(game, target_player, chosen)

        def _minus_two(game: "GameState") -> None:
            from engine.zones import move_to_zone

            controller = pw.controller
            target = _first_chosen_target(pw)
            if controller is None or target is None:
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if getattr(getattr(target, "mana_cost", None), "cmc", 0) > 3:
                return
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(target):
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: "GameState") -> None:
            controller = pw.controller
            target = _first_chosen_target(pw)
            if controller is None or target is None or target is controller:
                return
            if not hasattr(target, "life"):
                return
            heads = sum(1 for result in pw.flip_coins(game, 5) if result)
            game.skip_next_turns(target, heads)

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
