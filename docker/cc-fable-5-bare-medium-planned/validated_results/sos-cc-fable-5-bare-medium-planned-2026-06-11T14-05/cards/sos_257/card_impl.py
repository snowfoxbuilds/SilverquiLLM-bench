"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_COLORS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature
    gets +1/+0 until end of turn." It's still a land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n{T}, Pay 1 life: Add one mana of any color. "
            "Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Creature attributes used once animated (and harmlessly inert
        # before then).
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.damage_marked: int = 0
        self.summoning_sick: bool = False
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.is_token: bool = False
        self.dealt_deathtouch_damage: bool = False

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        """Reset for continuous-effect recalculation, keeping the animated
        identity (the {5} ability changes the object's baseline)."""
        super()._reset_characteristics()
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_and_life_cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None or getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_any_color_restricted(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            try:
                chosen = controller.choose(_COLORS, "choose a color of mana to add")
            except Exception:
                chosen = _COLORS[0]
            if chosen not in _COLORS:
                chosen = _COLORS[0]
            controller.mana_pool.add(chosen, 1, restriction="instant_or_sorcery")

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_life_cost,
                mana_produced=_add_any_color_restricted,
                description="{T}, Pay 1 life: Add one mana of any color. "
                "Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _mana_cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _animate(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return
            # Mutate in place: it becomes a 2/4 Wizard creature and is
            # still a land.  The new identity is the permanent baseline,
            # so the original-characteristic snapshots are updated too.
            source.card_types.add(CardType.CREATURE)
            source._original_card_types = frozenset(source.card_types)
            source.subtypes.add("Wizard")
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4
            source._register_pump_trigger(game)

        return [
            ActivatedAbility(
                cost=_mana_cost,
                effect=_animate,
                description="{5}: If this land isn't a creature, it becomes "
                "a 2/4 Wizard creature. It's still a land.",
            )
        ]

    def _register_pump_trigger(self, game: "GameState") -> None:
        from engine.continuous_effects import (
            DURATION_END_OF_TURN,
            ContinuousEffect,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            if CardType.CREATURE not in source.card_types:
                return False
            spell_card = getattr(event, "card", None)
            card_types = getattr(spell_card, "card_types", set())
            return bool(card_types & {CardType.INSTANT, CardType.SORCERY})

        def _effect(game: "GameState") -> None:
            def _apply(g: Any) -> None:
                source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )
            source.modified_power += 1  # immediate, idempotent under apply_all

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller or game.active_player,
            )
        )
