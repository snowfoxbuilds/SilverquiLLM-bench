"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.

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
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
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
        # Explicit color identity (KEY_DECISIONS convention) — the {B}{B} pips
        # make Ral black.
        self.colors: list[str] = ["B"]
        # Records the number of heads from the most recent −7 resolution so a
        # test can assert X directly. Defaults to None until the ultimate runs.
        self._last_heads: int | None = None

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """+1: Surveil 2.

            Look at the top two cards of the controller's library; put any
            number of them into the graveyard and the rest back on top. The
            keep/bin decision for each surveilled card is taken via the
            controller's ``choose_yes_no`` (the standard decision channel).
            """
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            if len(library) == 0:
                return

            # Top of library is the end of the internal list; surveil the top
            # two cards, processing the very top first.
            top_cards = list(reversed(library.top(2)))
            for card in top_cards:
                if not library.contains(card):
                    continue
                bin_it = controller.choose_yes_no(
                    f"Put {getattr(card, 'name', 'card')} into your graveyard?"
                )
                if bin_it:
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
            # Cards not binned remain on top of the library in their existing
            # order — surveil leaves the order of the kept cards on top.

        def _minus1(game: Any) -> None:
            """−1: Any number of target players each discard a card."""
            from engine.game import discard

            targets = getattr(pw, "_resolve_targets", None)
            if not targets:
                return
            for player in targets:
                if player is None:
                    continue
                hand = player.zones[Zone.HAND]
                cards = hand.get_all()
                if not cards:
                    continue
                try:
                    chosen = player.choose_card(cards, "Discard a card")
                except Exception:
                    chosen = None
                if chosen is None or not hand.contains(chosen):
                    # Fall back to the last card in hand if the choice is
                    # missing/invalid (a player with a card in hand must
                    # discard one).
                    chosen = cards[-1]
                discard(game, player, chosen)

        def _minus2(game: Any) -> None:
            """−2: Return a creature card with mana value ≤ 3 from your
            graveyard to the battlefield."""
            from engine.zones import move_to_zone

            controller = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if controller is None or target is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            # Lazy re-validation: creature card with mana value 3 or less.
            card_types = getattr(target, "card_types", set())
            if CardType.CREATURE not in card_types:
                return
            mana_cost = getattr(target, "mana_cost", None)
            mana_value = getattr(mana_cost, "cmc", 0) if mana_cost is not None else 0
            if mana_value > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: Any) -> None:
            """−7: Flip five coins. Target opponent skips their next X turns,
            where X is the number of coins that came up heads."""
            from engine.game import flip_coins

            target = getattr(pw, "_resolve_target", None)
            heads = flip_coins(game, 5, getattr(pw, "controller", None))
            pw._last_heads = heads
            if target is None:
                return
            # Schedule the opponent's next X turns to be skipped (CR 614.10),
            # honored by GameState turn rotation.
            current = getattr(target, "skipped_turns", 0)
            target.skipped_turns = current + heads

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
                description="−2: Return target creature card with mana value 3 "
                "or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins. Target opponent skips their "
                "next X turns (X = heads).",
            ),
        ]
