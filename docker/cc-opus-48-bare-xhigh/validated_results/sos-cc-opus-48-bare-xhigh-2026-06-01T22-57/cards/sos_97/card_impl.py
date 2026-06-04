"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    mc = getattr(card, "mana_cost", None)
    return mc.cmc if mc is not None else 0


def _flip_heads(game: "GameState", count: int) -> int:
    """Flip *count* coins; return the number that came up heads.

    Honours a deterministic override at ``game.coin_flip_results`` (a list of
    bool consumed front-to-back) so tests can pin the outcome; otherwise uses
    a fair random flip.
    """
    override = getattr(game, "coin_flip_results", None)
    heads = 0
    for _ in range(count):
        if override:
            result = bool(override.pop(0))
        else:
            result = random.random() < 0.5
        if result:
            heads += 1
    return heads


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — 3 loyalty.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is
        the number of coins that came up heads.

    SOS collector number 97.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
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

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            """Surveil 2."""
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            for _ in range(2):
                lib_cards = list(library.get_all())
                if not lib_cards:
                    return
                top = lib_cards[-1]
                if controller.choose_yes_no(
                    f"Surveil: Put {getattr(top, 'name', 'card')} into your graveyard?"
                ):
                    library.remove(top)
                    graveyard.add(top)

        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            controller = pw.controller
            if controller is None:
                return
            for player in game.players:
                hand = player.zones[Zone.HAND]
                if not hand.get_all():
                    continue
                if not controller.choose_yes_no(
                    f"Target {getattr(player, 'name', 'player')} to discard a card?"
                ):
                    continue
                cards = player.zones[Zone.HAND].get_all()
                if not cards:
                    continue
                chosen = player.choose_card(list(cards), "Choose a card to discard")
                if chosen is not None:
                    discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            """Reanimate a creature card with mana value 3 or less."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            candidates = [
                c
                for c in graveyard.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and _mana_value(c) <= 3
            ]
            if not candidates:
                return
            chosen = controller.choose_card(
                candidates,
                "Choose a creature card (mana value 3 or less) to return",
            )
            if chosen is None or chosen not in candidates:
                return
            chosen.controller = controller
            if hasattr(chosen, "summoning_sick"):
                chosen.summoning_sick = True
            if hasattr(chosen, "is_tapped"):
                chosen.is_tapped = False
            if hasattr(chosen, "damage_marked"):
                chosen.damage_marked = 0
            move_to_zone(game, chosen, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """Flip five coins; target opponent skips their next X turns."""
            controller = pw.controller
            if controller is None:
                return
            opponents = [p for p in game.players if p is not controller]
            if not opponents:
                return
            if len(opponents) == 1:
                target = opponents[0]
            else:
                target = controller.choose(opponents, "Choose target opponent")
            heads = _flip_heads(game, 5)
            if heads <= 0:
                return
            try:
                idx = game.players.index(target)
            except ValueError:
                return
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
                description="−2: Return target creature card with mana value 3 "
                "or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins. Target opponent skips their "
                "next X turns, where X is the number of heads.",
            ),
        ]
