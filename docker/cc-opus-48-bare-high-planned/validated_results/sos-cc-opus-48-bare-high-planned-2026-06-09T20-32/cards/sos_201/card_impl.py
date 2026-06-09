"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    return bool(
        getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}
    )


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste
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
            "Flying, haste\nEach instant and sorcery card in your hand has "
            "miracle {2}.\nAt the beginning of each opponent's upkeep, you may "
            "discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Loot: each opponent's upkeep ---
        def _upkeep_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            return ctrl is not None and game.active_player is not ctrl

        def _upkeep_effect(game: "GameState") -> None:
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
            chosen = ctrl.choose_card(cards, "discard a card")
            if chosen is None or not hand.contains(chosen):
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_upkeep_condition,
                effect=_upkeep_effect,
                source=self,
                controller=controller,
            )
        )

        # --- Miracle {2}: first card drawn this turn, if instant/sorcery ---
        def _draw_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if event.player is not ctrl or ctrl is None:
                return False
            cur = getattr(game, "turn_number", 0)
            if getattr(source, "_miracle_turn", None) != cur:
                source._miracle_turn = cur
                source._miracle_drawcount = 0
            source._miracle_drawcount += 1
            if source._miracle_drawcount != 1:
                return False  # only the first card drawn this turn
            card = event.card
            if card is None or not _is_instant_or_sorcery(card):
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = getattr(source, "controller", None)
            card = getattr(source, "_miracle_card", None)
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return
            cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(cost):
                return
            if not ctrl.choose_yes_no(
                f"Cast {card.name} for its miracle cost {{2}}?"
            ):
                return
            ctrl.mana_pool.pay(cost)
            # Free-cast path (cost already paid as the {2} miracle cost).
            cast_spell_free(game, ctrl, card, Zone.HAND)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_draw_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )
