"""Card implementation for Applied Geometry."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import CardType, Color, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


_FRACTAL_COPY_CLASSES: dict[type[object], type[Creature]] = {}


def _ensure_fractal_creature_copy(target: object) -> Creature:
    token = copy.copy(target)
    if isinstance(token, Creature):
        return token

    target_type = type(token)
    fractal_type = _FRACTAL_COPY_CLASSES.get(target_type)
    if fractal_type is None:
        fractal_type = type(
            f"{target_type.__name__}FractalCopy",
            (target_type, Creature),
            {},
        )
        _FRACTAL_COPY_CLASSES[target_type] = fractal_type

    token.__class__ = fractal_type
    token.base_power = 0
    token.base_toughness = 0
    token.modified_power = 0
    token.modified_toughness = 0
    token.damage_marked = getattr(token, "damage_marked", 0)
    token.is_tapped = getattr(token, "is_tapped", False)
    token.summoning_sick = True
    token.is_attacking = False
    token.is_blocking = False
    token.plus_one_counters = 0
    token.minus_one_counters = 0
    token.dealt_deathtouch_damage = False
    token._base_plus_one_counters = 0
    token._base_minus_one_counters = 0
    return token


class AppliedGeometry(Sorcery):
    """Applied Geometry."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Applied Geometry")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        permanent_types = {
            CardType.ARTIFACT,
            CardType.CREATURE,
            CardType.ENCHANTMENT,
            CardType.LAND,
            CardType.PLANESWALKER,
        }
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    getattr(obj, "controller", None) is controller
                    and not getattr(obj, "is_aura", False)
                    and bool(getattr(obj, "card_types", set()) & permanent_types)
                ),
                description="target non-Aura permanent you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        chosen_targets = getattr(self, "chosen_targets", [])
        target = chosen_targets[0] if chosen_targets else None
        if controller is None or target is None:
            return

        token = _ensure_fractal_creature_copy(target)
        target_colors = get_colors(target)
        if target_colors:
            token.colors = set(target_colors)  # type: ignore[attr-defined]
        token.card_types.add(CardType.CREATURE)
        token.base_power = 0
        token.base_toughness = 0
        token.modified_power = 0
        token.modified_toughness = 0
        token.subtypes = set(getattr(token, "subtypes", set())) | {"Fractal"}
        token.plus_one_counters = 6
        token._base_plus_one_counters = 6
        token.snapshot_current_characteristics()
        create_token(game, controller, token)
