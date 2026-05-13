"""Non-basic land implementations for the FDN (Foundations) set.

Categories:
- **Gain lands** (10): ETB tapped, gain 1 life, tap for one of two colors.
- **Utility lands** (2): Rogue's Passage (#264), Soulstone Sanctuary (#133).
- **Evolving Wilds** (#262): Fetch land.

Use :func:`register_lands` to register all with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import ManaType, CardType

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player
    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Tap-cost helper (shared with basic_lands.py pattern)
# ---------------------------------------------------------------------------

def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


# ---------------------------------------------------------------------------
# ManaType lookup
# ---------------------------------------------------------------------------

_MANA_SYMBOLS: dict[str, ManaType] = {
    "W": ManaType.WHITE,
    "U": ManaType.BLUE,
    "B": ManaType.BLACK,
    "R": ManaType.RED,
    "G": ManaType.GREEN,
    "C": ManaType.COLORLESS,
}


# ---------------------------------------------------------------------------
# Base: ETB-tapped land
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


# ---------------------------------------------------------------------------
# Gain lands — ETB tapped, gain 1 life, tap for one of two colors
# ---------------------------------------------------------------------------

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
# Concrete gain land classes
# ---------------------------------------------------------------------------

class BloodfellCaves(GainLand):
    """Bloodfell Caves — ETB tapped, gain 1 life, {T}: Add {B} or {R}."""
    _mana_colors = (ManaType.BLACK, ManaType.RED)
    _mana_symbols = ("B", "R")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class BlossomingSands(GainLand):
    """Blossoming Sands — ETB tapped, gain 1 life, {T}: Add {G} or {W}."""
    _mana_colors = (ManaType.GREEN, ManaType.WHITE)
    _mana_symbols = ("G", "W")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class DismalBackwater(GainLand):
    """Dismal Backwater — ETB tapped, gain 1 life, {T}: Add {U} or {B}."""
    _mana_colors = (ManaType.BLUE, ManaType.BLACK)
    _mana_symbols = ("U", "B")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class JungleHollow(GainLand):
    """Jungle Hollow — ETB tapped, gain 1 life, {T}: Add {B} or {G}."""
    _mana_colors = (ManaType.BLACK, ManaType.GREEN)
    _mana_symbols = ("B", "G")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class RuggedHighlands(GainLand):
    """Rugged Highlands — ETB tapped, gain 1 life, {T}: Add {R} or {G}."""
    _mana_colors = (ManaType.RED, ManaType.GREEN)
    _mana_symbols = ("R", "G")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class ScouredBarrens(GainLand):
    """Scoured Barrens — ETB tapped, gain 1 life, {T}: Add {W} or {B}."""
    _mana_colors = (ManaType.WHITE, ManaType.BLACK)
    _mana_symbols = ("W", "B")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class SwiftwaterCliffs(GainLand):
    """Swiftwater Cliffs — ETB tapped, gain 1 life, {T}: Add {U} or {R}."""
    _mana_colors = (ManaType.BLUE, ManaType.RED)
    _mana_symbols = ("U", "R")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class ThornwoodFalls(GainLand):
    """Thornwood Falls — ETB tapped, gain 1 life, {T}: Add {G} or {U}."""
    _mana_colors = (ManaType.GREEN, ManaType.BLUE)
    _mana_symbols = ("G", "U")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class TranquilCove(GainLand):
    """Tranquil Cove — ETB tapped, gain 1 life, {T}: Add {W} or {U}."""
    _mana_colors = (ManaType.WHITE, ManaType.BLUE)
    _mana_symbols = ("W", "U")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class WindScarredCrag(GainLand):
    """Wind-Scarred Crag — ETB tapped, gain 1 life, {T}: Add {R} or {W}."""
    _mana_colors = (ManaType.RED, ManaType.WHITE)
    _mana_symbols = ("R", "W")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Utility lands
# ---------------------------------------------------------------------------

class RoguesPassage(Land):
    """Rogue's Passage (#264) — {T}: Add {C}. {4}, {T}: Target creature
    can't be blocked this turn."""

    def __init__(self, **kwargs: Any) -> None:
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
            """Target creature can't be blocked this turn."""
            # The actual target selection is handled by the game engine.
            # This sets the unblockable flag on the target creature.
            target = getattr(source, "_current_target", None)
            if target is not None:
                target.cant_be_blocked_this_turn = True

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{4}, {T}: Target creature can't be blocked this turn.",
        )]


class SoulstoneSanctuary(Land):
    """Soulstone Sanctuary (#133) — {T}: Add {C}. {4}, {T}: Put a
    +1/+1 counter on target creature. It gains vigilance until end of turn."""

    def __init__(self, **kwargs: Any) -> None:
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


class EvolvingWilds(Land):
    """Evolving Wilds (#262) — {T}, Sacrifice this land: Search your library
    for a basic land card, put it onto the battlefield tapped, then shuffle."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        # Evolving Wilds has no mana abilities (its ability isn't a mana ability).
        return []

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            """Tap and sacrifice."""
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            # Sacrifice the land
            controller = src.controller
            if controller is not None:
                battlefield = getattr(controller, "battlefield", None)
                if battlefield is not None and src in battlefield:
                    battlefield.remove(src)
                graveyard = getattr(controller, "graveyard", None)
                if graveyard is not None:
                    graveyard.append(src)
            return True

        def _effect(game: Any) -> None:
            """Search library for a basic land, put it onto the battlefield tapped, shuffle."""
            controller = source.controller
            if controller is None:
                return
            library = getattr(controller, "library", None)
            if library is None:
                return
            # Find a basic land in the library
            basic_land = None
            for card in library:
                if getattr(card, "is_basic_land", False):
                    basic_land = card
                    break
            if basic_land is not None:
                library.remove(basic_land)
                basic_land.is_tapped = True
                basic_land.controller = controller
                battlefield = getattr(controller, "battlefield", None)
                if battlefield is not None:
                    battlefield.append(basic_land)
                # Shuffle library
                import random
                random.shuffle(library)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}, Sacrifice this land: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.",
        )]


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

# Card data: (name, class, collector_number, type_line, oracle_text, colors, rarity)
_LAND_CARDS: list[tuple[str, type[Land], str, str, str, list[str], str]] = [
    (
        "Bloodfell Caves", BloodfellCaves, "259",
        "Land",
        "This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {B} or {R}.",
        [], "common",
    ),
    (
        "Blossoming Sands", BlossomingSands, "260",
        "Land",
        "This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {G} or {W}.",
        [], "common",
    ),
    (
        "Dismal Backwater", DismalBackwater, "261",
        "Land",
        "This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {U} or {B}.",
        [], "common",
    ),
    (
        "Jungle Hollow", JungleHollow, "263",
        "Land",
        "This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {B} or {G}.",
        [], "common",
    ),
    (
        "Rugged Highlands", RuggedHighlands, "265",
        "Land",
        "This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {R} or {G}.",
        [], "common",
    ),
    (
        "Scoured Barrens", ScouredBarrens, "266",
        "Land",
        "This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {W} or {B}.",
        [], "common",
    ),
    (
        "Swiftwater Cliffs", SwiftwaterCliffs, "268",
        "Land",
        "This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {U} or {R}.",
        [], "common",
    ),
    (
        "Thornwood Falls", ThornwoodFalls, "269",
        "Land",
        "This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {G} or {U}.",
        [], "common",
    ),
    (
        "Tranquil Cove", TranquilCove, "270",
        "Land",
        "This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {W} or {U}.",
        [], "common",
    ),
    (
        "Wind-Scarred Crag", WindScarredCrag, "271",
        "Land",
        "This land enters tapped.\nWhen this land enters, you gain 1 life.\n{T}: Add {R} or {W}.",
        [], "common",
    ),
    (
        "Rogue's Passage", RoguesPassage, "264",
        "Land",
        "{T}: Add {C}.\n{4}, {T}: Target creature can't be blocked this turn.",
        [], "uncommon",
    ),
    (
        "Soulstone Sanctuary", SoulstoneSanctuary, "133",
        "Land",
        "{T}: Add {C}.\n{4}, {T}: Put a +1/+1 counter on target creature. It gains vigilance until end of turn.",
        [], "rare",
    ),
    (
        "Evolving Wilds", EvolvingWilds, "262",
        "Land",
        "{T}, Sacrifice this land: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.",
        [], "common",
    ),
]


def register_lands(registry: CardRegistry) -> None:
    """Register all FDN non-basic lands with *registry*."""
    from cards.registry import CardMetadata

    for name, impl_class, collector_number, type_line, oracle_text, colors, rarity in _LAND_CARDS:
        metadata = CardMetadata(
            name=name,
            mana_cost_str="",
            type_line=type_line,
            oracle_text=oracle_text,
            power=None,
            toughness=None,
            colors=colors,
            keywords=[],
            rarity=rarity,
            set_code="fdn",
            collector_number=collector_number,
        )
        registry.register(name, impl_class, metadata)
