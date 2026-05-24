"""Card implementation for Twinflame Tyrant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TwinflameTyrant(Creature):
    """Twinflame Tyrant — {3}{R}{R} — 3/5 — Dragon — Flying.

    If a source you control would deal damage to an opponent or a permanent
    an opponent controls, it deals double that damage instead.

    FDN collector number 97.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Twinflame Tyrant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{R}"))
        kwargs.setdefault("subtypes", {"Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying\nIf a source you control would deal damage to an "
            "opponent or a permanent an opponent controls, it deals double "
            "that damage instead.",
        )
        super().__init__(**kwargs)

    def apply_continuous_effect(self, game: "GameState") -> None:
        """Register damage-doubling replacement effect.

        Sets the ``_double_damage_to_opponents`` flag on the controller
        (via a continuous effect) and monkey-patches ``deal_damage`` so
        that any source controlled by the Tyrant's controller deals
        double damage to opponents and their permanents.
        """
        from benchmarks.sos.workspace.engine import game as game_module

        source = self
        _original_deal_damage = game_module.deal_damage

        def _patched_deal_damage(
            g: Any, src: Any, target: Any, amount: int
        ) -> None:
            ctrl = getattr(source, "controller", None)
            src_ctrl = getattr(src, "controller", None)
            if ctrl is not None and src_ctrl is ctrl and amount > 0:
                # Check if target is an opponent or an opponent's permanent
                target_ctrl = getattr(target, "controller", None)
                is_opponent_player = hasattr(target, "life") and target is not ctrl
                is_opponent_permanent = (
                    target_ctrl is not None and target_ctrl is not ctrl
                )
                if is_opponent_player or is_opponent_permanent:
                    amount *= 2
            _original_deal_damage(g, src, target, amount)

        def _apply(game_state: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is not None:
                ctrl._double_damage_to_opponents = True
                # Install the patched deal_damage if not already installed
                if game_module.deal_damage is not _patched_deal_damage:
                    game_module.deal_damage = _patched_deal_damage

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        ))

    def unregister_triggers(self, game: "GameState") -> None:
        """Clean up player attribute on leaving battlefield."""
        controller = getattr(self, "controller", None)
        if controller is not None:
            if hasattr(controller, "_double_damage_to_opponents"):
                del controller._double_damage_to_opponents
