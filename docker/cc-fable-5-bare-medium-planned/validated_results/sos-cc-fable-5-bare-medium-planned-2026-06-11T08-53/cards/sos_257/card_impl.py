"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _tap_cost(game: GameState, source: Any) -> bool:
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


def _on_battlefield(game: GameState, obj: Any) -> bool:
    return any(
        game.get_battlefield(p).contains(obj) for p in game.players
    )


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
        # Creature attributes used once animated (harmless while a pure
        # land — SBAs only consult them for CardType.CREATURE objects).
        self._animated: bool = False
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.damage_marked: int = 0
        self.summoning_sick: bool = False
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.is_token: bool = False
        self.dealt_deathtouch_damage: bool = False

    # power/toughness raise AttributeError while un-animated so that
    # hasattr-based engine checks (e.g. the zero-toughness SBA) keep
    # treating the plain land as a non-creature.
    @property
    def power(self) -> int:
        if not self._animated:
            raise AttributeError("not a creature")
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        if not self._animated:
            raise AttributeError("not a creature")
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        # P/T comes back from the animation continuous effect on reapply.
        self.modified_power = 0
        self.modified_toughness = 0

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _add_colorless(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_and_pay_life(game: GameState, src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            if not _tap_cost(game, src):
                return False
            controller.life -= 1
            return True

        def _add_any_color_restricted(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            colored = [
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            ]
            try:
                chosen = controller.choose(colored, "Choose a color of mana")
            except Exception:
                chosen = colored[0]
            if chosen not in colored:
                chosen = colored[0]
            controller.mana_pool.add_restricted(chosen, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life,
                mana_produced=_add_any_color_restricted,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5} animation (activated ability)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: GameState, src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            # Restricted mana cannot pay an ability cost (no for_spell).
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _animate(game: GameState) -> None:
            # "If this land isn't a creature" — checked on resolution.
            if CardType.CREATURE in source.card_types:
                return
            if not _on_battlefield(game, source):
                return
            source._animated = True
            source._apply_animation(game)

            from engine.continuous_effects import (
                ContinuousEffect,
                DURATION_PERMANENT,
                Layer,
            )

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.TYPE,
                    apply=lambda g: source._apply_animation(g),
                    duration=DURATION_PERMANENT,
                )
            )
            source._register_pump_trigger(game)

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with \"Whenever you cast an instant or "
                    "sorcery spell, this creature gets +1/+0 until end of "
                    "turn.\" It's still a land."
                ),
            )
        ]

    def _apply_animation(self, game: GameState) -> None:
        """(Re)apply the animated characteristics — idempotent, used both
        immediately and from the effect manager after resets."""
        if not self._animated or not _on_battlefield(game, self):
            return
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        self.modified_power = 2
        self.modified_toughness = 4

    def _register_pump_trigger(self, game: GameState) -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = self.controller

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(
                event, "player", None
            )
            if ctrl is None or caster is not ctrl:
                return False
            if not source._animated:
                return False
            types = getattr(event.card, "card_types", set())
            return bool(types & {CardType.INSTANT, CardType.SORCERY})

        def _effect(game: GameState) -> None:
            from engine.continuous_effects import (
                ContinuousEffect,
                DURATION_END_OF_TURN,
                Layer,
                SubLayer,
            )

            if not source._animated or not _on_battlefield(game, source):
                return
            source.modified_power += 1

            def _reapply(g: GameState) -> None:
                if source._animated and _on_battlefield(g, source):
                    source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_reapply,
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

    def register_triggers(self, game: GameState) -> None:
        # Fresh battlefield entry: a land that left while animated comes
        # back as a plain land (new-object rule, card-local approximation).
        self._animated = False
        for eff in game.effect_manager.get_effects_by_source(self):
            game.effect_manager.remove(eff)
