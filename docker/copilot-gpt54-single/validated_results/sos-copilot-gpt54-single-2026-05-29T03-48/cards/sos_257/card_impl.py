"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.abilities import tap_cost
from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.events import SpellCastTriggeredEvent
from engine.mana import ManaRestriction, ManaSpendContext
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return True if *card* is an instant or sorcery spell."""
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex."""

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
        self._original_subtypes: frozenset[str] = frozenset(self.subtypes)
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.damage_marked: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.summoning_sick: bool = True
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self._animation_registered: bool = False
        self._animation_type_effect: ContinuousEffect | None = None
        self._animation_stats_effect: ContinuousEffect | None = None
        self._spellcast_buff_effects: list[ContinuousEffect] = []

    def _reset_characteristics(self) -> None:
        """Reset mutable characteristics before continuous effects reapply."""
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes)
        self.modified_power = 0
        self.modified_toughness = 0
        if hasattr(self, "base_power"):
            delattr(self, "base_power")
        if hasattr(self, "base_toughness"):
            delattr(self, "base_toughness")
        if hasattr(self, "power"):
            delattr(self, "power")
        if hasattr(self, "toughness"):
            delattr(self, "toughness")

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return the printed mana abilities."""
        return [
            ManaAbility(
                cost=lambda game, source: tap_cost(game, source),
                mana_produced=lambda game: self._add_colorless_mana(),
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=self._life_mana_cost,
                mana_produced=lambda game: self._add_restricted_colored_mana(game),
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
                    "only to cast an instant or sorcery spell."
                ),
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the animation ability."""
        return [
            ActivatedAbility(
                cost=self._animation_cost,
                effect=self._animate,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                    'creature with "Whenever you cast an instant or sorcery spell, '
                    'this creature gets +1/+0 until end of turn." It\'s still a land.'
                ),
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        """Register the granted spell-cast trigger."""
        if self.controller is None:
            return
        if not self._animation_registered:
            return
        if game.trigger_manager.get_triggers_for_source(self):
            return

        def _condition(_game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            if not _is_on_battlefield(_game, self):
                return False
            if CardType.CREATURE not in self.card_types:
                return False
            if event.controller is not self.controller:
                return False
            spell = event.spell if event.spell is not None else event.card
            return _is_instant_or_sorcery(spell)

        def _effect(_game: "GameState") -> None:
            hall_ref = self

            def _apply_buff(game: "GameState") -> None:
                if not _is_on_battlefield(game, hall_ref):
                    return
                if CardType.CREATURE not in getattr(hall_ref, "card_types", set()):
                    return
                hall_ref.modified_power += 1
                hall_ref.power = hall_ref.modified_power
                hall_ref.toughness = hall_ref.modified_toughness

            self._spellcast_buff_effects = [
                effect
                for effect in self._spellcast_buff_effects
                if effect in _game.effect_manager.get_all()
            ]
            buff_effect = ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_buff,
                duration=DURATION_END_OF_TURN,
            )
            _game.effect_manager.add(buff_effect)
            self._spellcast_buff_effects.append(buff_effect)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller,
                controller_getter=lambda: self.controller,
            )
        )

    def on_zone_change(
        self,
        game: "GameState",
        from_zone: Zone,
        to_zone: Zone,
    ) -> None:
        """Clear animation state when this reused object changes zones."""
        if from_zone == Zone.BATTLEFIELD or to_zone == Zone.BATTLEFIELD:
            self._clear_animation_state(game)
        if to_zone == Zone.BATTLEFIELD:
            self.summoning_sick = True

    def _clear_animation_state(self, game: "GameState") -> None:
        """Remove animation-only effects and reset reused-object state."""
        if self._animation_type_effect is not None:
            game.effect_manager.remove(self._animation_type_effect)
            self._animation_type_effect = None
        if self._animation_stats_effect is not None:
            game.effect_manager.remove(self._animation_stats_effect)
            self._animation_stats_effect = None
        for effect in self._spellcast_buff_effects:
            game.effect_manager.remove(effect)
        self._spellcast_buff_effects = []
        self._animation_registered = False
        self.damage_marked = 0
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.is_attacking = False
        self.is_blocking = False
        self._reset_characteristics()

    def _add_colorless_mana(self) -> None:
        controller = self.controller
        if controller is None:
            return
        controller.mana_pool.add(ManaType.COLORLESS, 1)

    def _life_mana_cost(self, game: "GameState", source: Any) -> bool:
        controller = getattr(source, "controller", None)
        if controller is None:
            return False
        if controller.life < 1:
            return False
        if not tap_cost(game, source):
            return False
        controller.life -= 1
        return True

    def _add_restricted_colored_mana(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return
        chosen_color = controller.choose(
            [
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            ],
            "Choose a color of mana to add",
        )
        if chosen_color not in {
            ManaType.WHITE,
            ManaType.BLUE,
            ManaType.BLACK,
            ManaType.RED,
            ManaType.GREEN,
        }:
            return

        controller.mana_pool.add(
            chosen_color,
            1,
            restriction=ManaRestriction(
                description="Spend this mana only to cast an instant or sorcery spell.",
                can_spend=lambda context: (
                    context is not None
                    and context.purpose == "cast"
                    and _is_instant_or_sorcery(context.card)
                ),
            ),
        )

    def _animation_cost(self, game: "GameState", source: Any) -> bool:
        controller = getattr(source, "controller", None)
        if controller is None:
            return False
        spend_context = ManaSpendContext(
            purpose="activate_ability",
            player=controller,
            source=source,
        )
        cost = ManaCost(generic=5)
        if not controller.mana_pool.can_pay(cost, spend_context=spend_context):
            return False
        return controller.mana_pool.pay(cost, spend_context=spend_context)

    def _animate(self, game: "GameState") -> None:
        if CardType.CREATURE in self.card_types or self._animation_registered:
            return
        hall_ref = self

        def _apply_type(game: "GameState") -> None:
            if not _is_on_battlefield(game, hall_ref):
                return
            hall_ref.card_types.add(CardType.CREATURE)
            hall_ref.subtypes.add("Wizard")

        def _apply_stats(game: "GameState") -> None:
            if not _is_on_battlefield(game, hall_ref):
                return
            hall_ref.base_power = 2
            hall_ref.base_toughness = 4
            hall_ref.modified_power = 2
            hall_ref.modified_toughness = 4
            hall_ref.power = 2
            hall_ref.toughness = 4

        self._animation_registered = True
        self._animation_type_effect = ContinuousEffect(
            source=self,
            layer=Layer.TYPE,
            apply=_apply_type,
            duration=DURATION_PERMANENT,
        )
        self._animation_stats_effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.SET_PT,
            apply=_apply_stats,
            duration=DURATION_PERMANENT,
        )
        game.effect_manager.add(self._animation_type_effect)
        game.effect_manager.add(self._animation_stats_effect)
        self.register_triggers(game)
