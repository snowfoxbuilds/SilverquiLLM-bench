"""Card implementation for Fields of Strife."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility, ActivatedAbility
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class FieldsOfStrife(Land):
    """Fields of Strife — Land.

    This land enters tapped.
    {T}: Add {R} or {W}.
    {2}{R}{W}, {T}: Surveil 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fields of Strife")
        kwargs.setdefault(
            "rules_text",
            "This land enters tapped.\n{T}: Add {R} or {W}.\n{2}{R}{W}, {T}: Surveil 1.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None) -> None:
            source.is_tapped = True

        def _produce(game: Any = None, src: Any = None, player: Any = None) -> None:
            pass

        return [ManaAbility(
            cost=_cost,
            mana_produced=_produce,
            description="{T}: Add {R} or {W}.",
            mana_types=[ManaType.RED, ManaType.WHITE],
        )]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None, check_only: bool = False) -> bool:
            if source.is_tapped:
                return False
            if not check_only:
                source.is_tapped = True
            return True

        def _effect(game: Any = None, src: Any = None, player: Any = None, surveil_choice: str = "library", **kwargs: Any) -> None:
            """Surveil 1: look at top card, may put into graveyard."""
            controller = player or (source.controller if source else None)
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            all_cards = library.get_all()
            if not all_cards:
                return
            top_card = all_cards[-1]  # last card is top
            if surveil_choice == "graveyard":
                library.remove(top_card)
                controller.zones[Zone.GRAVEYARD].add(top_card)
            # else keep on top (do nothing)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{2}{R}{W}, {T}: Surveil 1.",
        )]

    def on_enter_battlefield(self, game: Any) -> None:
        """This land always enters tapped."""
        self.is_tapped = True

