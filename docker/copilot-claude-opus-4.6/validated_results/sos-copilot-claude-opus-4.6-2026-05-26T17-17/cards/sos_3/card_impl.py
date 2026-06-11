"""Card implementation for Sundering Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SunderingArchaic(Creature):
    """Sundering Archaic — {6} — Creature — Avatar — 3/3.

    Converge — When this creature enters, exile target nonland permanent an
    opponent controls with mana value less than or equal to the number of
    colors of mana spent to cast this creature.
    {2}: Put target card from a graveyard on the bottom of its owner's library.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sundering Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Converge — When this creature enters, exile target nonland permanent "
            "an opponent controls with mana value less than or equal to the number "
            "of colors of mana spent to cast this creature.\n"
            "{2}: Put target card from a graveyard on the bottom of its owner's library.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target nonland permanent an opponent controls."""
        from engine.types import TargetRequirement

        def _filter(obj: Any) -> bool:
            card_types = getattr(obj, "card_types", set())
            if CardType.LAND in card_types:
                return False
            return True

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target nonland permanent an opponent controls",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """ETB: exile target nonland permanent with MV <= colors spent."""
        colors_spent = getattr(self, "colors_spent", None)
        if colors_spent is None:
            count = 0
        elif isinstance(colors_spent, (list, tuple)):
            count = len(set(colors_spent))
        else:
            count = int(colors_spent)

        # Get chosen target
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        # Validate: must be nonland permanent opponent controls
        card_types = getattr(target, "card_types", set())
        if CardType.LAND in card_types:
            return  # Can't target lands

        # Check MV of target
        target_cost = getattr(target, "mana_cost", None)
        target_mv = target_cost.cmc if target_cost else 0
        if target_mv > count:
            return  # MV exceeds colors spent

        # Exile the target
        controller = getattr(target, "controller", None) or getattr(target, "owner", None)
        if controller is None:
            return
        bf = controller.zones[Zone.BATTLEFIELD]
        if bf.contains(target):
            bf.remove(target)
            owner = getattr(target, "owner", controller)
            owner.zones[Zone.EXILE].add(target)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the {2} graveyard-to-library ability."""
        source = self

        def _cost(game: Any) -> bool:
            controller = source.controller or source.owner
            if controller is None:
                return False
            return controller.mana_pool.get(ManaType.COLORLESS) >= 2 or \
                   controller.mana_pool.total() >= 2

        def _effect(game: Any, target_card: Any) -> None:
            """Move target card from graveyard to bottom of owner's library."""
            owner = getattr(target_card, "owner", None)
            if owner is None:
                # Try to find which player's graveyard has it
                for player in game.players:
                    gy = player.zones[Zone.GRAVEYARD]
                    if gy.contains(target_card):
                        owner = player
                        break
            if owner is None:
                return
            gy = owner.zones[Zone.GRAVEYARD]
            if gy.contains(target_card):
                gy.remove(target_card)
                owner.zones[Zone.LIBRARY].add(target_card, position="bottom")

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{2}: Put target card from a graveyard on the bottom of its owner's library.",
        )]

    def register_triggers(self, game: "GameState") -> None:
        """Register ETB trigger for converge exile."""
        pass
