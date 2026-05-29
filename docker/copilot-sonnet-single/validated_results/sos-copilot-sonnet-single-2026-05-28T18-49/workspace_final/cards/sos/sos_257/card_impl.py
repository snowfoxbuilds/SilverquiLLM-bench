"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility, ActivatedAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
        an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
        "Whenever you cast an instant or sorcery spell, this creature gets
        +1/+0 until end of turn." It's still a land.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to "
            "cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature "
            "with \"Whenever you cast an instant or sorcery spell, this creature "
            "gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        self._is_creature: bool = False
        # Creature stats when animated
        self._anim_base_power: int = 2
        self._anim_base_toughness: int = 4

    @property
    def power(self) -> int:
        """Current power (only meaningful when animated)."""
        if self._is_creature:
            return self._anim_base_power + getattr(self, "_power_bonus", 0)
        return 0

    @property
    def toughness(self) -> int:
        """Current toughness (only meaningful when animated)."""
        if self._is_creature:
            return self._anim_base_toughness
        return 0

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return {T}: Add {C} and {T}, pay 1 life: Add any color mana."""
        land = self

        def _cost_tap(game: Any) -> bool:
            """Tap the land."""
            if getattr(land, "is_tapped", False):
                return False
            land.is_tapped = True
            return True

        def _produce_colorless(game: Any) -> dict:
            return {ManaType.COLORLESS: 1}

        def _cost_tap_life(game: Any) -> bool:
            """Tap the land and pay 1 life."""
            if getattr(land, "is_tapped", False):
                return False
            controller = getattr(land, "controller", None)
            if controller is None:
                return False
            if controller.life <= 1:
                return False
            land.is_tapped = True
            controller.life -= 1
            return True

        def _produce_any_color(game: Any) -> dict:
            """Add any color of mana (player chooses)."""
            controller = getattr(land, "controller", None)
            if controller is None:
                return {ManaType.COLORLESS: 1}
            color_options = [ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN]
            try:
                chosen = controller.choose(color_options, "Choose a color of mana")
                if chosen not in color_options:
                    chosen = ManaType.COLORLESS
            except Exception:
                chosen = ManaType.COLORLESS
            return {chosen: 1}

        return [
            ManaAbility(
                cost=_cost_tap,
                mana_produced=_produce_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_cost_tap_life,
                mana_produced=_produce_any_color,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return {5}: Animate this land."""
        land = self

        def _animate_cost(game: Any) -> bool:
            """Pay {5} to animate."""
            if land._is_creature:
                return False  # Already a creature
            controller = getattr(land, "controller", None)
            if controller is None:
                return False
            animate_cost = ManaCost.parse("{5}")
            if not controller.mana_pool.can_pay(animate_cost):
                return False
            controller.mana_pool.pay(animate_cost)
            return True

        def _animate_effect(game: Any) -> None:
            """Become a 2/4 Wizard creature that's still a land."""
            if land._is_creature:
                return
            land._is_creature = True
            land._power_bonus = 0
            land.card_types = land.card_types | {CardType.CREATURE}
            if not hasattr(land, "subtypes"):
                land.subtypes = set()
            land.subtypes = land.subtypes | {"Wizard"}
            if not hasattr(land, "keywords"):
                land.keywords = Keyword(0)

            # Register the +1/+0 trigger
            from engine.triggers import TriggerRegistration
            from engine.events import SpellCastTriggeredEvent
            from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer

            controller = getattr(land, "controller", None) or game.active_player

            def _spell_condition(game: Any, event: Any) -> bool:
                caster = getattr(event, "player", None) or getattr(event, "controller", None)
                if caster is not controller:
                    return False
                if not land._is_creature:
                    return False
                spell = getattr(event, "spell", None) or getattr(event, "card", None)
                if spell is None:
                    return False
                ctypes = getattr(spell, "card_types", set())
                return CardType.INSTANT in ctypes or CardType.SORCERY in ctypes

            def _power_bump_effect(game: Any) -> None:
                """Add +1/+0 until end of turn."""
                if not land._is_creature:
                    return
                land._power_bonus = getattr(land, "_power_bonus", 0) + 1

            game.trigger_manager.register(TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_spell_condition,
                effect=_power_bump_effect,
                source=land,
                controller=controller,
            ))

        return [
            ActivatedAbility(
                cost=_animate_cost,
                effect=_animate_effect,
                description="{5}: Become a 2/4 Wizard creature until end of turn.",
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        """Nothing to register at ETB — animation is an activated ability."""
        pass

