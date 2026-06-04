"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_ANY_COLORS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


def _is_instant_or_sorcery(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            "creature with \"Whenever you cast an instant or sorcery spell, "
            "this creature gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        # Creature-stat scaffolding, live only while animated.
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.damage_marked: int = 0
        self.summoning_sick: bool = True
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.is_token: bool = False
        self._animated: bool = False
        self._original_subtypes: frozenset[str] = frozenset(self.subtypes)

    # ------------------------------------------------------------------
    # Creature-like characteristics (only meaningful once animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness
        self.subtypes = set(self._original_subtypes)

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_and_pay_life(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            ctrl = getattr(src, "controller", None)
            if ctrl is None:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_any_color(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            chosen = ctrl.choose(list(_ANY_COLORS), "color to add")
            if chosen not in _ANY_COLORS:
                chosen = ManaType.WHITE
            ctrl.mana_pool.add(chosen, 1)

        return [
            ManaAbility(
                cost=_tap,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life,
                mana_produced=_add_any_color,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            ctrl = getattr(src, "controller", None)
            if ctrl is None:
                return False
            cost = ManaCost.parse("{5}")
            if not ctrl.mana_pool.can_pay(cost):
                return False
            return ctrl.mana_pool.pay(cost)

        def _effect(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature. It's still a land."
                ),
            )
        ]

    def _animate(self, game: "GameState") -> None:
        from engine.continuous_effects import (
            DURATION_PERMANENT,
            ContinuousEffect,
            Layer,
            SubLayer,
        )

        source = self
        self._animated = True

        def _apply_type(game: "GameState") -> None:
            source.card_types = set(source.card_types) | {CardType.CREATURE}
            source.subtypes = set(source.subtypes) | {"Wizard"}

        def _apply_pt(game: "GameState") -> None:
            source.modified_power = 2
            source.modified_toughness = 4

        game.effect_manager.add(
            ContinuousEffect(
                source=source,
                layer=Layer.TYPE,
                apply=_apply_type,
                duration=DURATION_PERMANENT,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.SET_PT,
                apply=_apply_pt,
                duration=DURATION_PERMANENT,
            )
        )
        game.effect_manager.apply_all(game)

    # ------------------------------------------------------------------
    # Cast-trigger buff (only while animated)
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.continuous_effects import (
            DURATION_END_OF_TURN,
            ContinuousEffect,
            Layer,
            SubLayer,
        )
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            if not source._animated:
                return False
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            if caster is not ctrl:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            return spell is not None and _is_instant_or_sorcery(spell)

        def _effect(game: "GameState") -> None:
            def _buff(game: "GameState") -> None:
                source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_buff,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
