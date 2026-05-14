"""Card implementation for Garruk's Uprising."""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Creature, Enchantment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class GarruksUprising(Enchantment):
    """Garruk's Uprising — {2}{G} — Creatures you control have trample.

    When this enchantment enters, if you control a creature with power 4
    or greater, draw a card.
    Whenever a creature you control with power 4 or greater enters,
    draw a card.

    FDN collector number 220.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Garruk's Uprising")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault(
            "rules_text",
            "When this enchantment enters, if you control a creature with "
            "power 4 or greater, draw a card.\n"
            "Creatures you control have trample.\n"
            "Whenever a creature you control with power 4 or greater enters, "
            "draw a card.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        # ETB: if you control a creature with power 4+, draw a card.
        controller = self.controller
        if controller is not None:
            for obj in game.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    power = getattr(obj, "power", getattr(obj, "base_power", 0))
                    if power >= 4:
                        from engine.game import draw_card
                        draw_card(game, controller)
                        break
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        enchantment_ref = self

        def _apply(game: GameState) -> None:
            controller = enchantment_ref.controller
            if controller is None:
                return
            if not _is_on_battlefield(game, enchantment_ref):
                return
            for obj in game.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.keywords = obj.keywords | Keyword.TRAMPLE

        effect = ContinuousEffect(
            source=enchantment_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _condition(game: Any, data: dict) -> bool:
            permanent = data.get("permanent")
            if permanent is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            if getattr(permanent, "controller", None) is not controller:
                return False
            if CardType.CREATURE not in getattr(permanent, "card_types", set()):
                return False
            power = getattr(permanent, "power", getattr(permanent, "base_power", 0))
            return power >= 4

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def register_replacement_effects(self, game: GameState) -> None:
        if self._effect_ref is None:
            self._register_effect(game)
