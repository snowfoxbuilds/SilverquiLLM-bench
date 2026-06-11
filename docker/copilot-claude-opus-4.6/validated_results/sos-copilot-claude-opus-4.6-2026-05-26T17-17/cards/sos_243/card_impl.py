"""Card implementation for Wilt in the Heat."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class WiltInTheHeat(Instant):
    """Wilt in the Heat — {2}{R}{W} — Instant.

    This spell costs {2} less to cast if one or more cards left your graveyard this turn.
    Wilt in the Heat deals 5 damage to target creature. If that creature
    would die this turn, exile it instead.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wilt in the Heat")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{W}"))
        super().__init__(**kwargs)
        self.targets: list[Any] = []

    def get_effective_cost(self, game: "GameState") -> ManaCost:
        """Return effective cost, reduced by {2} if a card left graveyard this turn."""
        controller = self.controller or self.owner
        cards_left = getattr(game, "cards_left_graveyard_this_turn", {})
        count = cards_left.get(controller, 0)

        base = self.mana_cost
        if count > 0:
            new_generic = max(0, base.generic - 2)
            return ManaCost(generic=new_generic, pips=dict(base.pips), x_count=base.x_count)
        return base

    def on_resolve(self, game: "GameState") -> None:
        """Deal 5 damage to target creature. If it would die, exile instead."""
        from engine.game import deal_damage

        if not self.targets:
            return

        target = self.targets[0]

        # Deal 5 damage
        deal_damage(game, self, target, 5)

        # Check if the creature would die (damage >= toughness)
        if hasattr(target, "damage_marked") and hasattr(target, "toughness"):
            if target.damage_marked >= target.toughness:
                # Exile instead of going to graveyard
                controller = getattr(target, "controller", None)
                if controller is None:
                    owner = getattr(target, "owner", None)
                    controller = owner

                if controller is not None:
                    bf = game.get_battlefield(controller)
                    if bf.contains(target):
                        bf.remove(target)
                        owner = getattr(target, "owner", controller)
                        owner.zones[Zone.EXILE].add(target)
