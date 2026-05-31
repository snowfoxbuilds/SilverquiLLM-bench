"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature
    gets +1/+0 until end of turn." It's still a land.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault("subtypes", set())
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            "creature with \"Whenever you cast an instant or sorcery spell, "
            "this creature gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        # Wizard mode flag.
        self._is_wizard: bool = False

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return the land's two mana abilities."""

        # Ability 1: {T} → {C}
        def tap_cost(game: "GameState") -> bool:
            if self.is_tapped:
                return False
            self.is_tapped = True
            return True

        def colorless_produce(game: "GameState") -> dict[ManaType, int]:
            return {ManaType.COLORLESS: 1}

        colorless_ability = ManaAbility(
            cost=tap_cost,
            mana_produced=colorless_produce,
            description="{T}: Add {C}.",
        )

        # Ability 2: {T}, Pay 1 life → any color mana (instant/sorcery only)
        def colored_cost(game: "GameState") -> bool:
            if self.is_tapped:
                return False
            controller = self.controller
            if controller is not None:
                if controller.life <= 0:
                    return False
                controller.life -= 1
            self.is_tapped = True
            return True

        def colored_produce(game: "GameState") -> dict[ManaType, int]:
            # Produces one white mana by default (any color; white is representative).
            # In a full implementation the player would choose the color.
            return {ManaType.WHITE: 1}

        colored_ability = ManaAbility(
            cost=colored_cost,
            mana_produced=colored_produce,
            description="{T}, Pay 1 life: Add one mana of any color (instant/sorcery only).",
        )

        return [colorless_ability, colored_ability]

    def activate_wizard_form(self, game: "GameState") -> None:
        """Activate the {5} ability: become a 2/4 Wizard creature land."""
        if self._is_wizard:
            return
        self._is_wizard = True
        self.card_types = self.card_types | {CardType.CREATURE}
        subtypes = set(getattr(self, "subtypes", set()))
        subtypes.add("Wizard")
        self.subtypes = subtypes
        self.base_power = 2
        self.base_toughness = 4
