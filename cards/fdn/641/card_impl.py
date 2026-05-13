"""Card implementation for OrdealOfNylea."""

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


class OrdealOfNylea(Aura):
    """Ordeal of Nylea — {1}{G} — Enchant creature.
    Whenever enchanted creature attacks, put a +1/+1 counter on it. Then if
    it has three or more +1/+1 counters on it, sacrifice this Aura.
    When you sacrifice this Aura, search your library for up to two basic
    land cards, put them onto the battlefield tapped, then shuffle.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ordeal of Nylea")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Whenever enchanted creature attacks, put a +1/+1 counter on it. "
            "Then if it has three or more +1/+1 counters on it, sacrifice "
            "this Aura.\n"
            "When you sacrifice this Aura, search your library for up to two "
            "basic land cards, put them onto the battlefield tapped, then shuffle.",
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

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        aura_ref = self

        def _attack_condition(game: GameState, data: dict) -> bool:
            attacker = data.get("card")
            return attacker is aura_ref.attached_to

        def _attack_effect(game: GameState) -> None:
            from engine.game import add_counter
            from engine.zones import move_to_zone
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            add_counter(game, creature, "+1/+1", 1)
            # Also track in counters dict for query compatibility
            if not hasattr(creature, "counters"):
                creature.counters = {}
            creature.counters["+1/+1"] = creature.counters.get("+1/+1", 0) + 1
            # Check if 3+ counters — sacrifice the aura
            counter_count = getattr(creature, "plus_one_counters", 0)
            if counter_count >= 3:
                controller = getattr(aura_ref, "controller", None)
                if controller is not None and _is_on_battlefield(game, aura_ref):
                    move_to_zone(game, aura_ref, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ATTACKS,
            condition=_attack_condition,
            effect=_attack_effect,
            source=aura_ref,
            controller=controller,
        ))


__all__ = ["OrdealOfNylea"]
