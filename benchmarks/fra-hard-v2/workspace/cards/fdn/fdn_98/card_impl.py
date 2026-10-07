"""Card implementation for Ambush Wolf."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class AmbushWolfAbility1:
    text = 'Flash (You may cast this spell any time you could cast an instant.)'


class AmbushWolfAbility2:
    text = 'When this creature enters, exile up to one target card from a graveyard.'


# endregion Printed abilities


class AmbushWolf(Creature):
    """Ambush Wolf — {2}{G} — 4/2 — Wolf — Flash.

    Flash
    When this creature enters, exile up to one target card from a graveyard.

    FDN collector number 98.

    "Up to one target" is expressed as a single *optional* target requirement:
    the query is declinable and an empty graveyard set casts with zero targets
    rather than making the spell uncastable.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ambush Wolf")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Wolf"})
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Flash\nWhen this creature enters, exile up to one target card "
            "from a graveyard.",
        )
        super().__init__(**kwargs)

    def _enters_targets(self, game: "GameState", controller: Any) -> list[Any]:
        """Up to one target card in any graveyard."""

        def _filter(obj: Any) -> bool:
            return any(game.get_graveyard(p).contains(obj) for p in game.players)

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="up to one target card from a graveyard",
                zone=Zone.GRAVEYARD,
                optional=True,
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that uses the stack."""
        from engine.triggers import register_enters_trigger

        register_enters_trigger(game, self, AmbushWolfAbility2, self._enters, targets=self._enters_targets)

    def _enters(self, game: "GameState", targets: list[Any], controller: Any) -> None:
        """Exile the chosen graveyard card (if any was targeted)."""
        from engine.zones import move_to_zone

        chosen = targets
        target = chosen[0] if chosen else None
        if target is None:
            return
        for player in game.players:
            if game.get_graveyard(player).contains(target):
                move_to_zone(game, target, Zone.GRAVEYARD, Zone.EXILE)
                return
