"""Card implementation for Garruk's Uprising."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.continuous_effects import DURATION_PERMANENT, ContinuousEffect, Layer
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class GarruksUprisingAbility1:
    text = 'When this enchantment enters, if you control a creature with power 4 or greater, draw a card.'


class GarruksUprisingAbility2:
    text = "Creatures you control have trample. (Each of those creatures can deal excess combat damage to the player or planeswalker it's attacking.)"


class GarruksUprisingAbility3:
    text = 'Whenever a creature you control with power 4 or greater enters, draw a card.'


# endregion Printed abilities


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
        kwargs.setdefault('name', "Garruk's Uprising")
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{G}'))
        kwargs.setdefault('rules_text', 'When this enchantment enters, if you control a creature with power 4 or greater, draw a card.\nCreatures you control have trample.\nWhenever a creature you control with power 4 or greater enters, draw a card.')
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
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
                if CardType.CREATURE in getattr(obj, 'card_types', set()):
                    obj.keywords = obj.keywords | Keyword.TRAMPLE
        effect = ContinuousEffect(source=enchantment_ref, layer=Layer.ABILITY, sublayer=None, apply=_apply, duration=DURATION_PERMANENT)
        self._effect_ref = game.effect_manager.add(effect)

    def register_triggers(self, game: GameState) -> None:
        from engine.game import draw_card
        from engine.triggers import TriggerRegistration, register_enters_trigger
        source = self

        def _controls_power_four(game: Any, controller: Any) -> bool:
            return controller is not None and any(
                CardType.CREATURE in getattr(obj, 'card_types', set())
                and getattr(obj, 'power', getattr(obj, 'base_power', 0)) >= 4
                for obj in game.get_battlefield(controller).get_all()
            )

        register_enters_trigger(
            game, self, GarruksUprisingAbility1, lambda game, controller: draw_card(game, controller),
            condition=_controls_power_four,
        )

        def _condition(game: Any, event: dict) -> bool:
            permanent = event.permanent
            if permanent is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            if getattr(permanent, 'controller', None) is not controller:
                return False
            if CardType.CREATURE not in getattr(permanent, 'card_types', set()):
                return False
            power = getattr(permanent, 'power', getattr(permanent, 'base_power', 0))
            return power >= 4

        def _effect(game: GameState, controller: Any) -> None:
            if controller is not None:
                draw_card(game, controller)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller, printed=GarruksUprisingAbility3))

    def register_replacement_effects(self, game: GameState) -> None:
        if self._effect_ref is None:
            self._register_effect(game)
