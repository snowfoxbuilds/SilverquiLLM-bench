"""Card implementation for Sundering Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.game import exile
from benchmarks.sos.workspace.engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class SunderingArchaic(Creature):
    """Sundering Archaic."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sundering Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Converge — When this creature enters, exile target nonland permanent an "
            "opponent controls with mana value less than or equal to the number of "
            "colors of mana spent to cast this creature.\n"
            "{2}: Put target card from a graveyard on the bottom of its owner's library.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0] if getattr(self, "chosen_targets", None) else None
        if target is None:
            return

        controller = getattr(target, "controller", None)
        if controller is None or controller is self.controller:
            return
        if not game.get_battlefield(controller).contains(target):
            return
        if CardType.LAND in getattr(target, "card_types", set()):
            return

        colors_spent = len(set(getattr(self, "colors_spent", [])))
        mana_value = getattr(getattr(target, "mana_cost", None), "cmc", 0)
        if mana_value > colors_spent:
            return

        exile(game, target)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if not controller.mana_pool.can_pay(ManaCost.parse("{2}")):
                return False
            controller.mana_pool.pay(ManaCost.parse("{2}"))
            return True

        def _effect(game: GameState) -> None:
            target = getattr(source, "_current_target", None)
            if target is None:
                return
            owner = getattr(target, "owner", None)
            if owner is None:
                return
            graveyard = game.get_graveyard(owner)
            if not graveyard.contains(target):
                return
            graveyard.remove(target)
            game.get_library(owner).add(target, position="bottom")

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{2}: Put target card from a graveyard on the bottom of its owner's library.",
            )
        ]
