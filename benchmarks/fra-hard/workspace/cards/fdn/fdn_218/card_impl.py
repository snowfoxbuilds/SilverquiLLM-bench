"""Card implementation for Dwynen's Elite."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.tokens import make_creature_token
from engine.card import CardImpl, Creature
from engine.types import CardType, Color, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


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
        from engine.game import create_token

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
            token = make_creature_token(
                "Elf Warrior",
                {"Elf", "Warrior"},
                [Color.GREEN],
                1,
                1,
            )
            create_token(game, controller, token)
