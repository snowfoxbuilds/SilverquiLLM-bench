"""Card implementation for Twinblade Blessing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Aura
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


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


class TwinbladeBlessing(Aura):
    """Twinblade Blessing — {1}{W}{W} — Flash.

    Enchant creature.
    Enchanted creature has double strike.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Twinblade Blessing")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Flash\n"
            "Enchant creature\n"
            "Enchanted creature has double strike.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    # -- targeting --------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _creature_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="enchant creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_creature_targets(game))

    # -- resolution -------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        target = _get_chosen_target(self, game)
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return
        # Revalidate that target is still a creature (type may have changed).
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return
        self.attached_to = target
        self._register_effect(game)

    # -- continuous effect: Layer 6 (ability granting) --------------------

    def apply_continuous_effect(self, game: GameState) -> None:
        """Grant double strike to the enchanted creature (Layer 6)."""
        creature = self.attached_to
        if creature is None or not _is_on_battlefield(game, creature):
            return
        if not _is_on_battlefield(game, self):
            return
        creature.keywords = creature.keywords | Keyword.DOUBLE_STRIKE

    def _register_effect(self, game: GameState) -> None:
        aura_ref = self

        def _apply(game: GameState) -> None:
            aura_ref.apply_continuous_effect(game)

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)
