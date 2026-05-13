"""Card implementation for Condemn."""

from __future__ import annotations


from engine.card import (
    ActivatedAbility,
    Artifact,
    Creature,
    Enchantment,
    Instant,
    ManaAbility,
    Sorcery,
)
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Color, HybridManaSymbol, Keyword, ManaCost, ManaType, Supertype, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


class Condemn(Instant):
    """Condemn — {W} — Instant

    Put target attacking creature on the bottom of its owner's library.
    Its controller gains life equal to its toughness.

    SPG collector number 74.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Condemn")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Put target attacking creature on the bottom of its owner's "
            "library. Its controller gains life equal to its toughness.",
        )
        super().__init__(**kwargs)

    def _get_attacking_creatures(self, game: GameState) -> list[Any]:
        """Return all attacking creatures on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            bf = game.get_battlefield(player)
            for card in bf.get_all():
                if (
                    CardType.CREATURE in getattr(card, "card_types", set())
                    and getattr(card, "is_attacking", False)
                ):
                    targets.append(card)
        return targets

    def can_cast(self, game: GameState) -> bool:
        """Can only cast when there is at least one attacking creature."""
        return bool(self._get_attacking_creatures(game))

    def get_targets(self, game: GameState) -> list[Any]:
        """Return all attacking creatures as valid targets."""
        return self._get_attacking_creatures(game)

    def on_resolve(self, game: GameState) -> None:
        """Resolve Condemn: bottom-of-library + life gain."""
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        # Verify target is still on the battlefield and still attacking
        if not _is_on_battlefield(game, target):
            return
        if not getattr(target, "is_attacking", False):
            return

        controller = getattr(target, "controller", None)
        toughness = getattr(target, "toughness", 0)
        owner = getattr(target, "owner", controller)

        # BYPASS: move_to_zone doesn't support position="bottom", so we handle
        # the zone transition manually here.
        # Move to bottom of owner's library
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                bf.remove(target)
                break

        if owner is not None:
            owner.zones[Zone.LIBRARY].add(target, position="bottom")

        # Fire leaving-battlefield events
        from engine.triggers import EventType
        game.trigger_manager.fire_event(
            game,
            EventType.LEAVES_BATTLEFIELD,
            {"permanent": target, "controller": controller},
        )
        # Unregister triggers
        game.trigger_manager.unregister(target)
        if hasattr(game, "replacement_manager"):
            game.replacement_manager.unregister(target)

        # Controller gains life equal to toughness
        if controller is not None and toughness > 0:
            controller.life += toughness


__all__ = ["Condemn"]
