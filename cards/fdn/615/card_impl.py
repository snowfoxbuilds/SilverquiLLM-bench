"""Card implementation for VampiricRites."""

from __future__ import annotations


from dataclasses import dataclass
from engine.card import ActivatedAbility, Creature, Enchantment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class VampiricRites(Enchantment):
    """Vampiric Rites — {B} — {1}{B}, Sacrifice a creature: Gain 1 life, draw.

    FDN collector number 615.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vampiric Rites")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault(
            "rules_text",
            "{1}{B}, Sacrifice a creature: You gain 1 life and draw a card.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState) -> bool:
            controller = source.controller
            if controller is None:
                return False
            # Check mana availability (simplified) and a creature to sacrifice
            bf = game.get_battlefield(controller)
            has_creature = any(
                CardType.CREATURE in getattr(obj, "card_types", set())
                for obj in bf.get_all()
            )
            return has_creature

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            # ENGINE LIMITATION: Full implementation would let the player
            # choose which creature to sacrifice and pay {1}{B}.  For now
            # we sacrifice the first creature found.
            from engine.game import draw_card, sacrifice
            bf = game.get_battlefield(controller)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    sacrifice(game, controller, obj)
                    break
            controller.life += 1
            from engine.triggers import EventType
            game.trigger_manager.fire_event(
                game,
                EventType.GAINS_LIFE,
                {"player": controller, "amount": 1},
            )
            draw_card(game, controller)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{1}{B}, Sacrifice a creature: You gain 1 life "
                            "and draw a card.",
            ),
        ]


__all__ = ["VampiricRites"]
