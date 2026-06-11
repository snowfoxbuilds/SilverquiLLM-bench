"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Elder Dragon 5/5.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}. (You may
    cast a card for its miracle cost when you draw it if it's the first
    card you drew this turn.)
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.

    SOS collector number 201.
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
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard "
            "a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle trigger ---
        # When the controller draws their first instant/sorcery this turn,
        # offer to cast it for miracle cost {2}.

        def _miracle_condition(g: Any, event: Any) -> bool:
            ctrl = source.controller
            if event.player is not ctrl:
                return False
            drawn = event.card
            if drawn is None:
                return False
            card_types = getattr(drawn, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # First-draw check: consume the miracle window for this turn.
            last = getattr(ctrl, "_last_miracle_draw_turn", -1)
            if last == g.turn_number:
                return False
            ctrl._last_miracle_draw_turn = g.turn_number  # type: ignore[attr-defined]
            ctrl._miracle_drawn_card = drawn  # capture card for effect  # type: ignore[attr-defined]
            return True

        def _miracle_effect(g: Any) -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            card = getattr(ctrl, "_miracle_drawn_card", None)
            if card is None:
                return
            ctrl._miracle_drawn_card = None  # type: ignore[attr-defined]

            # Card must still be in hand.
            hand = ctrl.zones[Zone.HAND]
            if not hand.contains(card):
                return

            miracle_cost = ManaCost.parse("{2}")
            try:
                if not ctrl.choose_yes_no(f"Cast {card.name} for miracle cost {{2}}?"):
                    return
                if not ctrl.mana_pool.can_pay(miracle_cost):
                    return
                ctrl.mana_pool.pay(miracle_cost)
                from engine.casting import cast_spell_free
                cast_spell_free(g, ctrl, card, Zone.HAND)
            except Exception:
                pass

        game.trigger_manager.register(TriggerRegistration(
            event_type=DrawsCardTriggeredEvent,
            condition=_miracle_condition,
            effect=_miracle_effect,
            source=self,
            controller=controller,
        ))

        # --- Loot trigger at each opponent's upkeep ---

        def _loot_condition(g: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None:
                return False
            return g.active_player is not ctrl

        def _loot_effect(g: Any) -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            hand_cards = hand.get_all()
            if not hand_cards:
                return
            chosen = ctrl.choose_card(hand_cards, "Discard a card to draw a card?")
            if chosen is None:
                return
            discard(g, ctrl, chosen)
            draw_card(g, ctrl)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_loot_condition,
            effect=_loot_effect,
            source=self,
            controller=controller,
        ))
