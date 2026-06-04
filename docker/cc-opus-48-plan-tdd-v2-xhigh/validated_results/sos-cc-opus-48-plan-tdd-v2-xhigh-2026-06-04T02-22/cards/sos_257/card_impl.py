"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


_ANY_COLOR: list[ManaType] = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.

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
            "creature with \"Whenever you cast an instant or sorcery spell, "
            "this creature gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        # Creature-style P/T plumbing so that the continuous-effect layer
        # system can animate this land into a creature.
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self._base_plus_one_counters: int = 0
        self._base_minus_one_counters: int = 0
        self.damage_marked: int = 0
        self.summoning_sick: bool = True
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.dealt_deathtouch_damage: bool = False

    # ------------------------------------------------------------------
    # P/T characteristics (only meaningful once animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        """Reset card types/keywords and P/T to base before reapplying effects."""
        super()._reset_characteristics()
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

        def _colorless(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life(game: "GameState", src: Any) -> bool:
            ctrl = getattr(src, "controller", None)
            if getattr(src, "is_tapped", False):
                return False
            if ctrl is None or ctrl.life < 1:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _any_color(game: "GameState") -> None:
            # NOTE: the rules restrict this mana to casting instants/sorceries;
            # the engine has no per-mana restriction tagging, so the mana is
            # added untagged and the restriction is left unenforced.
            ctrl = source.controller
            if ctrl is None:
                return
            chosen = ctrl.choose(_ANY_COLOR, "Choose a color of mana to add")
            if chosen not in _ANY_COLOR:
                chosen = ManaType.WHITE
            ctrl.mana_pool.add(chosen, 1)

        return [
            ManaAbility(
                cost=_tap,
                mana_produced=_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life,
                mana_produced=_any_color,
                description="{T}, Pay 1 life: Add one mana of any color. "
                "Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: Animate into a 2/4 Wizard creature (still a land)
    # ------------------------------------------------------------------

    def get_activated_abilities(self, game: "GameState") -> list[ActivatedAbility]:
        # "If this land isn't a creature" — once animated, the ability is gone.
        if CardType.CREATURE in self.card_types:
            return []

        def _cost(game: "GameState", src: Any = self) -> bool:
            ctrl = src.controller
            if ctrl is None:
                return False
            cost = ManaCost.parse("{5}")
            if not ctrl.mana_pool.can_pay(cost):
                return False
            ctrl.mana_pool.pay(cost)
            return True

        def _effect(game: "GameState") -> None:
            self._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: If this land isn't a creature, it becomes a "
                "2/4 Wizard creature with \"Whenever you cast an instant or "
                "sorcery spell, this creature gets +1/+0 until end of turn.\" "
                "It's still a land.",
            )
        ]

    def _is_on_battlefield(self, game: "GameState") -> bool:
        for pl in game.players:
            if game.get_battlefield(pl).contains(self):
                return True
        return False

    def _animate(self, game: "GameState") -> None:
        from engine.continuous_effects import (
            ContinuousEffect,
            DURATION_PERMANENT,
            Layer,
            SubLayer,
        )

        if CardType.CREATURE in self.card_types:
            return  # intervening "if" — already a creature, do nothing

        source = self

        def _apply_type(g: "GameState") -> None:
            if not source._is_on_battlefield(g):
                return
            source.card_types = set(source.card_types) | {CardType.CREATURE}
            source.subtypes = set(source.subtypes) | {"Wizard"}

        def _apply_pt(g: "GameState") -> None:
            if not source._is_on_battlefield(g):
                return
            source.modified_power = 2
            source.modified_toughness = 4

        game.effect_manager.add(
            ContinuousEffect(
                source=source,
                layer=Layer.TYPE,
                sublayer=None,
                apply=_apply_type,
                duration=DURATION_PERMANENT,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.SET_PT,
                apply=_apply_pt,
                duration=DURATION_PERMANENT,
            )
        )
        self._register_pump_trigger(game)
        game.effect_manager.apply_all(game)

    def _register_pump_trigger(self, game: "GameState") -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = self.controller or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or getattr(event, "controller", None) is not ctrl:
                return False
            if CardType.CREATURE not in source.card_types:
                return False
            return _is_instant_or_sorcery(getattr(event, "card", None))

        def _effect(g: "GameState") -> None:
            from engine.continuous_effects import (
                ContinuousEffect,
                DURATION_END_OF_TURN,
                Layer,
                SubLayer,
            )

            def _pump(gg: "GameState") -> None:
                if not source._is_on_battlefield(gg):
                    return
                source.modified_power += 1

            g.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_pump,
                    duration=DURATION_END_OF_TURN,
                )
            )
            g.effect_manager.apply_all(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
