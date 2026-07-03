"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon — 5/5.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}. (You may
    cast a card for its miracle cost when you draw it if it's the first
    card you drew this turn.)
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.

    SOS collector number 201.
    """

    MIRACLE_COST = ManaCost(generic=2)

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
            "Flying, haste\nEach instant and sorcery card in your hand has "
            "miracle {2}. (You may cast a card for its miracle cost when "
            "you draw it if it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)
        # Card-local miracle tracking: draws seen per turn while this card
        # is registered.  Deliberate limitation: draws made before Lorehold
        # entered the battlefield this turn are not counted.
        self._draws_seen: dict[int, int] = {}
        self._pending_miracle: Any = None

    def register_triggers(self, game: GameState) -> None:
        from engine.events import (
            BeginningOfUpkeepTriggeredEvent,
            DrawsCardTriggeredEvent,
        )
        from engine.triggers import TriggerRegistration

        source = self

        # ----- Miracle {2} for instants/sorceries in your hand -----

        def _miracle_condition(game: GameState, event: Any) -> bool:
            if getattr(event, "player", None) is not source.controller:
                return False
            turn = game.turn_number
            source._draws_seen[turn] = source._draws_seen.get(turn, 0) + 1
            if source._draws_seen[turn] != 1:
                return False
            card = getattr(event, "card", None)
            if card is None or not (
                getattr(card, "card_types", set())
                & {CardType.INSTANT, CardType.SORCERY}
            ):
                return False
            source._pending_miracle = card
            return True

        def _miracle_effect(game: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free

            controller = source.controller
            card = source._pending_miracle
            source._pending_miracle = None
            if controller is None or card is None:
                return
            # The card must still be in hand to be cast for its miracle cost.
            if not game.get_hand(controller).contains(card):
                return
            if not controller.mana_pool.can_pay(
                source.MIRACLE_COST, include_restricted=True
            ):
                return
            if not controller.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            try:
                # Free-cast stack path from hand; the miracle cost {2} is
                # paid in place of the mana cost.
                cast_spell_free(game, controller, card, Zone.HAND)
            except CastingError:
                return
            controller.mana_pool.pay(
                source.MIRACLE_COST, include_restricted=True
            )

        game.trigger_manager.register(TriggerRegistration(
            event_type=DrawsCardTriggeredEvent,
            condition=_miracle_condition,
            effect=_miracle_effect,
            source=self,
            controller=self.controller,
        ))

        # ----- Loot at the beginning of each opponent's upkeep -----

        def _loot_condition(game: GameState, event: Any) -> bool:
            return game.active_player is not source.controller

        def _loot_effect(game: GameState) -> None:
            from engine.game import discard, draw_card

            controller = source.controller
            if controller is None:
                return
            hand_cards = game.get_hand(controller).get_all()
            if not hand_cards:
                return
            chosen = controller.choose_card(
                hand_cards, "discard a card to draw a card (None to decline)"
            )
            if chosen is None or chosen not in hand_cards:
                return
            discard(game, controller, chosen)
            draw_card(game, controller)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_loot_condition,
            effect=_loot_effect,
            source=self,
            controller=self.controller,
        ))
