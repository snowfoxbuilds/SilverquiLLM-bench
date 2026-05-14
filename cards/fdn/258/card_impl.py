"""Card implementation for Swiftfoot Boots."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Artifact, ActivatedAbility, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, ManaType
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class SwiftfootBoots(Artifact):
    """Swiftfoot Boots — {2} — Equipped creature has hexproof and haste. Equip {1}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swiftfoot Boots")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault("rules_text", "Equipped creature has hexproof and haste.\nEquip {1}")
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._effect_ref: ContinuousEffect | None = None

    def equip(self, target: Any, game: Any) -> None:
        self.attached_to = target
        self._register_effect(game)

    def _register_effect(self, game: Any) -> None:
        equip_ref = self

        def _apply(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.keywords = creature.keywords | Keyword.HEXPROOF | Keyword.HASTE

        if self._effect_ref is None:
            effect = ContinuousEffect(
                source=equip_ref,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
            self._effect_ref = game.effect_manager.add(effect)
