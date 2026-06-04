"""Card implementation for Great Hall of the Biblioplex.

Animation model: ``{5}`` turns the land into a 2/4 Wizard creature while it
remains a land.  Rather than registering a separate continuous effect, the
animation is made durable by overriding ``_reset_characteristics`` so that
``EffectManager.apply_all`` (which resets battlefield objects before
reapplying effects, e.g. each cleanup step) re-asserts CREATURE + Wizard and
the 2/4 base P/T whenever ``_animated`` is set.

The "+1/+0 until end of turn" pump (granted while animated, on each instant
or sorcery you cast — wired through the Gap-A ``SpellCastTriggeredEvent``) is
a direct, transient bump to ``modified_power``; it is wiped back to base 2/4
by ``_reset_characteristics`` during the cleanup ``apply_all``.

Mana note: the second ability's "spend this mana only on an instant or
sorcery" restriction is not enforced — the engine's ``ManaPool`` does not tag
mana by allowed use — so the mana is produced untagged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}
_ANY_COLORS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]
_ANIMATE_COST = "{5}"


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
        an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
        "Whenever you cast an instant or sorcery spell, this creature gets
        +1/+0 until end of turn." It's still a land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
            "only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            "creature with \"Whenever you cast an instant or sorcery spell, "
            "this creature gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        # Creature-capable attributes so the land can act as a creature once
        # animated.
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self._base_plus_one_counters: int = 0
        self._base_minus_one_counters: int = 0
        self.damage_marked: int = 0
        self.summoning_sick: bool = False
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.dealt_deathtouch_damage: bool = False
        self._animated: bool = False
        self._pump_registered: bool = False

    # ------------------------------------------------------------------
    # Creature-like characteristics
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        if getattr(self, "_animated", False):
            self.card_types = set(self.card_types) | {CardType.CREATURE}
            self.subtypes = set(self.subtypes) | {"Wizard"}
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness
        self.plus_one_counters = self._base_plus_one_counters
        self.minus_one_counters = self._base_minus_one_counters

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

        def _colorless_effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _any_cost(game: "GameState", src: Any) -> bool:
            ctrl = getattr(src, "controller", None)
            if ctrl is None or getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _any_effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            color = ctrl.choose(_ANY_COLORS, "Choose a color of mana to add")
            if color not in _ANY_COLORS:
                color = ManaType.WHITE
            ctrl.mana_pool.add(color, 1)

        return [
            ManaAbility(
                cost=_tap,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_any_cost,
                mana_produced=_any_effect,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5} animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            ctrl = getattr(src, "controller", None)
            if ctrl is None:
                return False
            if getattr(src, "_animated", False) or CardType.CREATURE in getattr(
                src, "card_types", set()
            ):
                return False
            cost = ManaCost.parse(_ANIMATE_COST)
            if not ctrl.mana_pool.can_pay(cost):
                return False
            ctrl.mana_pool.pay(cost)
            return True

        def _effect(game: "GameState") -> None:
            source.animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with a +1/+0 instant/sorcery pump. Still "
                    "a land."
                ),
            )
        ]

    def animate(self, game: "GameState") -> None:
        """Turn this land into a 2/4 Wizard creature (if it isn't one)."""
        if self._animated or CardType.CREATURE in self.card_types:
            return
        self._animated = True
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.summoning_sick = False
        self._register_pump_trigger(game)

    def _register_pump_trigger(self, game: "GameState") -> None:
        if self._pump_registered:
            return
        self._pump_registered = True

        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", e: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or getattr(e, "controller", None) is not ctrl:
                return False
            spell = getattr(e, "spell", None) or getattr(e, "card", None)
            return bool(getattr(spell, "card_types", set()) & _INSTANT_SORCERY)

        def _effect(g: "GameState") -> None:
            source.modified_power += 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=getattr(self, "controller", None) or game.active_player,
            )
        )
