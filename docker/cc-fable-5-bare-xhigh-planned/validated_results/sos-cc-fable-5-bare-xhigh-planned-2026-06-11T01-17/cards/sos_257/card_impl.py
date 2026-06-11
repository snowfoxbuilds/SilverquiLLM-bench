"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
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
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Creature-shaped state, live once animated.  Initialised up front
        # so combat/SBA getattr probes behave while unanimated too.
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

    @property
    def power(self) -> int:
        """Current power including counter modifications."""
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        """Current toughness including counter modifications."""
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        """Mirror Creature's reset so layer-7 effects (the pump) recalc
        idempotently.  card_types reset from _original_card_types, which
        the animation updates so the Creature type survives resets."""
        super()._reset_characteristics()
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness
        self.plus_one_counters = self._base_plus_one_counters
        self.minus_one_counters = self._base_minus_one_counters
        self._cant_attack = False
        self._cant_block = False
        self._cant_be_blocked = False
        self._cant_activate = False
        self._max_attackers_blocked = 1

    # ------------------------------------------------------------------
    # Mana abilities (printed order)
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _colorless_effect(game: GameState) -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life_cost(game: Any, src: Any) -> bool:
            ctrl = getattr(src, "controller", None)
            if ctrl is None or ctrl.life < 1:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _any_color_restricted_effect(game: GameState) -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            colors = [ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                      ManaType.RED, ManaType.GREEN]
            choice = ctrl.choose(colors, "Choose a color of mana to add")
            if choice not in colors:
                choice = colors[0]
            ctrl.mana_pool.add_restricted(choice, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life_cost,
                mana_produced=_any_color_restricted_effect,
                description="{T}, Pay 1 life: Add one mana of any color. "
                "Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            ctrl = getattr(src, "controller", None)
            if ctrl is None:
                return False
            if not ctrl.mana_pool.can_pay(ManaCost(generic=5)):
                return False
            return ctrl.mana_pool.pay(ManaCost(generic=5))

        def _effect(game: GameState) -> None:
            if CardType.CREATURE in source.card_types:
                return  # already a creature — no effect
            source.card_types.add(CardType.CREATURE)
            # Update the reset snapshot so continuous-effect recalculation
            # does not strip the animation (it has no duration).
            source._original_card_types = frozenset(source.card_types)
            source.subtypes.add("Wizard")
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4
            # The land has been on the battlefield, so it can act at once.
            # LIMITATION: a land played this very turn would really have
            # summoning sickness; not tracked for lands.
            source.summoning_sick = False
            _register_pump_trigger(game, source)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: If this land isn't a creature, it becomes "
                "a 2/4 Wizard creature with \"Whenever you cast an instant "
                "or sorcery spell, this creature gets +1/+0 until end of "
                "turn.\" It's still a land.",
            )
        ]


def _register_pump_trigger(game: GameState, source: GreatHallOfTheBiblioplex) -> None:
    """Animated ability: your instant/sorcery casts give +1/+0 until EOT."""
    from engine.continuous_effects import (
        DURATION_END_OF_TURN,
        ContinuousEffect,
        Layer,
        SubLayer,
    )
    from engine.events import SpellCastTriggeredEvent
    from engine.triggers import TriggerRegistration

    def _condition(game: Any, event: Any) -> bool:
        ctrl = getattr(source, "controller", None)
        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if ctrl is None or caster is not ctrl:
            return False
        spell = getattr(event, "card", None)
        return bool(
            getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}
        )

    def _effect(game: GameState) -> None:
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
        game.effect_manager.apply_all(game)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=source,
            controller=getattr(source, "controller", None) or game.active_player,
        )
    )
