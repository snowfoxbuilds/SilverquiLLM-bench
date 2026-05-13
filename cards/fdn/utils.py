"""Shared helpers for FDN card implementations.

Provides base classes and utility functions used by multiple per-card
``card_impl.py`` modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Land, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


# ---------------------------------------------------------------------------
# Tap-cost helper
# ---------------------------------------------------------------------------

def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


# ---------------------------------------------------------------------------
# TapLand / GainLand base classes
# ---------------------------------------------------------------------------

class TapLand(Land):
    """A land that enters the battlefield tapped.

    Subclasses set ``enters_tapped = True`` so the engine (or
    ``register_triggers``) can apply the tapped status on ETB.
    """

    enters_tapped: bool = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def register_triggers(self, game: Any) -> None:
        """Apply enters-tapped status."""
        if self.enters_tapped:
            self.is_tapped = True


class GainLand(TapLand):
    """A gain land: ETB tapped, gain 1 life, tap for one of two colors.

    Subclasses must set ``_mana_colors`` to a tuple of two ManaType values.
    """

    _mana_colors: tuple[ManaType, ManaType] = (ManaType.COLORLESS, ManaType.COLORLESS)
    _mana_symbols: tuple[str, str] = ("C", "C")

    def register_triggers(self, game: Any) -> None:
        """Apply enters-tapped and gain 1 life."""
        super().register_triggers(game)
        # Gain 1 life on ETB
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.life += 1

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return two mana abilities, one for each color."""
        source = self
        abilities: list[ManaAbility] = []
        for mana_type, symbol in zip(self._mana_colors, self._mana_symbols):
            mt = mana_type  # capture for closure

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


# ---------------------------------------------------------------------------
# make_vanilla factory
# ---------------------------------------------------------------------------

def make_vanilla(
    name: str,
    cost_str: str,
    power: int,
    toughness: int,
    keywords: Keyword | None = None,
    creature_types: set[str] | None = None,
) -> type[Creature]:
    """Create a :class:`~engine.card.Creature` subclass dynamically.

    The returned class, when instantiated, produces a creature with the
    specified stats, mana cost, keywords, and creature subtypes.
    """
    _cost = ManaCost.parse(cost_str)
    _keywords = keywords if keywords is not None else Keyword(0)
    _subtypes = creature_types if creature_types is not None else set()
    _power = power
    _toughness = toughness
    _default_name = name

    class _VanillaCreature(Creature):
        __doc__ = f"{name} — {cost_str} {power}/{toughness}"

        def __init__(self, **kwargs: Any) -> None:
            kwargs.setdefault("name", _default_name)
            kwargs.setdefault("mana_cost", _cost)
            kwargs.setdefault("keywords", _keywords)
            kwargs.setdefault("base_power", _power)
            kwargs.setdefault("base_toughness", _toughness)
            if _subtypes:
                kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | _subtypes
            super().__init__(**kwargs)

    _VanillaCreature.__name__ = name.replace(" ", "").replace(",", "").replace("'", "").replace("-", "")
    _VanillaCreature.__qualname__ = _VanillaCreature.__name__
    return _VanillaCreature
