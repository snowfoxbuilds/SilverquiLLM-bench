"""Card implementation for Ascendant Dustspeaker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class AscendantDustspeaker(Creature):
    """{4}{W} 3/4 Flying Orc Cleric. ETB: +1/+1 on another creature you control.
    Beginning of combat: exile up to one card from a graveyard."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ascendant Dustspeaker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}"))
        kwargs.setdefault("subtypes", {"Orc", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def get_etb_targets(self, game: "GameState") -> list[Any]:
        """ETB targets: another creature you control."""
        self_ref = self
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    obj is not self_ref
                    and CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is controller
                ),
                description="another target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Put a +1/+1 counter on another target creature you control."""
        from engine.game import add_counter

        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is not None and CardType.CREATURE in getattr(target, "card_types", set()):
            add_counter(game, target, "+1/+1", 1)

    def on_combat_trigger(self, game: "GameState") -> None:
        """Exile up to one target card from a graveyard."""
        from engine.game import exile

        targets = getattr(self, "combat_trigger_targets", None)
        if not targets:
            return
        for target in targets:
            exile(game, target)
