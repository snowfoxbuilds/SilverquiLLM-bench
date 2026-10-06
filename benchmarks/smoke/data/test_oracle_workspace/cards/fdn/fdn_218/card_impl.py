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


def _controls_another_elf(game: "GameState", controller: Any, source: Any) -> bool:
    """Whether *controller* controls an Elf other than the ability's *source*
    as it triggered (a :class:`~engine.triggers.TriggerSource`)."""
    return controller is not None and any(
        not source.is_source(game, obj) and "Elf" in getattr(obj, "subtypes", set())
        for obj in game.get_battlefield(controller).get_all()
    )


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
        """The enters ability is a triggered ability that uses the stack. Its
        intervening "if" is checked as it triggers and again as it resolves."""
        from engine.triggers import register_enters_trigger

        register_enters_trigger(
            game, self, DwynensEliteAbility1, self._enters, condition=_controls_another_elf, knows_source=True
        )

    def _enters(self, game: "GameState", controller: Any, source: Any) -> None:
        """ETB: create a 1/1 Elf Warrior token."""
        from engine.game import create_token

        if controller is not None:
            token = make_creature_token(
                "Elf Warrior",
                {"Elf", "Warrior"},
                [Color.GREEN],
                1,
                1,
            )
            create_token(game, controller, token)
