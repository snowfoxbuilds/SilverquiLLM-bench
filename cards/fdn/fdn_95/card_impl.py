"""Card implementation for Sower of Chaos."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from cards.registry import CardRegistry

class SowerOfChaos(Creature):
    """Sower of Chaos — {3}{R} — 4/3 — Devil

    {2}{R}: Target creature can't block this turn.

    FDN collector number 95.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sower of Chaos")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("subtypes", {"Devil"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "{2}{R}: Target creature can't block this turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 3:
                return False
            # Need at least 1 red
            if controller.mana_pool.get(ManaType.RED) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{2}{R}"))
            return True

        def _effect(game: Any) -> None:
            target = getattr(source, "_current_target", None)
            if target is not None:
                target._cant_block = True

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{2}{R}: Target creature can't block this turn.",
        )]
