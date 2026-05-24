"""Card implementation for Heartfire Immolator."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from benchmarks.sos.workspace.cards.registry import CardRegistry

class HeartfireImmolator(Creature):
    """Heartfire Immolator — {1}{R} — 2/2 — Human Wizard

    Prowess
    {R}, Sacrifice this creature: It deals damage equal to its power to
    target creature or planeswalker.

    FDN collector number 201.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Heartfire Immolator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("keywords", Keyword.PROWESS)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Prowess\n{R}, Sacrifice this creature: It deals damage equal "
            "to its power to target creature or planeswalker.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            # Pay {R}
            if controller.mana_pool.get(ManaType.RED) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{R}"))
            # Snapshot power before sacrifice (last known information)
            src._snapshot_power = getattr(src, "power", src.modified_power)
            # Sacrifice self
            from benchmarks.sos.workspace.engine.game import sacrifice
            sacrifice(game, controller, src)
            return True

        def _effect(game: Any) -> None:
            from benchmarks.sos.workspace.engine.game import deal_damage

            target = getattr(source, "_current_target", None)
            if target is None:
                return
            # Use last-known power (snapshotted during cost payment)
            dmg = getattr(source, "_snapshot_power", source.modified_power)
            deal_damage(game, source, target, dmg)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{R}, Sacrifice this creature: It deals damage "
            "equal to its power to target creature or planeswalker.",
        )]
