"""Card implementation for Group Project."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.types import Color, ManaCost, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class GroupProject(Sorcery):
    """Group Project."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Group Project")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Create a 2/2 red and white Spirit creature token.\n"
            "Flashback—Tap three untapped creatures you control.",
        )
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost()
        self._flashback_tap_creatures: list[Creature] = []

    def _get_flashback_creatures(self, game: GameState) -> list[Creature]:
        controller = self.controller
        if controller is None:
            return []
        return [
            permanent
            for permanent in game.get_battlefield(controller).get_all()
            if isinstance(permanent, Creature)
            and getattr(permanent, "controller", None) is controller
            and not permanent.is_tapped
        ]

    def _choose_flashback_creatures(self, game: GameState, available: list[Creature]) -> list[Creature]:
        controller = self.controller
        if controller is None:
            return []
        if len(available) <= 3:
            return list(available)
        chosen: list[Creature] = []
        remaining = list(available)
        for index in range(3):
            selection = controller.choose_card(
                remaining,
                f"Choose untapped creature to tap for Group Project flashback ({index + 1}/3)",
            )
            if not isinstance(selection, Creature) or selection not in remaining:
                return []
            chosen.append(selection)
            remaining.remove(selection)
        return chosen

    def can_cast(self, game: GameState) -> bool:
        controller = self.controller
        if controller is None:
            return True
        if not game.get_graveyard(controller).contains(self):
            return True
        available = self._get_flashback_creatures(game)
        if len(available) < 3:
            self._flashback_tap_creatures = []
            return False
        self._flashback_tap_creatures = self._choose_flashback_creatures(game, available)
        return len(self._flashback_tap_creatures) == 3

    def on_cast(self, game: GameState) -> None:
        if getattr(self, "cast_from_zone", None) != Zone.GRAVEYARD:
            return
        chosen = self._flashback_tap_creatures
        if len(chosen) < 3:
            chosen = self._choose_flashback_creatures(game, self._get_flashback_creatures(game))
        if len(chosen) < 3:
            return
        for creature in chosen:
            creature.is_tapped = True
        self._flashback_tap_creatures = []

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        token = Creature(
            name="Spirit",
            base_power=2,
            base_toughness=2,
            subtypes={"Spirit"},
            owner=controller,
            controller=controller,
        )
        token.colors = {Color.RED, Color.WHITE}
        create_token(game, controller, token)
