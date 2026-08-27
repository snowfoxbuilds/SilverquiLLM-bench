"""Card implementation for Condemn."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from engine.events import LeavesBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


def _is_attacking_creature(obj: Any) -> bool:
    """Legal target: an attacking creature."""
    return (
        CardType.CREATURE in getattr(obj, "card_types", set())
        and bool(getattr(obj, "is_attacking", False))
    )


class Condemn(Instant):
    """Condemn — {W} — Instant

    Put target attacking creature on the bottom of its owner's library.
    Its controller gains life equal to its toughness.

    SPG collector number 74.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Condemn')
        kwargs.setdefault('mana_cost', ManaCost.parse('{W}'))
        kwargs.setdefault('rules_text', "Put target attacking creature on the bottom of its owner's library. Its controller gains life equal to its toughness.")
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target attacking creature (required)."""
        return [
            TargetRequirement(
                filter_fn=_is_attacking_creature,
                description="target attacking creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve Condemn: bottom-of-library + life gain."""
        targets = getattr(self, 'chosen_targets', None) or []
        target = targets[0] if targets else None
        if target is None:
            return
        # Revalidate the FULL original predicate (rule 608.2b): the target must
        # still be an attacking creature, not merely still on the battlefield.
        # A creature removed from combat (or that stopped being a creature) is
        # no longer a legal target, so Condemn does nothing.
        if not _is_on_battlefield(game, target):
            return
        if not _is_attacking_creature(target):
            return

        # Capture characteristics before the creature leaves the battlefield.
        controller = getattr(target, 'controller', None)
        toughness = getattr(target, 'toughness', 0)
        owner = getattr(target, 'owner', controller)

        # Move the creature to the bottom of its owner's library.
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                bf.remove(target)
                break
        if owner is not None:
            owner.zones[Zone.LIBRARY].add(target, position='bottom')
        game.trigger_manager.fire_event(
            game,
            LeavesBattlefieldTriggeredEvent(permanent=target, controller=controller),
        )
        game.trigger_manager.unregister(target)
        if hasattr(game, 'replacement_manager'):
            game.replacement_manager.unregister(target)

        # Its controller gains life equal to its toughness.
        if controller is not None and toughness > 0:
            from engine.game import gain_life
            gain_life(game, controller, toughness)
