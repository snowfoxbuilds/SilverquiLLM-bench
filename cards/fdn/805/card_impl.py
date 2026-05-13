"""Card implementation for WhispersilkCloak."""

from __future__ import annotations


from engine.card import Artifact, ActivatedAbility, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, ManaType
from typing import TYPE_CHECKING, Any


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class WhispersilkCloak(Artifact):
    """Whispersilk Cloak — {3} — Equipped creature has hexproof and can't be blocked. Equip {2}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Whispersilk Cloak")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault("rules_text", "Equipped creature has hexproof and can't be blocked.\nEquip {2}")
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
            creature.keywords = creature.keywords | Keyword.HEXPROOF
            creature._cant_be_blocked = True  # type: ignore[attr-defined]

        if self._effect_ref is None:
            effect = ContinuousEffect(
                source=equip_ref,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
            self._effect_ref = game.effect_manager.add(effect)


__all__ = ["WhispersilkCloak"]
