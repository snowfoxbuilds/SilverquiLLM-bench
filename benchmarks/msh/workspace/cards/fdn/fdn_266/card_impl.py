"""Card implementation for Scoured Barrens."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.events import GainsLifeTriggeredEvent
from engine.types import ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class ScouredBarrens(Land):
    """Scoured Barrens — Land.

    This land enters tapped.
    When this land enters, you gain 1 life.
    {T}: Add {W} or {B}.

    FDN collector number 266.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scoured Barrens")
        kwargs.setdefault(
            "rules_text",
            "This land enters tapped.\n"
            "When this land enters, you gain 1 life.\n"
            "{T}: Add {W} or {B}.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Enter tapped; the enters trigger has its controller gain 1 life."""
        self.is_tapped = True
        controller = self.controller or self.owner
        if controller is not None and hasattr(controller, "life"):
            controller.life += 1
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=1)
            )

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_white(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.WHITE, 1)

        def _add_black(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.BLACK, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_white,
                description="{T}: Add {W}.",
            ),
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_black,
                description="{T}: Add {B}.",
            ),
        ]
