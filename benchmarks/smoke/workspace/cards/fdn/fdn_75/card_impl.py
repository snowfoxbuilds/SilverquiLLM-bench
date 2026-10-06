"""Card implementation for Vampire Soulcaller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class VampireSoulcallerAbility1:
    text = 'Flying'


class VampireSoulcallerAbility2:
    text = "This creature can't block."


class VampireSoulcallerAbility3:
    text = 'When this creature enters, return target creature card from your graveyard to your hand.'


# endregion Printed abilities


class VampireSoulcaller(Creature):
    """Vampire Soulcaller — {4}{B} — 3/2 — Vampire Warlock — Flying.

    Flying
    This creature can't block.
    When this creature enters, return target creature card from your
    graveyard to your hand.

    FDN collector number 75.

    The enters-the-battlefield ability targets a creature card in your
    graveyard. Targets are chosen at cast (``get_targets``) and stored on
    the stack object; the return is applied in ``on_resolve`` before the
    creature arrives — the canonical ETB-with-target creature shape.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vampire Soulcaller")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Flying\nThis creature can't block.\nWhen this creature enters, "
            "return target creature card from your graveyard to your hand.",
        )
        super().__init__(**kwargs)

    def _is_creature_card_in_my_graveyard(self, game: "GameState", obj: Any, controller: Any) -> bool:
        """Legal target: a creature card currently in your graveyard."""
        if controller is None:
            return False
        if CardType.CREATURE not in getattr(obj, "card_types", set()):
            return False
        return game.get_graveyard(controller).contains(obj)

    def _enters_targets(self, game: "GameState", controller: Any) -> list[Any]:
        """Target a creature card in your graveyard."""
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: self._is_creature_card_in_my_graveyard(game, obj, _c),
                description="target creature card from your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that uses the stack."""
        from engine.triggers import register_enters_trigger

        register_enters_trigger(game, self, VampireSoulcallerAbility3, self._enters, targets=self._enters_targets)

    def _enters(self, game: "GameState", targets: list[Any], controller: Any) -> None:
        """Return the chosen creature card from your graveyard to your hand."""
        from engine.zones import move_to_zone

        if controller is None:
            return
        chosen = targets
        target = chosen[0] if chosen else None
        if target is None:
            return
        # Revalidate the COMPLETE target predicate at resolution (rule 608.2b):
        # the target must still be a creature card *and* still in your
        # graveyard — not merely still present. If either fails, do nothing.
        if not self._is_creature_card_in_my_graveyard(game, target, controller):
            return
        move_to_zone(game, target, Zone.GRAVEYARD, Zone.HAND)
