"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility, ActivatedAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """{T}: Add {C}.
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
        # Animation state (deliberate card-local flag).
        self._animated = False
        # Creature stats for when animated.
        self.base_power = 0
        self.base_toughness = 0
        self.modified_power = 0
        self.modified_toughness = 0
        self.damage_marked = 0
        self.summoning_sick = False
        self.is_attacking = False
        self.is_blocking = False
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.dealt_deathtouch_damage = False

    def _reset_characteristics(self) -> None:
        """Reset card_types and P/T for continuous-effect recalculation."""
        super()._reset_characteristics()  # resets card_types to {LAND}
        # Reset modified P/T to base for this turn (animation effect re-applies later).
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    # -- Mana abilities -------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        land = self

        def _tap_c_cost(g: Any) -> bool:
            if land.is_tapped:
                return False
            land.is_tapped = True
            return True

        def _tap_c_mana(g: Any) -> None:
            ctrl = getattr(land, "controller", None)
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_life_cost(g: Any) -> bool:
            ctrl = getattr(land, "controller", None)
            if land.is_tapped or ctrl is None or ctrl.life < 1:
                return False
            land.is_tapped = True
            ctrl.life -= 1
            return True

        def _tap_life_mana(g: Any) -> None:
            """Add one restricted colored mana (instant/sorcery only)."""
            ctrl = getattr(land, "controller", None)
            if ctrl is None:
                return
            color_options = [
                ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                ManaType.RED, ManaType.GREEN,
            ]
            try:
                chosen = ctrl.choose_card(color_options, "Choose a color for restricted mana")
            except Exception:
                chosen = color_options[0]
            if chosen not in color_options:
                chosen = color_options[0]
            ctrl.mana_pool.add_restricted(chosen, 1)

        return [
            ManaAbility(
                cost=_tap_c_cost,
                mana_produced=_tap_c_mana,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_life_cost,
                mana_produced=_tap_life_mana,
                description="{T}, Pay 1 life: Add one mana (instant/sorcery only).",
            ),
        ]

    # -- Activated abilities --------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        land = self

        def _animate_cost(g: Any) -> bool:
            ctrl = getattr(land, "controller", None)
            if ctrl is None or land._animated:
                return False
            if not ctrl.mana_pool.can_pay(ManaCost(generic=5)):
                return False
            ctrl.mana_pool.pay(ManaCost(generic=5))
            return True

        def _animate_effect(g: "GameState") -> None:
            if land._animated:
                return
            land._animated = True
            # Set base P/T for the creature (used by _reset_characteristics).
            land.base_power = 2
            land.base_toughness = 4
            land.modified_power = 2
            land.modified_toughness = 4
            # Add Wizard subtype (permanent — no reset for subtypes).
            if not hasattr(land, "subtypes"):
                land.subtypes = set()
            land.subtypes = land.subtypes | {"Wizard"}
            # Register permanent animation continuous effect (Layer 4: type).
            _register_animation_effect(g, land)
            # Register spell-cast pump trigger (E1).
            _register_pump_trigger(g, land)

        return [
            ActivatedAbility(
                cost=_animate_cost,
                effect=_animate_effect,
                description="{5}: Animate into 2/4 Wizard creature (still a land).",
            ),
        ]


def _register_animation_effect(game: "GameState", land: GreatHallOfTheBiblioplex) -> None:
    """Add permanent continuous effect that keeps CREATURE type while animated."""
    from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer

    def _apply(g: "GameState") -> None:
        if land._animated:
            land.card_types.add(CardType.CREATURE)

    eff = ContinuousEffect(
        source=land,
        layer=Layer.TYPE,
        sublayer=None,
        apply=_apply,
        duration=DURATION_PERMANENT,
    )
    game.effect_manager.add(eff)
    game.effect_manager.apply_all(game)


def _register_pump_trigger(game: "GameState", land: GreatHallOfTheBiblioplex) -> None:
    """Register: whenever controller casts IS spell while animated, +1/+0 until EOT."""
    from engine.continuous_effects import (
        ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer,
    )
    from engine.events import SpellCastTriggeredEvent
    from engine.triggers import TriggerRegistration

    def _condition(g: Any, event: Any) -> bool:
        if not land._animated:
            return False
        caster = getattr(event, "controller", None)
        if caster is not getattr(land, "controller", None):
            return False
        card = getattr(event, "card", None)
        if card is None:
            return False
        return bool(getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})

    def _effect(g: "GameState") -> None:
        if not land._animated:
            return

        def _apply(g2: "GameState") -> None:
            land.modified_power += 1

        eff = ContinuousEffect(
            source=land,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_END_OF_TURN,
        )
        g.effect_manager.add(eff)
        g.effect_manager.apply_all(g)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=land,
            controller=getattr(land, "controller", None),
        )
    )
