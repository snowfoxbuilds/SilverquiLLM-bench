"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


# Number of coins flipped by the ultimate ability.
_COINS: int = 5


def _cmc(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return cost.cmc if cost is not None else 0


def _is_creature_card(card: Any) -> bool:
    return CardType.CREATURE in getattr(card, "card_types", set())


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.
    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is
        the number of coins that came up heads.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from "
            "your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, "
            "where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)
        self.colors: list[str] = ["B"]

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self
        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=lambda game: pw._surveil(game, 2),
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=pw._each_target_player_discards,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=pw._reanimate_small_creature,
                description=(
                    "−2: Return target creature card with mana value 3 or less "
                    "from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=pw._flip_for_skipped_turns,
                description=(
                    "−7: Flip five coins. Target opponent skips their next X "
                    "turns, where X is the number of heads."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # +1: Surveil 2
    # ------------------------------------------------------------------

    def _surveil(self, game: GameState, amount: int) -> None:
        controller = self.controller
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]
        graveyard = controller.zones[Zone.GRAVEYARD]
        # top(amount) is ordered bottom→top; reverse so we look from the top.
        for card in reversed(library.top(amount)):
            if not library.contains(card):
                continue
            name = getattr(card, "name", "card")
            if controller.choose_yes_no(f"Surveil: put {name} into your graveyard?"):
                library.remove(card)
                graveyard.add(card)

    # ------------------------------------------------------------------
    # −1: Any number of target players each discard a card
    # ------------------------------------------------------------------

    def _each_target_player_discards(self, game: GameState) -> None:
        from engine.game import discard

        controller = self.controller
        if controller is None:
            return
        for player in game.players:
            if not controller.choose_yes_no(f"Target {player.name} to discard a card?"):
                continue
            hand = player.zones[Zone.HAND]
            cards = hand.get_all()
            if not cards:
                continue
            card = player.choose_card(cards, "Discard a card")
            if card is not None and hand.contains(card):
                discard(game, player, card)

    # ------------------------------------------------------------------
    # −2: Reanimate a creature with mana value 3 or less
    # ------------------------------------------------------------------

    def _reanimate_small_creature(self, game: GameState) -> None:
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return
        graveyard = controller.zones[Zone.GRAVEYARD]
        candidates = [
            c for c in graveyard.get_all() if _is_creature_card(c) and _cmc(c) <= 3
        ]
        if not candidates:
            return
        card = controller.choose_card(
            candidates, "Return a creature card (mana value 3 or less) to the battlefield"
        )
        if card is None or not graveyard.contains(card):
            return
        move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

    # ------------------------------------------------------------------
    # −7: Flip five coins; target opponent skips their next X turns
    # ------------------------------------------------------------------

    def _flip_for_skipped_turns(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        opponents = [p for p in game.players if p is not controller]
        if not opponents:
            return
        target = opponents[0] if len(opponents) == 1 else controller.choose(
            opponents, "Choose an opponent to skip turns"
        )
        heads = sum(1 for _ in range(_COINS) if controller.flip_coin())
        if heads > 0:
            target.skipped_turns = getattr(target, "skipped_turns", 0) + heads
