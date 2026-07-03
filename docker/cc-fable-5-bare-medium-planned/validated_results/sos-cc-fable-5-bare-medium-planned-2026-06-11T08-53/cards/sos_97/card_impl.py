"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and hasattr(obj, "zones")


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker —
    Ral — starting loyalty 3.

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
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("supertypes", {"Legendary"})
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

        def _plus1_surveil2(game: GameState) -> None:
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            library = game.get_library(controller)
            looked = list(reversed(library.top(2)))  # topmost first
            for card in looked:
                try:
                    to_graveyard = controller.choose_yes_no(
                        f"Surveil: put {getattr(card, 'name', 'card')} into "
                        "your graveyard? (No keeps it on top)"
                    )
                except Exception:
                    to_graveyard = False
                if to_graveyard:
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
            # Cards kept stay on top in their original order (the engine
            # offers no reorder primitive — deliberate simplification).

        def _minus1_discards(game: GameState) -> None:
            from engine.game import discard

            targets = [
                t
                for t in (getattr(pw, "chosen_targets", None) or [])
                if _is_player(t)
            ]
            for player in targets:
                hand = game.get_hand(player).get_all()
                if not hand:
                    continue
                try:
                    chosen = player.choose_card(hand, "Choose a card to discard")
                except Exception:
                    chosen = hand[0]
                if chosen is None:
                    chosen = hand[0]
                discard(game, player, chosen)

        def _minus2_reanimate(game: GameState) -> None:
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            chosen = getattr(pw, "chosen_targets", None) or []
            target = chosen[0] if chosen else None
            if target is None:
                return
            # Validate: creature card, mv <= 3, in your graveyard.
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if getattr(target.mana_cost, "cmc", 0) > 3:
                return
            if not game.get_graveyard(controller).contains(target):
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7_skip_turns(game: GameState) -> None:
            controller = pw.controller
            chosen = getattr(pw, "chosen_targets", None) or []
            target = chosen[0] if chosen else None
            if not _is_player(target) or target is controller:
                return
            heads = sum(game.rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                target.skip_turns += heads

        return [
            LoyaltyAbility(
                loyalty_cost=1,
                effect=_plus1_surveil2,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1_discards,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2_reanimate,
                description=(
                    "−2: Return target creature card with mana value 3 or "
                    "less from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7_skip_turns,
                description=(
                    "−7: Flip five coins. Target opponent skips their next "
                    "X turns, where X is the number of coins that came up "
                    "heads."
                ),
            ),
        ]
