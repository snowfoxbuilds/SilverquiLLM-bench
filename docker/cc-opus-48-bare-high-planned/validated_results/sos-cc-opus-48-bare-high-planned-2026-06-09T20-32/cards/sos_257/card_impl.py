"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility, ActivatedAbility
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_COLOR_MANA = {
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
}


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
        # Creature-state fields (only meaningful once animated).  base_power is
        # deliberately NOT set until animation so combat does not treat the
        # unanimated land as a creature.
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.damage_marked = 0
        self.is_attacking = False
        self.is_blocking = False
        self.is_token = False
        self.dealt_deathtouch_damage = False
        self.summoning_sick = False
        self._pt_pump = 0  # "+1/+0 until end of turn" accumulator

    # ------------------------------------------------------------------
    # Power / toughness (active once animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        return (
            getattr(self, "base_power", 0)
            + self.plus_one_counters
            - self.minus_one_counters
            + self._pt_pump
        )

    @property
    def toughness(self) -> int:
        return (
            getattr(self, "base_toughness", 0)
            + self.plus_one_counters
            - self.minus_one_counters
        )

    def _reset_characteristics(self) -> None:
        """Reset for the continuous-effect cycle (runs during cleanup).

        Resets card types/keywords to their (possibly animation-updated)
        originals and clears the until-end-of-turn pump.
        """
        super()._reset_characteristics()
        self._pt_pump = 0

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life_cost(game: Any, src: Any) -> bool:
            ctrl = getattr(src, "controller", None)
            if getattr(src, "is_tapped", False):
                return False
            if ctrl is None or ctrl.life < 1:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_any_color_restricted(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            color = ctrl.choose(sorted(_COLOR_MANA, key=lambda m: m.value),
                                "choose a color of mana to add")
            if color not in _COLOR_MANA:
                color = ManaType.WHITE
            ctrl.mana_pool.add(color, 1, restricted=True)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_add_colorless,
                        description="{T}: Add {C}."),
            ManaAbility(cost=_tap_pay_life_cost,
                        mana_produced=_add_any_color_restricted,
                        description="{T}, Pay 1 life: Add one mana of any color. "
                                    "Spend only to cast an instant or sorcery."),
        ]

    # ------------------------------------------------------------------
    # Activated ability — animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            ctrl = getattr(src, "controller", None)
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
                description="{5}: This land becomes a 2/4 Wizard creature.",
            )
        ]

    # ------------------------------------------------------------------
    # Animation (mutate in place; stays a land)
    # ------------------------------------------------------------------

    def _animate(self, game: "GameState") -> None:
        if CardType.CREATURE in self.card_types:
            return  # already a creature
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        self.base_power = 2
        self.base_toughness = 4
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.damage_marked = 0
        self.summoning_sick = False  # has been on the battlefield
        self._pt_pump = 0
        # Update the snapshot so the cleanup reset keeps the creature type.
        self._original_card_types = frozenset(self.card_types)
        self._register_pump_trigger(game)

    def _register_pump_trigger(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not ctrl or ctrl is None:
                return False
            spell = getattr(event, "spell", None)
            card = spell.source if spell is not None else getattr(event, "card", None)
            if card is None:
                return False
            return bool(
                getattr(card, "card_types", set())
                & {CardType.INSTANT, CardType.SORCERY}
            )

        def _effect(game: "GameState") -> None:
            source._pt_pump += 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
