"""Card implementation for Soulstone Sanctuary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import ManaType




def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True
class SoulstoneSanctuary(Land):
    """Soulstone Sanctuary (#133) — {T}: Add {C}. {4}, {T}: Put a
    +1/+1 counter on target creature. It gains vigilance until end of turn."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Soulstone Sanctuary")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [ManaAbility(
            cost=_tap_cost,
            mana_produced=_effect,
            description="{T}: Add {C}.",
        )]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            """Pay {4} and tap."""
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 4:
                return False
            controller.mana_pool.pay_generic(4)
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            """Put a +1/+1 counter on target creature. It gains vigilance until end of turn."""
            target = getattr(source, "_current_target", None)
            if target is not None:
                counters = getattr(target, "plus1_counters", 0)
                target.plus1_counters = counters + 1
                target.vigilance_until_eot = True

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{4}, {T}: Put a +1/+1 counter on target creature. It gains vigilance until end of turn.",
        )]
