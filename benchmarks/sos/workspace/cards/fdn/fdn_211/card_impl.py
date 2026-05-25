"""Card implementation for Affectionate Indrik."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class AffectionateIndrik(Creature):
    """Affectionate Indrik — {5}{G} — 4/4 — Beast.

    When this creature enters, you may have it fight target creature
    you don't control.

    FDN collector number 211.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Affectionate Indrik")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{G}"))
        kwargs.setdefault("subtypes", {"Beast"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, you may have it fight target "
            "creature you don't control.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: fight target creature you don't control."""
        from engine.game import deal_damage

        controller = self.controller
        if controller is None:
            return

        # Find a target creature an opponent controls
        targets: list[Any] = []
        for player in game.players:
            if player is controller:
                continue
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)

        if not targets:
            return

        try:
            target = controller.choose(targets, "creature to fight")
        except Exception:
            target = targets[0]

        if target is None:
            return

        # Fight: each deals damage equal to its power to the other
        my_power = self.power
        their_power = getattr(target, "power", getattr(target, "base_power", 0))

        if my_power > 0:
            deal_damage(game, self, target, my_power)
        if their_power > 0:
            deal_damage(game, target, self, their_power)
