"""Card implementation for Confiscate."""

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


def _permanent_targets(game: Any) -> list[Any]:
    """Return all permanents on the battlefield."""
    targets: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
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


class Confiscate(Aura):
    """Confiscate — {4}{U}{U} — Enchant permanent.
    You control enchanted permanent.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Confiscate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant permanent\n"
            "You control enchanted permanent.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _permanent_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="enchant permanent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_permanent_targets(game))

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
            perm = aura_ref.attached_to
            if perm is None or not _is_on_battlefield(game, perm):
                return
            aura_controller = getattr(aura_ref, "controller", None)
            if aura_controller is not None:
                # ENGINE LIMITATION: Just setting .controller doesn't move the
                # permanent between player battlefield zones. A proper
                # controller-change helper is needed in the engine to handle
                # zone migration and related triggers.
                perm.controller = aura_controller

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.CONTROL,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


__all__ = ["Confiscate"]
