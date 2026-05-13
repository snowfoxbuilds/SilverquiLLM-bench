"""Shared base classes for FDN land implementations.

Provides TapLand and GainLand base classes that all non-basic land
card_impl modules import from, ensuring isinstance() checks work
correctly across different collector-number directories.
"""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType


def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


class TapLand(Land):
    """A land that enters the battlefield tapped."""

    enters_tapped: bool = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def register_triggers(self, game: Any) -> None:
        """Apply enters-tapped status."""
        if self.enters_tapped:
            self.is_tapped = True


class GainLand(TapLand):
    """A gain land: ETB tapped, gain 1 life, tap for one of two colors."""

    _mana_colors: tuple[ManaType, ManaType] = (ManaType.COLORLESS, ManaType.COLORLESS)
    _mana_symbols: tuple[str, str] = ("C", "C")

    def register_triggers(self, game: Any) -> None:
        """Apply enters-tapped and gain 1 life."""
        super().register_triggers(game)
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.life += 1

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return two mana abilities, one for each color."""
        source = self
        abilities: list[ManaAbility] = []
        for mana_type, symbol in zip(self._mana_colors, self._mana_symbols):
            mt = mana_type

            def _make_effect(mtype: ManaType):
                def _effect(game: Any) -> None:
                    controller = source.controller
                    if controller is not None:
                        controller.mana_pool.add(mtype, 1)
                return _effect

            abilities.append(ManaAbility(
                cost=_tap_cost,
                mana_produced=_make_effect(mt),
                description=f"{{T}}: Add {{{symbol}}}.",
            ))
        return abilities
