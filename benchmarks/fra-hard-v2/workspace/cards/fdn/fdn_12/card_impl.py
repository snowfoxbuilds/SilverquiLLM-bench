"""Card implementation for Felidar Savior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class FelidarSaviorAbility1:
    text = 'Lifelink (Damage dealt by this creature also causes you to gain that much life.)'


class FelidarSaviorAbility2:
    text = 'When this creature enters, put a +1/+1 counter on each of up to two other target creatures you control.'


# endregion Printed abilities


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class FelidarSavior(Creature):
    """Felidar Savior — {3}{W} — 2/3 — Cat Beast — Lifelink.

    When this creature enters, put a +1/+1 counter on each of up to two
    other target creatures you control.

    FDN collector number 12.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Felidar Savior")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Beast"})
        kwargs.setdefault("keywords", Keyword.LIFELINK)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Lifelink\nWhen this creature enters, put a +1/+1 counter on "
            "each of up to two other target creatures you control.",
        )
        super().__init__(**kwargs)

    def _enters_targets(self, game: "GameState", controller: Any) -> list[Any]:
        """Return targeting requirement: up to two other creatures you control."""
        controller = self.controller or getattr(self, "owner", None)
        source = self

        def _filter(obj: Any) -> bool:
            if obj is source:
                return False
            if CardType.CREATURE not in getattr(obj, "card_types", set()):
                return False
            return getattr(obj, "controller", None) is controller

        # "Up to two" → two optional requirements; the engine picks distinct
        # creatures (rule 601.2c) and the ETB stays castable with fewer than two
        # (or zero) other creatures you control.
        return [
            TargetRequirement(
                filter_fn=_filter,
                description="first of up to two other target creatures you control",
                zone=Zone.BATTLEFIELD,
                optional=True,
            ),
            TargetRequirement(
                filter_fn=_filter,
                description="second of up to two other target creatures you control",
                zone=Zone.BATTLEFIELD,
                optional=True,
            ),
        ]

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that uses the stack."""
        from engine.triggers import register_enters_trigger

        register_enters_trigger(game, self, FelidarSaviorAbility2, self._enters, targets=self._enters_targets)

    def _enters(self, game: "GameState", targets: list[Any], controller: Any) -> None:
        """ETB: put a +1/+1 counter on each of up to two other target
        creatures you control."""
        from engine.game import add_counter

        if controller is None:
            return

        chosen = targets
        if not chosen:
            return

        for target in chosen[:2]:
            if target is self:
                continue
            if not _is_on_battlefield(game, target):
                continue
            if getattr(target, "controller", None) is not controller:
                continue
            add_counter(game, target, "+1/+1", 1)
            # Sync original counters
