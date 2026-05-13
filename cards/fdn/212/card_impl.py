"""Card implementation for BiteDown."""

from __future__ import annotations


from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


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

def _get_chosen_target_idx(card: Any, game: Any, idx: int) -> Any:
    """Retrieve the *idx*-th chosen target for a spell (0-indexed)."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen and len(chosen) > idx:
        return chosen[idx]
    # Fall back to list-based test backdoor
    targets = getattr(card, "_resolve_targets", None)
    if targets and len(targets) > idx:
        return targets[idx]
    if idx == 0:
        return getattr(card, "_resolve_target", None)
    return None


class BiteDown(Instant):
    """Bite Down — {1}{G} — Target creature you control deals damage
    equal to its power to target creature or planeswalker you don't
    control.

    FDN collector number 212.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bite Down")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature you control deals damage equal to its power "
            "to target creature or planeswalker you don't control.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Two targets: a creature you control and a creature/PW an
        opponent controls.
        """
        controller = self.controller
        my_targets: list[Any] = []
        opp_targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                card_types = getattr(obj, "card_types", set())
                obj_ctrl = getattr(obj, "controller", None)
                if obj_ctrl is controller:
                    if CardType.CREATURE in card_types:
                        my_targets.append(obj)
                else:
                    if CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types:
                        opp_targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is _c
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    bool(getattr(obj, "card_types", set()) & {CardType.CREATURE, CardType.PLANESWALKER})
                    and getattr(obj, "controller", None) is not _c
                ),
                description="target creature or planeswalker you don't control",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Your creature deals damage equal to its power to the second target."""
        from engine.game import deal_damage

        source_creature = _get_chosen_target_idx(self, game, 0)
        fight_target = _get_chosen_target_idx(self, game, 1)

        if source_creature is None or fight_target is None:
            return

        # Verify both are still on the battlefield
        source_valid = False
        target_valid = False
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(source_creature):
                source_valid = True
            if bf.contains(fight_target):
                target_valid = True

        if source_valid and target_valid:
            power = getattr(source_creature, "power", getattr(source_creature, "base_power", 0))
            if power > 0:
                deal_damage(game, source_creature, fight_target, power)


__all__ = ["BiteDown"]
