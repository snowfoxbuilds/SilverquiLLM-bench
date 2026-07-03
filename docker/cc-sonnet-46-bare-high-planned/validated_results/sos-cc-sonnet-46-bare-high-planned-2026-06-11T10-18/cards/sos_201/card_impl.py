"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon 5/5.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card. If
    you do, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a card. "
            "If you do, draw a card.",
        )
        super().__init__(**kwargs)
        # Maps id(player) → turn_number of last miracle offer to prevent double-offering.
        self._miracle_offered_turn: dict[int, int] = {}

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # Miracle trigger: fires on controller's draws.
        # condition uses a mutable cell so effect can reference event.card.
        _last_drawn: list[Any] = [None]

        def _draw_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            _last_drawn[0] = event.card
            return True

        def _draw_effect(g: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Offer miracle only once per turn (Miracle triggers on the first draw).
            cur_turn = g.turn_number
            if source._miracle_offered_turn.get(id(ctrl)) == cur_turn:
                return

            if not g.get_battlefield(ctrl).contains(source):
                return

            drawn_card = _last_drawn[0]
            if drawn_card is None:
                return

            if (CardType.INSTANT not in getattr(drawn_card, "card_types", set())
                    and CardType.SORCERY not in getattr(drawn_card, "card_types", set())):
                return

            if not g.get_hand(ctrl).contains(drawn_card):
                return

            source._miracle_offered_turn[id(ctrl)] = cur_turn

            try:
                want = ctrl.choose_yes_no(
                    f"Cast {getattr(drawn_card, 'name', 'card')} for miracle cost {{2}}?"
                )
            except Exception:
                want = False

            if not want:
                return

            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(miracle_cost, for_instant_sorcery=True):
                return

            ctrl.mana_pool.pay(miracle_cost, for_instant_sorcery=True)
            try:
                cast_spell_free(g, ctrl, drawn_card, Zone.HAND)
            except Exception:
                pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_draw_condition,
                effect=_draw_effect,
                source=self,
                controller=controller,
            )
        )

        # Opponent upkeep loot trigger.
        def _upkeep_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if not g.get_battlefield(ctrl).contains(source):
                return False
            return g.active_player is not ctrl

        def _upkeep_effect(g: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            hand_cards = g.get_hand(ctrl).get_all()
            if not hand_cards:
                return

            try:
                want = ctrl.choose_yes_no("Discard a card to draw a card?")
            except Exception:
                want = False

            if not want:
                return

            try:
                card_to_discard = ctrl.choose_card(hand_cards, "Choose a card to discard")
            except Exception:
                card_to_discard = hand_cards[0]

            if card_to_discard is None:
                return

            discard(g, ctrl, card_to_discard)
            draw_card(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=self,
                controller=controller,
            )
        )
