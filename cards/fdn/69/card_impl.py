"""Card implementation for SeekersFolly."""

from __future__ import annotations


from engine.card import Creature, Instant, Mode, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _get_controller(card: Any) -> Any:
    """Return the controller of a card, or None."""
    return getattr(card, "controller", None)

def _get_target(card: Any) -> Any:
    """Return the first chosen target or the _resolve_target fallback."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


class SeekersFolly(Sorcery):
    """Seeker's Folly — {2}{B} — Choose one.

    - Target opponent discards two cards.
    - Creatures your opponents control get -1/-1 until end of turn.

    FDN collector number 69.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Seeker's Folly")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Target opponent discards two cards.\n"
            "• Creatures your opponents control get -1/-1 until end of turn.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Discard", description="Target opponent discards two cards."),
            Mode(name="Shrink", description="Creatures your opponents control get -1/-1 until end of turn."),
        ]

    def on_resolve(self, game: GameState) -> None:
        mode = self.chosen_mode
        if mode is None:
            return
        controller = _get_controller(self)
        if controller is None:
            return
        if mode == 0:
            from engine.game import discard
            target = _get_target(self)
            if target is not None:
                hand = game.get_hand(target)
                for _ in range(2):
                    cards = hand.get_all()
                    if cards:
                        discard(game, target, cards[0])
        elif mode == 1:
            spell_ref = self
            opponents = [p for p in game.players if p is not controller]

            def _apply_shrink(game: GameState) -> None:
                for opponent in opponents:
                    for obj in game.get_battlefield(opponent).get_all():
                        if CardType.CREATURE in getattr(obj, "card_types", set()):
                            obj.base_power -= 1
                            obj.base_toughness -= 1

            game.effect_manager.add(ContinuousEffect(
                source=spell_ref,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_shrink,
                duration=DURATION_END_OF_TURN,
            ))


__all__ = ["SeekersFolly"]
