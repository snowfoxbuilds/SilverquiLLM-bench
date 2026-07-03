"""Factory for the FDN gain-life tapland cycle.

All ten "lifelands" (Bloodfell Caves, Blossoming Sands, ...) share the same
text modulo name and mana colors:

    This land enters tapped.
    When this land enters, you gain 1 life.
    {T}: Add {X} or {Y}.

``make_gainlife_tapland`` builds the Land subclass once; each card dir's
``card_impl.py`` is a one-line instantiation, so the cycle has a single
behavioral definition instead of ten copies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def make_gainlife_tapland(
    name: str,
    colors: tuple[ManaType, ManaType],
    collector_number: int,
) -> type[Land]:
    """Build a gain-life tapland class for *name* producing *colors*."""
    first, second = (m.value for m in colors)
    rules_text = (
        "This land enters tapped.\n"
        "When this land enters, you gain 1 life.\n"
        f"{{T}}: Add {{{first}}} or {{{second}}}."
    )

    class GainlifeTapland(Land):
        def __init__(self, **kwargs: Any) -> None:
            kwargs.setdefault("name", name)
            kwargs.setdefault("rules_text", rules_text)
            super().__init__(**kwargs)

        def on_resolve(self, game: "GameState") -> None:
            """Enter tapped; the enters trigger has its controller gain 1 life."""
            self.is_tapped = True
            controller = self.controller or self.owner
            if controller is not None:
                from engine.game import gain_life

                gain_life(game, controller, 1)

        def get_mana_abilities(self) -> list[ManaAbility]:
            source = self

            def _tap_cost(game: "GameState", src: Any) -> bool:
                if getattr(src, "is_tapped", False):
                    return False
                src.is_tapped = True
                return True

            def _make_add(mana_type: ManaType):
                def _add(game: "GameState") -> None:
                    controller = source.controller
                    if controller is not None:
                        controller.mana_pool.add(mana_type, 1)

                return _add

            return [
                ManaAbility(
                    cost=_tap_cost,
                    mana_produced=_make_add(mana_type),
                    description=f"{{T}}: Add {{{mana_type.value}}}.",
                )
                for mana_type in colors
            ]

    GainlifeTapland.__name__ = "".join(
        part for part in name.replace("-", " ").title().split() if part
    )
    GainlifeTapland.__qualname__ = GainlifeTapland.__name__
    GainlifeTapland.__doc__ = (
        f"{name} — Land.\n\n"
        "This land enters tapped.\n"
        "When this land enters, you gain 1 life.\n"
        f"{{T}}: Add {{{first}}} or {{{second}}}.\n\n"
        f"FDN collector number {collector_number}."
    )
    return GainlifeTapland
