"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import LoyaltyAbility, Planeswalker
from benchmarks.sos.workspace.engine.game import discard, flip_coins, skip_next_turns
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


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
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins "
            "that came up heads.",
        )
        super().__init__(**kwargs)

    def _surveil(self, game: GameState, count: int) -> None:
        controller = self.controller
        if controller is None or count <= 0:
            return
        cards = list(game.get_library(controller).get_all())
        if not cards:
            return
        top_cards = cards[-min(count, len(cards)) :]
        for card in reversed(top_cards):
            if controller.choose_yes_no(
                f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
            ):
                move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

    def _discard_from_hand(self, game: GameState, player: Player) -> None:
        cards_in_hand = game.get_hand(player).get_all()
        if not cards_in_hand:
            return
        try:
            chosen = player.choose_card(cards_in_hand, "card to discard")
        except Exception:
            chosen = cards_in_hand[0]
        if chosen not in cards_in_hand:
            chosen = cards_in_hand[0]
        discard(game, player, chosen)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        source = self

        def _plus_one(game: GameState) -> None:
            source._surveil(game, 2)

        def _minus_one(game: GameState) -> None:
            seen_players: set[int] = set()
            for player in getattr(source, "chosen_targets", []):
                if not hasattr(player, "zones"):
                    continue
                player_identity = id(player)
                if player_identity in seen_players:
                    continue
                seen_players.add(player_identity)
                source._discard_from_hand(game, player)

        def _minus_two(game: GameState) -> None:
            controller = source.controller
            target = (
                getattr(source, "chosen_targets", [None])[0]
                if getattr(source, "chosen_targets", None)
                else None
            )
            if controller is None or target is None:
                return
            if not game.get_graveyard(controller).contains(target):
                return
            if not hasattr(target, "base_power"):
                return
            if getattr(getattr(target, "mana_cost", None), "cmc", 0) > 3:
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: GameState) -> None:
            controller = source.controller
            target = (
                getattr(source, "chosen_targets", [None])[0]
                if getattr(source, "chosen_targets", None)
                else None
            )
            if controller is None or target is None or target is controller:
                return
            heads = sum(1 for result in flip_coins(game, 5, controller) if result)
            skip_next_turns(game, target, heads)

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
                description="−7: Flip five coins. Target opponent skips their next X turns.",
            ),
        ]
