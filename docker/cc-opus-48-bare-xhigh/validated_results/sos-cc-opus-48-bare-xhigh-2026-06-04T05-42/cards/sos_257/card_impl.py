"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature gets
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
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        self._is_animated: bool = False

    # ------------------------------------------------------------------
    # Power / toughness — only meaningful once animated.  Defined as
    # properties so combat can read them, but ``base_power`` is left unset
    # until animation so the land is not a legal attacker beforehand.
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
        if getattr(self, "_is_animated", False):
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness
            self.plus_one_counters = getattr(self, "_base_plus_one_counters", 0)
            self.minus_one_counters = getattr(self, "_base_minus_one_counters", 0)

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------
    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _tap_pay_life_cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None or getattr(src, "is_tapped", False):
                return False
            if getattr(controller, "life", 0) < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _colorless_effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _any_color_effect(game: Any) -> None:
            # ENGINE LIMITATION: the engine has no concept of "spend this mana
            # only to cast an instant or sorcery spell", so the restriction is
            # not enforced — the mana is produced as ordinary mana.
            from engine.player import ScriptExhaustedError

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
            try:
                chosen = controller.choose(options, "choose a color of mana")
            except (ScriptExhaustedError, NotImplementedError):
                chosen = ManaType.WHITE
            if chosen not in options:
                chosen = ManaType.WHITE
            controller.mana_pool.add(chosen, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life_cost,
                mana_produced=_any_color_effect,
                description="{T}, Pay 1 life: Add one mana of any color "
                "(restricted to instants/sorceries).",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated ability — {5}: animate into a 2/4 Wizard creature
    # ------------------------------------------------------------------
    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _animate_cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            cost = ManaCost.parse("{5}")
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _animate_effect(game: Any) -> None:
            if getattr(source, "_is_animated", False):
                return
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_animate_cost,
                effect=_animate_effect,
                description="{5}: If this land isn't a creature, it becomes a "
                "2/4 Wizard creature. It's still a land.",
            )
        ]

    def _animate(self, game: "GameState") -> None:
        from engine.continuous_effects import (
            DURATION_PERMANENT,
            ContinuousEffect,
            Layer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        self._is_animated = True
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0
        self.is_attacking = False
        self.is_blocking = False
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0
        # A land that's been under your control acts as though it has no
        # summoning sickness once animated (the common man-land case).
        self.summoning_sick = False

        source = self

        def _type_apply(g: "GameState") -> None:
            source.card_types.add(CardType.CREATURE)
            source.subtypes.add("Wizard")

        game.effect_manager.add(
            ContinuousEffect(
                source=source,
                layer=Layer.TYPE,
                apply=_type_apply,
                duration=DURATION_PERMANENT,
            )
        )

        def _pump_condition(
            g: "GameState", event: SpellCastTriggeredEvent
        ) -> bool:
            if not getattr(source, "_is_animated", False):
                return False
            if getattr(event, "controller", None) is not source.controller:
                return False
            card = getattr(event, "card", None)
            if card is None:
                return False
            types = getattr(card, "card_types", set())
            return CardType.INSTANT in types or CardType.SORCERY in types

        def _pump_effect(g: "GameState") -> None:
            from engine.continuous_effects import (
                DURATION_END_OF_TURN,
                ContinuousEffect as _CE,
                Layer as _Layer,
                SubLayer as _SubLayer,
            )

            def _apply(gg: "GameState") -> None:
                source.modified_power = (
                    getattr(source, "modified_power", source.base_power) + 1
                )

            g.effect_manager.add(
                _CE(
                    source=source,
                    layer=_Layer.POWER_TOUGHNESS,
                    sublayer=_SubLayer.MODIFY_PT,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )
            g.effect_manager.apply_all(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_pump_condition,
                effect=_pump_effect,
                source=source,
                controller=source.controller,
            )
        )

        # Apply the type-changing effect immediately so the land is a creature.
        game.effect_manager.apply_all(game)
