"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
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

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: GameState) -> None:
            """Surveil 2 — look at the top two cards; bin any number, the
            rest stay on top (existing order kept — no reorder choice)."""
            from engine.zones import move_to_zone

            ctrl = pw.controller
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            # Top card first.
            for card in reversed(library.top(2)):
                if ctrl.choose_yes_no(
                    f"Surveil: put {getattr(card, 'name', 'card')} into your graveyard?"
                ):
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        def _minus1(game: GameState) -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            targets = getattr(pw, "chosen_targets", None) or []
            for player in targets:
                if player not in game.players:
                    continue
                hand_cards = player.zones[Zone.HAND].get_all()
                if not hand_cards:
                    continue
                chosen = player.choose_card(hand_cards, "Choose a card to discard")
                if chosen is None or chosen not in hand_cards:
                    chosen = hand_cards[-1]
                discard(game, player, chosen)

        def _minus2(game: GameState) -> None:
            """Return target creature card (MV <= 3) from your graveyard
            to the battlefield."""
            from engine.zones import move_to_zone

            ctrl = pw.controller
            targets = getattr(pw, "chosen_targets", None) or []
            card = targets[0] if targets else None
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.GRAVEYARD].contains(card):
                return
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                return
            cost = getattr(card, "mana_cost", None)
            if cost is not None and cost.cmc > 3:
                return
            card.controller = ctrl
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: GameState) -> None:
            """Flip five coins; target opponent skips their next X turns."""
            rng = getattr(game, "rng", None)
            if rng is None:
                game.rng = rng = random.Random()
            heads = sum(rng.randint(0, 1) for _ in range(5))

            targets = getattr(pw, "chosen_targets", None) or []
            opponent = targets[0] if targets else None
            if opponent is None or opponent not in game.players:
                return
            if opponent is pw.controller:
                return  # must be an opponent
            if heads > 0:
                opponent.skip_turns = getattr(opponent, "skip_turns", 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1,
                           description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1,
                           description="−1: Any number of target players "
                                       "each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2,
                           description="−2: Return target creature card "
                                       "with mana value 3 or less from "
                                       "your graveyard to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7,
                           description="−7: Flip five coins. Target "
                                       "opponent skips their next X turns, "
                                       "where X is the number of heads."),
        ]
