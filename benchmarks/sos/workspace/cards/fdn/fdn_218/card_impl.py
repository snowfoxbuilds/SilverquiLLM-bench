"""Card implementation for Dwynen's Elite."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


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

    def on_resolve(self, game: "GameState") -> None:
        """ETB: if you control another Elf, create a 1/1 Elf Warrior token."""
        from benchmarks.sos.workspace.engine.game import create_token

        controller = self.controller
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
            token = Creature(
                name="Elf Warrior",
                base_power=1,
                base_toughness=1,
                subtypes={"Elf", "Warrior"},
            )
            token.is_token = True
            create_token(game, controller, token)
