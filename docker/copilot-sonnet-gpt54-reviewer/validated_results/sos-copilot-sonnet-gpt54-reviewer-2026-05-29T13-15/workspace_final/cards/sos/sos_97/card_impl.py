"""Card implementation for Ral Zarek, Guest Lecturer (sos_97)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Planeswalker — Ral (3 loyalty).

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins
        that came up heads.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your "
            "graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X "
            "is the number of coins that came up heads.",
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
            cards_to_look = library.top(2)
            for card in reversed(cards_to_look):
                if library.contains(card):
                    put_in_gy = controller.choose_yes_no(
                        f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
                    )
                    if put_in_gy:
                        library.remove(card)
                        controller.zones[Zone.GRAVEYARD].add(card)

        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            chosen = getattr(pw, "chosen_targets", [])
            for target_player in chosen:
                if target_player is None or not hasattr(target_player, "zones"):
                    continue
                hand = target_player.zones[Zone.HAND]
                hand_cards = hand.get_all()
                if not hand_cards:
                    continue
                card_to_discard = target_player.choose_card(
                    hand_cards, "Discard a card (Ral -1)"
                )
                if card_to_discard is not None and hand.contains(card_to_discard):
                    hand.remove(card_to_discard)
                    gy = target_player.zones[Zone.GRAVEYARD]
                    if hasattr(target_player, "owner"):
                        owner = getattr(card_to_discard, "owner", target_player)
                        owner.zones[Zone.GRAVEYARD].add(card_to_discard)
                    else:
                        gy.add(card_to_discard)

        def _minus2(game: "GameState") -> None:
            """Return target creature with MV ≤ 3 from GY to battlefield."""
            chosen = getattr(pw, "chosen_targets", [])
            target = chosen[0] if chosen else None
            if target is None:
                return
            # Check it's a creature with MV ≤ 3
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            mc = getattr(target, "mana_cost", None)
            if mc is not None and mc.cmc > 3:
                return
            # Find and move from graveyard to battlefield
            controller = pw.controller
            owner = getattr(target, "owner", controller)
            if owner is None:
                owner = controller
            target.controller = controller
            gy = owner.zones[Zone.GRAVEYARD]
            if not gy.contains(target):
                return
            gy.remove(target)
            from engine.zones import move_to_zone
            # Add directly to battlefield
            bf = game.get_battlefield(controller)
            bf.add(target)
            from engine.events import EntersBattlefieldTriggeredEvent
            game.trigger_manager.fire_event(
                game,
                EntersBattlefieldTriggeredEvent(permanent=target, controller=controller),
            )
            if hasattr(target, "register_triggers"):
                target.register_triggers(game)

        def _minus7(game: "GameState") -> None:
            """Flip 5 coins. Opponent skips their next X turns (X = heads)."""
            controller = pw.controller
            chosen = getattr(pw, "chosen_targets", [])
            target_opponent = chosen[0] if chosen else None

            heads = 0
            for _ in range(5):
                flip = controller.choose_yes_no("Flip a coin (heads = True)?")
                if flip:
                    heads += 1

            if target_opponent is not None and heads > 0:
                current_skips = getattr(target_opponent, "turns_to_skip", 0)
                target_opponent.turns_to_skip = current_skips + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1, description="−1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description="−2: Return target creature card with MV 3 or less from your GY to battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="−7: Flip five coins. Target opponent skips their next X turns."),
        ]
