"""Card implementation for Dwynen's Elite."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.tokens import make_creature_token
from engine.card import Creature
from engine.types import Color, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class DwynensEliteAbility1:
    text = 'When this creature enters, if you control another Elf, create a 1/1 green Elf Warrior creature token.'


# endregion Printed abilities


class DwynensElite(Creature):
    """Dwynen's Elite — {1}{G} — 2/2 — Elf Warrior.

    When this creature enters, if you control another Elf, create a
    1/1 green Elf Warrior creature token.

    FDN collector number 218.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dwynen's Elite")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Warrior"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, if you control another Elf, "
            "create a 1/1 green Elf Warrior creature token.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that uses the stack."""
        from engine.triggers import register_enters_trigger

        def _condition(game: Any, controller: Any) -> bool:
            return controller is not None and any(
                obj is not self and "Elf" in getattr(obj, "subtypes", set())
                for obj in game.get_battlefield(controller).get_all()
            )

        register_enters_trigger(game, self, DwynensEliteAbility1, self._enters, condition=_condition)

    def _enters(self, game: "GameState", controller: Any) -> None:
        """ETB: if you control another Elf, create a 1/1 Elf Warrior token."""
        from engine.game import create_token

        if controller is None:
            return

        bf = game.get_battlefield(controller)
        has_other_elf = False
        for obj in bf.get_all():
            if obj is self:
                continue
            if "Elf" in getattr(obj, "subtypes", set()):
                has_other_elf = True
                break

        if has_other_elf:
            token = make_creature_token(
                "Elf Warrior",
                {"Elf", "Warrior"},
                [Color.GREEN],
                1,
                1,
            )
            create_token(game, controller, token)
