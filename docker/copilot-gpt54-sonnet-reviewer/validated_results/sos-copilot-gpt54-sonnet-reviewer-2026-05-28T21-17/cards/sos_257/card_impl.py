"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: "GameState", permanent: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(permanent):
            return True
    return False


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault("mana_cost", ManaCost())
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with "
            '"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn." '
            "It's still a land.",
        )
        super().__init__(**kwargs)
        self._original_subtypes = frozenset(self.subtypes)
        self._biblioplex_animated = False
        self.base_power = 0
        self.base_toughness = 0
        self.modified_power = 0
        self.modified_toughness = 0

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes)
        self.base_power = 0
        self.base_toughness = 0
        self.modified_power = 0
        self.modified_toughness = 0
        if self._biblioplex_animated:
            self.card_types.add(CardType.CREATURE)
            self.subtypes.add("Wizard")
            self.base_power = 2
            self.base_toughness = 4
            self.modified_power = 2
            self.modified_toughness = 4

    @property
    def power(self) -> int:
        return self.modified_power

    @property
    def toughness(self) -> int:
        return self.modified_toughness

    def register_triggers(self, game: "GameState") -> None:
        existing = [
            trigger
            for trigger in game.trigger_manager.get_triggers_for_source(self)
            if trigger.event_type is SpellCastTriggeredEvent
        ]
        if existing:
            return

        source = self

        def _condition(game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            if not source._biblioplex_animated:
                return False
            if getattr(event, "player", None) is not source.controller:
                return False
            spell = getattr(event, "card", None) or getattr(event, "spell", None)
            if spell is None:
                return False
            return bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})

        def _effect(game: "GameState") -> None:
            if not _is_on_battlefield(game, source):
                return

            def _apply_bonus(game: "GameState") -> None:
                if _is_on_battlefield(game, source):
                    source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_bonus,
                    duration=DURATION_END_OF_TURN,
                )
            )

        controller = self.controller or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_for_colorless_cost(game: "GameState", permanent: Any) -> bool:
            if permanent.is_tapped:
                return False
            permanent.is_tapped = True
            return True

        def _tap_for_colorless_effect(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS)

        def _tap_pay_life_cost(game: "GameState", permanent: Any) -> bool:
            controller = permanent.controller
            if permanent.is_tapped or controller is None or controller.life <= 0:
                return False
            permanent.is_tapped = True
            controller.life -= 1
            return True

        def _tap_pay_life_effect(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            chosen = controller.choose(
                [
                    ManaType.WHITE,
                    ManaType.BLUE,
                    ManaType.BLACK,
                    ManaType.RED,
                    ManaType.GREEN,
                ],
                "Choose a color of mana to add",
            )
            controller.mana_pool.add_restricted(
                chosen,
                can_spend=lambda card: bool(
                    getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}
                ),
            )

        return [
            ManaAbility(
                cost=_tap_for_colorless_cost,
                mana_produced=_tap_for_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life_cost,
                mana_produced=_tap_pay_life_effect,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self
        animation_cost = ManaCost.parse("{5}")

        def _cost(game: "GameState", permanent: Any) -> bool:
            controller = permanent.controller
            if controller is None or not controller.mana_pool.can_pay(animation_cost):
                return False
            return controller.mana_pool.pay(animation_cost)

        def _effect(game: "GameState") -> None:
            if source._biblioplex_animated:
                return
            source._biblioplex_animated = True
            source.register_triggers(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: Animate Great Hall of the Biblioplex.",
            )
        ]
