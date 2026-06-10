"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.
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
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n−1: Any number of target players each discard "
            "a card.\n−2: Return target creature card with mana value 3 or "
            "less from your graveyard to the battlefield.\n−7: Flip five "
            "coins. Target opponent skips their next X turns, where X is "
            "the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def _targets(self) -> list[Any]:
        """Flattened chosen targets (set by the engine from the activation)."""
        chosen = getattr(self, "chosen_targets", None) or []
        flat: list[Any] = []
        for t in chosen:
            if isinstance(t, (list, tuple)):
                flat.extend(t)
            elif t is not None:
                flat.append(t)
        return flat

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: GameState) -> None:
            """Surveil 2: look at the top 2; bin any number, rest stays on top."""
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            looked = list(reversed(library.top(2)))  # top card first
            for card in looked:
                try:
                    to_graveyard = controller.choose_yes_no(
                        f"Surveil: put {getattr(card, 'name', 'card')} into "
                        "your graveyard?"
                    )
                except Exception:
                    to_graveyard = False
                if to_graveyard:
                    library.remove(card)
                    graveyard.add(card)
            # Kept cards stay on top in their original order (no reorder
            # prompt — deliberate simplification).

        def _minus1(game: GameState) -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            for player in pw._targets():
                hand = getattr(player, "zones", None)
                if hand is None:
                    continue
                cards_in_hand = player.zones[Zone.HAND].get_all()
                if not cards_in_hand:
                    continue
                try:
                    chosen = player.choose_card(cards_in_hand, "Discard a card")
                except Exception:
                    chosen = cards_in_hand[-1]
                if chosen is None or chosen not in cards_in_hand:
                    chosen = cards_in_hand[-1]
                discard(game, player, chosen)

        def _minus2(game: GameState) -> None:
            """Return target creature card (MV <= 3) from your graveyard to
            the battlefield."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            targets = pw._targets()
            target = targets[0] if targets else None
            if target is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            cost = getattr(target, "mana_cost", None)
            if cost is not None and cost.cmc > 3:
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: GameState) -> None:
            """Flip five coins; target opponent skips their next X turns."""
            targets = pw._targets()
            target = targets[0] if targets else None
            if target is None or not hasattr(target, "life"):
                return
            heads = sum(game.rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                target.skip_turns = getattr(target, "skip_turns", 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1,
                           description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1,
                           description="−1: Any number of target players "
                           "each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2,
                           description="−2: Return target creature card "
                           "with mana value 3 or less from your graveyard "
                           "to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7,
                           description="−7: Flip five coins. Target "
                           "opponent skips their next X turns, where X is "
                           "the number of heads."),
        ]
