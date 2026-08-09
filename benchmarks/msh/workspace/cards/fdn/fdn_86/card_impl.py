"""Card implementation for Fiery Annihilation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import CreatureDiesTriggeredEvent
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _is_equipment(obj: Any) -> bool:
    return "Equipment" in getattr(obj, "subtypes", set())


def _on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


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
        """Target creature (required) and *up to one* target Equipment attached
        to *that creature* (optional, dependent).

        The Equipment requirement is a **dependent** target (rule 601.2c): its
        filter takes the already-chosen targets, so only Equipment attached to
        the creature chosen for the first requirement is offered. When no such
        Equipment exists (or none is on the battlefield) the optional requirement
        is simply skipped — the spell stays castable and exiles no Equipment.
        """
        def _equipment_on_chosen_creature(obj: Any, chosen: list[Any]) -> bool:
            if not _is_equipment(obj):
                return False
            creature = chosen[0] if chosen else None
            return creature is not None and getattr(obj, "attached_to", None) is creature

        return [
            TargetRequirement(
                filter_fn=_is_creature,
                description='target creature',
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=_equipment_on_chosen_creature,
                description='up to one target Equipment attached to that creature',
                zone=Zone.BATTLEFIELD,
                optional=True,
            ),
        ]

    def on_resolve(self, game: 'GameState') -> None:
        """Deal 5 damage; exile the chosen Equipment iff still attached to the
        creature target; set the "exile instead of dying" replacement.

        Each target is revalidated independently (rule 608.2b): if only one of
        the two remains legal, that one still resolves. The Equipment is exiled
        only while it is *still attached to the creature target* — an Equipment
        that moved or reattached elsewhere is no longer a legal target and is
        left alone.
        """
        from engine.game import deal_damage, exile

        chosen = getattr(self, 'chosen_targets', None) or []
        target = chosen[0] if chosen else None
        equip_target = chosen[1] if len(chosen) > 1 else None
        controller = self.controller

        # Revalidate each target independently (rule 608.2b). The creature target
        # must still be a creature on the battlefield; the Equipment target must
        # still be Equipment on the battlefield attached to *that creature target*
        # (not any other Equipment). If only one survives, that one still resolves.
        creature_legal = target is not None and _is_creature(target) and _on_battlefield(game, target)
        equip_legal = (
            equip_target is not None
            and _is_equipment(equip_target)
            and _on_battlefield(game, equip_target)
            and getattr(equip_target, "attached_to", None) is target
        )

        # Instruction order: deal the 5 damage, then exile the Equipment.
        if creature_legal:
            deal_damage(game, self, target, 5)
        if equip_legal:
            exile(game, equip_target)
        if not creature_legal:
            return

        target._exile_on_death = True
        from engine.triggers import TriggerRegistration
        _target_ref = target

        def _death_condition(game: Any, event: Any) -> bool:
            return event.creature is _target_ref

        def _death_effect(game: 'GameState') -> None:
            ctrl = getattr(_target_ref, 'controller', None) or getattr(_target_ref, 'owner', None)
            if ctrl is not None:
                graveyard = ctrl.zones[Zone.GRAVEYARD]
                if graveyard.contains(_target_ref):
                    graveyard.remove(_target_ref)
                    exile(game, _target_ref)
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_death_condition, effect=_death_effect, source=self, controller=controller))
