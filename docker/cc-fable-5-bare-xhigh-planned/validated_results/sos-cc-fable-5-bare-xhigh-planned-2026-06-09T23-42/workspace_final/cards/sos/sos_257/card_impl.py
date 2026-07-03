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
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard '
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Creature bookkeeping used once animated; harmless before.
        self.damage_marked: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self._base_plus_one_counters: int = 0
        self._base_minus_one_counters: int = 0
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.dealt_deathtouch_damage: bool = False
        self.is_token: bool = False
        self.summoning_sick: bool = False

    # ------------------------------------------------------------------
    # Creature stats — only exposed once animated.  Raising AttributeError
    # pre-animation keeps hasattr() False so state-based actions don't
    # treat the un-animated land as a 0-toughness creature.
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        if CardType.CREATURE not in self.card_types:
            raise AttributeError("Great Hall is not a creature")
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        if CardType.CREATURE not in self.card_types:
            raise AttributeError("Great Hall is not a creature")
        return (
            self.modified_toughness + self.plus_one_counters - self.minus_one_counters
        )

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        if hasattr(self, "base_power"):
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

        def _life_tap_cost(game: "GameState", src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            if not _tap_cost(game, src):
                return False
            controller.life -= 1
            return True

        def _add_restricted_any_color(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            try:
                chosen = controller.choose(list(_COLORS), "Choose a color of mana")
            except Exception:
                chosen = ManaType.BLUE
            if chosen not in _COLORS:
                chosen = ManaType.BLUE
            controller.mana_pool.add_restricted(chosen, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_life_tap_cost,
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

        def _pay_five(game: "GameState", src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            # Restricted mana cannot pay for this — it's not a spell cast.
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _animate(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return  # already a creature — no effect
            source.card_types.add(CardType.CREATURE)
            source.subtypes.add("Wizard")
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4
            # Make the animation survive continuous-effect recalculation.
            source._original_card_types = frozenset(source.card_types)
            # Deliberate simplification: the land has been on the
            # battlefield, so the animated creature is not summoning sick.
            source.summoning_sick = False

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with \"Whenever you cast an instant or "
                    "sorcery spell, this creature gets +1/+0 until end of "
                    "turn.\" It's still a land."
                ),
            )
        ]

    # ------------------------------------------------------------------
    # Animated pump trigger — registered on entry, inert until animated.
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.continuous_effects import (
            DURATION_END_OF_TURN,
            ContinuousEffect,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            if CardType.CREATURE not in source.card_types:
                return False  # not animated yet
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not getattr(source, "controller", None):
                return False
            card = getattr(event, "card", None)
            return bool(getattr(card, "card_types", set()) & _SPELL_TYPES)

        def _effect(game: "GameState") -> None:
            def _apply(g: "GameState") -> None:
                if CardType.CREATURE in source.card_types:
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
            # Apply immediately (the engine recalculates lazily otherwise).
            _apply(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
