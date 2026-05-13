"""Card implementation for RavenousAmulet."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class RavenousAmulet(Artifact):
    """Ravenous Amulet — {2} — Sacrifice creature to draw; sac self to drain."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ravenous Amulet")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault(
            "rules_text",
            "{1}, {T}, Sacrifice a creature: Draw a card and put a soul counter on "
            "this artifact. Activate only as a sorcery.\n"
            "{4}, {T}, Sacrifice this artifact: Each opponent loses life equal to "
            "the number of soul counters on this artifact.",
        )
        super().__init__(**kwargs)
        self.soul_counters: int = 0

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _sac_creature_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            # Sacrifice a creature as part of the cost
            from engine.game import sacrifice
            controller = source.controller
            if controller is not None:
                bf = game.get_battlefield(controller)
                creatures = [
                    o for o in bf.get_all()
                    if CardType.CREATURE in getattr(o, "card_types", set())
                ]
                if creatures:
                    sacrifice(game, controller, creatures[0])
            return True

        def _sac_creature_effect(game: Any) -> None:
            from engine.game import draw_card
            controller = source.controller
            if controller is not None:
                draw_card(game, controller)
                source.soul_counters += 1

        def _drain_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _drain_effect(game: Any) -> None:
            from engine.game import sacrifice
            controller = source.controller
            if controller is not None:
                # Sacrifice this artifact
                sacrifice(game, controller, source)
                for p in game.players:
                    if p is not controller:
                        p.life -= source.soul_counters

        return [
            ActivatedAbility(
                cost=_sac_creature_cost,
                effect=_sac_creature_effect,
                description="{1}, {T}, Sacrifice a creature: Draw a card and put a soul counter.",
            ),
            ActivatedAbility(
                cost=_drain_cost,
                effect=_drain_effect,
                description="{4}, {T}, Sacrifice: Each opponent loses life equal to soul counters.",
            ),
        ]


__all__ = ["RavenousAmulet"]
