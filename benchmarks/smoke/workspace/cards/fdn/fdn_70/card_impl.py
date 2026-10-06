"""Card implementation for Soul-Shackled Zombie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SoulShackledZombieAbility1:
    text = 'When this creature enters, exile up to two target cards from a single graveyard. If at least one creature card was exiled this way, each opponent loses 2 life and you gain 2 life.'


# endregion Printed abilities


class SoulShackledZombie(Creature):
    """Soul-Shackled Zombie — {3}{B} — 4/2 — Zombie.

    When this creature enters, exile up to two target cards from a single
    graveyard. If at least one creature card was exiled this way, each
    opponent loses 2 life and you gain 2 life.

    FDN collector number 70.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Soul-Shackled Zombie")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("subtypes", {"Zombie"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, exile up to two target cards from a "
            "single graveyard. If at least one creature card was exiled this "
            "way, each opponent loses 2 life and you gain 2 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that targets as it is put
        on the stack (rule 603.3d)."""
        from engine.triggers import register_enters_trigger

        def _up_to_two_from_one_graveyard(game: Any, controller: Any) -> list[Any]:
            def _first(obj: Any) -> bool:
                return any(p.zones[Zone.GRAVEYARD].contains(obj) for p in game.players)

            def _same_graveyard(obj: Any, chosen: Any) -> bool:
                if not chosen:
                    return _first(obj)
                return getattr(obj, "owner", None) is getattr(chosen[0], "owner", None) and _first(obj)

            return [
                TargetRequirement(filter_fn=_first, description="up to two target cards from a single graveyard", zone=Zone.GRAVEYARD, optional=True),
                TargetRequirement(filter_fn=_same_graveyard, description="second target card from the same graveyard", zone=Zone.GRAVEYARD, optional=True),
            ]

        register_enters_trigger(game, self, SoulShackledZombieAbility1, self._enters, targets=_up_to_two_from_one_graveyard)

    def _enters(self, game: "GameState", targets: list[Any], controller: Any) -> None:
        """Exile the targets still in a graveyard; if a creature card was
        exiled, each opponent loses 2 life and you gain 2 life."""
        from engine.game import exile, gain_life, lose_life

        exiled_creature = False
        for target in targets:
            if target is None:
                continue
            exile(game, target)
            if CardType.CREATURE in getattr(target, "card_types", set()):
                exiled_creature = True
        if exiled_creature:
            for player in game.players:
                if player is not controller:
                    lose_life(game, player, 2)
            gain_life(game, controller, 2)
