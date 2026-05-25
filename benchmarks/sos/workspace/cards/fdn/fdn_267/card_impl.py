"""Card implementation for Secluded Courtyard."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Land, ManaAbility
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class SecludedCourtyard(Land):
    """Secluded Courtyard — Land

    As this land enters, choose a creature type.
    {T}: Add {C}.
    {T}: Add one mana of any color. Spend this mana only to cast a creature
    spell of the chosen type or activate an ability of a creature source of
    the chosen type.

    FDN collector number 267.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Secluded Courtyard")
        kwargs.setdefault(
            "rules_text",
            "As this land enters, choose a creature type.\n"
            "{T}: Add {C}.\n"
            "{T}: Add one mana of any color. Spend this mana only to cast "
            "a creature spell of the chosen type or activate an ability of "
            "a creature source of the chosen type.",
        )
        super().__init__(**kwargs)
        self.chosen_creature_type: str | None = None

    def on_resolve(self, game: Any) -> None:
        """As this land enters, choose a creature type.

        Note: play_land() should ideally call this method (or an equivalent
        on_enter hook) so the choice is recorded during normal land play.
        The engine currently does not invoke on_resolve() for lands, so
        callers must trigger this explicitly.
        """
        controller = self.controller
        if controller is not None:
            # Use controller.choose to pick a creature type.
            # Signature: choose(options, description)
            creature_types = [
                "Human", "Elf", "Goblin", "Wizard", "Soldier",
                "Zombie", "Merfolk", "Angel", "Dragon", "Vampire",
                "Beast", "Elemental", "Knight", "Warrior", "Rogue",
                "Cleric", "Shaman", "Druid", "Spirit", "Demon",
                "Bird", "Cat", "Dog", "Dinosaur", "Sliver",
            ]
            choice = controller.choose(
                creature_types,
                "Choose a creature type for Secluded Courtyard",
            )
            self.chosen_creature_type = choice

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _colorless_effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _any_color_effect(game: Any) -> None:
            # ENGINE LIMITATION: The engine does not support conditional mana
            # spending restrictions. This should only be usable to cast creature
            # spells of the chosen type or activate abilities of creature sources
            # of the chosen type. The restriction is not enforced here.
            controller = source.controller
            if controller is not None:
                # Produce one mana of any color. Let the controller choose.
                color_options = [
                    ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                    ManaType.RED, ManaType.GREEN,
                ]
                chosen_color = controller.choose(
                    color_options,
                    "Choose a color of mana to produce",
                )
                controller.mana_pool.add(chosen_color, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_any_color_effect,
                description="{T}: Add one mana of any color (restricted).",
            ),
        ]
