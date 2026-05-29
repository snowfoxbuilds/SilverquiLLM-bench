"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — 3 loyalty — Legendary Planeswalker — Ral.

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
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your "
            "graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where "
            "X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Surveil 2 — look at top 2, put any into graveyard, rest on top."""
            controller = getattr(pw, "controller", None)
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            top_cards = list(library.top(min(2, len(library))))
            for card in reversed(top_cards):
                try:
                    send_to_gy = controller.choose_yes_no(
                        f"Surveil: put {getattr(card, 'name', 'card')} into graveyard?"
                    )
                except Exception:
                    send_to_gy = False
                if send_to_gy:
                    library.remove(card)
                    graveyard.add(card)

        def _minus1(game: Any) -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard as _discard
            controller = getattr(pw, "controller", None)
            if controller is None:
                return

            # Choose which players to target
            targets = getattr(pw, "_resolve_targets", None) or getattr(pw, "chosen_targets", None) or []
            if not targets:
                # Default: offer each player
                for p in game.players:
                    hand = p.zones[Zone.HAND]
                    cards_in_hand = hand.get_all()
                    if cards_in_hand:
                        try:
                            chosen_card = p.choose_card(cards_in_hand, "Choose a card to discard")
                        except Exception:
                            chosen_card = cards_in_hand[0] if cards_in_hand else None
                        if chosen_card is not None:
                            _discard(game, p, chosen_card)
            else:
                for p in targets:
                    hand = p.zones[Zone.HAND]
                    cards_in_hand = hand.get_all()
                    if cards_in_hand:
                        try:
                            chosen_card = p.choose_card(cards_in_hand, "Choose a card to discard")
                        except Exception:
                            chosen_card = cards_in_hand[0] if cards_in_hand else None
                        if chosen_card is not None:
                            _discard(game, p, chosen_card)

        def _minus2(game: Any) -> None:
            """Return target creature card with CMC ≤ 3 from your graveyard to battlefield."""
            controller = getattr(pw, "controller", None)
            if controller is None:
                return

            target = getattr(pw, "_resolve_target", None)
            if target is None:
                targets = getattr(pw, "chosen_targets", None) or []
                target = targets[0] if targets else None

            if target is None:
                # Find candidates automatically
                gy = controller.zones[Zone.GRAVEYARD]
                candidates = [
                    c for c in gy.get_all()
                    if CardType.CREATURE in getattr(c, "card_types", set())
                    and getattr(getattr(c, "mana_cost", None), "cmc", 99) <= 3
                ]
                if not candidates:
                    return
                try:
                    target = controller.choose_card(candidates, "Return creature card (CMC ≤ 3) from graveyard")
                except Exception:
                    target = candidates[0]

            if target is None:
                return

            # Verify target is in graveyard and is a creature with CMC ≤ 3
            gy = controller.zones[Zone.GRAVEYARD]
            if not gy.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            cmc = getattr(getattr(target, "mana_cost", None), "cmc", 99)
            if cmc > 3:
                return

            from engine.zones import move_to_zone
            target.controller = controller
            target.owner = getattr(target, "owner", controller)
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: Any) -> None:
            """Flip 5 coins; target opponent skips next X turns (X = heads)."""
            import random
            controller = getattr(pw, "controller", None)
            if controller is None:
                return

            heads = sum(1 for _ in range(5) if random.random() < 0.5)

            if heads == 0:
                return

            # Find target opponent
            target_opponent = None
            targets = getattr(pw, "chosen_targets", None) or []
            if targets:
                target_opponent = targets[0]
            else:
                for p in game.players:
                    if p is not controller:
                        target_opponent = p
                        break

            if target_opponent is None:
                return

            # Grant X skip-turn credits: insert target_opponent's index into extra_turns
            # but actually we want them to skip — inject the active player's turns
            # to give effective skips to the opponent.
            # ENGINE LIMITATION: The engine uses extra_turns for extra turns, not skip-turns.
            # We approximate by setting a skip counter on the opponent.
            target_opponent._turns_to_skip = getattr(target_opponent, "_turns_to_skip", 0) + heads  # type: ignore[attr-defined]

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1, description="−1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description="−2: Return target creature card with mana value 3 or less from graveyard to battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="−7: Flip five coins, opponent skips X turns where X = heads."),
        ]

