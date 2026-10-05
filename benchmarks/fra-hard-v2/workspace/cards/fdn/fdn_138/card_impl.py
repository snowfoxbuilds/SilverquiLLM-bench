"""Card implementation for Banishing Light."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.events import LeavesBattlefieldTriggeredEvent
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class BanishingLightAbility1:
    text = 'When this enchantment enters, exile target nonland permanent an opponent controls until this enchantment leaves the battlefield.'


# endregion Printed abilities


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class BanishingLight(Enchantment):
    """Banishing Light — {2}{W} — Exile nonland permanent until this leaves.

    When this enchantment enters, exile target nonland permanent an opponent
    controls until this enchantment leaves the battlefield.

    FDN collector number 138.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Banishing Light')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{W}'))
        kwargs.setdefault('rules_text', 'When this enchantment enters, exile target nonland permanent an opponent controls until this enchantment leaves the battlefield.')
        super().__init__(**kwargs)
        self._exiled_card: Any | None = None
        self._exiled_owner: Any | None = None

    def _enters_targets(self, game: GameState, controller: Any) -> list[Any]:
        return [TargetRequirement(filter_fn=lambda obj, _c=controller: CardType.LAND not in getattr(obj, 'card_types', set()) and getattr(obj, 'controller', None) is not _c, description='nonland permanent an opponent controls', zone=Zone.BATTLEFIELD)]

    def _enters(self, game: GameState, targets: list[Any], controller: Any) -> None:
        chosen = targets
        target = chosen[0] if chosen else None
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return
        from engine.zones import move_to_zone
        self._exiled_card = target
        self._exiled_owner = getattr(target, 'owner', None) or getattr(target, 'controller', None)
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import register_enters_trigger

        register_enters_trigger(game, self, BanishingLightAbility1, self._enters, targets=self._enters_targets)

        from engine.triggers import TriggerRegistration
        source = self

        def _condition(game: Any, event: dict) -> bool:
            permanent = event.permanent
            return permanent is source

        def _effect(game: GameState) -> None:
            card = source._exiled_card
            owner = source._exiled_owner
            if card is None or owner is None:
                return
            from engine.zones import move_to_zone
            card.controller = owner
            move_to_zone(game, card, Zone.EXILE, Zone.BATTLEFIELD)
            source._exiled_card = None
            source._exiled_owner = None
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=LeavesBattlefieldTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller, printed=BanishingLightAbility1))
