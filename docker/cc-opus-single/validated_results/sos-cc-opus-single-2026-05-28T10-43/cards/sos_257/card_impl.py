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
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex -- Land

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
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
            "only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            "creature with \"Whenever you cast an instant or sorcery spell, "
            "this creature gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        # Creature stats when animated
        self._is_animated: bool = False
        self._power_bonus: int = 0

    # ------------------------------------------------------------------
    # Continuous-effect reset support
    # ------------------------------------------------------------------

    def _reset_characteristics(self) -> None:
        """Reset mutable characteristics, including power bonus."""
        super()._reset_characteristics()
        self._power_bonus = 0

    # ------------------------------------------------------------------
    # Properties for creature stats after animation
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        """Current power (only meaningful when animated)."""
        if self._is_animated:
            return 2 + self._power_bonus
        return None  # type: ignore[return-value]

    @property
    def toughness(self) -> int:
        """Current toughness (only meaningful when animated)."""
        if self._is_animated:
            return 4
        return None  # type: ignore[return-value]

    @property
    def base_power(self) -> int | None:
        if self._is_animated:
            return 2
        return None

    @property
    def base_toughness(self) -> int | None:
        if self._is_animated:
            return 4
        return None

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _colorless_tap_cost(game: Any) -> bool:
            if source.is_tapped:
                return False
            source.is_tapped = True
            return True

        def _colorless_mana_produced(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _any_color_tap_cost(game: Any) -> bool:
            if source.is_tapped:
                return False
            controller = source.controller
            if controller is None or controller.life < 1:
                return False
            source.is_tapped = True
            controller.life -= 1
            return True

        def _any_color_mana_produced(game: Any) -> None:
            # ENGINE LIMITATION: The engine does not support conditional mana
            # spending restrictions. This should only be usable to cast
            # instant or sorcery spells. The restriction is not enforced here.
            controller = source.controller
            if controller is not None:
                color_options = [
                    ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                    ManaType.RED, ManaType.GREEN,
                ]
                chosen_color = controller.choose(
                    color_options,
                    "Choose a color of mana to produce",
                )
                controller.mana_pool.add(chosen_color, 1)

        return [
            ManaAbility(
                cost=_colorless_tap_cost,
                mana_produced=_colorless_mana_produced,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_any_color_tap_cost,
                mana_produced=_any_color_mana_produced,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated abilities
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _animate_cost(game: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _animate_effect(game: Any) -> None:
            # "If this land isn't a creature..."
            if CardType.CREATURE in source.card_types:
                return
            # It becomes a 2/4 Wizard creature. It's still a land.
            source.card_types.add(CardType.CREATURE)
            source.subtypes.add("Wizard")
            source._is_animated = True
            source._power_bonus = 0

            # Register the triggered ability:
            # "Whenever you cast an instant or sorcery spell, this creature
            #  gets +1/+0 until end of turn."
            def _spell_cast_condition(game: Any, event: Any) -> bool:
                # Must be controlled by the same player
                if event.controller is not source.controller:
                    return False
                spell = event.spell
                if spell is None:
                    return False
                spell_types = getattr(spell, "card_types", set())
                return (CardType.INSTANT in spell_types or
                        CardType.SORCERY in spell_types)

            def _pump_effect(game: Any) -> None:
                # Register a ContinuousEffect with DURATION_END_OF_TURN
                # so the +1/+0 bonus resets at end of turn.
                def _apply_pump(_game: Any) -> None:
                    source._power_bonus += 1

                effect = ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_pump,
                    duration=DURATION_END_OF_TURN,
                )
                game.effect_manager.add(effect)
                # Apply immediately so the bonus is visible right away
                # (without requiring a full apply_all cycle).
                _apply_pump(game)

            trigger = TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_spell_cast_condition,
                effect=_pump_effect,
                source=source,
                controller=source.controller,
            )
            game.trigger_manager.register(trigger)

        return [
            ActivatedAbility(
                cost=_animate_cost,
                effect=_animate_effect,
                description="{5}: Animate into 2/4 Wizard creature.",
            ),
        ]
