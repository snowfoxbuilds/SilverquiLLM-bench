"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: "GameState", obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_instant_or_sorcery(obj: Any) -> bool:
    return bool(getattr(obj, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste.
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
        self._miracle_seen_turn: int = -1
        self._miracle_draw_index: int = 0
        self._miracle_card: Any = None

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle {2} on the first card drawn this turn ---
        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or not _on_battlefield(game, source):
                return False
            if getattr(event, "player", None) is not ctrl:
                return False
            # Track the controller's draws per turn (turn-stamped).
            turn = getattr(game, "turn_number", 0)
            if source._miracle_seen_turn != turn:
                source._miracle_seen_turn = turn
                source._miracle_draw_index = 0
            source._miracle_draw_index += 1
            if source._miracle_draw_index != 1:
                return False  # not the first card drawn this turn
            card = getattr(event, "card", None)
            if not _is_instant_or_sorcery(card):
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            card = getattr(source, "_miracle_card", None)
            if ctrl is None or card is None:
                return
            if not ctrl.zones[Zone.HAND].contains(card):
                return
            try:
                if not ctrl.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for its miracle cost {{2}}?"
                ):
                    return
            except Exception:
                return
            cost = ManaCost(generic=2)
            if not ctrl.mana_pool.can_pay(cost):
                return
            ctrl.mana_pool.pay(cost)
            from engine.casting import cast_spell_free
            try:
                cast_spell_free(game, ctrl, card, Zone.HAND)
            except Exception:
                pass

        game.trigger_manager.register(TriggerRegistration(
            event_type=DrawsCardTriggeredEvent,
            condition=_miracle_condition,
            effect=_miracle_effect,
            source=self,
            controller=controller,
        ))

        # --- Loot at each opponent's upkeep ---
        def _loot_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or not _on_battlefield(game, source):
                return False
            # Opponent's upkeep = the active player is not the controller.
            return game.active_player is not ctrl

        def _loot_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            hand_cards = ctrl.zones[Zone.HAND].get_all()
            if not hand_cards:
                return  # may discard, but nothing to discard
            try:
                if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                    return
            except Exception:
                return
            try:
                chosen = ctrl.choose_card(hand_cards, "Choose a card to discard")
            except Exception:
                chosen = hand_cards[0]
            if chosen is None:
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfUpkeepTriggeredEvent,
            condition=_loot_condition,
            effect=_loot_effect,
            source=self,
            controller=controller,
        ))
