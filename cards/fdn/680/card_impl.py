"""Card implementation for SoulGuideLantern."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class SoulGuideLantern(Artifact):
    """Soul-Guide Lantern — {1} — ETB: exile target card from graveyard.
    Sac: exile opponents' graveyards. Or sac to draw."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Soul-Guide Lantern")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "When this artifact enters, exile target card from a graveyard.\n"
            "{T}, Sacrifice this artifact: Exile each opponent's graveyard.\n"
            "{1}, {T}, Sacrifice this artifact: Draw a card.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _exile_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _exile_effect(game: Any) -> None:
            from engine.types import Zone
            from engine.zones import move_to_zone
            from engine.game import sacrifice
            controller = source.controller
            if controller is not None:
                # Sacrifice the Lantern as part of activation
                sacrifice(game, controller, source)
                for p in game.players:
                    if p is not controller:
                        gy = p.zones[Zone.GRAVEYARD]
                        for card in list(gy.get_all()):
                            move_to_zone(game, card, Zone.GRAVEYARD, Zone.EXILE)

        def _draw_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _draw_effect(game: Any) -> None:
            from engine.game import draw_card, sacrifice
            controller = source.controller
            if controller is not None:
                # Sacrifice the Lantern as part of activation
                sacrifice(game, controller, source)
                draw_card(game, controller)

        return [
            ActivatedAbility(
                cost=_exile_cost, effect=_exile_effect,
                description="{T}, Sacrifice: Exile each opponent's graveyard.",
            ),
            ActivatedAbility(
                cost=_draw_cost, effect=_draw_effect,
                description="{1}, {T}, Sacrifice: Draw a card.",
            ),
        ]


__all__ = ["SoulGuideLantern"]
