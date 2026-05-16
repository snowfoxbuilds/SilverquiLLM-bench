"""Card implementation for Heroic Reinforcements."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Creature, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class HeroicReinforcements(Sorcery):
    """Heroic Reinforcements — {2}{R}{W} — Sorcery.

    Create two 1/1 white Soldier creature tokens. Until end of turn,
    creatures you control get +1/+1 and gain haste.

    FDN collector number 241.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Heroic Reinforcements")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Create two 1/1 white Soldier creature tokens. Until end of "
            "turn, creatures you control get +1/+1 and gain haste.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Create 2 Soldier tokens, then pump and grant haste."""
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Create two 1/1 white Soldier tokens
        for _ in range(2):
            token = Creature(
                name="Soldier",
                base_power=1,
                base_toughness=1,
                subtypes={"Soldier"},
            )
            token.is_token = True
            create_token(game, controller, token)

        # +1/+1 until end of turn
        def _apply_pt(game: Any) -> None:
            bf = game.get_battlefield(controller)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.modified_power += 1
                    obj.modified_toughness += 1

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_pt,
            duration=DURATION_END_OF_TURN,
        ))

        # Haste until end of turn
        def _apply_haste(game: Any) -> None:
            bf = game.get_battlefield(controller)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.keywords = obj.keywords | Keyword.HASTE

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_haste,
            duration=DURATION_END_OF_TURN,
        ))
