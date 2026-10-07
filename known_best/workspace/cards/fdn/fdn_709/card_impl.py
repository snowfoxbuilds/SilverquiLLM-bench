"""Card implementation for Confiscate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Aura
from engine.continuous_effects import (
    DURATION_PERMANENT,
    ContinuousEffect,
    Layer,
    set_controller,
)
from engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ConfiscateAbility1:
    text = 'Enchant permanent'


class ConfiscateAbility2:
    text = 'You control enchanted permanent.'


# endregion Printed abilities


def _permanents(game: Any) -> list[Any]:
    return [
        obj
        for player in game.players
        for obj in game.get_battlefield(player).get_all()
    ]


def _on_battlefield(game: Any, obj: Any) -> bool:
    return any(game.get_battlefield(p).contains(obj) for p in game.players)


class Confiscate(Aura):
    """Confiscate — {4}{U}{U} — Enchantment — Aura.

    Enchant permanent
    You control enchanted permanent.

    FDN collector number 709.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Confiscate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text", "Enchant permanent\nYou control enchanted permanent."
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        if not _permanents(game):
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="enchant permanent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_permanents(game))

    def on_resolve(self, game: GameState) -> None:
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None or not _on_battlefield(game, target):
            return
        self.attached_to = target
        aura = self

        def _control(g: Any) -> None:
            enchanted = aura.attached_to
            if enchanted is None or aura.controller is None:
                return
            if _on_battlefield(g, aura) and _on_battlefield(g, enchanted):
                set_controller(enchanted, aura.controller)

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.CONTROL,
                apply=_control,
                duration=DURATION_PERMANENT,
                controls=lambda: aura.attached_to,
                reads_controller_of=aura,
            )
        )
        game.effect_manager.apply_all(game)
