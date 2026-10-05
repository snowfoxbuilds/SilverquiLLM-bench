"""Card implementation for Affectionate Indrik."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class AffectionateIndrikAbility1:
    text = "When this creature enters, you may have it fight target creature you don't control. (Each deals damage equal to its power to the other.)"


# endregion Printed abilities


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

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that targets as it is put
        on the stack (rule 603.3d)."""
        from engine.triggers import register_enters_trigger

        def _creature_you_dont_control(game: Any, controller: Any) -> list[Any]:
            def _legal(obj: Any) -> bool:
                return CardType.CREATURE in getattr(obj, "card_types", set()) and getattr(obj, "controller", None) is not controller

            return [TargetRequirement(filter_fn=_legal, description="target creature you don't control", zone=Zone.BATTLEFIELD)]

        register_enters_trigger(game, self, AffectionateIndrikAbility1, self._enters, targets=_creature_you_dont_control)

    def _enters(self, game: "GameState", targets: list[Any], controller: Any) -> None:
        """This creature fights the target, if it is still legal: each deals
        damage equal to its power to the other."""
        from engine.game import deal_damage

        target = targets[0] if targets else None
        if target is None or getattr(target, "controller", None) is controller:
            return
        my_power = self.power
        their_power = getattr(target, "power", getattr(target, "base_power", 0))
        if my_power > 0:
            deal_damage(game, self, target, my_power)
        if their_power > 0:
            deal_damage(game, target, self, their_power)
