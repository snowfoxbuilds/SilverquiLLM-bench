"""Card implementation for NewHorizons."""

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

def _land_targets(game: Any) -> list[Any]:
    """Return all lands on the battlefield."""
    targets: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
            if CardType.LAND in getattr(obj, "card_types", set()):
                targets.append(obj)
    return targets


class NewHorizons(Aura):
    """New Horizons — {2}{G} — Enchant land.
    When this Aura enters, put a +1/+1 counter on target creature you control.
    Enchanted land has "{T}: Add two mana of any one color."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "New Horizons")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant land\n"
            "When this Aura enters, put a +1/+1 counter on target creature "
            "you control.\n"
            'Enchanted land has "{T}: Add two mana of any one color."',
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _land_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.LAND in getattr(obj, "card_types", set()),
                description="enchant land",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_land_targets(game))

    def on_resolve(self, game: GameState) -> None:
        target = _get_chosen_target(self, game)
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return
        self.attached_to = target
        # ETB: put a +1/+1 counter on target creature you control
        # ENGINE LIMITATION: auto-picks first creature instead of being a
        # targeted trigger — proper targeted ETB triggers need engine support.
        controller = getattr(self, "controller", None)
        if controller is not None:
            from engine.game import add_counter
            for obj in game.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    add_counter(game, obj, "+1/+1", 1)
                    # Also track in counters dict for query compatibility
                    if not hasattr(obj, "counters"):
                        obj.counters = {}
                    obj.counters["+1/+1"] = obj.counters.get("+1/+1", 0) + 1
                    break
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        aura_ref = self

        def _apply(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            land = aura_ref.attached_to
            if land is None or not _is_on_battlefield(game, land):
                return
            land._new_horizons_mana = True  # type: ignore[attr-defined]

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


__all__ = ["NewHorizons"]
