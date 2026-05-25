"""Card implementation for Bushwhack."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature, Instant, Mode, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from benchmarks.sos.workspace.cards.registry import CardRegistry

def _get_controller(card: Any) -> Any:
    """Return the controller of a card, or None."""
    return getattr(card, "controller", None)
def _get_target(card: Any) -> Any:
    """Return the first chosen target or the _resolve_target fallback."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)
def _get_targets(card: Any) -> list[Any]:
    """Return chosen targets list."""
    return getattr(card, "chosen_targets", []) or []

class Bushwhack(Sorcery):
    """Bushwhack — {G} — Choose one.

    - Search your library for a basic land card, reveal it, put it into
      your hand, then shuffle.
    - Target creature you control fights target creature you don't control.

    FDN collector number 215.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bushwhack")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Search your library for a basic land card, reveal it, put it into your hand, then shuffle.\n"
            "• Target creature you control fights target creature you don't control.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Land Search", description="Search your library for a basic land card, reveal it, put it into your hand, then shuffle."),
            Mode(name="Fight", description="Target creature you control fights target creature you don't control."),
        ]

    def on_resolve(self, game: GameState) -> None:
        mode = self.chosen_mode
        if mode is None:
            return
        controller = _get_controller(self)
        if controller is None:
            return
        if mode == 0:
            # Search library for a basic land.
            from benchmarks.sos.workspace.engine.types import Supertype
            library = controller.zones[Zone.LIBRARY]
            found = False
            for card in library.get_all():
                if (CardType.LAND in getattr(card, "card_types", set())
                        and Supertype.BASIC in getattr(card, "supertypes", set())):
                    library.remove(card)
                    controller.zones[Zone.HAND].add(card)
                    found = True
                    break
            library.shuffle()
        elif mode == 1:
            # Fight
            from benchmarks.sos.workspace.engine.game import deal_damage
            targets = _get_targets(self)
            if len(targets) >= 2:
                a, b = targets[0], targets[1]
                deal_damage(game, a, b, getattr(a, "power", 0))
                deal_damage(game, b, a, getattr(b, "power", 0))
