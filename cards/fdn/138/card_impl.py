"""Card implementation for Banishing Light."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.game import exile
from engine.triggers import EventType, TriggerRegistration
from engine.types import (
    CardType,
    ManaCost,
    TargetRequirement,
    Zone,
)
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState




def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

def _nonland_opponent_targets(game: Any, controller: Any) -> list[Any]:
    """Return all nonland permanents on opponents' battlefields."""
    targets: list[Any] = []
    for player in game.players:
        if player is controller:
            continue
        for obj in game.get_battlefield(player).get_all():
            card_types = getattr(obj, "card_types", set())
            if CardType.LAND not in card_types:
                targets.append(obj)
    return targets
class BanishingLight(Enchantment):
    """Banishing Light — {2}{W} — Exile nonland permanent until this leaves.

    When this enchantment enters, exile target nonland permanent an opponent
    controls until this enchantment leaves the battlefield.

    FDN collector number 138.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Banishing Light")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault(
            "rules_text",
            "When this enchantment enters, exile target nonland permanent an "
            "opponent controls until this enchantment leaves the battlefield.",
        )
        super().__init__(**kwargs)
        self._exiled_card: Any | None = None
        self._exiled_owner: Any | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        controller = self.controller or game.active_player
        targets = _nonland_opponent_targets(game, controller)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.LAND not in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is not _c
                ),
                description="nonland permanent an opponent controls",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return  # fizzle

        from engine.zones import move_to_zone
        self._exiled_card = target
        self._exiled_owner = getattr(target, "owner", None) or getattr(
            target, "controller", None
        )
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            permanent = data.get("permanent")
            return permanent is source

        def _effect(game: GameState) -> None:
            card = source._exiled_card
            owner = source._exiled_owner
            if card is None or owner is None:
                return
            from engine.zones import move_to_zone
            card.controller = owner
            move_to_zone(game, card, Zone.EXILE, Zone.BATTLEFIELD)
            source._exiled_card = None
            source._exiled_owner = None

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.LEAVES_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
