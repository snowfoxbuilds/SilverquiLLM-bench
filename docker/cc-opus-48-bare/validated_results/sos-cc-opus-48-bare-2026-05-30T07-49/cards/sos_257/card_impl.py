"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_instant_or_sorcery(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color.  Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn."  It's still a land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Animation state.  While not animated, the creature characteristics
        # (power/toughness/base_power) are intentionally *not* exposed so that
        # state-based actions and combat treat this purely as a land.
        self._animated: bool = False
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
        self.is_token: bool = False
        self.dealt_deathtouch_damage: bool = False

    # ------------------------------------------------------------------
    # Power / toughness — only present while animated.  Raising
    # AttributeError makes ``hasattr(land, "toughness")`` False so the
    # zero-toughness state-based action never reaps the un-animated land.
    # ------------------------------------------------------------------

    @property
    def base_power(self) -> int:
        if not self._animated:
            raise AttributeError("base_power")
        return 2

    @property
    def base_toughness(self) -> int:
        if not self._animated:
            raise AttributeError("base_toughness")
        return 4

    @property
    def power(self) -> int:
        if not self._animated:
            raise AttributeError("power")
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        if not self._animated:
            raise AttributeError("toughness")
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        # Re-establish the animation each layer-recalculation cycle (the base
        # reset reverts card_types to {LAND}).  Layer 7c MODIFY effects (the
        # +1/+0 pumps) then stack on top of the 2/4 base set here.
        if self._animated:
            self.card_types = set(self.card_types) | {CardType.CREATURE}
            self.subtypes = set(self.subtypes) | {"Wizard"}
            self.modified_power = 2
            self.modified_toughness = 4
            self.plus_one_counters = 0
            self.minus_one_counters = 0
            self._cant_attack = False
            self._cant_block = False
            self._cant_be_blocked = False
            self._cant_activate = False
            self._max_attackers_blocked = 1

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_only(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            if getattr(controller, "life", 0) < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_any_color(game: Any) -> None:
            # ENGINE LIMITATION: the "spend only on an instant or sorcery
            # spell" restriction is not tracked by the mana pool.
            controller = source.controller
            if controller is None:
                return
            options = [
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            ]
            chosen = controller.choose(
                options, "color of mana to produce (instant/sorcery only)"
            )
            controller.mana_pool.add(chosen, 1)

        return [
            ManaAbility(
                cost=_tap_only,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life,
                mana_produced=_add_any_color,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. "
                    "Spend this mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # Activated ability — {5}: become a creature
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if controller.mana_pool.total() < 5:
                return False
            controller.mana_pool.pay(ManaCost(generic=5))
            return True

        def _effect(game: Any) -> None:
            source._animate(game)

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

    def _animate(self, game: "GameState") -> None:
        # "If this land isn't a creature ..." — no effect if already animated.
        if self._animated:
            return
        self._animated = True
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0

    # ------------------------------------------------------------------
    # Triggered ability (active only while animated): +1/+0 per inst/sorcery
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            if not source._animated:
                return False
            if not _is_on_battlefield(g, source):
                return False
            controller = source.controller
            if controller is None:
                return False
            spell = getattr(event, "spell", None)
            if spell is None:
                return False
            if getattr(spell, "controller", None) is not controller:
                return False
            return _is_instant_or_sorcery(spell)

        def _effect(g: "GameState") -> None:
            source._pump(g)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _pump(self, game: "GameState") -> None:
        if not self._animated:
            return
        source = self
        # Immediate effect (visible before any layer recalculation).
        self.modified_power += 1

        # Registered until-end-of-turn effect so a layer recalculation
        # (EffectManager.apply_all) reproduces — and later expires — the pump.
        def _apply(g: "GameState") -> None:
            if not _is_on_battlefield(g, source) or not source._animated:
                return
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
