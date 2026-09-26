"""Card implementation for Sun-Blessed Healer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SunBlessedHealer(Creature):
    """Sun-Blessed Healer — {1}{W} — 3/1 — Human Cleric.

    Kicker {1}{W}
    Lifelink
    When this creature enters, if it was kicked, return target nonland
    permanent card with mana value 2 or less from your graveyard to the
    battlefield.

    FDN collector number 25.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sun-Blessed Healer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Cleric"})
        kwargs.setdefault("keywords", Keyword.LIFELINK)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Kicker {1}{W}\n"
            "Lifelink\n"
            "When this creature enters, if it was kicked, return target "
            "nonland permanent card with mana value 2 or less from your "
            "graveyard to the battlefield.",
        )
        super().__init__(**kwargs)
        self.kicked: bool = False
        self.kicker_cost: ManaCost = ManaCost.parse("{1}{W}")

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target nonland permanent card with MV <= 2 in your graveyard (if kicked)."""
        if not self.kicked:
            return []

        def _filter(obj: Any) -> bool:
            # Must be in controller's graveyard (checked via owner/controller)
            if getattr(obj, "owner", None) is not self.controller and \
               getattr(obj, "controller", None) is not self.controller:
                return False
            card_types = getattr(obj, "card_types", set())
            if CardType.LAND in card_types:
                return False
            is_permanent = bool(
                card_types & {CardType.CREATURE, CardType.ARTIFACT,
                              CardType.ENCHANTMENT, CardType.PLANESWALKER}
            )
            if not is_permanent:
                return False
            mc = getattr(obj, "mana_cost", None)
            if mc is None:
                return True  # MV 0
            return mc.cmc <= 2

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target nonland permanent card with mana value 2 or less in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """ETB: if kicked, return target nonland permanent from graveyard to battlefield."""
        if not self.kicked:
            return

        from engine.zones import move_to_zone

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        controller = self.controller
        if controller is None:
            return

        # Validate target is still in graveyard
        graveyard = controller.zones[Zone.GRAVEYARD]
        if not graveyard.contains(target):
            return

        target.controller = controller
        move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
