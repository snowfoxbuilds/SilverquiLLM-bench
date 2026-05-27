"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import discard, draw_card
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on the battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian."""

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
        self._miracle_effect_ref: ContinuousEffect | None = None

    def register_triggers(self, game: "GameState") -> None:
        """Register Lorehold's upkeep trigger and miracle-granting static effect."""
        source = self
        controller = self.controller or self.owner or game.active_player

        if self._miracle_effect_ref is None:
            def _apply_miracle(game: Any) -> None:
                ctrl = getattr(source, "controller", None) or getattr(source, "owner", None)
                if ctrl is None or not _is_on_battlefield(game, source):
                    return
                for card in game.get_hand(ctrl).get_all():
                    card_types = getattr(card, "card_types", set())
                    if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                        card.non_evergreen_keywords.add("Miracle")
                        card.miracle_cost = ManaCost.parse("{2}")

            self._miracle_effect_ref = game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.ABILITY,
                    sublayer=None,
                    apply=_apply_miracle,
                    duration=DURATION_PERMANENT,
                )
            )

        def _condition(game: Any, event: BeginningOfUpkeepTriggeredEvent) -> bool:
            ctrl = getattr(source, "controller", None) or getattr(source, "owner", None)
            return ctrl is not None and game.active_player is not ctrl and _is_on_battlefield(game, source)

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None) or getattr(source, "owner", None)
            if ctrl is None:
                return
            hand = game.get_hand(ctrl)
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                return
            if not ctrl.choose_yes_no("Discard a card to draw a card?"):
                return
            chosen = ctrl.choose_card(cards_in_hand, "card to discard")
            if chosen is None or not hand.contains(chosen):
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
