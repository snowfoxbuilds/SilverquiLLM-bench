"""Card implementation for Harmonized Trio // Brainstorm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Brainstorm(Instant):
    """Prepared spell copy for Harmonized Trio."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Brainstorm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class HarmonizedTrioBrainstorm(Creature):
    """Harmonized Trio."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Harmonized Trio")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Bard", "Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, card: Creature) -> bool:
            if getattr(card, "is_tapped", False):
                return False
            controller = source.controller
            if controller is None:
                return False
            allies = [
                permanent
                for permanent in game.get_battlefield(controller).get_all()
                if permanent is not source
                and isinstance(permanent, Creature)
                and not getattr(permanent, "is_tapped", False)
            ]
            if len(allies) < 2:
                return False

            chosen_allies: list[Creature] = []
            for index in range(2):
                remaining = [permanent for permanent in allies if permanent not in chosen_allies]
                if not remaining:
                    return False
                try:
                    chosen = controller.choose_card(
                        remaining,
                        f"untapped creature to tap ({index + 1}/2)",
                    )
                except Exception:
                    chosen = remaining[0]
                if chosen not in remaining:
                    chosen = remaining[0]
                chosen_allies.append(chosen)

            source.is_tapped = True
            for ally in chosen_allies:
                ally.is_tapped = True
            return True

        def _effect(game: GameState) -> None:  # noqa: ARG001
            source.become_prepared()

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{T}, Tap two untapped creatures you control: This creature becomes prepared.",
            )
        ]

    def create_prepared_spell_copy(self) -> Instant:
        return Brainstorm(owner=self.owner, controller=self.controller)
