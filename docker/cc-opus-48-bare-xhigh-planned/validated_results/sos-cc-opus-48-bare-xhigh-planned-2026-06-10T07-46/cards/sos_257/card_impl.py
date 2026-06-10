"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.events import (
    BeginningOfUpkeepTriggeredEvent,
    SpellCastTriggeredEvent,
)
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_COLORS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an
    instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n{T}, Pay 1 life: Add one mana of any color. Spend "
            "this mana only to cast an instant or sorcery spell.\n{5}: If this "
            "land isn't a creature, it becomes a 2/4 Wizard creature with "
            '"Whenever you cast an instant or sorcery spell, this creature gets '
            '+1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Animation state.  Until animated, this is a plain land with no P/T —
        # the power/toughness properties raise AttributeError so state-based
        # actions and combat (which guard with ``hasattr``) ignore it.
        self._animated: bool = False
        self._base_power: int = 2
        self._base_toughness: int = 4
        self._pump: int = 0  # "+1/+0 until end of turn", stacks per spell

    # ------------------------------------------------------------------
    # Creature characteristics (only meaningful once animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        if not self._animated:
            raise AttributeError("power")
        return self._base_power + self._pump

    @property
    def toughness(self) -> int:
        if not self._animated:
            raise AttributeError("toughness")
        return self._base_toughness

    @property
    def base_power(self) -> int:
        if not self._animated:
            raise AttributeError("base_power")
        return self._base_power

    @property
    def base_toughness(self) -> int:
        if not self._animated:
            raise AttributeError("base_toughness")
        return self._base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if ctrl is None or getattr(src, "is_tapped", False):
                return False
            if getattr(ctrl, "life", 0) < 1:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_any_color_restricted(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            try:
                chosen = ctrl.choose(_COLORS, "choose a color of mana to add")
            except Exception:
                chosen = ManaType.WHITE
            if chosen not in _COLORS:
                chosen = ManaType.WHITE
            # Restricted: usable only to cast an instant or sorcery spell.
            ctrl.mana_pool.add_restricted(chosen, 1)

        return [
            ManaAbility(
                cost=_tap, mana_produced=_add_colorless, description="{T}: Add {C}."
            ),
            ManaAbility(
                cost=_tap_pay_life,
                mana_produced=_add_any_color_restricted,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
                    "only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation (activated ability)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if ctrl is None:
                return False
            cost = ManaCost(generic=5)
            if not ctrl.mana_pool.can_pay(cost):
                return False
            return ctrl.mana_pool.pay(cost)

        def _effect(game: "GameState") -> None:
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                    "creature; it's still a land."
                ),
            )
        ]

    def _animate(self, game: "GameState") -> None:
        # Gate: only if this land isn't already a creature.
        if CardType.CREATURE in self.card_types:
            return
        self._animated = True
        # Add the Creature type in place (still a land).  Update the original
        # snapshot too so _reset_characteristics (run at cleanup) preserves it.
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self._original_card_types = frozenset(self.card_types)
        self.subtypes = set(self.subtypes) | {"Wizard"}
        # Creature scaffolding the engine reads via plain attributes.
        self.modified_power = self._base_power
        self.modified_toughness = self._base_toughness
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.damage_marked = 0
        self.dealt_deathtouch_damage = False
        self.is_attacking = False
        self.is_blocking = False
        # It has been on the battlefield, so no summoning sickness.
        self.summoning_sick = False
        self._register_animation_triggers(game)

    def _register_animation_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _pump_condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            return bool(
                card is not None
                and getattr(card, "card_types", set())
                & {CardType.INSTANT, CardType.SORCERY}
            )

        def _pump_effect(g: "GameState") -> None:
            # "+1/+0 until end of turn", stacks per spell.
            source._pump += 1

        def _reset_effect(g: "GameState") -> None:
            # Reset the until-end-of-turn pump at the start of each turn (the
            # engine fires no end-of-turn event; upkeep is the reliable reset
            # point and the pump is gone before the next combat).
            source._pump = 0

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_pump_condition,
                effect=_pump_effect,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfUpkeepTriggeredEvent,
                condition=None,
                effect=_reset_effect,
                source=self,
                controller=controller,
            )
        )
