"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}

_COLOR_OPTIONS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


def _tap_cost(game: "GameState", source: Any) -> bool:
    """Generic tap cost — fail if already tapped."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


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
        self.is_animated: bool = False

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _add_colorless(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _restricted_cost(game: "GameState", s: Any) -> bool:
            ctrl = s.controller
            if getattr(s, "is_tapped", False):
                return False
            if ctrl is None or ctrl.life < 1:
                return False
            s.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_restricted_any(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            color = ctrl.choose(_COLOR_OPTIONS, "Choose a color of mana to add")
            if color not in _COLOR_OPTIONS:
                color = ManaType.WHITE
            ctrl.mana_pool.add_restricted(color, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_restricted_cost,
                mana_produced=_add_restricted_any,
                description="{T}, Pay 1 life: Add one mana of any color "
                "(instant/sorcery only).",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _five_cost(game: "GameState", s: Any) -> bool:
            ctrl = s.controller
            if ctrl is None:
                return False
            cost = ManaCost(generic=5)
            # Restricted (instant/sorcery-only) mana cannot pay an ability cost.
            if not ctrl.mana_pool.can_pay(cost, instant_or_sorcery=False):
                return False
            return ctrl.mana_pool.pay(cost, instant_or_sorcery=False)

        def _five_effect(game: "GameState") -> None:
            # "If this land isn't a creature" — gate read from self.
            if CardType.CREATURE in source.card_types:
                return
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_five_cost,
                effect=_five_effect,
                description="{5}: Animate into a 2/4 Wizard (still a land).",
            )
        ]

    # ------------------------------------------------------------------
    # Animation (card-local in-place mutation)
    # ------------------------------------------------------------------

    def _animate(self, game: "GameState") -> None:
        """Become a 2/4 Wizard creature in place; it stays a land."""
        self.is_animated = True
        # Add the Creature type and persist it across continuous-effect resets.
        self.card_types = self.card_types | {CardType.CREATURE}
        self._original_card_types = frozenset(self.card_types)
        self.subtypes = self.subtypes | {"Wizard"}
        # Creature combat stats (plain attributes; the land has no Creature
        # machinery of its own).  Power is recomputed by the layer system; the
        # pump trigger adds an until-end-of-turn +1/+0 effect.
        self.base_power = 2
        self.base_toughness = 4
        self.power = 2
        self.toughness = 4
        self.damage_marked = 0
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.summoning_sick = False  # has been on the battlefield
        self.is_attacking = False
        self.is_blocking = False
        self.is_token = False
        self.dealt_deathtouch_damage = False
        self._register_pump_trigger(game)

    def _reset_characteristics(self) -> None:
        # Reset card_types/keywords (CardImpl); when animated, also reset the
        # pump-modified power back to base before continuous effects reapply.
        super()._reset_characteristics()
        if getattr(self, "is_animated", False):
            self.power = self.base_power
            self.toughness = self.base_toughness

    def _register_pump_trigger(self, game: "GameState") -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            if CardType.CREATURE not in source.card_types:
                return False
            ctrl = source.controller
            caster = getattr(event, "controller", None) or getattr(
                event, "player", None
            )
            if caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            return bool(getattr(card, "card_types", set()) & _SPELL_TYPES)

        def _effect(game: "GameState") -> None:
            from engine.continuous_effects import (
                DURATION_END_OF_TURN,
                ContinuousEffect,
                Layer,
                SubLayer,
            )

            def _pump(g: "GameState") -> None:
                source.power = getattr(source, "power", source.base_power) + 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_pump,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
