"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon.

    Flying, Haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card. If you
    do, draw a card.

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
            "Flying, haste\nEach instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if it's the "
            "first card you drew this turn.)\nAt the beginning of each opponent's "
            "upkeep, you may discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register miracle draw trigger and opponent-upkeep loot trigger."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # -- Miracle trigger --
        # Use a mutable list to pass the drawn card from condition → effect.
        # The condition evaluates synchronously in fire_event; the effect resolves
        # later. This is a deliberate card-local pattern (see KEY_DECISIONS.md).
        _pending_card: list[Any] = []

        def _draw_condition(game: Any, event: Any) -> bool:
            if event.player is not controller:
                return False
            if getattr(event.player, "cards_drawn_this_turn", 0) != 1:
                return False
            card = event.card
            if card is None:
                return False
            types = getattr(card, "card_types", set())
            if CardType.INSTANT not in types and CardType.SORCERY not in types:
                return False
            # Capture card for effect resolution (condition called synchronously).
            _pending_card.clear()
            _pending_card.append(card)
            return True

        def _miracle_effect(game: "GameState") -> None:
            if not _pending_card:
                return
            drawn_card = _pending_card.pop()
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Card must still be in hand (might have been discarded, etc.)
            hand = ctrl.zones[Zone.HAND]
            if not hand.contains(drawn_card):
                return

            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(miracle_cost):
                return

            try:
                if not ctrl.choose_yes_no(
                    f"Cast {getattr(drawn_card, 'name', 'card')!r} for its miracle cost {{2}}?"
                ):
                    return
            except Exception:
                return

            ctrl.mana_pool.pay(miracle_cost)
            from engine.casting import cast_spell_free, CastingError
            try:
                cast_spell_free(game, ctrl, drawn_card, Zone.HAND)
            except CastingError:
                # Refund the {2} if cast fails (no legal targets, etc.)
                ctrl.mana_pool.add(ManaType.COLORLESS, 2)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_draw_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )

        # -- Opponent upkeep loot trigger --
        def _upkeep_condition(game: Any, event: Any) -> bool:
            return game.active_player is not controller

        def _loot_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            from engine.game import discard, draw_card

            hand = ctrl.zones[Zone.HAND]
            cards_in_hand = list(hand.get_all())
            if not cards_in_hand:
                return

            try:
                if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                    return
                chosen = ctrl.choose_card(cards_in_hand, "Choose a card to discard")
            except Exception:
                return

            if chosen is not None and hand.contains(chosen):
                discard(game, ctrl, chosen)
                draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
