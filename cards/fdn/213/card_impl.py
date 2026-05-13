"""Card implementation for Blanchwood Armor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Aura, ContinuousEffect
from engine.continuous_effects import Layer, SubLayer
from engine.types import (
    CardType,
    ManaCost,
    TargetRequirement,
    Zone,
)

if TYPE_CHECKING:
    from engine.game_state import GameState




def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

def _creature_targets(game: Any) -> list[Any]:
    """Return all creatures on the battlefield."""
    targets: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                targets.append(obj)
    return targets

def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)
class BlanchwoodArmor(Aura):
    """Blanchwood Armor — {2}{G} — Enchanted creature gets +1/+1 for each
    Forest you control.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Blanchwood Armor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature gets +1/+1 for each Forest you control.",
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
            controller = getattr(aura_ref, "controller", None)
            if controller is None:
                return
            forest_count = 0
            for obj in game.get_battlefield(controller).get_all():
                subtypes = getattr(obj, "subtypes", set()) or set()
                if "Forest" in subtypes:
                    forest_count += 1
            creature.base_power += forest_count
            creature.base_toughness += forest_count

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)
