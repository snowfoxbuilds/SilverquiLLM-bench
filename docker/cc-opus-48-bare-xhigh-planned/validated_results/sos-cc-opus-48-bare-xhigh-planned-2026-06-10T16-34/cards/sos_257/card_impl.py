"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}
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
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
        an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
        "Whenever you cast an instant or sorcery spell, this creature gets
        +1/+0 until end of turn." It's still a land.

    SOS collector number 257.

    Implementation note: this starts as a pure Land (no creature
    characteristics). The {5} animation installs creature attributes in place
    (the same object stays a land). ``power``/``toughness`` raise
    ``AttributeError`` until animated, so ``hasattr`` checks in combat/SBAs
    correctly treat the un-animated land as a non-creature.
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

    # ------------------------------------------------------------------
    # Creature characteristics (only meaningful once animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        if CardType.CREATURE not in self.card_types:
            raise AttributeError("power")
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        if CardType.CREATURE not in self.card_types:
            raise AttributeError("toughness")
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        """Reset to base characteristics. Keeps the (permanent) creature type
        via ``_original_card_types`` and resets the until-EOT pump."""
        super()._reset_characteristics()
        if CardType.CREATURE in self.card_types:
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _add_colorless(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _pay_life_tap(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if getattr(src, "is_tapped", False):
                return False
            if ctrl is None or ctrl.life < 1:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_any_color_restricted(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            try:
                color = ctrl.choose(_COLORS, "choose a color for restricted mana")
            except Exception:
                color = ManaType.WHITE
            if color not in _COLORS:
                color = ManaType.WHITE
            ctrl.mana_pool.add(color, 1, restricted=True)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_add_colorless, description="{T}: Add {C}."),
            ManaAbility(
                cost=_pay_life_tap,
                mana_produced=_add_any_color_restricted,
                description="{T}, Pay 1 life: Add one mana of any color (instant/sorcery only).",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animate into a 2/4 Wizard creature
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if ctrl is None:
                return False
            cost = ManaCost(generic=5)
            # The {5} is an ability cost, not an instant/sorcery spell, so
            # instant/sorcery-restricted mana may not pay for it.
            if not ctrl.mana_pool.can_pay(cost, allow_restricted=False):
                return False
            return ctrl.mana_pool.pay(cost, allow_restricted=False)

        def _effect(game: "GameState") -> None:
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: Becomes a 2/4 Wizard creature; it's still a land.",
            )
        ]

    def _animate(self, game: "GameState") -> None:
        """Mutate in place into a 2/4 Wizard creature (still a land)."""
        if CardType.CREATURE in self.card_types:
            return  # "If this land isn't a creature" — already animated.

        self.card_types = set(self.card_types) | {CardType.CREATURE}
        # Make the creature type persist across continuous-effect resets.
        self._original_card_types = frozenset(self.card_types)
        self.subtypes = set(self.subtypes) | {"Wizard"}

        # Install creature runtime characteristics.
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.damage_marked = 0
        # It has been on the battlefield, so no summoning sickness.
        self.summoning_sick = False
        self.is_attacking = False
        self.is_blocking = False
        self.is_token = False
        self.dealt_deathtouch_damage = False

        self._register_pump_trigger(game)

    def _register_pump_trigger(self, game: "GameState") -> None:
        """Whenever you cast an instant/sorcery spell, +1/+0 until end of turn."""
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            if CardType.CREATURE not in source.card_types:
                return False
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not source.controller:
                return False
            spell_card = getattr(event, "card", None)
            return bool(spell_card is not None and getattr(spell_card, "card_types", set()) & _INSTANT_SORCERY)

        def _effect(game: "GameState") -> None:
            # +1/+0 "until end of turn": bump modified_power directly. The
            # cleanup step's effect-manager reset restores base P/T, which is
            # exactly the until-end-of-turn duration (apply_all runs there).
            if CardType.CREATURE in source.card_types:
                source.modified_power += 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
