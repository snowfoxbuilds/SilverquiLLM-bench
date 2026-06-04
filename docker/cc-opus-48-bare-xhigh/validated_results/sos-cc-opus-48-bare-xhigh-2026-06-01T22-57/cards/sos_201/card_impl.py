"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


def _on_battlefield(game: "GameState", perm: Any) -> bool:
    controller = getattr(perm, "controller", None)
    if controller is None:
        return False
    return perm in controller.zones[Zone.BATTLEFIELD].get_all()


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Elder Dragon.

    Flying, haste.
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card. If you
    do, draw a card.

    SOS collector number 201.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
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

        # --- Miracle {2} for instant/sorcery cards in hand ---
        def _miracle_condition(game: "GameState", event: DrawsCardTriggeredEvent) -> bool:
            if not _on_battlefield(game, source):
                return False
            ctrl = source.controller
            player = getattr(event, "player", None)
            if ctrl is None or player is not ctrl:
                return False
            turn = getattr(game, "turn_number", 0)
            first_this_turn = getattr(ctrl, "_lorehold_miracle_turn", None) != turn
            ctrl._lorehold_miracle_turn = turn
            if not first_this_turn:
                return False
            card = getattr(event, "card", None)
            if card is None or not _is_instant_or_sorcery(card):
                return False
            source._miracle_card = card
            return True

        def _miracle_effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            card = getattr(source, "_miracle_card", None)
            source._miracle_card = None
            ctrl = source.controller
            if card is None or ctrl is None:
                return
            if card not in ctrl.zones[Zone.HAND].get_all():
                return
            cost = ManaCost.parse("{2}")
            if not ctrl.mana_pool.can_pay(cost):
                return
            if not ctrl.choose_yes_no(
                f"Cast {getattr(card, 'name', 'this card')} for its miracle cost {{2}}?"
            ):
                return
            if not ctrl.mana_pool.pay(cost):
                return
            cast_spell_free(game, ctrl, card, Zone.HAND)

        # --- Each opponent's upkeep: loot (discard, then draw) ---
        def _loot_condition(game: "GameState", event: BeginningOfUpkeepTriggeredEvent) -> bool:
            if not _on_battlefield(game, source):
                return False
            ctrl = source.controller
            return ctrl is not None and game.active_player is not ctrl

        def _loot_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand_cards = ctrl.zones[Zone.HAND].get_all()
            if not hand_cards:
                return
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = ctrl.choose_card(list(hand_cards), "Choose a card to discard")
            if chosen is None:
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
