"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}

_COLORS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


def _tap_cost(game: "GameState", source: Any) -> bool:
    """Tap cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


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
            "creature with \"Whenever you cast an instant or sorcery "
            "spell, this creature gets +1/+0 until end of turn.\" It's "
            "still a land.",
        )
        super().__init__(**kwargs)
        self._animated: bool = False
        # Creature attributes — meaningful only once animated.
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
        self._base_plus_one_counters: int = 0
        self._base_minus_one_counters: int = 0

    # ------------------------------------------------------------------
    # Creature stats — only visible once animated (state-based actions
    # key off hasattr(obj, "toughness"), so these must raise before then).
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        if not self._animated:
            raise AttributeError("Great Hall is not a creature")
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        if not self._animated:
            raise AttributeError("Great Hall is not a creature")
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        """Reset for continuous-effect recalculation (mirrors Creature)."""
        super()._reset_characteristics()
        if self._animated:
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness
            self.plus_one_counters = self._base_plus_one_counters
            self.minus_one_counters = self._base_minus_one_counters

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _add_colorless(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life_cost(game: "GameState", src: Any) -> bool:
            controller = src.controller
            if controller is None or controller.life < 1:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_restricted_any_color(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            chosen = controller.choose(list(_COLORS), "Choose a color of mana")
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
                cost=_tap_pay_life_cost,
                mana_produced=_add_restricted_any_color,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5} animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five_cost(game: "GameState", src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost.parse("{5}"))

        def _animate(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return  # already a creature — no effect
            source._animated = True
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4
            source.subtypes.add("Wizard")
            source.card_types.add(CardType.CREATURE)
            # The animation has no duration — make it survive continuous-
            # effect recalculation by updating the original snapshot.
            source._original_card_types = frozenset(source.card_types)
            # The land has been on the battlefield, so it can act at once.
            # DELIBERATE LIMITATION: a land played and animated the same
            # turn would really have summoning sickness; not tracked.
            source.summoning_sick = False
            source._register_pump_trigger(game)

        return [
            ActivatedAbility(
                cost=_pay_five_cost,
                effect=_animate,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with \"Whenever you cast an instant or "
                    "sorcery spell, this creature gets +1/+0 until end of "
                    "turn.\" It's still a land."
                ),
            )
        ]

    def _register_pump_trigger(self, game: "GameState") -> None:
        """Animated ability: your instant/sorcery casts give +1/+0 until EOT."""
        from engine.continuous_effects import (
            ContinuousEffect,
            DURATION_END_OF_TURN,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not getattr(source, "controller", None):
                return False
            spell = getattr(event, "card", None)
            return bool(getattr(spell, "card_types", set()) & _SPELL_TYPES)

        def _effect(game: "GameState") -> None:
            def _apply(game: "GameState") -> None:
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
            game.effect_manager.apply_all(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=getattr(self, "controller", None) or game.active_player,
            )
        )
