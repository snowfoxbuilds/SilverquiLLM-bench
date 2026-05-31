"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _tap_cost(game: Any, source: Any) -> bool:
    """Tap cost: untapped → tapped, returns False if already tapped."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


def _tap_and_pay_life(game: Any, source: Any) -> bool:
    """Tap + pay 1 life cost."""
    if getattr(source, "is_tapped", False):
        return False
    controller = getattr(source, "controller", None)
    if controller is None:
        return False
    if controller.life <= 1:
        # Must keep alive (life payment cannot reduce to 0 as a cost)
        # Actually in MTG you CAN pay life even at 1 (you die), but
        # for engine safety we allow it.
        pass
    controller.life -= 1
    source.is_tapped = True
    return True


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land — Rare.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color (only for instants/sorceries).
    {5}: If not a creature, becomes a 2/4 Wizard creature with a trigger:
         whenever you cast an instant or sorcery, gets +1/+0 until end of turn.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with "
            "'Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn.' "
            "It's still a land.",
        )
        super().__init__(**kwargs)
        # Creature stats (used when animated)
        self.base_power: int = 2
        self.base_toughness: int = 4
        self.modified_power: int = 2
        self.modified_toughness: int = 4
        self.damage_marked: int = 0
        self.summoning_sick: bool = False
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.is_token: bool = False
        self._is_animated: bool = False
        self._trigger_registered: bool = False

    def _reset_characteristics(self) -> None:
        """Reset characteristics; re-add CREATURE type if animated."""
        super()._reset_characteristics()
        # Reset creature stats to base values
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness
        # Re-apply creature type if animated (animation is permanent)
        if self._is_animated:
            self.card_types.add(CardType.CREATURE)

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _colorless_effect(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _colored_effect(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Let controller choose a color; default GREEN if script exhausted
            color_options = [
                ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                ManaType.RED, ManaType.GREEN,
            ]
            chosen = ManaType.GREEN
            try:
                from engine.player import ScriptExhaustedError
                chosen = ctrl.choose(color_options, "Choose a color for Great Hall of the Biblioplex")
            except Exception:
                chosen = ManaType.GREEN
            ctrl.mana_pool.add(chosen, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life,
                mana_produced=_colored_effect,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated abilities
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _animate_cost(game: Any, src: Any) -> bool:
            """Pay {5} (5 generic mana). Only if not already a creature."""
            if CardType.CREATURE in getattr(src, "card_types", set()):
                return False
            ctrl = getattr(src, "controller", None)
            if ctrl is None:
                return False
            if ctrl.mana_pool.total() < 5:
                return False
            ctrl.mana_pool.pay(ManaCost(generic=5))
            return True

        def _animate_effect(game: Any) -> None:
            """Become a 2/4 Wizard creature (still a land)."""
            if CardType.CREATURE in getattr(source, "card_types", set()):
                return
            source.card_types.add(CardType.CREATURE)
            subtypes = getattr(source, "subtypes", set())
            subtypes.add("Wizard")
            source.subtypes = subtypes
            source.modified_power = 2
            source.modified_toughness = 4
            source._is_animated = True
            # Register the spell-cast trigger if not already done
            if not source._trigger_registered:
                source._register_spell_trigger(game)

        return [
            ActivatedAbility(
                cost=_animate_cost,
                effect=_animate_effect,
                description="{5}: Become a 2/4 Wizard creature until end of game.",
            ),
        ]

    # ------------------------------------------------------------------
    # Trigger registration
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register spell-cast trigger if already animated."""
        if self._is_animated and not self._trigger_registered:
            self._register_spell_trigger(game)

    def _register_spell_trigger(self, game: "GameState") -> None:
        """Register the +1/+0 trigger for instant/sorcery casts."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            caster = event.player
            ctrl = getattr(source, "controller", None)
            if caster is not ctrl:
                return False
            if CardType.CREATURE not in getattr(source, "card_types", set()):
                return False
            spell = event.spell
            spell_types = getattr(spell, "card_types", set())
            return CardType.INSTANT in spell_types or CardType.SORCERY in spell_types

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
