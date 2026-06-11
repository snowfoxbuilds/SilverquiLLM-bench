"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState

_INSTANT_OR_SORCERY = {CardType.INSTANT, CardType.SORCERY}
_COLORS = [
    ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
    ManaType.RED, ManaType.GREEN,
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
        self._animated: bool = False

    # ------------------------------------------------------------------
    # Creature stats — only present while animated, so the zero-toughness
    # state-based action never sees an unanimated land.
    # ------------------------------------------------------------------

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
        """Keep the animation through continuous-effect recalculations."""
        super()._reset_characteristics()
        if self._animated:
            self.card_types.add(CardType.CREATURE)
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _colorless(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None or controller.life < 1:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller.life -= 1
            from engine.events import LosesLifeTriggeredEvent

            game.trigger_manager.fire_event(
                game, LosesLifeTriggeredEvent(player=controller, amount=1)
            )
            return True

        def _any_color_restricted(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            choice = controller.choose(list(_COLORS), "Choose a color of mana to add")
            if choice not in _COLORS:
                choice = _COLORS[0]
            controller.mana_pool.add_restricted(choice, 1)

        return [
            ManaAbility(cost=_tap, mana_produced=_colorless,
                        description="{T}: Add {C}."),
            ManaAbility(cost=_tap_pay_life, mana_produced=_any_color_restricted,
                        description="{T}, Pay 1 life: Add one mana of any "
                                    "color. Spend this mana only to cast an "
                                    "instant or sorcery spell."),
        ]

    # ------------------------------------------------------------------
    # {5} animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _effect(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return  # already a creature — the ability does nothing
            source._animate(game)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{5}: If this land isn't a creature, it becomes a "
                        "2/4 Wizard creature. It's still a land.",
        )]

    def _animate(self, game: "GameState") -> None:
        """Become a 2/4 Wizard creature (still a land), in place."""
        self._animated = True
        self.card_types.add(CardType.CREATURE)
        self.subtypes.add("Wizard")
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.damage_marked = 0
        # It has been on the battlefield since the turn began (the {5}
        # ability is paid with mana from permanents already in play), so
        # treat it as not summoning sick — a deliberate simplification.
        self.summoning_sick = False
        self.is_attacking = False
        self.is_blocking = False
        self.dealt_deathtouch_damage = False
        self._register_pump_trigger(game)

    def _register_pump_trigger(self, game: "GameState") -> None:
        from engine.continuous_effects import (
            ContinuousEffect,
            DURATION_END_OF_TURN,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            if not source._animated:
                return False
            spell_card = getattr(event, "card", None)
            return bool(
                getattr(spell_card, "card_types", set()) & _INSTANT_OR_SORCERY
            )

        def _effect(g: "GameState") -> None:
            if not source._animated:
                return
            # Apply immediately, and register an until-end-of-turn effect so
            # a continuous-effect recalculation reapplies it idempotently.
            source.modified_power += 1

            def _apply(gg: Any) -> None:
                for p in gg.players:
                    if gg.get_battlefield(p).contains(source):
                        source.modified_power += 1
                        return

            g.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            ))

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
