"""Card implementation for Seeker's Folly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Mode, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SeekersFolly(Sorcery):
    """Seeker's Folly — {2}{B} — Sorcery.

    Choose one —
    • Target opponent discards two cards.
    • Creatures your opponents control get -1/-1 until end of turn.

    FDN collector number 69.

    Modal spell (Pattern 5 + Pattern 1): the mode is chosen in ``get_targets``
    (so the correct target requirement is returned) and stored on ``chosen_mode``
    for ``on_resolve``. Mode 0 targets an opponent (a player); mode 1 is a
    non-targeted board effect.
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
            Mode(
                name="Shrink",
                description="Creatures your opponents control get -1/-1 until end of turn.",
            ),
        ]

    def _is_opponent(self, game: "GameState", obj: Any) -> bool:
        """Legal target: a player in the game other than the caster."""
        controller = self.controller or getattr(self, "owner", None)
        return obj is not controller and any(obj is p for p in game.players)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Choose the mode; return a target requirement only for mode 0."""
        from engine.card_queries import choose_mode

        controller = self.controller or getattr(self, "owner", None)
        modes = self.get_modes()
        chosen_name = choose_mode(
            game,
            controller,
            [m.name for m in modes],
            "Choose one",
            source_card=self,
        )
        self.chosen_mode = next(
            i for i, m in enumerate(modes) if m.name == chosen_name
        )

        if self.chosen_mode == 0:
            return [
                TargetRequirement(
                    filter_fn=lambda obj: self._is_opponent(game, obj),
                    description="target opponent",
                    zone=Zone.BATTLEFIELD,
                )
            ]
        return []

    def on_resolve(self, game: "GameState") -> None:
        mode = self.chosen_mode
        controller = self.controller or getattr(self, "owner", None)
        if mode is None or controller is None:
            return

        if mode == 0:
            from engine.game import discard

            chosen = getattr(self, "chosen_targets", None) or []
            target = chosen[0] if chosen else None
            if target is None:
                return
            # Revalidate the full target predicate at resolution (rule 608.2b):
            # the target must still be an opponent in the game.
            if not self._is_opponent(game, target):
                return
            hand = game.get_hand(target)
            for _ in range(2):
                cards = hand.get_all()
                if not cards:
                    break
                discard(game, target, cards[0])
        elif mode == 1:
            opponents = [p for p in game.players if p is not controller]

            def _apply_shrink(game: "GameState") -> None:
                for opponent in opponents:
                    for obj in game.get_battlefield(opponent).get_all():
                        if CardType.CREATURE in getattr(obj, "card_types", set()):
                            obj.modified_power -= 1
                            obj.modified_toughness -= 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_shrink,
                    duration=DURATION_END_OF_TURN,
                )
            )
