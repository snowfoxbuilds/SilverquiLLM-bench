"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState

_COLORS: list[ManaType] = [
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
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        self._animated: bool = False

    # ------------------------------------------------------------------
    # P/T view (meaningful once animated; 0/0 otherwise)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        return (
            getattr(self, "modified_power", 0)
            + getattr(self, "plus_one_counters", 0)
            - getattr(self, "minus_one_counters", 0)
        )

    @property
    def toughness(self) -> int:
        return (
            getattr(self, "modified_toughness", 0)
            + getattr(self, "plus_one_counters", 0)
            - getattr(self, "minus_one_counters", 0)
        )

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        if self._animated:
            # Animated base P/T; until-EOT pumps reapply on top of this.
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

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

        def _life_tap_cost(game: GameState, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None or controller.life < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_restricted_any_color(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            chosen = controller.choose(list(_COLORS), "choose a color of mana")
            if chosen not in _COLORS:
                chosen = _COLORS[0]
            controller.mana_pool.add_restricted(chosen, 1)

        return [
            ManaAbility(
                cost=tap_cost,
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
    # {5}: animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _effect(game: GameState) -> None:
            if CardType.CREATURE in source.card_types:
                return
            source._animate()

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature. It's still a land."
                ),
            )
        ]

    def _animate(self) -> None:
        """Become a 2/4 Wizard creature in place (still a land).

        The animation has no duration, so the creature type is folded into
        ``_original_card_types`` — continuous-effect reset cycles must not
        un-animate the land.
        """
        self._animated = True
        self.card_types.add(CardType.CREATURE)
        self._original_card_types = frozenset(self.card_types)
        self.subtypes.add("Wizard")
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0
        self.is_attacking = False
        self.is_blocking = False
        self.dealt_deathtouch_damage = False
        # Deliberate simplification: the land has been on the battlefield,
        # so the animated creature is not summoning sick.
        self.summoning_sick = False

    # ------------------------------------------------------------------
    # Animated pump trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        from engine.continuous_effects import (
            ContinuousEffect,
            DURATION_END_OF_TURN,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: GameState, event: Any) -> bool:
            if not source._animated:
                return False
            if getattr(event, "controller", None) is not source.controller:
                return False
            card = getattr(event, "card", None)
            return card is not None and bool(
                getattr(card, "card_types", set())
                & {CardType.INSTANT, CardType.SORCERY}
            )

        def _effect(game: GameState) -> None:
            def _pump(g: GameState) -> None:
                if source._animated:
                    source.modified_power += 1

            game.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_pump,
                duration=DURATION_END_OF_TURN,
            ))
            # Recalculate so the pump is observable immediately.
            game.effect_manager.apply_all(game)

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=self.controller,
        ))
