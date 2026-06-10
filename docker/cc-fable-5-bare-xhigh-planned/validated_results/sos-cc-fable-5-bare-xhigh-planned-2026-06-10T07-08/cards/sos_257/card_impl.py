"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


def _instant_or_sorcery(spell: Any) -> bool:
    """Restriction predicate: mana usable only for instant/sorcery spells."""
    return bool(_SPELL_TYPES & getattr(spell, "card_types", set()))


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature gets
    +1/+0 until end of turn." It's still a land.

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

    @property
    def power(self) -> int:
        """Current power (creature-style; meaningful once animated)."""
        return (
            getattr(self, "modified_power", 0)
            + getattr(self, "plus_one_counters", 0)
            - getattr(self, "minus_one_counters", 0)
        )

    @property
    def toughness(self) -> int:
        """Current toughness (creature-style; meaningful once animated)."""
        return (
            getattr(self, "modified_toughness", 0)
            + getattr(self, "plus_one_counters", 0)
            - getattr(self, "minus_one_counters", 0)
        )

    # ------------------------------------------------------------------
    # Mana abilities (printed order)
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        from engine.abilities import tap_cost

        source = self

        def _colorless_effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _life_tap_cost(game: GameState, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            if controller.life < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _any_color_restricted_effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            options = [
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            ]
            chosen = controller.choose(options, "Choose a color of mana to add")
            if chosen not in options:
                chosen = options[0]
            controller.mana_pool.add_restricted(chosen, _instant_or_sorcery)

        return [
            ManaAbility(
                cost=tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_life_tap_cost,
                mana_produced=_any_color_restricted_effect,
                description="{T}, Pay 1 life: Add one mana of any color. "
                "Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation (activated, uses the stack)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _effect(game: GameState) -> None:
            # "If this land isn't a creature" — checked on resolution.
            if CardType.CREATURE in source.card_types:
                return
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: If this land isn't a creature, it becomes "
                "a 2/4 Wizard creature. It's still a land.",
            )
        ]

    def _animate(self, game: GameState) -> None:
        """Become a 2/4 Wizard creature (still a land), with the pump trigger."""
        self.card_types.add(CardType.CREATURE)
        # Update the original snapshot too, so continuous-effect resets
        # (_reset_characteristics) don't strip the creature type.
        self._original_card_types = frozenset(self._original_card_types | {CardType.CREATURE})
        self.subtypes.add("Wizard")
        # Creature state expected by combat / SBAs / counters.
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0
        # Deliberate limitation: summoning sickness is not tracked for the
        # animated land (it has typically been on the battlefield already).
        self.summoning_sick = False
        self.is_attacking = False
        self.is_blocking = False
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0
        self.is_token = False
        self.dealt_deathtouch_damage = False
        self._register_pump_trigger(game)

    def _register_pump_trigger(self, game: GameState) -> None:
        """Whenever you cast an instant/sorcery, +1/+0 until end of turn."""
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
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            return bool(_SPELL_TYPES & getattr(card, "card_types", set()))

        def _effect(game: GameState) -> None:
            def _apply(g: Any) -> None:
                bf = g.get_battlefield(source.controller) if source.controller else None
                if bf is not None and bf.contains(source):
                    source.modified_power += 1

            # Apply immediately and register for recalculation cycles.
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

    def _reset_characteristics(self) -> None:
        """Reset for continuous-effect recalc; keep animation state coherent."""
        super()._reset_characteristics()
        if hasattr(self, "modified_power"):
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness
            self.plus_one_counters = self._base_plus_one_counters
            self.minus_one_counters = self._base_minus_one_counters
