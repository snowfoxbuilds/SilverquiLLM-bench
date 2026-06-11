"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


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
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard '
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # P/T plumbing — meaningful only once animated
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
        """Mirror Creature's P/T reset so until-EOT pumps reapply cleanly."""
        super()._reset_characteristics()
        if hasattr(self, "base_power"):
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        from engine.abilities import tap_cost

        source = self

        def _add_colorless(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life(game: "GameState", src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None or controller.life < 1:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_any_color_restricted(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            color = controller.choose(
                list(_COLOR_CHOICES), "Choose a color of mana to add"
            )
            if color not in _COLOR_CHOICES:
                color = _COLOR_CHOICES[0]
            controller.mana_pool.add_restricted(color, 1)

        return [
            ManaAbility(
                cost=tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life,
                mana_produced=_add_any_color_restricted,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5} animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _effect(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return  # already a creature — no effect
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with an instant/sorcery pump trigger. "
                    "It's still a land."
                ),
            )
        ]

    def _animate(self, game: "GameState") -> None:
        """Become a 2/4 Wizard creature (still a land), permanently."""
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        self.card_types.add(CardType.CREATURE)
        # Persist through EffectManager resets — the animation has no
        # duration, so it becomes part of the card's base characteristics.
        self._original_card_types = frozenset(self.card_types)
        self.subtypes.add("Wizard")
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.is_attacking = False
        self.is_blocking = False
        self.dealt_deathtouch_damage = False
        # Deliberate simplification (per plan): the land has been on the
        # battlefield, so the animated creature is not summoning sick.
        self.summoning_sick = False

        def _pump_condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or getattr(event, "controller", None) is not ctrl:
                return False
            card = getattr(event, "card", None)
            return bool(
                getattr(card, "card_types", set())
                & {CardType.INSTANT, CardType.SORCERY}
            )

        def _pump_effect(game: "GameState") -> None:
            from engine.continuous_effects import (
                ContinuousEffect,
                DURATION_END_OF_TURN,
                Layer,
                SubLayer,
            )

            def _apply(g: "GameState") -> None:
                ctrl = getattr(source, "controller", None)
                if ctrl is not None and g.get_battlefield(ctrl).contains(source):
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
            # Recalculate now so the pump is immediately observable.
            game.effect_manager.apply_all(game)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_pump_condition,
                effect=_pump_effect,
                source=self,
                controller=controller,
            )
        )
