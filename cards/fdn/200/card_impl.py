"""Card implementation for Goblin Surprise."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import (
    ContinuousEffect,
    Creature,
    Instant,
    Mode,
)
from engine.continuous_effects import Layer, SubLayer
from engine.game import create_token
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState




def _get_controller(card: Any) -> Any:
    """Return the controller of a card, or None."""
    return getattr(card, "controller", None)
class GoblinSurprise(Instant):
    """Goblin Surprise — {2}{R} — Choose one.

    - Creatures you control get +2/+0 until end of turn.
    - Create two 1/1 red Goblin creature tokens.

    FDN collector number 200.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Surprise")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Creatures you control get +2/+0 until end of turn.\n"
            "• Create two 1/1 red Goblin creature tokens.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Pump", description="Creatures you control get +2/+0 until end of turn."),
            Mode(name="Tokens", description="Create two 1/1 red Goblin creature tokens."),
        ]

    def on_resolve(self, game: GameState) -> None:
        mode = self.chosen_mode
        if mode is None:
            return
        controller = _get_controller(self)
        if controller is None:
            return
        if mode == 0:
            spell_ref = self
            controller_ref = controller

            def _apply_pump(game: GameState) -> None:
                for obj in game.get_battlefield(controller_ref).get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        obj.base_power += 2

            game.effect_manager.add(ContinuousEffect(
                source=spell_ref,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_pump,
                duration=DURATION_END_OF_TURN,
            ))
        elif mode == 1:
            from engine.game import create_token
            for _ in range(2):
                token = Creature(
                    name="Goblin",
                    base_power=1,
                    base_toughness=1,
                    subtypes={"Goblin"},
                )
                token.is_token = True
                create_token(game, controller, token)
