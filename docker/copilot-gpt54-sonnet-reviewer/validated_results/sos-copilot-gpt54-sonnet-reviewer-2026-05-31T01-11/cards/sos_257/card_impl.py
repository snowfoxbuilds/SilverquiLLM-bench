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


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Great Hall of the Biblioplex')
        kwargs.setdefault(
            'rules_text',
            '{T}: Add {C}.\\n'
            '{T}, Pay 1 life: Add one mana of any color. Spend this mana only '
            'to cast an instant or sorcery spell.\\n'
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard '
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self._animated: bool = False

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness
        if self._animated:
            self.card_types.add(CardType.CREATURE)
            self.subtypes.add('Wizard')
            self.modified_power = 2
            self.modified_toughness = 4

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, 'is_tapped', False):
                return False
            src.is_tapped = True
            return True

        def _tap_and_pay_life(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if getattr(src, 'is_tapped', False):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_colorless(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _add_chosen_color(game: Any) -> None:
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
                'Choose a color of mana to produce',
            )
            # ENGINE LIMITATION: restricted-mana spending is out of scope for
            # the verified surface of this run, so only the produced color is
            # tracked here.
            controller.mana_pool.add(chosen, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description='{T}: Add {C}.',
            ),
            ManaAbility(
                cost=_tap_and_pay_life,
                mana_produced=_add_chosen_color,
                description=(
                    '{T}, Pay 1 life: Add one mana of any color. '
                    'Spend this mana only to cast an instant or sorcery spell.'
                ),
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self
        animation_cost = ManaCost.parse('{5}')

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if not controller.mana_pool.can_pay(animation_cost):
                return False
            controller.mana_pool.pay(animation_cost)
            return True

        def _effect(game: Any) -> None:
            if source._animated:
                return
            source._animated = True

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    '{5}: If this land isn\'t a creature, it becomes a 2/4 '
                    'Wizard creature with a spell-cast trigger. '
                    'It\'s still a land.'
                ),
            )
        ]

    def register_triggers(self, game: 'GameState') -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: SpellCastTriggeredEvent) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            if (event.player or event.controller) is not ctrl:
                return False
            if CardType.CREATURE not in getattr(source, 'card_types', set()):
                return False
            spell = event.card or event.spell
            if spell is None:
                return False
            card_types = getattr(spell, 'card_types', set())
            return bool(card_types & {CardType.INSTANT, CardType.SORCERY})

        def _effect(game: 'GameState') -> None:
            def _apply(game: Any) -> None:
                if CardType.CREATURE in getattr(source, 'card_types', set()):
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

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
