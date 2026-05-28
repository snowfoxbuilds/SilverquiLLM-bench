"""Card implementation for Ral Zarek, Guest Lecturer (SOS 97)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your graveyard
        to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is the
        number of coins that came up heads.

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
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)
        # Injectable coin-flip results for testing (list of True/False).
        # When set, values are consumed left-to-right instead of calling random.
        self._coin_flip_results: list[bool] | None = None
        # Targets for −1 (list of players)
        self._resolve_targets: list[Any] = []
        # Single target for −2 and −7
        self._resolve_target: Any | None = None

    # ------------------------------------------------------------------
    # Loyalty abilities
    # ------------------------------------------------------------------

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        # ---- +1: Surveil 2 ----
        def _plus1(game: "GameState") -> None:
            """Surveil 2: look at top 2 cards, put any in graveyard, rest back on top."""
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            surveiled: list[Any] = []
            n = min(2, len(library))
            # Take top n cards (they come out in bottom→top order; last is topmost)
            top_cards = library.top(n)
            # Remove them from the library in reverse order (top first)
            for card in reversed(top_cards):
                library.remove(card)
                surveiled.append(card)
            # surveiled[0] = topmost card, surveiled[-1] = deepest card
            kept: list[Any] = []
            for card in surveiled:
                # Ask controller whether to send this card to the graveyard
                try:
                    send_to_graveyard = controller.choose_yes_no(
                        f"Send {getattr(card, 'name', str(card))!r} to the graveyard?"
                    )
                except Exception:
                    send_to_graveyard = False
                if send_to_graveyard:
                    graveyard.add(card)
                else:
                    kept.append(card)
            # Put kept cards back on top of library in their original order
            # (deepest first → topmost last so the topmost ends up on top)
            for card in reversed(kept):
                library.add(card)

        # ---- −1: Any number of target players each discard a card ----
        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            targets = getattr(pw, "_resolve_targets", []) or []
            for player in targets:
                hand = player.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                try:
                    chosen = player.choose_card(cards_in_hand, "Choose a card to discard")
                except Exception:
                    chosen = cards_in_hand[0] if cards_in_hand else None
                if chosen is not None and hand.contains(chosen):
                    hand.remove(chosen)
                    player.zones[Zone.GRAVEYARD].add(chosen)

        # ---- −2: Return target creature card with MV <= 3 from graveyard ----
        def _minus2(game: "GameState") -> None:
            """Return target creature with MV <= 3 from controller's graveyard to battlefield."""
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                return
            controller = pw.controller
            if controller is None:
                return
            # Validate the target is in the controller's graveyard (not an opponent's)
            source_player = None
            for player in game.players:
                graveyard = player.zones[Zone.GRAVEYARD]
                if graveyard.contains(target):
                    source_player = player
                    break
            if source_player is None:
                return
            # "from your graveyard" — must be the controller's graveyard only
            if source_player is not controller:
                return
            from engine.zones import move_to_zone
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        # ---- −7: Flip five coins; opponent skips X turns ----
        def _minus7(game: "GameState") -> None:
            """Flip five coins. Target opponent skips their next X turns (X = heads)."""
            target_opponent = getattr(pw, "_resolve_target", None)
            if target_opponent is None:
                return
            # Perform coin flips
            coin_flip_results = getattr(pw, "_coin_flip_results", None)
            if coin_flip_results is not None:
                # Use injectable results (for testing)
                results = list(coin_flip_results)
            else:
                import random
                results = [random.random() < 0.5 for _ in range(5)]
            heads = sum(1 for r in results if r)
            if heads == 0:
                return
            # Determine who controls this planeswalker
            controller = pw.controller
            if controller is None:
                return
            # Skip target_opponent's next X turns.
            # In a 2-player game, "skip opponent's turns" is implemented by
            # inserting extra turns for the controller: while the controller
            # takes those extra turns, the opponent's turns are effectively
            # skipped. We use target_opponent to derive the controller's seat
            # so the targeted opponent is the one whose turns are skipped.
            opponent_index = game.players.index(target_opponent)
            controller_index = 1 - opponent_index  # 2-player only
            for _ in range(heads):
                game.extra_turns.append(controller_index)

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1, description="−1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="−7: Flip five coins. Target opponent skips their next X turns (X = heads)."),
        ]
