"""Card implementation for Witness Protection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Aura, ContinuousEffect
from engine.continuous_effects import Layer
from engine.types import (
    CardType,
    Keyword,
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
class WitnessProtection(Aura):
    """Witness Protection — {U} — Enchant creature.
    Enchanted creature loses all abilities and is a green and white Citizen
    creature with base power and toughness 1/1 named Legitimate Businessperson.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witness Protection")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature loses all abilities and is a green and white "
            "Citizen creature with base power and toughness 1/1 named "
            "Legitimate Businessperson.",
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
            creature.name = "Legitimate Businessperson"
            creature.card_types = {CardType.CREATURE}
            creature.subtypes = {"Citizen"}
            creature.keywords = Keyword(0)
            creature.base_power = 1
            creature.base_toughness = 1
            # ENGINE LIMITATION: EffectManager._reset_objects() doesn't
            # restore name or subtypes. When this aura leaves the battlefield
            # the name/subtype changes persist until engine-level reset is added.

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.TYPE,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)
