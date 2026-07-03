"""Card implementation for Planar Engineering."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Land, Sorcery
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.game import sacrifice, shuffle_library
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


class PlanarEngineering(Sorcery):
    """Planar Engineering."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Planar Engineering")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        super().__init__(**kwargs)
        self._lands_to_sacrifice_on_cast: list[Land] = []

    def can_cast(self, game: GameState) -> bool:
        controller = self.controller
        if controller is None:
            return True
        lands = [
            permanent
            for permanent in game.get_battlefield(controller).get_all()
            if isinstance(permanent, Land)
        ]
        return len(lands) >= 2

    def get_additional_cast_cost(
        self,
        game: GameState,
        player: Player,
        from_zone: Zone,  # noqa: ARG002
    ) -> ManaCost:
        lands = [
            permanent
            for permanent in game.get_battlefield(player).get_all()
            if isinstance(permanent, Land)
        ]
        if len(lands) < 2:
            raise CastingError(f"Cannot cast {self.name!r} — you must sacrifice two lands")

        if len(lands) == 2:
            self._lands_to_sacrifice_on_cast = lands
            return ManaCost()

        chosen: list[Land] = []
        remaining = list(lands)
        for index in range(2):
            selection = player.choose_card(
                remaining,
                f"Choose land to sacrifice for {self.name} ({index + 1}/2)",
            )
            if selection not in remaining:
                raise CastingError(f"Cannot cast {self.name!r} — invalid land choice")
            chosen.append(selection)
            remaining.remove(selection)
        self._lands_to_sacrifice_on_cast = chosen
        return ManaCost()

    def pay_additional_cast_costs(
        self,
        game: GameState,
        player: Player,
        from_zone: Zone,  # noqa: ARG002
    ) -> None:
        for land in list(self._lands_to_sacrifice_on_cast):
            if game.get_battlefield(player).contains(land):
                sacrifice(game, player, land)
        self._lands_to_sacrifice_on_cast = []

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        basics = [
            card
            for card in library.get_all()
            if isinstance(card, Land) and Supertype.BASIC in getattr(card, "supertypes", set())
        ]

        chosen: list[Land] = []
        remaining = list(basics)
        while remaining and len(chosen) < 4:
            if len(remaining) == 4 - len(chosen):
                chosen.extend(remaining)
                break
            try:
                selection = controller.choose_card(
                    remaining,
                    f"Choose basic land for {self.name}",
                )
            except Exception:
                selection = None
            if selection not in remaining:
                selection = remaining[0]
            chosen.append(selection)
            remaining.remove(selection)

        for land in chosen:
            land.is_tapped = True
            move_to_zone(game, land, Zone.LIBRARY, Zone.BATTLEFIELD)

        shuffle_library(game, controller, source=self, reason=self.name)
