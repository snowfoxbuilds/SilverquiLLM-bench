"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Creature — Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}. (You may cast
    a card for its miracle cost when you draw it if it's the first card you
    drew this turn.)
    At the beginning of each opponent's upkeep, you may discard a card. If
    you do, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\nEach instant and sorcery card in your hand has "
            "miracle {2}.\nAt the beginning of each opponent's upkeep, you may "
            "discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register miracle (draw trigger) and opponent upkeep trigger."""
        from engine.triggers import TriggerRegistration
        from engine.events import DrawsCardTriggeredEvent, BeginningOfUpkeepTriggeredEvent

        source = self

        # --- Miracle trigger: when controller draws a card ---
        def _draw_condition(game: Any, event: Any) -> bool:
            controller = getattr(source, "controller", None)
            on_bf = any(
                game.get_battlefield(p).contains(source)
                for p in game.players
            )
            return on_bf and event.player is controller

        def _draw_effect(game: Any) -> None:
            """If drawn card is an instant/sorcery and was the first draw, offer miracle cast."""
            from engine.casting import cast_spell_free
            from engine.types import ManaCost as _ManaCost, ManaType

            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # Find the most recently drawn card (tagged by draw_card)
            hand = controller.zones[Zone.HAND]
            miracle_card = None
            for card in reversed(hand.get_all()):
                if getattr(card, "_drawn_as_first_this_turn", False):
                    ctypes = getattr(card, "card_types", set())
                    if CardType.INSTANT in ctypes or CardType.SORCERY in ctypes:
                        miracle_card = card
                    break

            if miracle_card is None:
                return

            # Ask if player wants to cast it for miracle cost {2}
            try:
                do_miracle = controller.choose_yes_no(
                    f"Cast {getattr(miracle_card, 'name', '?')} via miracle for {{2}}?"
                )
            except Exception:
                do_miracle = False

            if not do_miracle:
                return

            # Pay {2} mana
            miracle_cost = _ManaCost.parse("{2}")
            if not controller.mana_pool.can_pay(miracle_cost):
                return
            controller.mana_pool.pay(miracle_cost)

            # Cast it for free (we already paid the miracle cost manually)
            try:
                cast_spell_free(game, controller, miracle_card, Zone.HAND)
            except Exception:
                # Refund mana on failure (approximate)
                controller.mana_pool.add(ManaType.COLORLESS, 2)

        controller_ref = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=DrawsCardTriggeredEvent,
            condition=_draw_condition,
            effect=_draw_effect,
            source=self,
            controller=controller_ref,
        ))

        # --- Opponent upkeep trigger: may discard then draw ---
        def _upkeep_condition(game: Any, event: Any) -> bool:
            controller = getattr(source, "controller", None)
            on_bf = any(
                game.get_battlefield(p).contains(source)
                for p in game.players
            )
            # Trigger during opponent's upkeep
            return on_bf and game.active_player is not controller

        def _upkeep_effect(game: Any) -> None:
            from engine.game import discard, draw_card

            controller = getattr(source, "controller", None)
            if controller is None:
                return
            hand = controller.zones[Zone.HAND]
            if not hand.get_all():
                return

            try:
                do_discard = controller.choose_yes_no("Discard a card to draw a card (Lorehold)?")
            except Exception:
                do_discard = False

            if not do_discard:
                return

            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            try:
                chosen = controller.choose_card(cards_in_hand, "Discard a card")
            except Exception:
                chosen = cards_in_hand[0]
            if chosen is None:
                return

            discard(game, controller, chosen)
            draw_card(game, controller)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_upkeep_condition,
            effect=_upkeep_effect,
            source=self,
            controller=controller_ref,
        ))

