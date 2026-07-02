"""Card implementation for Rugged Highlands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.events import GainsLifeTriggeredEvent
from engine.types import ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class RuggedHighlands(Land):
    """Rugged Highlands — Land.

    This land enters tapped.
    When this land enters, you gain 1 life.
    {T}: Add {R} or {G}.

    FDN collector number 265.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rugged Highlands")
        kwargs.setdefault(
            "rules_text",
            "This land enters tapped.\n"
            "When this land enters, you gain 1 life.\n"
            "{T}: Add {R} or {G}.",
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

        def _add_red(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 1)

        def _add_green(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.GREEN, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_red,
                description="{T}: Add {R}.",
            ),
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_green,
                description="{T}: Add {G}.",
            ),
        ]
