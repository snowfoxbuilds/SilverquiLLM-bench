"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility, ActivatedAbility
from engine.types import CardType, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color (instant/sorcery only).
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature. Still a land.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        super().__init__(**kwargs)
        self.base_power: int = 0
        self.base_toughness: int = 0

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _colorless_cost(game: Any = None, src: Any = None, player: Any = None) -> None:
            source.is_tapped = True

        def _colorless_produce(game: Any = None, src: Any = None, player: Any = None) -> None:
            pass

        def _any_color_cost(game: Any = None, src: Any = None, player: Any = None) -> None:
            source.is_tapped = True
            if player is not None:
                player.life -= 1

        def _any_color_produce(game: Any = None, src: Any = None, player: Any = None) -> None:
            pass

        return [
            ManaAbility(
                cost=_colorless_cost,
                mana_produced=_colorless_produce,
                description="{T}: Add {C}.",
                mana_types=[ManaType.COLORLESS],
            ),
            ManaAbility(
                cost=_any_color_cost,
                mana_produced=_any_color_produce,
                description="{T}, Pay 1 life: Add one mana of any color.",
                mana_types=[ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN],
                any_color=True,
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None, check_only: bool = False) -> bool:
            return True

        def _effect(game: Any = None, src: Any = None, player: Any = None, **kwargs: Any) -> None:
            if CardType.CREATURE in source.card_types:
                return
            source.card_types.add(CardType.CREATURE)
            source.subtypes.add("Wizard")
            source.base_power = 2
            source.base_toughness = 4

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{5}: Becomes a 2/4 Wizard creature. Still a land.",
        )]
