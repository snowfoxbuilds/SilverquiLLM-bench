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
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying, haste\nEach instant and sorcery card in your hand has "
            "miracle {2}. (You may cast a card for its miracle cost when "
            "you draw it if it's the first card you drew this turn.)\nAt "
            "the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        self._register_upkeep_loot(game)
        self._register_miracle(game)

    # ------------------------------------------------------------------
    # At the beginning of each opponent's upkeep: may discard, then draw.
    # ------------------------------------------------------------------

    def _register_upkeep_loot(self, game: "GameState") -> None:
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            return ctrl is not None and game.active_player is not ctrl

        def _effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND].get_all()
            if not hand:
                return
            try:
                chosen = ctrl.choose_card(
                    hand, "discard a card to draw a card? (None to decline)"
                )
            except Exception:
                chosen = None
            if chosen is None or chosen not in hand:
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Miracle {2} for instant/sorcery cards drawn first this turn.
    # CARD-LOCAL gap: miracle is implemented as a draw trigger here, not
    # as a general engine mechanic.
    # ------------------------------------------------------------------

    def _register_miracle(self, game: "GameState") -> None:
        from engine.events import DrawsCardTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or getattr(event, "player", None) is not ctrl:
                return False
            # First card drawn this turn (counter reset at each turn wrap).
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            card = getattr(event, "card", None)
            card_types = getattr(card, "card_types", set())
            if not card_types & {CardType.INSTANT, CardType.SORCERY}:
                return False
            source._miracle_pending = card
            return True

        def _effect(game: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = source.controller
            card = getattr(source, "_miracle_pending", None)
            source._miracle_pending = None
            if ctrl is None or card is None:
                return
            hand = ctrl.zones[Zone.HAND]
            if not hand.contains(card):
                return
            miracle_cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(miracle_cost):
                return
            try:
                wants = ctrl.choose_yes_no(
                    f"cast {card.name} for its miracle cost {{2}}?"
                )
            except Exception:
                wants = False
            if not wants:
                return
            ctrl.mana_pool.pay(miracle_cost)
            try:
                # Miracle pays {2} instead of the mana cost; the cast
                # itself rides the free-cast stack path from hand.
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except CastingError:
                # Illegal cast (e.g. no legal target) — refund the {2}.
                from engine.types import ManaType

                ctrl.mana_pool.add(ManaType.COLORLESS, 2)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
