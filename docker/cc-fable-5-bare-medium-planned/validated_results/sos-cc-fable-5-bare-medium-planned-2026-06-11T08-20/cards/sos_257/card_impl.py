"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}

_COLOR_CHOICES = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color.  Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature gets
    +1/+0 until end of turn."  It's still a land.

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
        self._animated: bool = False

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

        def _add_any_color_restricted(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            chosen = controller.choose(
                list(_COLOR_CHOICES), "Choose a color of mana to add"
            )
            if chosen not in _COLOR_CHOICES:
                chosen = ManaType.WHITE
            controller.mana_pool.add(chosen, 1, restriction="instant_sorcery")

        return [
            ManaAbility(
                cost=tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life,
                mana_produced=_add_any_color_restricted,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation (activated ability)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: GameState, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _animate(game: GameState) -> None:
            # "If this land isn't a creature" — checked on resolution.
            if CardType.CREATURE in source.card_types:
                return
            source._animated = True
            source._apply_animation()
            source._register_pump_trigger(game)

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature. It's still a land."
                ),
            )
        ]

    def _apply_animation(self) -> None:
        """Graft creature characteristics onto this permanent in place."""
        self.card_types.add(CardType.CREATURE)
        self.subtypes.add("Wizard")
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0
        # It has been on the battlefield as a land, so it can act at once.
        self.summoning_sick = False
        self.is_attacking = False
        self.is_blocking = False
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.dealt_deathtouch_damage = False
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0

    def _reset_characteristics(self) -> None:
        """Re-assert the (permanent) animation after effect-cycle resets."""
        super()._reset_characteristics()
        if self._animated:
            self.card_types.add(CardType.CREATURE)
            self.subtypes.add("Wizard")
            self.modified_power = 2
            self.modified_toughness = 4

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

    def _register_pump_trigger(self, game: GameState) -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            ctrl = source.controller
            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            if ctrl is None or caster is not ctrl:
                return False
            if CardType.CREATURE not in source.card_types:
                return False
            card = getattr(event, "card", None)
            return bool(
                card is not None
                and getattr(card, "card_types", set()) & _SPELL_TYPES
            )

        def _effect(g: GameState) -> None:
            # +1/+0 until end of turn — direct mutation; cleanup's
            # characteristic reset restores the 2/4 base.
            source.modified_power += 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller or game.active_player,
            )
        )
