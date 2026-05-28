"""Card implementation for Great Hall of the Biblioplex (sos_257)."""

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


def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap. Returns False if already tapped."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


class GreatHallOfTheBiblioplex(Land):
    """{T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature gets
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
            "creature with \"Whenever you cast an instant or sorcery spell, this "
            "creature gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        # Creature tracking
        self.is_creature: bool = False
        # Power/toughness (only meaningful after creature transformation)
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        # Temporary power bonuses from instant/sorcery casts
        self.power_bonus: int = 0
        # Track whether the spell-cast trigger has been registered
        self._trigger_registered: bool = False

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return the two mana abilities: tap for colorless, tap + 1 life for any color."""
        source = self

        # --- Ability 1: {T}: Add {C} ---
        def _colorless_effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        # --- Ability 2: {T}, Pay 1 life: Add one mana of any color ---
        def _life_cost(game: Any, src: Any) -> bool:
            """Tap the source and pay 1 life."""
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            # Pay 1 life from the controller
            controller = getattr(src, "controller", None)
            if controller is not None:
                controller.life -= 1
            return True

        def _colored_effect(game: Any) -> None:
            """Produce one mana of any color (controller chooses)."""
            controller = source.controller
            if controller is None:
                return
            color_options = [
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            ]
            try:
                chosen_color = controller.choose(color_options, "Choose a color of mana to produce")
            except Exception:
                chosen_color = ManaType.WHITE
            controller.mana_pool.add(chosen_color, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_life_cost,
                mana_produced=_colored_effect,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated abilities
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the {5} creature-transformation ability."""
        source = self

        def _transform_cost(game: Any, src: Any) -> bool:
            """Pay {5} generic mana."""
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _transform_effect(game: Any) -> None:
            """If not already a creature, become a 2/4 Wizard creature."""
            source.activate_creature_form(game)

        return [
            ActivatedAbility(
                cost=_transform_cost,
                effect=_transform_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                    "creature with the instant/sorcery trigger. It's still a land."
                ),
            )
        ]

    # ------------------------------------------------------------------
    # Continuous-effect reset support
    # ------------------------------------------------------------------

    def _reset_characteristics(self) -> None:
        """Reset mutable characteristics to their original (pre-effect) values.

        Called by :meth:`EffectManager.apply_all` before reapplying effects.
        When in creature form, also resets modified_power/toughness to base values.
        """
        super()._reset_characteristics()
        if self.is_creature:
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Creature transformation
    # ------------------------------------------------------------------

    def activate_creature_form(self, game: Any) -> None:
        """Transform this land into a 2/4 Wizard creature (one-time, idempotent)."""
        if self.is_creature:
            # Already a creature — no-op
            return
        self.is_creature = True
        self.card_types.add(CardType.CREATURE)
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.subtypes.add("Wizard")
        # Register the trigger now that we're a creature
        self._register_spell_cast_trigger(game)

    # ------------------------------------------------------------------
    # Trigger registration
    # ------------------------------------------------------------------

    def _register_spell_cast_trigger(self, game: Any) -> None:
        """Register the SpellCastTriggeredEvent trigger for +1/+0 until end of turn."""
        if self._trigger_registered:
            return
        source = self
        controller = getattr(self, "controller", None)
        if controller is None:
            return

        def _condition(game: Any, event: SpellCastTriggeredEvent) -> bool:
            """Fire only when this card is a creature and an instant/sorcery is cast."""
            if not source.is_creature:
                return False
            spell = event.spell
            if spell is None:
                return False
            spell_types = getattr(spell, "card_types", set())
            is_instant_or_sorcery = (
                CardType.INSTANT in spell_types or CardType.SORCERY in spell_types
            )
            if not is_instant_or_sorcery:
                return False
            return True

        def _effect(game: Any) -> None:
            """Grant +1/+0 until end of turn via a DURATION_END_OF_TURN continuous effect."""
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
            # Immediately apply all effects so modified_power is up to date.
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
        self._trigger_registered = True

    def register_triggers(self, game: Any) -> None:
        """Register triggers; only the spell-cast trigger applies, and only after creature transformation."""
        if self.is_creature and not self._trigger_registered:
            self._register_spell_cast_trigger(game)
        # If not yet a creature, do nothing — the trigger is registered on transformation
