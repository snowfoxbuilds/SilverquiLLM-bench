"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.game import discard
from engine.types import CardType, ManaCost, Supertype, Zone
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
        self.last_coin_flip_heads: int = 0

    def _resolved_targets(self) -> list[Any]:
        targets = getattr(self, "chosen_targets", None)
        if targets is not None:
            return list(targets)

        targets = getattr(self, "_resolve_targets", None)
        if targets is not None:
            return list(targets)

        target = getattr(self, "_resolve_target", None)
        if target is None:
            return []
        return [target]

    def _surveil(self, game: "GameState", controller: "Player | None", count: int) -> None:
        if controller is None or count <= 0:
            return

        library = controller.zones[Zone.LIBRARY]
        cards = list(library.get_all())
        if not cards:
            return

        top_cards = cards[-min(count, len(cards)):]
        for card in reversed(top_cards):
            if controller.choose_yes_no(
                f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
            ):
                library.remove(card)
                controller.zones[Zone.GRAVEYARD].add(card)

    def _discard_one(self, game: "GameState", player: "Player") -> None:
        hand = player.zones[Zone.HAND]
        cards = hand.get_all()
        if not cards:
            return

        try:
            chosen = player.choose_card(cards, "discard a card")
        except Exception:
            chosen = cards[-1]

        if chosen is None or not hand.contains(chosen):
            return
        discard(game, player, chosen)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        plus1_controller = pw.controller
        minus1_targets = pw._resolved_targets()
        minus2_controller = pw.controller
        minus2_target = next(iter(pw._resolved_targets()), None)
        minus7_controller = pw.controller
        minus7_target = next(iter(pw._resolved_targets()), None)

        def _plus1(game: "GameState") -> None:
            pw._surveil(game, plus1_controller, 2)

        def _minus1(game: "GameState") -> None:
            for player in minus1_targets:
                if hasattr(player, "zones") and hasattr(player, "choose_card"):
                    pw._discard_one(game, player)

        def _minus2(game: "GameState") -> None:
            controller = minus2_controller
            if controller is None:
                return

            target = minus2_target
            if target is None:
                return

            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return

            mana_cost = getattr(target, "mana_cost", None)
            if mana_cost is not None and mana_cost.cmc > 3:
                return

            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            controller = minus7_controller
            if controller is None:
                return

            target = minus7_target
            if target is None or target is controller or target not in game.players:
                return

            results = pw.flip_coins(game, 5, player=controller)
            heads = sum(1 for result in results if result)
            pw.last_coin_flip_heads = heads
            if heads > 0:
                game.skip_next_turns(target, heads)

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
            ),
        ]
