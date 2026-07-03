"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState

# The five color choices for the second mana ability.
_COLOR_CHOICES: list[ManaType] = [
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
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard '
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Creature state, live only once animated.  The land has been on
        # the battlefield before the {5} ability can be activated, so it is
        # not treated as summoning sick.
        self._animated: bool = False
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
        self._base_plus_one_counters: int = 0
        self._base_minus_one_counters: int = 0
        self.is_token: bool = False
        self.dealt_deathtouch_damage: bool = False

    @property
    def power(self) -> int:
        """Current power including counter modifications (mirrors Creature)."""
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        """Current toughness including counter modifications."""
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        """Reset for continuous-effect recalculation, preserving the animation.

        The {5} animation has no duration — it must survive the effect
        manager's reset-and-reapply cycles.
        """
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
        if self._animated:
            self.card_types.add(CardType.CREATURE)
            self.subtypes.add("Wizard")

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        from engine.abilities import tap_cost

        source = self

        def _add_colorless(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_and_pay_life(game: GameState, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_restricted_any_color(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            chosen = controller.choose(list(_COLOR_CHOICES), "Choose a color of mana to add")
            if chosen not in _COLOR_CHOICES:
                chosen = _COLOR_CHOICES[0]
            controller.mana_pool.add_restricted(chosen, 1)

        return [
            ManaAbility(
                cost=tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life,
                mana_produced=_add_restricted_any_color,
                description="{T}, Pay 1 life: Add one mana of any color. "
                "Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5} animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _effect(game: GameState) -> None:
            if CardType.CREATURE in source.card_types:
                return  # already a creature — no effect
            source._animate(game)

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

    def _animate(self, game: GameState) -> None:
        """Become a 2/4 Wizard creature (still a land) with the pump trigger."""
        from engine.continuous_effects import (
            DURATION_END_OF_TURN,
            ContinuousEffect,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        self._animated = True
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.card_types.add(CardType.CREATURE)
        self.subtypes.add("Wizard")

        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            return bool(
                getattr(card, "card_types", set())
                & {CardType.INSTANT, CardType.SORCERY}
            )

        def _pump(game: GameState) -> None:
            # Immediate, plus a registered until-EOT effect so the bonus is
            # idempotent under the effect manager's reset-and-reapply cycle
            # and expires at cleanup.
            source.modified_power += 1

            def _apply(g: Any) -> None:
                for p in g.players:
                    if g.get_battlefield(p).contains(source):
                        source.modified_power += 1
                        return

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
                effect=_pump,
                source=self,
                controller=controller,
            )
        )
