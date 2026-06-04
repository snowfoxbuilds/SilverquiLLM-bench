"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} Legendary Planeswalker — Ral — 3.

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

    # ------------------------------------------------------------------
    # Targeting
    # ------------------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        """Declare the graveyard-scoped target requirement for −2.

        The −2 ability returns a *creature card with mana value 3 or less*
        from the controller's graveyard.  The other abilities target players
        ("any number of target players", "target opponent"); those are
        resolved via the engine's player-choice plumbing and stashed on
        ``_resolve_targets`` / ``_resolve_target`` and so do not need a
        battlefield/graveyard ``TargetRequirement`` here.
        """
        controller = self.controller or game.active_player

        def _reanimate_filter(obj: Any) -> bool:
            if CardType.CREATURE not in getattr(obj, "card_types", set()):
                return False
            cost = getattr(obj, "mana_cost", None)
            mana_value = cost.cmc if cost is not None else 0
            return mana_value <= 3

        return [
            TargetRequirement(
                filter_fn=_reanimate_filter,
                description="creature card with mana value 3 or less in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    # ------------------------------------------------------------------
    # Loyalty abilities
    # ------------------------------------------------------------------

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """+1: Surveil 2.

            Look at the top two cards of your library; for each, the
            controller may put it into the graveyard.  Processed
            top-card-first via ``choose_yes_no`` (engine surveil convention,
            see ``cards/fdn/fdn_157`` Lightshell Duo).
            """
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            cards = list(library.get_all())
            if not cards:
                return
            # Top of library is the last element; take up to two, top first.
            top_cards = cards[-min(2, len(cards)):]
            for card in reversed(top_cards):
                put_in_gy = controller.choose_yes_no(
                    f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
                )
                if put_in_gy:
                    library.remove(card)
                    controller.zones[Zone.GRAVEYARD].add(card)

        def _minus1(game: Any) -> None:
            """−1: Any number of target players each discard a card."""
            from engine.game import discard

            targets = getattr(pw, "_resolve_targets", None) or []
            for player in targets:
                hand = player.zones[Zone.HAND].get_all()
                if hand:
                    # The player chooses which card to discard; with no
                    # scripted choice, discard deterministically from the end.
                    card = None
                    chooser = getattr(player, "choose_card", None)
                    if chooser is not None:
                        try:
                            card = chooser(hand, "discard a card")
                        except Exception:
                            card = None
                    if card is None or card not in hand:
                        card = hand[-1]
                    discard(game, player, card)

        def _minus2(game: Any) -> None:
            """−2: Return target creature (mv ≤ 3) from your graveyard to play."""
            from engine.zones import move_to_zone

            target = getattr(pw, "_resolve_target", None)
            controller = pw.controller
            if target is None or controller is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            # Enters under the planeswalker's controller's control.
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: Any) -> None:
            """−7: Flip five coins. Target opponent skips their next X turns."""
            from engine.game import add_skipped_turns, flip_coins

            target = getattr(pw, "_resolve_target", None)
            if target is None:
                return
            heads = flip_coins(game, 5)
            add_skipped_turns(game, target, heads)

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
                description="−2: Return target creature card with mana value 3 or "
                "less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins. Target opponent skips their next "
                "X turns, where X is the number of heads.",
            ),
        ]
