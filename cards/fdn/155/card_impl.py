"""Card implementation for FleetingDistraction."""

from __future__ import annotations


from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


class FleetingDistraction(Instant):
    """Fleeting Distraction — {U} — Target creature gets -1/-0 until end
    of turn. Draw a card.

    FDN collector number 155.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fleeting Distraction")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature gets -1/-0 until end of turn.\nDraw a card.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Give target creature -1/-0 until EOT; draw a card."""
        from engine.game import draw_card

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still legal; if not, spell fizzles entirely
        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        creature_ref = target

        def _apply_debuff(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.base_power -= 1
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_debuff,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)

        # Draw a card as part of the spell's effect
        controller = self.controller
        if controller is not None:
            draw_card(game, controller)


__all__ = ["FleetingDistraction"]
