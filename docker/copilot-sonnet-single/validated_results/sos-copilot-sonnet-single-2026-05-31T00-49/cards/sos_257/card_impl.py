"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Land, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature
    gets +1/+0 until end of turn." It's still a land.

    ENGINE LIMITATION: The "spend this mana only to cast an instant or
    sorcery spell" restriction is noted on the mana produced but not
    enforced by the engine. The creature state persists until explicitly
    reset.

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
        self._is_creature_form: bool = False
        # Creature characteristics when animated.
        self._creature_base_power: int = 2
        self._creature_base_toughness: int = 4
        self.modified_power: int = 0
        self.modified_toughness: int = 0

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        land = self

        def _basic_cost(game: Any) -> bool:
            if getattr(land, "is_tapped", True):
                return False
            land.is_tapped = True
            return True

        def _basic_mana(game: Any) -> dict[ManaType, int]:
            return {ManaType.COLORLESS: 1}

        def _color_cost(game: Any) -> bool:
            ctrl = getattr(land, "controller", None)
            if ctrl is None:
                return False
            if getattr(land, "is_tapped", True):
                return False
            if ctrl.life <= 1:
                return False
            land.is_tapped = True
            ctrl.life -= 1
            return True

        def _color_mana(game: Any) -> dict[ManaType, int]:
            # ENGINE LIMITATION: "spend only to cast instant/sorcery" not enforced.
            # Default: add White (controller can script other colors in tests).
            return {ManaType.WHITE: 1}

        return [
            ManaAbility(
                cost=_basic_cost,
                mana_produced=_basic_mana,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_color_cost,
                mana_produced=_color_mana,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: Animate
    # ------------------------------------------------------------------

    def animate(self, game: "GameState") -> bool:
        """Pay {5} to animate this land into a 2/4 Wizard creature.

        Returns True if the animation succeeded (costs were paid and land
        was not already a creature).
        """
        if self._is_creature_form:
            return False  # Already a creature.
        controller = self.controller
        if controller is None:
            return False
        # Check {5} generic mana.
        from engine.types import ManaCost as MC
        cost = MC.parse("{5}")
        if not controller.mana_pool.can_pay(cost):
            return False
        controller.mana_pool.pay(cost)
        self._become_creature(game)
        return True

    def _become_creature(self, game: "GameState") -> None:
        """Transform this land into a 2/4 Wizard creature (still a land)."""
        self._is_creature_form = True
        self.card_types = self.card_types | {CardType.CREATURE}
        self.subtypes = getattr(self, "subtypes", set()) | {"Wizard"}
        self.modified_power = self._creature_base_power
        self.modified_toughness = self._creature_base_toughness
        # Register the spell-cast pump trigger.
        self._register_pump_trigger(game)

    def _register_pump_trigger(self, game: "GameState") -> None:
        """Register +1/+0 until EOT when an instant/sorcery is cast."""
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
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            spell_ctrl = getattr(event, "controller", None) or getattr(event, "player", None)
            if spell_ctrl is not ctrl:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _effect(game: "GameState") -> None:
            if not source._is_creature_form:
                return
            src = source

            def _apply(g: Any) -> None:
                src.modified_power += 1

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

    # ------------------------------------------------------------------
    # Creature-like properties (used when in creature form)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        """Return power when in creature form, else 0."""
        if self._is_creature_form:
            return self.modified_power
        return 0

    @property
    def toughness(self) -> int:
        """Return toughness when in creature form, else 0."""
        if self._is_creature_form:
            return self.modified_toughness
        return 0

    @property
    def base_power(self) -> int:
        """Base power (2 when animated, 0 otherwise)."""
        return self._creature_base_power if self._is_creature_form else 0

    @property
    def base_toughness(self) -> int:
        """Base toughness (4 when animated, 0 otherwise)."""
        return self._creature_base_toughness if self._is_creature_form else 0

