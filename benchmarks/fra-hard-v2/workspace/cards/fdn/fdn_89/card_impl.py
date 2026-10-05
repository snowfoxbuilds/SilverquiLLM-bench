"""Card implementation for Gorehorn Raider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class GorehornRaiderAbility1:
    text = 'Raid — When this creature enters, if you attacked this turn, this creature deals 2 damage to any target.'


# endregion Printed abilities


class GorehornRaider(Creature):
    """Gorehorn Raider — {4}{R} — 4/4 — Minotaur Pirate.

    Raid — When this creature enters, if you attacked this turn, this
    creature deals 2 damage to any target.

    FDN collector number 89.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gorehorn Raider")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault("subtypes", {"Minotaur", "Pirate"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Raid — When this creature enters, if you attacked this turn, "
            "this creature deals 2 damage to any target.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Raid — an enters trigger with an intervening "if" (rule 603.4) that
        targets as it is put on the stack (rule 603.3d)."""
        from engine.triggers import register_enters_trigger

        def _raided(game: "GameState", controller: Any) -> bool:
            return bool(getattr(controller, "attacked_this_turn", False))

        def _any_target(game: "GameState", controller: Any) -> list[Any]:
            def _legal(obj: Any) -> bool:
                if any(obj is p for p in game.players):
                    return True
                types = getattr(obj, "card_types", set())
                return CardType.CREATURE in types or CardType.PLANESWALKER in types

            return [TargetRequirement(filter_fn=_legal, description="any target", zone=Zone.BATTLEFIELD)]

        register_enters_trigger(
            game, self, GorehornRaiderAbility1, self._enters, targets=_any_target, condition=_raided
        )

    def _enters(self, game: "GameState", targets: list[Any], controller: Any) -> None:
        """Deal 2 damage to the target, if it is still legal."""
        from engine.game import deal_damage

        if targets and targets[0] is not None:
            deal_damage(game, self, targets[0], 2)
