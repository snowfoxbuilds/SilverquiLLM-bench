"""Card implementation for Reclamation Sage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ReclamationSageAbility1:
    text = 'When this creature enters, you may destroy target artifact or enchantment.'


# endregion Printed abilities


def _on_battlefield(game: Any, obj: Any) -> bool:
    return any(game.get_battlefield(p).contains(obj) for p in game.players)


class ReclamationSage(Creature):
    """Reclamation Sage — {2}{G} — 2/1 — Elf Shaman.

    When this creature enters, you may destroy target artifact or enchantment.

    FDN collector number 231.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Reclamation Sage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Shaman"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, you may destroy target artifact or "
            "enchantment.",
        )
        super().__init__(**kwargs)

    def _enters_targets(self, game: "GameState", controller: Any) -> list[Any]:
        """"You may" → optional target artifact or enchantment (declinable)."""

        def _filter(obj: Any) -> bool:
            types = getattr(obj, "card_types", set())
            return CardType.ARTIFACT in types or CardType.ENCHANTMENT in types

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target artifact or enchantment",
                zone=Zone.BATTLEFIELD,
                optional=True,
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that uses the stack."""
        from engine.triggers import register_enters_trigger

        register_enters_trigger(game, self, ReclamationSageAbility1, self._enters, targets=self._enters_targets)

    def _enters(self, game: "GameState", targets: list[Any], controller: Any) -> None:
        """Destroy the chosen artifact/enchantment, if one was targeted."""
        from engine.game import destroy

        chosen = targets
        target = chosen[0] if chosen else None
        if target is None:
            return
        if not _on_battlefield(game, target):
            return
        types = getattr(target, "card_types", set())
        if CardType.ARTIFACT in types or CardType.ENCHANTMENT in types:
            destroy(game, target)
