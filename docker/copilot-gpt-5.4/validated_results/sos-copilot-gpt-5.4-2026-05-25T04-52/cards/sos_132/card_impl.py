"""Card implementation for Tablet of Discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Artifact, ManaAbility
from benchmarks.sos.workspace.engine.mana import instant_or_sorcery_spell_only_restriction
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TabletOfDiscovery(Artifact):
    """Tablet of Discovery."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tablet of Discovery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        top_cards = library.top(1)
        if not top_cards:
            return
        top_card = top_cards[0]
        move_to_zone(game, top_card, Zone.LIBRARY, Zone.GRAVEYARD)
        game.grant_graveyard_play_permission_until_end_of_turn(
            controller,
            top_card,
            source=self,
        )

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self
        restriction = instant_or_sorcery_spell_only_restriction()

        def _tap_cost(game: GameState, artifact: Artifact) -> bool:  # noqa: ARG001
            if artifact.is_tapped:
                return False
            artifact.is_tapped = True
            return True

        def _single_red(game: GameState) -> None:  # noqa: ARG001
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 1)

        def _double_red(game: GameState) -> None:  # noqa: ARG001
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 1, restriction=restriction)
                controller.mana_pool.add(ManaType.RED, 1, restriction=restriction)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_single_red,
                description="{T}: Add {R}.",
            ),
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_double_red,
                description="{T}: Add {R}{R}. Spend this mana only to cast instant and sorcery spells.",
            ),
        ]
