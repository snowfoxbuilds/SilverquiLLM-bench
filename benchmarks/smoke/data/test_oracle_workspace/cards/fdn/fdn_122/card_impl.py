"""Card implementation for Kykar, Zephyr Awakener."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.tokens import make_creature_token
from engine.card import Creature
from engine.card_queries import choose_mode
from engine.events import EndStepTriggeredEvent, SpellCastTriggeredEvent
from engine.types import CardType, Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class KykarZephyrAwakenerAbility1:
    text = 'Flying'


class KykarZephyrAwakenerAbility2:
    text = 'Whenever you cast a noncreature spell, choose one —'


class KykarZephyrAwakenerAbility3:
    text = "• Exile another target creature you control. Return that card to the battlefield under its owner's control at the beginning of the next end step."


class KykarZephyrAwakenerAbility4:
    text = '• Create a 1/1 white Spirit creature token with flying.'


# endregion Printed abilities


class KykarZephyrAwakener(Creature):
    """Kykar, Zephyr Awakener — {2}{W}{U} — 3/4 — Legendary Bird Wizard.

    Flying
    Whenever you cast a noncreature spell, choose one —
    • Exile another target creature you control. Return that card to the
      battlefield under its owner's control at the beginning of the next
      end step.
    • Create a 1/1 white Spirit creature token with flying.

    FDN collector number 122.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Kykar, Zephyr Awakener')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{W}{U}'))
        kwargs.setdefault('subtypes', {'Bird', 'Wizard'})
        kwargs.setdefault('supertypes', {'Legendary'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', "Flying\nWhenever you cast a noncreature spell, choose one —\n• Exile another target creature you control. Return that card to the battlefield under its owner's control at the beginning of the next end step.\n• Create a 1/1 white Spirit creature token with flying.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register noncreature spell cast trigger."""
        from engine.game import create_token
        from engine.stack import stint_checked_targets
        from engine.triggers import TriggerRegistration, choose_trigger_targets
        from engine.zones import move_to_zone
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            spell = event.spell or event.card
            if spell is None:
                return False
            caster = event.player or getattr(spell, 'controller', None)
            ctrl = getattr(source, 'controller', None)
            if caster is not ctrl:
                return False
            card_types = getattr(spell, 'card_types', set())
            return CardType.CREATURE not in card_types

        def _targeting(game: 'GameState', event: Any, ctrl: Any) -> list[Any]:
            # The mode, and the flicker mode's target, are chosen as the trigger
            # goes on the stack (rule 603.3c-d): no target means the token mode.
            def _another_creature_you_control(obj: Any) -> bool:
                return (CardType.CREATURE in getattr(obj, 'card_types', set()) and obj is not source
                        and getattr(obj, 'controller', None) is ctrl)

            if ctrl is None or not any(_another_creature_you_control(c) for c in game.get_battlefield(ctrl).get_all()):
                return []
            mode_choice = choose_mode(game, ctrl, ['flicker', 'token'], 'Choose mode for Kykar trigger', source_card=source, printed=[KykarZephyrAwakenerAbility3, KykarZephyrAwakenerAbility4])
            if mode_choice != 'flicker':
                return []
            return choose_trigger_targets(game, ctrl, source, [TargetRequirement(
                filter_fn=_another_creature_you_control, description='creature to exile and return at end step',
                zone=Zone.BATTLEFIELD)]) or []

        def _effect(game: 'GameState', targets: list[Any], context: Any) -> None:
            ctrl = context.controller
            if ctrl is None:
                return
            if targets:
                (chosen,) = stint_checked_targets(game, context, targets)
                still_legal = chosen is not None and CardType.CREATURE in getattr(chosen, 'card_types', set()) \
                    and getattr(chosen, 'controller', None) is ctrl
                if still_legal:
                    move_to_zone(game, chosen, Zone.BATTLEFIELD, Zone.EXILE)
                    _exiled_card = chosen
                    _owner = getattr(chosen, 'owner', ctrl)
                    _returned = [False]

                    def _return_condition(game: Any, event: dict) -> bool:
                        return not _returned[0]

                    def _return_effect(game: 'GameState') -> None:
                        if _returned[0]:
                            return
                        _returned[0] = True
                        _exiled_card.controller = _owner
                        move_to_zone(game, _exiled_card, Zone.EXILE, Zone.BATTLEFIELD)
                    game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_return_condition, effect=_return_effect, source=source, controller=ctrl, printed=KykarZephyrAwakenerAbility3))
            else:
                token = make_creature_token("Spirit", {"Spirit"}, [Color.WHITE], 1, 1, keywords=Keyword.FLYING)
                create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller, targeting=_targeting, printed=KykarZephyrAwakenerAbility2))
