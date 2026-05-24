"""Card implementation for Krenko, Mob Boss."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from cards.registry import CardRegistry

def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True

class KrenkoMobBoss(Creature):
    """Krenko, Mob Boss — {2}{R}{R} — 3/3 — Goblin Warrior

    {T}: Create X 1/1 red Goblin creature tokens, where X is the number
    of Goblins you control.

    FDN collector number 204.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Krenko, Mob Boss")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{R}"))
        kwargs.setdefault("subtypes", {"Goblin", "Warrior"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "{T}: Create X 1/1 red Goblin creature tokens, where X is "
            "the number of Goblins you control.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            return _tap_cost(game, src)

        def _effect(game: Any) -> None:
            from benchmarks.sos.workspace.engine.game import create_token

            controller = source.controller
            if controller is None:
                return
            # Count Goblins you control
            goblin_count = 0
            bf = game.get_battlefield(controller)
            for card in bf.get_all():
                if "Goblin" in getattr(card, "subtypes", set()):
                    goblin_count += 1
            for _ in range(goblin_count):
                token = Creature(
                    name="Goblin",
                    base_power=1,
                    base_toughness=1,
                    subtypes={"Goblin"},
                )
                token.is_token = True
                create_token(game, controller, token)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}: Create X 1/1 red Goblin creature tokens, "
            "where X is the number of Goblins you control.",
        )]
