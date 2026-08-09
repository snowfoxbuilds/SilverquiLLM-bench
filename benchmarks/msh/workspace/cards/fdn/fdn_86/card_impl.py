"""Card implementation for Fiery Annihilation."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from engine.events import CreatureDiesTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class FieryAnnihilation(Instant):
    """Fiery Annihilation — {2}{R} — Instant.

    Fiery Annihilation deals 5 damage to target creature. Exile up to one
    target Equipment attached to that creature. If that creature would die
    this turn, exile it instead.

    FDN collector number 86.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Fiery Annihilation')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{R}'))
        kwargs.setdefault('rules_text', 'Fiery Annihilation deals 5 damage to target creature. Exile up to one target Equipment attached to that creature. If that creature would die this turn, exile it instead.')
        super().__init__(**kwargs)

    def get_targets(self, game: 'GameState') -> list:
        """Target creature (required) and *up to one* target Equipment (optional).

        The Equipment target is optional (rule "up to one target"), so the spell
        stays castable when no Equipment is on the battlefield — the second
        requirement is simply skipped, contributing no entry to ``chosen_targets``.
        """
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, 'card_types', set()),
                description='target creature',
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: 'Equipment' in getattr(obj, 'subtypes', set())
                and getattr(obj, 'attached_to', None) is not None,
                description='up to one target Equipment attached to that creature',
                zone=Zone.BATTLEFIELD,
                optional=True,
            ),
        ]

    def on_resolve(self, game: 'GameState') -> None:
        """Deal 5 damage, exile the chosen Equipment (if any), set exile replacement."""
        from engine.game import deal_damage, exile
        chosen = getattr(self, 'chosen_targets', None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return
        if CardType.CREATURE not in getattr(target, 'card_types', set()):
            return
        controller = self.controller
        deal_damage(game, self, target, 5)
        # The Equipment target is chosen at cast ("up to one"): exile it if the
        # player targeted one, otherwise exile nothing (never re-choose here).
        equip_target = chosen[1] if len(chosen) > 1 else None
        if equip_target is not None:
            exile(game, equip_target)
        target._exile_on_death = True
        from engine.triggers import TriggerRegistration
        _target_ref = target

        def _death_condition(game: Any, event: dict) -> bool:
            return event.creature is _target_ref

        def _death_effect(game: 'GameState') -> None:
            ctrl = getattr(_target_ref, 'controller', None) or getattr(_target_ref, 'owner', None)
            if ctrl is not None:
                graveyard = ctrl.zones[Zone.GRAVEYARD]
                if graveyard.contains(_target_ref):
                    graveyard.remove(_target_ref)
                    exile(game, _target_ref)
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_death_condition, effect=_death_effect, source=self, controller=controller))
