"""Card implementation for Shattered Acolyte."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ShatteredAcolyte(Creature):
    """Shattered Acolyte — {1}{W} — Creature — Dwarf Warlock — 2/2.

    Lifelink
    {1}, Sacrifice this creature: Destroy target artifact or enchantment.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Shattered Acolyte")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Warlock"})
        kwargs.setdefault("keywords", Keyword.LIFELINK)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Lifelink\n{1}, Sacrifice this creature: Destroy target artifact or enchantment.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any = None) -> bool:
            controller = source.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 1:
                return False
            controller.mana_pool.pay(ManaCost(generic=1))
            # Sacrifice self
            bf = game.get_battlefield(controller)
            if bf.contains(source):
                bf.remove(source)
                source.zone = Zone.GRAVEYARD
                graveyard = game.get_graveyard(controller)
                graveyard.add(source)
            return True

        def _effect(game: Any, targets: list[Any] | None = None) -> None:
            if not targets:
                return
            target = targets[0]
            from engine.game import destroy
            destroy(game, target)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}, Sacrifice this creature: Destroy target artifact or enchantment.",
        )]

    def activate_ability(self, game: "GameState", ability_index: int, targets: list[Any] | None = None) -> None:
        """Activate an ability by index, with targets."""
        abilities = self.get_activated_abilities()
        if ability_index >= len(abilities):
            raise ValueError(f"No ability at index {ability_index}")
        ability = abilities[ability_index]

        # Validate targets
        if targets:
            for t in targets:
                card_types = getattr(t, "card_types", set())
                if CardType.ARTIFACT not in card_types and CardType.ENCHANTMENT not in card_types:
                    raise ValueError(
                        f"Illegal target: {getattr(t, 'name', t)} is not an artifact or enchantment"
                    )

        # Pay cost
        if not ability.cost(game):
            raise ValueError("Cannot pay cost for ability")

        # Apply effect
        ability.effect(game, targets=targets)
