"""Card implementation for Studious First-Year // Rampant Growth."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.game import shuffle_library
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Supertype, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RampantGrowth(Sorcery):
    """Prepared spell copy for Studious First-Year."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rampant Growth")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        basics = [
            card
            for card in library.get_all()
            if CardType.LAND in getattr(card, "card_types", set())
            and Supertype.BASIC in getattr(card, "supertypes", set())
        ]
        chosen = None
        if basics:
            try:
                chosen = controller.choose_card(basics, "Choose a basic land card")
            except Exception:
                chosen = basics[0]
        if chosen in basics:
            chosen.controller = controller
            move_to_zone(game, chosen, Zone.LIBRARY, Zone.BATTLEFIELD)
            chosen.is_tapped = True
        shuffle_library(game, controller, source=self, reason="Rampant Growth")


class StudiousFirstYearRampantGrowth(Creature):
    """Studious First-Year."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Studious First-Year")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault("subtypes", {"Bear", "Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> CardImpl:
        return RampantGrowth(owner=self.owner, controller=self.controller)
