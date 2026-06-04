"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(card: Any) -> bool:
    return CardType.CREATURE in getattr(card, "card_types", set())


def _mana_value(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return getattr(cost, "cmc", 0) if cost is not None else 0


def _target_players(pw: Any) -> list:
    """Return the chosen target player(s) for a multi-target ability."""
    targets = getattr(pw, "_resolve_targets", None)
    if targets:
        return list(targets)
    single = getattr(pw, "_resolve_target", None)
    return [single] if single is not None else []


def surveil(game: "GameState", player: Any, amount: int) -> None:
    """Surveil *amount*: look at the top *amount* cards of *player*'s library;
    put any number of them into their graveyard (the rest stay on top)."""
    if player is None or amount <= 0:
        return
    library = player.zones[Zone.LIBRARY]
    graveyard = player.zones[Zone.GRAVEYARD]
    # Look at the top *amount* cards (top of library is the last element).
    top = list(library.get_all())[-amount:]
    # Process from the very top downward.
    for card in reversed(top):
        try:
            put_in_gy = player.choose_yes_no(
                f"Surveil: put {getattr(card, 'name', 'card')} into your graveyard?"
            )
        except Exception:
            put_in_gy = False
        if put_in_gy and library.contains(card):
            library.remove(card)
            graveyard.add(card)


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.
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
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {
            Supertype.LEGENDARY
        }
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
            controller = pw.controller
            if controller is not None:
                surveil(game, controller, 2)

        def _minus1(game: "GameState") -> None:
            from engine.game import discard

            for player in _target_players(pw):
                if player is None:
                    continue
                hand = player.zones[Zone.HAND].get_all()
                if not hand:
                    continue
                try:
                    chosen = player.choose_card(hand, "Discard a card")
                except Exception:
                    chosen = hand[-1]
                if chosen is None or chosen not in hand:
                    chosen = hand[-1]
                discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone

            controller = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if controller is None or target is None:
                return
            gy = controller.zones[Zone.GRAVEYARD]
            if not gy.contains(target):
                return
            if not _is_creature(target) or _mana_value(target) > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            from engine.game import flip_coin

            controller = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if controller is None or target is None or target is controller:
                return
            if target not in game.players:
                return
            heads = sum(1 for _ in range(5) if flip_coin(game, controller))
            if heads <= 0:
                return
            idx = game.players.index(target)
            if not hasattr(game, "skipped_turns"):
                game.skipped_turns = {}
            game.skipped_turns[idx] = game.skipped_turns.get(idx, 0) + heads

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Surveil 2.",
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
                    "−2: Return target creature card with mana value 3 or less "
                    "from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description=(
                    "−7: Flip five coins. Target opponent skips their next X "
                    "turns (X = heads)."
                ),
            ),
        ]
