"""Card implementation for Soulstone Sanctuary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    ContinuousEffect,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class SoulstoneSanctuary(Land):
    """Soulstone Sanctuary — Land.

    {T}: Add {C}.
    {4}: This land becomes a 3/3 creature with vigilance and all creature
    types. It's still a land.

    FDN collector number 133.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Soulstone Sanctuary")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{4}: This land becomes a 3/3 creature with vigilance and all "
            "creature types. It's still a land.",
        )
        super().__init__(**kwargs)
        # P/T attributes so combat and continuous-effect code can treat the
        # animated land as a creature (Land does not define them).
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.damage_marked: int = 0
        self.summoning_sick: bool = False

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        """Also reset P/T — Land's base reset only covers types/keywords."""
        super()._reset_characteristics()
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            )
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 4:
                return False
            controller.mana_pool.pay(ManaCost(generic=4))
            return True

        def _effect(game: "GameState") -> None:
            def _apply_type(game: "GameState") -> None:
                source.card_types = source.card_types | {CardType.CREATURE}
                # "all creature types" — the engine keeps subtypes as strings;
                # record the changeling marker for subtype checks.
                source.all_creature_types = True

            def _apply_ability(game: "GameState") -> None:
                source.keywords = (
                    getattr(source, "keywords", None) or Keyword(0)
                ) | Keyword.VIGILANCE

            def _apply_pt(game: "GameState") -> None:
                source.modified_power = 3
                source.modified_toughness = 3

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.TYPE,
                    apply=_apply_type,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.ABILITY,
                    apply=_apply_ability,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.SET_PT,
                    apply=_apply_pt,
                    duration=DURATION_END_OF_TURN,
                )
            )
            # Apply immediately as well: the flags/P/T take effect now and
            # are re-applied on each apply_all() pass until end of turn.
            _apply_type(game)
            _apply_ability(game)
            _apply_pt(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{4}: This land becomes a 3/3 creature with "
                "vigilance and all creature types. It's still a land.",
            )
        ]
