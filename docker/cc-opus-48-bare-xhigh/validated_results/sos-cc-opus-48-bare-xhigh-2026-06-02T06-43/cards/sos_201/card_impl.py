"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


MIRACLE_COST = ManaCost.parse("{2}")


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


def cast_for_miracle(
    game: "GameState", controller: Any, card: Any, miracle_cost: "ManaCost"
) -> bool:
    """Cast *card* from *controller*'s hand for its miracle cost.

    Pays *miracle_cost* from the controller's mana pool, then casts the card
    without paying its normal mana cost.  Returns ``True`` if the spell was
    cast, ``False`` if the cost could not be paid or casting failed.
    """
    from engine.casting import cast_spell_free

    if not controller.zones[Zone.HAND].contains(card):
        return False
    if not controller.mana_pool.can_pay(miracle_cost):
        return False
    controller.mana_pool.pay(miracle_cost)
    try:
        cast_spell_free(game, controller, card, Zone.HAND)
    except Exception:
        return False
    return True


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — Legendary Creature — Elder Dragon.

    Flying, haste (5/5).
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card. If you
    do, draw a card.

    SOS collector number 201.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {
            Supertype.LEGENDARY
        }
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
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
        # Cards awaiting a miracle decision (captured in the draw condition).
        self._miracle_pending: list = []

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Miracle grant (draw-triggered) ---
        def _miracle_condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or getattr(event, "player", None) is not ctrl:
                return False
            if not ctrl.zones[Zone.BATTLEFIELD].contains(source):
                return False
            card = getattr(event, "card", None)
            if card is None or not _is_instant_or_sorcery(card):
                return False
            # Only the first card drawn this turn has miracle.
            if getattr(ctrl, "cards_drawn_this_turn", 0) != 1:
                return False
            source._miracle_pending.append(card)
            return True

        def _miracle_effect(game: "GameState") -> None:
            if not source._miracle_pending:
                return
            card = source._miracle_pending.pop()
            ctrl = source.controller
            if ctrl is None or not ctrl.zones[Zone.HAND].contains(card):
                return
            try:
                if not ctrl.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for its miracle cost {{2}}?"
                ):
                    return
            except Exception:
                return
            cast_for_miracle(game, ctrl, card, MIRACLE_COST)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DrawsCardTriggeredEvent,
                condition=_miracle_condition,
                effect=_miracle_effect,
                source=self,
                controller=controller,
            )
        )

        # --- Loot on each opponent's upkeep ---
        def _loot_condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None:
                return False
            if not ctrl.zones[Zone.BATTLEFIELD].contains(source):
                return False
            # "each opponent's upkeep" — fires when it is not your turn.
            return game.active_player is not ctrl

        def _loot_effect(game: "GameState") -> None:
            from engine.game import discard, draw_card

            ctrl = source.controller
            if ctrl is None:
                return
            hand = ctrl.zones[Zone.HAND].get_all()
            if not hand:
                return
            try:
                if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                    return
            except Exception:
                return
            try:
                chosen = ctrl.choose_card(hand, "Discard a card")
            except Exception:
                chosen = hand[-1]
            if chosen is None or not ctrl.zones[Zone.HAND].contains(chosen):
                return
            discard(game, ctrl, chosen)
            draw_card(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=_loot_condition,
                effect=_loot_effect,
                source=self,
                controller=controller,
            )
        )
