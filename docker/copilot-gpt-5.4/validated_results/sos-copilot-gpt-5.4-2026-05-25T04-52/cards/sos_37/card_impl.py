"""Card implementation for Summoned Dromedary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.casting import is_sorcery_speed
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class SummonedDromedary(Creature):
    """Summoned Dromedary."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Summoned Dromedary")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Spirit", "Camel"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Vigilance\n{1}{W}: Return this card from your graveyard to your hand. "
            "Activate only as a sorcery.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self
        activation_cost = ManaCost.parse("{1}{W}")

        def _cost(game: GameState, card: Creature) -> bool:
            owner = getattr(card, "owner", None)
            if owner is None:
                return False
            if not is_sorcery_speed(game, owner):
                return False
            if not game.get_graveyard(owner).contains(card):
                return False
            if not owner.mana_pool.can_pay(activation_cost):
                return False
            owner.mana_pool.pay(activation_cost)
            return True

        def _effect(game: GameState) -> None:
            owner = getattr(source, "owner", None)
            if owner is None or not game.get_graveyard(owner).contains(source):
                return
            move_to_zone(game, source, Zone.GRAVEYARD, Zone.HAND)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{1}{W}: Return this card from your graveyard to your hand.",
            )
        ]
