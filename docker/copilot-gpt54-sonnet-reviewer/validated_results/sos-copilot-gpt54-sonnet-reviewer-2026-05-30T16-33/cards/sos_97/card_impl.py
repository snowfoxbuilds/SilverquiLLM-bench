"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.game import discard
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _surveil(game: "GameState", player: "Player", count: int) -> None:
    """Surveil *count* cards for *player*."""
    library = player.zones[Zone.LIBRARY]
    cards = list(library.get_all())
    if not cards:
        return

    top_cards = cards[-min(count, len(cards)):]
    for card in reversed(top_cards):
        put_in_graveyard = player.choose_yes_no(
            f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
        )
        if put_in_graveyard and library.contains(card):
            library.remove(card)
            player.zones[Zone.GRAVEYARD].add(card)


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer."""

    surveil_amount: int = 2

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs["keywords"] = kwargs.get("keywords") or Keyword(0)
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)
        self.mechanic_keywords: set[str] = {"Surveil"}
        self.keyword_metadata: dict[str, dict[str, Any]] = {
            "Surveil": {"amount": self.surveil_amount, "ability_cost": +1}
        }
        self.last_coin_flip_results: list[bool] = []
        self.last_coin_flip_heads: int = 0

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus_one(game: "GameState") -> None:
            controller = pw.controller
            if controller is None:
                return
            _surveil(game, controller, pw.surveil_amount)

        def _minus_one(game: "GameState") -> None:
            for player in getattr(pw, "chosen_targets", []) or []:
                hand = game.get_hand(player)
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                chosen_card = player.choose_card(cards_in_hand, "Discard a card")
                if chosen_card is None or not hand.contains(chosen_card):
                    chosen_card = cards_in_hand[-1]
                discard(game, player, chosen_card)

        def _minus_two(game: "GameState") -> None:
            controller = pw.controller
            chosen = getattr(pw, "chosen_targets", None) or []
            target = chosen[0] if chosen else None
            if controller is None or target is None:
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if getattr(getattr(target, "mana_cost", None), "cmc", 0) > 3:
                return
            if not controller.zones[Zone.GRAVEYARD].contains(target):
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus_seven(game: "GameState") -> None:
            controller = pw.controller
            chosen = getattr(pw, "chosen_targets", None) or []
            target = chosen[0] if chosen else None
            if controller is None or target is None or target is controller:
                return
            if target not in game.players:
                return

            results = [game.flip_coin() for _ in range(5)]
            heads = sum(1 for result in results if result)
            pw.last_coin_flip_results = results
            pw.last_coin_flip_heads = heads
            if heads > 0:
                game.schedule_skip_next_turn(target, heads)

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus_one, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus_one, description="−1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus_two, description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus_seven, description="−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads."),
        ]
