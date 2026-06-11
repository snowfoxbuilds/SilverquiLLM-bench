"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Loyalty 3.

    Legendary Planeswalker — Ral
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
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n−1: Any number of target players each discard "
            "a card.\n−2: Return target creature card with mana value 3 or "
            "less from your graveyard to the battlefield.\n−7: Flip five "
            "coins. Target opponent skips their next X turns, where X is "
            "the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Loyalty abilities
    # ------------------------------------------------------------------

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            """Surveil 2: look at the top two; bin any, rest stay on top."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            # Top card first; the rest go back on top in their original
            # order (deliberate simplification: no reordering choice).
            for card in reversed(library.top(2)):
                try:
                    to_graveyard = controller.choose_yes_no(
                        f"Surveil: put {getattr(card, 'name', 'card')} into "
                        "your graveyard?"
                    )
                except Exception:
                    to_graveyard = False
                if to_graveyard:
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            controller = pw.controller
            chosen = getattr(pw, "chosen_targets", None)
            if chosen is not None:
                targets = [t for t in chosen if hasattr(t, "life")]
            elif controller is not None:
                # Fallback when activated without explicit targets: ask.
                try:
                    answer = controller.choose(
                        list(game.players),
                        "Choose any number of target players to discard "
                        "(a player, a list of players, or None)",
                    )
                except Exception:
                    answer = None
                if answer is None:
                    targets = []
                elif isinstance(answer, list):
                    targets = [t for t in answer if hasattr(t, "life")]
                else:
                    targets = [answer] if hasattr(answer, "life") else []
            else:
                targets = []

            for target_player in targets:
                hand_cards = target_player.zones[Zone.HAND].get_all()
                if not hand_cards:
                    continue
                try:
                    card = target_player.choose_card(
                        hand_cards, "Choose a card to discard"
                    )
                except Exception:
                    card = hand_cards[-1]
                if card is None or not target_player.zones[Zone.HAND].contains(card):
                    card = hand_cards[-1]
                discard(game, target_player, card)

        def _minus2(game: "GameState") -> None:
            """Return target creature card with MV <= 3 from your graveyard."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            candidates = [
                c
                for c in graveyard.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and (getattr(c, "mana_cost", None) is None
                     or c.mana_cost.cmc <= 3)
            ]
            if not candidates:
                return

            chosen = getattr(pw, "chosen_targets", None)
            if chosen is not None:
                target = chosen[0] if chosen else None
                if target not in candidates:
                    return  # illegal target — the ability does nothing
            elif len(candidates) == 1:
                target = candidates[0]
            else:
                try:
                    target = controller.choose_card(
                        candidates,
                        "Return a creature card with mana value 3 or less "
                        "to the battlefield",
                    )
                except Exception:
                    target = candidates[0]
                if target not in candidates:
                    return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """Flip five coins; target opponent skips their next X turns."""
            controller = pw.controller
            chosen = getattr(pw, "chosen_targets", None)
            target = chosen[0] if chosen else None
            if target is None or not hasattr(target, "life"):
                # 2-player fallback: the only opponent.
                target = next(
                    (p for p in game.players if p is not controller), None
                )
            if target is None:
                return
            rng = getattr(game, "rng", None)
            if rng is None:
                # Older game states may lack the shared rng; attach one so
                # tests can seed it.
                rng = random.Random()
                game.rng = rng
            heads = sum(rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                target.skip_turns = getattr(target, "skip_turns", 0) + heads

        return [
            LoyaltyAbility(
                loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."
            ),
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
