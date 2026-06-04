"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_COLOR_MANA = (
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
)


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


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
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Creature characteristics — inert until the land is animated.
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.damage_marked: int = 0
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.summoning_sick: bool = False
        self.is_token: bool = False
        self._animated: bool = False
        self._pump_registered: bool = False

    # ------------------------------------------------------------------
    # Creature-like characteristics (only meaningful once animated)
    # ------------------------------------------------------------------
    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return (
            self.modified_toughness + self.plus_one_counters - self.minus_one_counters
        )

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------
    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_only(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_and_pay_life(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            controller = source.controller
            if controller is None or getattr(controller, "life", 0) < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_any_color(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            try:
                color = controller.choose(
                    list(_COLOR_MANA),
                    "Choose a color of mana to add (instant/sorcery only)",
                )
            except Exception:
                color = ManaType.BLUE
            if color not in _COLOR_MANA:
                color = ManaType.BLUE
            controller.mana_pool.add(color, 1)
            # Engine limitation: the "spend only on instant/sorcery" restriction
            # is not tracked by the mana pool, so it is not enforced here.

        return [
            ManaAbility(
                cost=_tap_only,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life,
                mana_produced=_add_any_color,
                description="{T}, Pay 1 life: Add one mana of any color. Spend "
                "this mana only to cast an instant or sorcery spell.",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated ability — animate
    # ------------------------------------------------------------------
    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost.parse("{5}"))

        def _effect(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return  # already a creature
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: If this land isn't a creature, it becomes a "
                "2/4 Wizard creature that pumps when you cast instants and "
                "sorceries. It's still a land.",
            )
        ]

    # ------------------------------------------------------------------
    # Animation helpers
    # ------------------------------------------------------------------
    def _animate(self, game: "GameState") -> None:
        from engine.continuous_effects import (
            DURATION_PERMANENT,
            ContinuousEffect,
            Layer,
        )

        self._animated = True
        self.base_power = 2
        self.base_toughness = 4
        self._apply_animation(game)

        # Survive future apply_all/_reset cycles.
        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.TYPE,
                apply=self._apply_animation,
                duration=DURATION_PERMANENT,
            )
        )
        self._register_pump_trigger(game)

    def _apply_animation(self, game: "GameState") -> None:
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        if self.modified_power < 2:
            self.modified_power = 2
        if self.modified_toughness < 4:
            self.modified_toughness = 4

    def _register_pump_trigger(self, game: "GameState") -> None:
        if self._pump_registered:
            return
        self._pump_registered = True

        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: "GameState", event: Any) -> bool:
            if CardType.CREATURE not in source.card_types:
                return False
            if getattr(event, "controller", None) is not source.controller:
                return False
            card = getattr(event, "card", None) or getattr(
                getattr(event, "spell", None), "source", None
            )
            return card is not None and _is_instant_or_sorcery(card)

        def _effect(game: "GameState") -> None:
            from engine.continuous_effects import (
                DURATION_END_OF_TURN,
                ContinuousEffect,
                Layer,
                SubLayer,
            )

            source.modified_power += 1

            def _pump(game: "GameState") -> None:
                source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_pump,
                    duration=DURATION_END_OF_TURN,
                )
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
