"""Card implementation for Shattered Acolyte."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.game import destroy, sacrifice
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _get_current_target(card: Any) -> Any:
    chosen_targets = getattr(card, "chosen_targets", None)
    if chosen_targets:
        return chosen_targets[0]
    return getattr(card, "_current_target", None)


class ShatteredAcolyte(Creature):
    """Shattered Acolyte."""

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

        def _cost(game: GameState, permanent: Creature) -> bool:
            controller = getattr(permanent, "controller", None)
            if controller is None:
                return False
            activation_cost = ManaCost.parse("{1}")
            if not controller.mana_pool.can_pay(activation_cost):
                return False
            controller.mana_pool.pay(activation_cost)
            sacrifice(game, controller, permanent)
            return True

        def _effect(game: GameState) -> None:
            target = _get_current_target(source)
            if target is None:
                return
            if not any(
                game.get_battlefield(player).contains(target)
                for player in game.players
            ):
                return
            if not getattr(target, "card_types", set()) & {CardType.ARTIFACT, CardType.ENCHANTMENT}:
                return
            destroy(game, target)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{1}, Sacrifice this creature: Destroy target artifact or enchantment.",
            )
        ]
