"""Card implementation for Hydro-Channeler."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, ManaAbility
from benchmarks.sos.workspace.engine.mana import instant_or_sorcery_spell_only_restriction
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class HydroChanneler(Creature):
    """Hydro-Channeler."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hydro-Channeler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self
        restriction = instant_or_sorcery_spell_only_restriction()

        def _tap_cost(game: GameState, card: Creature) -> bool:  # noqa: ARG001
            if getattr(card, "is_tapped", False):
                return False
            card.is_tapped = True
            return True

        def _blue_mana(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.BLUE, 1, restriction=restriction)

        def _paid_tap_cost(game: GameState, card: Creature) -> bool:
            controller = source.controller
            if controller is None or getattr(card, "is_tapped", False):
                return False
            if not controller.mana_pool.can_pay(ManaCost(generic=1)):
                return False
            controller.mana_pool.pay(ManaCost(generic=1))
            card.is_tapped = True
            return True

        def _chosen_color_mana(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            chosen = controller.choose(
                [
                    ManaType.WHITE,
                    ManaType.BLUE,
                    ManaType.BLACK,
                    ManaType.RED,
                    ManaType.GREEN,
                ],
                "Choose a color of mana to produce",
            )
            controller.mana_pool.add(chosen, 1, restriction=restriction)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_blue_mana,
                description="{T}: Add {U}. Spend this mana only to cast an instant or sorcery spell.",
            ),
            ManaAbility(
                cost=_paid_tap_cost,
                mana_produced=_chosen_color_mana,
                description="{1}, {T}: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]
