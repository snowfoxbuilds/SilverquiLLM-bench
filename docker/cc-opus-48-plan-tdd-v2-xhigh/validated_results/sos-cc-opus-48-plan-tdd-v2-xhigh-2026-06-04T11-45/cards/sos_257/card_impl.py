"""Card implementation for Great Hall of the Biblioplex (SOS #257).

ENGINE NOTE: The manland is modelled as a :class:`Land` that grows the
creature surface only once animated (gap #2 for the cast trigger).  We avoid
defining ``base_power`` until ``_animate`` runs so a non-animated land is not
picked up as a legal attacker (``declare_attackers_step`` gates on
``hasattr(c, "base_power")``).  ``_reset_characteristics`` re-applies the
type/PT change so the transformation survives ``EffectManager.apply_all``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ActivatedAbility, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_COLORS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
        an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
        "Whenever you cast an instant or sorcery spell, this creature gets
        +1/+0 until end of turn." It's still a land.

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
        self._is_animated: bool = False

    # ------------------------------------------------------------------
    # Creature surface (only meaningful while animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        return (
            getattr(self, "modified_power", 0)
            + getattr(self, "plus_one_counters", 0)
            - getattr(self, "minus_one_counters", 0)
        )

    @property
    def toughness(self) -> int:
        return (
            getattr(self, "modified_toughness", 0)
            + getattr(self, "plus_one_counters", 0)
            - getattr(self, "minus_one_counters", 0)
        )

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _colorless_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _colorless_produced(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _anycolor_cost(game: Any, src: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if getattr(src, "is_tapped", False) or ctrl is None:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _anycolor_produced(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            color = ctrl.choose(_COLORS, "choose a color of mana to add")
            if color is None:
                color = ManaType.COLORLESS
            ctrl.mana_pool.add(color, 1)

        return [
            ManaAbility(
                cost=_colorless_cost,
                mana_produced=_colorless_produced,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_anycolor_cost,
                mana_produced=_anycolor_produced,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "_is_animated", False):
                return False
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            cost = ManaCost.parse("{5}")
            if not ctrl.mana_pool.can_pay(cost):
                return False
            return ctrl.mana_pool.pay(cost)

        def _effect(game: Any) -> None:
            source._animate()

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: Becomes a 2/4 Wizard creature.",
            )
        ]

    def _animate(self) -> None:
        if self._is_animated:
            return
        self._is_animated = True
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0
        self.is_attacking = False
        self.is_blocking = False
        self.summoning_sick = False
        self.is_token = False
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        if getattr(self, "_is_animated", False):
            self.card_types = set(self.card_types) | {CardType.CREATURE}
            self.subtypes = set(self.subtypes) | {"Wizard"}
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Granted "whenever you cast an instant or sorcery" pump (gap #2)
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.continuous_effects import (
            ContinuousEffect,
            DURATION_END_OF_TURN,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            if not getattr(source, "_is_animated", False):
                return False
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "player", None) or getattr(
                event, "controller", None
            )
            if caster is not ctrl:
                return False
            return _is_instant_or_sorcery(getattr(event, "card", None))

        def _effect(game: "GameState") -> None:
            def _apply(g: Any) -> None:
                source.modified_power = getattr(source, "modified_power", 0) + 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
