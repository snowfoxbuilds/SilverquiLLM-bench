"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — loyalty 3 — Legendary
    Planeswalker — Ral.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where
        X is the number of coins that came up heads.

    SOS collector number 97.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n−1: Any number of target players each discard "
            "a card.\n−2: Return target creature card with mana value 3 or "
            "less from your graveyard to the battlefield.\n−7: Flip five "
            "coins. Target opponent skips their next X turns, where X is "
            "the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            """Surveil 2 — look at the top two cards; bin any, rest stay
            on top (kept cards retain their order — a legal choice)."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            top_cards = library.top(2)  # bottom→top order
            for card in reversed(top_cards):  # look from the top down
                try:
                    to_graveyard = controller.choose_yes_no(
                        f"Surveil — put {getattr(card, 'name', 'card')} into "
                        "your graveyard?"
                    )
                except Exception:
                    to_graveyard = False
                if to_graveyard:
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            targets = getattr(pw, "_resolve_targets", None)
            if targets is None:
                single = getattr(pw, "_resolve_target", None)
                targets = [single] if single is not None else []
            for player in targets:
                if player not in game.players:
                    continue
                hand = player.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                try:
                    chosen = player.choose_card(
                        cards_in_hand, "Choose a card to discard"
                    )
                except Exception:
                    chosen = cards_in_hand[-1]
                if chosen is not None and hand.contains(chosen):
                    discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            """Return target creature card with mana value <= 3 from your
            graveyard to the battlefield."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            target = getattr(pw, "_resolve_target", None)
            graveyard = controller.zones[Zone.GRAVEYARD]
            if target is None or not graveyard.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if getattr(target, "mana_cost", ManaCost()).cmc > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """Flip five coins; target opponent skips their next X turns."""
            controller = pw.controller
            if controller is None:
                return
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                target = game.non_active_player if game.active_player is controller else game.active_player
            if target not in game.players or target is controller:
                return
            rng = getattr(game, "rng", None)
            if rng is None:
                rng = random.Random()
                game.rng = rng  # seedable in tests for determinism
            heads = sum(rng.randint(0, 1) for _ in range(5))
            if heads <= 0:
                return
            idx = game.players.index(target)
            game.skip_turns[idx] = game.skip_turns.get(idx, 0) + heads

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
                description=(
                    "−2: Return target creature card with mana value 3 or "
                    "less from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description=(
                    "−7: Flip five coins. Target opponent skips their next "
                    "X turns, where X is the number of heads."
                ),
            ),
        ]
