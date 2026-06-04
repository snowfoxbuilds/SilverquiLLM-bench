"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}. (You may cast
    a card for its miracle cost when you draw it if it's the first card you
    drew this turn.)
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
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}.\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # ----- Miracle: first instant/sorcery drawn each turn ------------
        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if getattr(event, "player", None) is not ctrl:
                return False
            if getattr(event.player, "cards_drawn_this_turn", 0) != 1:
                return False
            card = getattr(event, "card", None)
            if card is None or not _is_instant_or_sorcery(card):
                return False
            source._miracle_card = card  # type: ignore[attr-defined]
            return True

        def _miracle_effect(game: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_alt_cost

            ctrl = getattr(source, "controller", None)
            card = getattr(source, "_miracle_card", None)
            source._miracle_card = None  # type: ignore[attr-defined]
            if ctrl is None or card is None:
                return
            hand = ctrl.zones[Zone.HAND]
            if not hand.contains(card):
                return
            if not ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            try:
                cast_spell_alt_cost(game, ctrl, card, Zone.HAND, ManaCost(generic=2))
            except CastingError:
                return

        # ----- Loot: each opponent's upkeep ------------------------------
        def _loot_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and game.active_player is not ctrl

        def _loot_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND]
            cards = hand.get_all()
            if not cards:
                return
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = ctrl.choose_card(cards, "card to discard")
            if chosen is None or not hand.contains(chosen):
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
