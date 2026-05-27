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
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return ``True`` if *card* is an instant or sorcery spell."""
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with "
            "\"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn.\" "
            "It's still a land.",
        )
        super().__init__(**kwargs)
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self._original_subtypes: frozenset[str] = frozenset(self.subtypes)
        self._animated: bool = False
        self._animation_effects_registered: bool = False

    def _reset_characteristics(self) -> None:
        """Reset local creature-like surfaces before reapplying effects."""
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes)
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

    @property
    def power(self) -> int:
        """Return current power while animated."""
        return self.modified_power

    @property
    def toughness(self) -> int:
        """Return current toughness while animated."""
        return self.modified_toughness

    def _ensure_animation_effects(self, game: "GameState") -> None:
        """Register the permanent animation effects once."""
        if self._animation_effects_registered:
            return
        source = self

        def _apply_type(game: "GameState") -> None:
            if not source._animated or not _is_on_battlefield(game, source):
                return
            source.card_types.add(CardType.CREATURE)
            source.subtypes.add("Wizard")

        def _apply_pt(game: "GameState") -> None:
            if not source._animated or not _is_on_battlefield(game, source):
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
        self._animation_effects_registered = True

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return Great Hall's two mana abilities."""
        source = self

        def _colorless_effect(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_life_cost(game: "GameState", src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None or controller.life < 1:
                return False
            if not tap_cost(game, src):
                return False
            controller.life -= 1
            return True

        def _restricted_color_effect(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            colors = [
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            ]
            try:
                chosen_color = controller.choose(colors, "Choose a color of mana to produce")
            except Exception:
                chosen_color = ManaType.WHITE
            controller.mana_pool.add_restricted(
                chosen_color,
                restriction=_is_instant_or_sorcery,
            )

        return [
            ManaAbility(
                cost=tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_life_cost,
                mana_produced=_restricted_color_effect,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
                    "only to cast an instant or sorcery spell."
                ),
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return Great Hall's animation ability."""
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
            if CardType.CREATURE in source.card_types or source._animated:
                return
            source._animated = True
            source._ensure_animation_effects(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                    "creature with \"Whenever you cast an instant or sorcery spell, "
                    "this creature gets +1/+0 until end of turn.\" It's still a land."
                ),
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        """Register the animated spell-cast trigger once."""
        if game.trigger_manager.get_triggers_for_source(self):
            return
        source = self
        controller = self.controller or self.owner or game.active_player

        def _condition(game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            if getattr(event, "player", None) is not controller:
                return False
            if not source._animated or not _is_on_battlefield(game, source):
                return False
            if CardType.CREATURE not in source.card_types:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            return _is_instant_or_sorcery(spell)

        def _effect(game: "GameState") -> None:
            if not source._animated or not _is_on_battlefield(game, source):
                return

            def _apply_buff(game: "GameState") -> None:
                if CardType.CREATURE in source.card_types:
                    source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_buff,
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
