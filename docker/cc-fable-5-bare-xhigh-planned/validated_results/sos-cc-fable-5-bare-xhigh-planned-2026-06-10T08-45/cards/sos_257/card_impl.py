"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.events import SpellCastTriggeredEvent
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

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: GameState, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _colorless_effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life_cost(game: GameState, src: Any) -> bool:
            controller = src.controller
            if controller is None or controller.life < 1:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _restricted_effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            try:
                color = controller.choose(list(_COLORS), "Choose a color of mana")
            except Exception:
                color = ManaType.BLUE
            if color not in _COLORS:
                color = ManaType.BLUE
            controller.mana_pool.add(color, 1, restriction="instant_or_sorcery")

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life_cost,
                mana_produced=_restricted_effect,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: GameState, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _animate(game: GameState) -> None:
            if CardType.CREATURE in source.card_types:
                return
            source._become_creature()

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description="{5}: If this land isn't a creature, it becomes "
                "a 2/4 Wizard creature. It's still a land.",
            )
        ]

    def _become_creature(self) -> None:
        """Mutate in place into a 2/4 Wizard creature (still a land).

        The animation has no duration, so it is baked into the "original"
        characteristics snapshot — continuous-effect recalculation must
        not strip it.
        """
        self.card_types.add(CardType.CREATURE)
        self.subtypes.add("Wizard")
        self._original_card_types = frozenset(self.card_types)
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
        self.dealt_deathtouch_damage = False
        # The land has already been on the battlefield, so the new creature
        # can act immediately (deliberate simplification).
        self.summoning_sick = False

    def _reset_characteristics(self) -> None:
        """Also reset P/T like a creature once animated."""
        super()._reset_characteristics()
        if hasattr(self, "base_power"):
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness
            self.plus_one_counters = self._base_plus_one_counters
            self.minus_one_counters = self._base_minus_one_counters

    @property
    def power(self) -> int:
        """Current power — only meaningful once animated (mirrors Creature)."""
        if not hasattr(self, "base_power"):
            raise AttributeError("power")
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        """Current toughness — only meaningful once animated (mirrors Creature)."""
        if not hasattr(self, "base_toughness"):
            raise AttributeError("toughness")
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    # ------------------------------------------------------------------
    # Animated pump: whenever you cast an instant/sorcery, +1/+0 until EOT
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
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
            # Only pumps while animated.
            if CardType.CREATURE not in source.card_types:
                return False
            if event.controller is not getattr(source, "controller", None):
                return False
            return bool(_SPELL_TYPES & getattr(event.card, "card_types", set()))

        def _effect(game: GameState) -> None:
            def _apply_pump(g: GameState) -> None:
                ctrl = getattr(source, "controller", None)
                if ctrl is None or not g.get_battlefield(ctrl).contains(source):
                    return
                if CardType.CREATURE in source.card_types:
                    source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_pump,
                    duration=DURATION_END_OF_TURN,
                )
            )
            # Realize the new effect immediately.
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
