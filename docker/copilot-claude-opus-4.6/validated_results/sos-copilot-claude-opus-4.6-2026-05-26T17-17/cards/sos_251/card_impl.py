"""Card implementation for Potioner's Trove."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Artifact, ActivatedAbility, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class PotionersTrove(Artifact):
    """Potioner's Trove — {3} — Artifact.

    {T}: Add one mana of any color.
    {T}: You gain 2 life. Activate only if you've cast an instant or sorcery spell this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Potioner's Trove")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault(
            "rules_text",
            "{T}: Add one mana of any color.\n"
            "{T}: You gain 2 life. Activate only if you've cast an instant or sorcery spell this turn.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None) -> None:
            source.is_tapped = True

        def _produce(game: Any = None, src: Any = None, player: Any = None) -> None:
            pass  # In a full engine, would add mana to pool

        return [ManaAbility(
            cost=_cost,
            mana_produced=_produce,
            description="{T}: Add one mana of any color.",
            mana_types=[ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN],
            any_color=True,
        )]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None, check_only: bool = False) -> bool:
            controller = player or (source.controller if source else None)
            if controller is None:
                return False
            if not getattr(controller, "cast_instant_or_sorcery_this_turn", False):
                return False
            if source.is_tapped:
                return False
            if not check_only:
                source.is_tapped = True
            return True

        def _effect(game: Any = None, src: Any = None, player: Any = None, **kwargs: Any) -> None:
            controller = player or (source.controller if source else None)
            if controller is not None:
                controller.life += 2

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}: You gain 2 life. Activate only if you've cast an instant or sorcery spell this turn.",
        )]

