"""Card implementation for HedronArchive."""

from __future__ import annotations


from engine.card import Artifact, Aura, Enchantment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any



class HedronArchive(Artifact):
    """Hedron Archive — {4} — {T}: Add {C}{C}.

    The sacrifice ability ({2}, {T}, Sacrifice: Draw two cards) is not
    implemented in this phase.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hedron Archive")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}{C}.\n"
            "{2}, {T}, Sacrifice this artifact: Draw two cards.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[Any]:
        """Return a mana ability: {T}: Add {C}{C}."""
        from engine.card import ManaAbility

        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 2)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_effect,
                description="{T}: Add {C}{C}.",
            )
        ]

    def get_activated_abilities(self) -> list[Any]:
        """Return activated abilities for this artifact.

        The mana ability is handled via get_mana_abilities() and the
        abilities system. We also expose it as an ActivatedAbilityInstance
        for use with activate_ability().
        """
        from engine.abilities import ActivatedAbilityInstance

        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 2)

        return [
            ActivatedAbilityInstance(
                source=source,
                controller=source.controller,
                cost=_cost,
                effect=_effect,
                is_mana_ability=True,
                description="{T}: Add {C}{C}.",
            )
        ]


__all__ = ["HedronArchive"]
