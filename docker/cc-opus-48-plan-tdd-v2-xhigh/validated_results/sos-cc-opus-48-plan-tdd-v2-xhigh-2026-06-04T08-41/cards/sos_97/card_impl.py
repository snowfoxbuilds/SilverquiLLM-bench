"""Card implementation for Ral Zarek, Guest Lecturer.

Targeting / coin-flip notes:

* Loyalty abilities in this engine do not run a targeting pipeline, so the
  ``−1`` (multi-player discard) and ``−2`` (reanimate) effects read their
  targets from ``self.chosen_targets`` (a list) / ``self._resolve_target``
  (a single object), mirroring the Ajani analogue.
* The ``−7`` "flip five coins" is resolved deterministically through the
  controller's ``choose_yes_no`` (heads = ``True``) so it can be scripted in
  tests. ``X`` = number of heads; the targeted opponent then skips ``X``
  turns via the ``_turns_to_skip`` turn-loop seam.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, Color, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_REANIMATE_MAX_MV = 3
_COIN_FLIPS = 5


def _get_single_target(pw: Any) -> Any:
    chosen = getattr(pw, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(pw, "_resolve_target", None)


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.
    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X
        is the number of coins that came up heads.

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
            "+1: Surveil 2.\n"
            "-1: Any number of target players each discard a card.\n"
            "-2: Return target creature card with mana value 3 or less from "
            "your graveyard to the battlefield.\n"
            "-7: Flip five coins. Target opponent skips their next X turns, "
            "where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)
        self.colors = {Color.BLACK}

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            # Surveil 2: look at the top two cards; for each, may put it into
            # the graveyard. Cards not chosen stay on top of the library.
            ctrl = pw.controller
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            looked = list(library.top(2))  # bottom-to-top among the top two
            kept: list[Any] = []
            for card in reversed(looked):  # process the top card first
                library.remove(card)
                if ctrl.choose_yes_no(
                    f"Surveil: put {getattr(card, 'name', 'card')} into graveyard?"
                ):
                    graveyard.add(card)
                else:
                    kept.append(card)
            # Return kept cards to the top, original top-most ending on top.
            for card in reversed(kept):
                library.add(card, position="top")

        def _minus1(game: "GameState") -> None:
            from engine.game import discard

            # "Any number of target players" — a (possibly empty) list.
            targets = getattr(pw, "chosen_targets", None) or []
            for player in targets:
                if player is None or not hasattr(player, "zones"):
                    continue
                hand = player.zones[Zone.HAND]
                cards = hand.get_all()
                if not cards:
                    continue
                chosen = player.choose_card(cards, "Choose a card to discard")
                if chosen is None or not hand.contains(chosen):
                    chosen = cards[0]
                discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone

            ctrl = pw.controller
            if ctrl is None:
                return
            card = _get_single_target(pw)
            if card is None:
                return
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            if not graveyard.contains(card):
                return
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                return
            cost = getattr(card, "mana_cost", None)
            if cost is None or cost.cmc > _REANIMATE_MAX_MV:
                return
            card.controller = ctrl
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            heads = 0
            for _ in range(_COIN_FLIPS):
                if ctrl.choose_yes_no("Flip a coin — heads?"):
                    heads += 1
            # Target opponent: explicit chosen target, else the other player.
            opponent = _get_single_target(pw)
            if opponent is None or opponent is ctrl:
                opponent = None
                for player in game.players:
                    if player is not ctrl:
                        opponent = player
                        break
            if opponent is None:
                return
            opponent._turns_to_skip = getattr(opponent, "_turns_to_skip", 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(
                loyalty_cost=-1, effect=_minus1,
                description="-1: Any number of target players each discard a card."),
            LoyaltyAbility(
                loyalty_cost=-2, effect=_minus2,
                description="-2: Return target creature card with mana value 3 "
                "or less from your graveyard to the battlefield."),
            LoyaltyAbility(
                loyalty_cost=-7, effect=_minus7,
                description="-7: Flip five coins. Target opponent skips their "
                "next X turns, where X is the number of heads."),
        ]
