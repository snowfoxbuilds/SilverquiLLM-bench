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
from engine.types import CardType, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """{T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with "
            "\"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn.\" "
            "It's still a land.",
        )
        super().__init__(**kwargs)
        # Animation state flag — True once ability 3 has been activated.
        self._is_animated: bool = False
        # Permanent continuous effect handles for animation (set on activation).
        self._animation_type_effect: ContinuousEffect | None = None
        self._animation_pt_effect: ContinuousEffect | None = None
        # Creature-like attributes (used by the effect system and combat when animated).
        self.base_power: int = 2
        self.base_toughness: int = 4
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.damage_marked: int = 0
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.summoning_sick: bool = False
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self._base_plus_one_counters: int = 0
        self._base_minus_one_counters: int = 0

    # ------------------------------------------------------------------
    # Characteristic reset — called by EffectManager before reapplication
    # ------------------------------------------------------------------

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self.modified_power = 0
        self.modified_toughness = 0
        self.plus_one_counters = self._base_plus_one_counters
        self.minus_one_counters = self._base_minus_one_counters

    # ------------------------------------------------------------------
    # Power/toughness properties (creature mode)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        """Current power including counter modifications."""
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        """Current toughness including counter modifications."""
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    # ------------------------------------------------------------------
    # Mana abilities — resolve immediately without the stack
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        # Ability 1: {T}: Add {C}
        def _colorless_effect(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        # Ability 2: {T}, Pay 1 life: Add one mana of any color
        def _life_tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            ctrl = getattr(src, "controller", None)
            if ctrl is None:
                return False
            if ctrl.life < 1:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _any_color_effect(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Default to adding blue mana; tests can override via _chosen_mana_type.
            chosen_type = getattr(source, "_chosen_mana_type", None)
            if chosen_type is None:
                # Try to ask the controller; fall back to BLUE.
                try:
                    from engine.types import ManaType as MT
                    options = [MT.WHITE, MT.BLUE, MT.BLACK, MT.RED, MT.GREEN]
                    chosen_type = ctrl.choose(options, "Choose a color for Great Hall mana")
                except Exception:
                    chosen_type = ManaType.BLUE
            ctrl.mana_pool.add(chosen_type, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_life_tap_cost,
                mana_produced=_any_color_effect,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated abilities — go on the stack
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _five_mana_cost(game: Any, src: Any) -> bool:
            """Pay {5} and check the land isn't already a creature."""
            if CardType.CREATURE in getattr(src, "card_types", set()):
                return False
            ctrl = getattr(src, "controller", None)
            if ctrl is None:
                return False
            from engine.types import ManaCost as MC
            cost = MC(generic=5)
            if not ctrl.mana_pool.can_pay(cost):
                return False
            ctrl.mana_pool.pay(cost)
            return True

        def _animate_effect(game: Any) -> None:
            """Animate this land into a 2/4 Wizard creature (permanent)."""
            if source._is_animated:
                return  # Already animated; no-op.
            source._is_animated = True
            # Add Wizard subtype.
            source.subtypes.add("Wizard")
            # --- Layer 4: add CREATURE to card_types permanently ---
            def _type_apply(game: Any) -> None:
                source.card_types.add(CardType.CREATURE)

            type_eff = ContinuousEffect(
                source=source,
                layer=Layer.TYPE,
                apply=_type_apply,
                duration=DURATION_PERMANENT,
            )
            game.effect_manager.add(type_eff)
            source._animation_type_effect = type_eff

            # --- Layer 7b: set P/T to 2/4 permanently ---
            def _pt_apply(game: Any) -> None:
                source.modified_power = 2
                source.modified_toughness = 4

            pt_eff = ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.SET_PT,
                apply=_pt_apply,
                duration=DURATION_PERMANENT,
            )
            game.effect_manager.add(pt_eff)
            source._animation_pt_effect = pt_eff

            # Immediately apply so card_types and P/T reflect the change now.
            game.effect_manager.apply_all(game)

            # Register the instant/sorcery trigger now that we're a creature.
            _register_spell_trigger(game, source)

        return [
            ActivatedAbility(
                cost=_five_mana_cost,
                effect=_animate_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                    "creature with the triggered ability."
                ),
            )
        ]

    # ------------------------------------------------------------------
    # Trigger registration — ETB (registers on-enter trigger to watch
    # for instants/sorceries while animated)
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """When already animated on entry, register the spell trigger."""
        if self._is_animated:
            _register_spell_trigger(game, self)


# ---------------------------------------------------------------------------
# Helper — register the "+1/+0 on instant/sorcery" trigger
# ---------------------------------------------------------------------------

def _register_spell_trigger(game: "GameState", source: GreatHallOfTheBiblioplex) -> None:
    """Register: whenever controller casts an instant or sorcery, +1/+0 until EOT."""
    from engine.events import SpellCastTriggeredEvent
    from engine.triggers import TriggerRegistration

    controller = getattr(source, "controller", None) or game.active_player

    def _condition(game: Any, event: Any) -> bool:
        # Only fire when source is still animated.
        if not source._is_animated:
            return False
        # Only fire for controller's casts.
        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if caster is not getattr(source, "controller", None):
            return False
        # Spell must be an instant or sorcery.
        spell_obj = getattr(event, "spell", None)
        card = getattr(spell_obj, "source", spell_obj) if spell_obj else None
        if card is None:
            return False
        types = getattr(card, "card_types", set())
        return CardType.INSTANT in types or CardType.SORCERY in types

    def _effect(game: Any) -> None:
        if not source._is_animated:
            return

        def _apply(game: Any) -> None:
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
            source=source,
            controller=controller,
        )
    )
