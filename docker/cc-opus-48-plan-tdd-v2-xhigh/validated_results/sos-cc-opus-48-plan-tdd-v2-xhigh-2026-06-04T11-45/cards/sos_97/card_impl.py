"""Card implementation for Ral Zarek, Guest Lecturer (SOS #97)."""

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
    -1: Any number of target players each discard a card.
    -2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    -7: Flip five coins. Target opponent skips their next X turns, where X
        is the number of coins that came up heads.

    SOS collector number 97.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {
            Supertype.LEGENDARY
        }
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
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

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            cards = list(library.get_all())
            if not cards:
                return
            top_cards = cards[-min(2, len(cards)):]
            for card in reversed(top_cards):
                if ctrl.choose_yes_no(
                    f"Surveil: Put {getattr(card, 'name', 'card')} into "
                    "your graveyard?"
                ):
                    library.remove(card)
                    ctrl.zones[Zone.GRAVEYARD].add(card)

        def _minus1(game: Any) -> None:
            from engine.game import discard

            ctrl = pw.controller
            if ctrl is None:
                return
            for player in list(game.players):
                if not ctrl.choose_yes_no(
                    f"Target {getattr(player, 'name', 'player')} to "
                    "discard a card?"
                ):
                    continue
                hand = game.get_hand(player)
                cards = hand.get_all()
                if not cards:
                    continue
                card = player.choose_card(cards, "choose a card to discard")
                if card is not None and hand.contains(card):
                    discard(game, player, card)

        def _minus2(game: Any) -> None:
            from engine.zones import move_to_zone

            ctrl = pw.controller
            if ctrl is None:
                return
            gy = ctrl.zones[Zone.GRAVEYARD]
            eligible = [
                o
                for o in gy.get_all()
                if CardType.CREATURE in getattr(o, "card_types", set())
                and getattr(getattr(o, "mana_cost", None), "cmc", 99) <= 3
            ]
            if not eligible:
                return
            target = getattr(pw, "_resolve_target", None)
            if target not in eligible:
                target = ctrl.choose(
                    eligible, "choose a creature card to reanimate"
                )
            if target is None or not gy.contains(target):
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: Any) -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            heads = sum(
                1 for _ in range(5) if ctrl.choose_yes_no("Coin flip: heads?")
            )
            opponents = [pl for pl in game.players if pl is not ctrl]
            target = getattr(pw, "_resolve_target", None)
            if target not in opponents:
                target = opponents[0] if opponents else None
            if target is None:
                return
            idx = game.players.index(target)
            game.skipped_turns[idx] = game.skipped_turns.get(idx, 0) + heads

        return [
            LoyaltyAbility(
                loyalty_cost=1, effect=_plus1, description="+1: Surveil 2."
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="-1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="-2: Return target creature card with mana value 3 "
                "or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="-7: Flip five coins. Target opponent skips their "
                "next X turns, where X is the number of heads.",
            ),
        ]
