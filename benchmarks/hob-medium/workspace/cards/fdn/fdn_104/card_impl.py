"""Card implementation for Elvish Regrower."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_PERMANENT_TYPES = frozenset(
    {
        CardType.CREATURE,
        CardType.ENCHANTMENT,
        CardType.ARTIFACT,
        CardType.PLANESWALKER,
        CardType.LAND,
    }
)


class ElvishRegrower(Creature):
    """Elvish Regrower — {2}{G}{G} — 4/3 — Elf Druid.

    When this creature enters, return target permanent card from your
    graveyard to your hand.

    FDN collector number 104.

    The enters-the-battlefield ability targets a *permanent* card (creature,
    artifact, enchantment, land, or planeswalker) in your graveyard. Targets
    are chosen at cast (``get_targets``) and applied in ``on_resolve``.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elvish Regrower")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, return target permanent card from "
            "your graveyard to your hand.",
        )
        super().__init__(**kwargs)

    def _is_permanent_card(self, obj: Any) -> bool:
        """The type half of the target predicate — a permanent card (creature,
        artifact, enchantment, land, or planeswalker).

        Shared by cast-time targeting (``get_targets``) and resolution
        revalidation (``on_resolve``) so both enforce one predicate (rule
        608.2b): the effect re-checks the *complete* original restriction at
        resolution, not merely graveyard membership.
        """
        return bool(getattr(obj, "card_types", set()) & _PERMANENT_TYPES)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target a permanent card in your graveyard."""
        controller = self.controller or getattr(self, "owner", None)

        def _filter(obj: Any) -> bool:
            if controller is None:
                return False
            if not self._is_permanent_card(obj):
                return False
            return game.get_graveyard(controller).contains(obj)

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target permanent card from your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Return the chosen permanent card from your graveyard to your hand."""
        from engine.zones import move_to_zone

        controller = self.controller or getattr(self, "owner", None)
        if controller is None:
            return
        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return
        # Revalidate the FULL original predicate (rule 608.2b): the card must
        # still be in your graveyard AND still be a permanent card.
        if not game.get_graveyard(controller).contains(target):
            return
        if not self._is_permanent_card(target):
            return
        move_to_zone(game, target, Zone.GRAVEYARD, Zone.HAND)
