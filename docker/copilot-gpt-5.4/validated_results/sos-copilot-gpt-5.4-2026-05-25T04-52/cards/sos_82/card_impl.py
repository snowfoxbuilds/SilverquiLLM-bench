"""Card implementation for Eternal Student."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _create_inkling_token() -> Creature:
    token = Creature(
        name="Inkling",
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        base_power=1,
        base_toughness=1,
    )
    token.colors = {Color.WHITE, Color.BLACK}  # type: ignore[attr-defined]
    return token


class EternalStudent(Creature):
    """Eternal Student."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Eternal Student")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("subtypes", {"Zombie", "Warlock"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{1}{B}, Exile this card from your graveyard: Create two 1/1 white and black "
            "Inkling creature tokens with flying.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self
        activation_cost = ManaCost.parse("{1}{B}")

        def _cost(game: GameState, card: Creature) -> bool:
            owner = getattr(card, "owner", None)
            if owner is None:
                return False
            if not game.get_graveyard(owner).contains(card):
                return False
            if not owner.mana_pool.can_pay(activation_cost):
                return False
            owner.mana_pool.pay(activation_cost)
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.EXILE)
            return True

        def _effect(game: GameState) -> None:
            owner = getattr(source, "owner", None)
            if owner is None:
                return
            create_token(game, owner, _create_inkling_token())
            create_token(game, owner, _create_inkling_token())

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{1}{B}, Exile this card from your graveyard: Create two 1/1 white and "
                    "black Inkling creature tokens with flying."
                ),
            )
        ]
