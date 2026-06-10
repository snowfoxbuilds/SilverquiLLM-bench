"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, ManaType
from engine.events import SpellCastTriggeredEvent

if TYPE_CHECKING:
    from engine.game_state import GameState


_ANY_COLOR = [
    ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN,
]


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
            "{T}: Add {C}.\n{T}, Pay 1 life: Add one mana of any color. Spend "
            "this mana only to cast an instant or sorcery spell.\n{5}: If this "
            "land isn't a creature, it becomes a 2/4 Wizard creature with "
            '"Whenever you cast an instant or sorcery spell, this creature gets '
            '+1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        self._animated: bool = False

    # ------------------------------------------------------------------
    # Creature characteristics (only meaningful while animated)
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

    def _reset_characteristics(self) -> None:
        """Reset card_types/keywords, then reapply animation if active.

        The animation is a permanent characteristic change, so it must
        survive the periodic reset performed by ``EffectManager.apply_all``
        (mirrors how Progenitus reapplies its protection).
        """
        super()._reset_characteristics()
        if getattr(self, "_animated", False):
            self._apply_animation_characteristics()

    def _apply_animation_characteristics(self) -> None:
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _tap_pay_life_cost(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if getattr(src, "is_tapped", False):
                return False
            if ctrl is None or ctrl.life < 1:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_colorless(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _add_any_color_restricted(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            try:
                color = ctrl.choose(_ANY_COLOR, "Choose a color of mana")
            except Exception:
                color = ManaType.BLUE
            if color not in _ANY_COLOR:
                color = ManaType.BLUE
            # Restricted: usable only to cast an instant or sorcery.
            ctrl.mana_pool.add(color, 1, restricted=True)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_add_colorless,
                        description="{T}: Add {C}."),
            ManaAbility(cost=_tap_pay_life_cost,
                        mana_produced=_add_any_color_restricted,
                        description="{T}, Pay 1 life: Add one mana of any color "
                                    "(instant/sorcery only)."),
        ]

    # ------------------------------------------------------------------
    # Activated ability — {5}: animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if ctrl is None:
                return False
            cost = ManaCost(generic=5)
            # Restricted mana cannot pay for an activated ability (it is not
            # casting a spell), so exclude it.
            if not ctrl.mana_pool.can_pay(cost, instant_or_sorcery=False):
                return False
            return ctrl.mana_pool.pay(cost, instant_or_sorcery=False)

        def _animate(game: "GameState") -> None:
            # "If this land isn't a creature" — only animate once.
            if CardType.CREATURE in source.card_types:
                return
            source._animated = True
            source.base_power = 2
            source.base_toughness = 4
            # Establish the creature runtime fields on this Land instance.
            source.modified_power = 2
            source.modified_toughness = 4
            source.damage_marked = 0
            source.plus_one_counters = 0
            source.minus_one_counters = 0
            source.is_attacking = False
            source.is_blocking = False
            source.is_token = False
            source.dealt_deathtouch_damage = False
            source._base_plus_one_counters = 0
            source._base_minus_one_counters = 0
            # It has been on the battlefield, so it isn't summoning sick.
            source.summoning_sick = False
            source._apply_animation_characteristics()
            source._register_pump_trigger(game)

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description="{5}: Becomes a 2/4 Wizard creature (still a land).",
            )
        ]

    # ------------------------------------------------------------------
    # Pump trigger (granted by the animation)
    # ------------------------------------------------------------------

    def _register_pump_trigger(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        if getattr(source, "_pump_registered", False):
            return
        source._pump_registered = True

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            return bool(
                getattr(card, "card_types", set())
                & {CardType.INSTANT, CardType.SORCERY}
            )

        def _effect(game: "GameState") -> None:
            if not getattr(source, "_animated", False):
                return
            # +1/+0 until end of turn.  Bump immediately so it's visible
            # without an explicit apply_all, and register an end-of-turn
            # continuous effect so it persists across recalcs and clears at
            # cleanup.
            source.modified_power += 1

            def _apply(g: Any) -> None:
                source.modified_power += 1

            game.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            ))

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
