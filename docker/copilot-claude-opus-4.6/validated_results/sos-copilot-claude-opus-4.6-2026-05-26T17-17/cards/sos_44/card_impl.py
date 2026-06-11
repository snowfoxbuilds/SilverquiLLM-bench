"""Card implementation for Echocasting Symposium."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EchocastingSymposium(Sorcery):
    """Echocasting Symposium — {4}{U}{U} — Sorcery — Lesson.

    Target player creates a token that's a copy of target creature you control.
    Paradigm (exile after resolution).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Echocasting Symposium")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Target player creates a token that's a copy of target creature you control.\n"
            "Paradigm (Then exile this spell.)",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Two targets: a player and a creature you control."""
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),  # player check
                description="target player",
                zone=Zone.BATTLEFIELD,  # players aren't in zones but needed
            ),
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is controller
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Create a token copy of target creature for target player, then exile self."""
        chosen = getattr(self, "chosen_targets", None) or []
        if len(chosen) < 2:
            # Exile self even if no valid targets (Paradigm)
            game.get_exile(self.controller).add(self)
            return

        target_player = chosen[0]
        target_creature = chosen[1]

        # Create a token copy
        token = Creature(
            name=target_creature.name,
            owner=target_player,
            controller=target_player,
            base_power=target_creature.base_power,
            base_toughness=target_creature.base_toughness,
            card_types=set(getattr(target_creature, "card_types", {CardType.CREATURE})),
            subtypes=set(getattr(target_creature, "subtypes", set())),
            keywords=getattr(target_creature, "keywords", None),
        )
        token.is_token = True
        game.get_battlefield(target_player).add(token)

        # Paradigm: exile this spell after resolution
        game.get_exile(self.controller).add(self)
