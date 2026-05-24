"""Basic land implementations — Plains, Island, Swamp, Mountain, Forest.

Each basic land:
- Subclasses :class:`~engine.card.Land`.
- Has ``supertypes = {Supertype.BASIC}``.
- Has a subtype matching its land type (e.g. ``{"Plains"}``).
- Provides a :class:`~engine.card.ManaAbility` that taps to produce
  one mana of its associated color.

Use :func:`register_basic_lands` to register all five with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Land, ManaAbility
from benchmarks.sos.workspace.engine.types import ManaType, Supertype

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Mana-ability helpers
# ---------------------------------------------------------------------------

def _tap_cost(game: GameState, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap.

    Mirrors :func:`engine.abilities.tap_cost` logic so basic lands
    can be activated through the abilities system or directly.
    """
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


def _make_mana_effect(mana_type: ManaType):
    """Return an effect callable that adds 1 mana of *mana_type* to the controller's pool."""

    def _effect(game: GameState) -> None:  # noqa: ARG001 – game needed for signature
        # The source is captured via the ability's activation context.
        # However, ManaAbility.mana_produced is called by activate_ability's
        # effect path.  We need to figure out who the controller is.
        # This is handled at activation time — see get_mana_abilities below.
        pass

    return _effect


# ---------------------------------------------------------------------------
# Basic land classes
# ---------------------------------------------------------------------------

class Plains(Land):
    """Basic Plains — taps for {W}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.BASIC}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Plains"}
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return a single mana ability: {T}: Add {W}."""
        source = self

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.WHITE, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_effect,
                description="{T}: Add {W}.",
            )
        ]


class Island(Land):
    """Basic Island — taps for {U}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.BASIC}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Island"}
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return a single mana ability: {T}: Add {U}."""
        source = self

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.BLUE, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_effect,
                description="{T}: Add {U}.",
            )
        ]


class Swamp(Land):
    """Basic Swamp — taps for {B}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.BASIC}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Swamp"}
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return a single mana ability: {T}: Add {B}."""
        source = self

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.BLACK, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_effect,
                description="{T}: Add {B}.",
            )
        ]


class Mountain(Land):
    """Basic Mountain — taps for {R}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.BASIC}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Mountain"}
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return a single mana ability: {T}: Add {R}."""
        source = self

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_effect,
                description="{T}: Add {R}.",
            )
        ]


class Forest(Land):
    """Basic Forest — taps for {G}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.BASIC}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Forest"}
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return a single mana ability: {T}: Add {G}."""
        source = self

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.GREEN, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_effect,
                description="{T}: Add {G}.",
            )
        ]


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_basic_lands(registry: CardRegistry) -> None:
    """Register all five basic lands with *registry*.

    Each is registered under its canonical name (e.g. ``"Plains"``) with
    :class:`~cards.registry.CardMetadata` reflecting its type line, colors,
    and lack of mana cost.
    """
    from cards.registry import CardMetadata

    _BASIC_LANDS: list[tuple[str, type[Land], str]] = [
        ("Plains", Plains, "W"),
        ("Island", Island, "U"),
        ("Swamp", Swamp, "B"),
        ("Mountain", Mountain, "R"),
        ("Forest", Forest, "G"),
    ]

    for card_name, impl_class, mana_symbol in _BASIC_LANDS:
        metadata = CardMetadata(
            name=card_name,
            mana_cost_str="",
            type_line=f"Basic Land — {card_name}",
            oracle_text=f"({{T}}: Add {{{mana_symbol}}}.)",
            power=None,
            toughness=None,
            colors=[],
            keywords=[],
            rarity="common",
            set_code="",
            collector_number="",
        )
        registry.register(card_name, impl_class, metadata)
