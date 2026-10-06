"""Card implementation for Involuntary Employment."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    set_controller,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class InvoluntaryEmploymentAbility1:
    text = 'Gain control of target creature until end of turn. Untap that creature. It gains haste until end of turn. Create a Treasure token. (It\'s an artifact with "{T}, Sacrifice this token: Add one mana of any color.")'


# endregion Printed abilities


class InvoluntaryEmployment(Sorcery):
    """Involuntary Employment — {3}{R} — Sorcery.

    Gain control of target creature until end of turn. Untap that creature.
    It gains haste until end of turn. Create a Treasure token.

    FDN collector number 203.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Involuntary Employment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Gain control of target creature until end of turn. Untap that "
            "creature. It gains haste until end of turn. Create a Treasure "
            "token.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Target creature."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Gain control, untap, grant haste, create Treasure."""
        from engine.game import create_token

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        # Verify still valid
        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        controller = self.controller
        creature_ref = target

        # Gain control until end of turn: the effect manager restores the
        # previous controller once the effect is gone.
        def _apply_control(game: Any) -> None:
            set_controller(creature_ref, controller)

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.CONTROL,
            sublayer=None,
            bound_to=[creature_ref],
            apply=_apply_control,
            duration=DURATION_END_OF_TURN,
            controls=lambda: creature_ref,
        ))

        # Apply the control change immediately so subsequent code in
        # this resolution sees the correct controller.
        game.effect_manager.apply_all(game)

        # Untap
        target.is_tapped = False

        # Grant haste until end of turn
        def _apply_haste(game: Any) -> None:
            current = getattr(creature_ref, "keywords", Keyword(0))
            creature_ref.keywords = current | Keyword.HASTE

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            bound_to=[creature_ref],
            apply=_apply_haste,
            duration=DURATION_END_OF_TURN,
        ))

        # Create a Treasure token
        if controller is not None:
            from cards.fdn.tokens import make_treasure_token
            create_token(game, controller, make_treasure_token())
