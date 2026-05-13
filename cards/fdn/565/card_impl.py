"""Card implementation for AngelicDestiny."""

from __future__ import annotations


from engine.card import Aura, Enchantment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _creature_targets(game: Any) -> list[Any]:
    """Return all creatures on the battlefield."""
    targets: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                targets.append(obj)
    return targets

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

def _get_chosen_target(card: Any, game: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


class AngelicDestiny(Aura):
    """Angelic Destiny — {2}{W}{W} — Enchanted creature gets +4/+4,
    has flying and first strike, and is an Angel in addition to its other
    types.  When enchanted creature dies, return this card to its owner's
    hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Angelic Destiny")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{W}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature gets +4/+4, has flying and first strike, "
            "and is an Angel in addition to its other types.\n"
            "When enchanted creature dies, return this card to its owner's hand.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _creature_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="enchant creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_creature_targets(game))

    def on_resolve(self, game: GameState) -> None:
        target = _get_chosen_target(self, game)
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return
        self.attached_to = target
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        aura_ref = self

        def _apply(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.base_power += 4
            creature.base_toughness += 4
            creature.keywords = creature.keywords | Keyword.FLYING | Keyword.FIRST_STRIKE
            subtypes = getattr(creature, "subtypes", set()) or set()
            creature.subtypes = subtypes | {"Angel"}

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        aura_ref = self

        def _condition(game: GameState, data: dict) -> bool:
            dying_creature = data.get("creature")
            return dying_creature is aura_ref.attached_to

        def _effect(game: GameState) -> None:
            from engine.zones import move_to_zone
            owner = getattr(aura_ref, "owner", None)
            if owner is None:
                return
            # Return aura to owner's hand via move_to_zone
            move_to_zone(game, aura_ref, Zone.GRAVEYARD, Zone.HAND)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=aura_ref,
            controller=controller,
        ))


__all__ = ["AngelicDestiny"]
