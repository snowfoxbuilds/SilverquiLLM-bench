"""Card implementation for Kykar, Zephyr Awakener."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent, SpellCastTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

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
        from benchmarks.sos.workspace.engine.card import Creature as _Creature
        from benchmarks.sos.workspace.engine.game import create_token
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        from benchmarks.sos.workspace.engine.zones import move_to_zone
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

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            bf = game.get_battlefield(ctrl)
            candidates = [c for c in bf.get_all() if CardType.CREATURE in getattr(c, 'card_types', set()) and c is not source]
            mode_choice = None
            if candidates:
                try:
                    mode_choice = ctrl.choose(['flicker', 'token'], 'Choose mode for Kykar trigger')
                except Exception:
                    mode_choice = 'token'
            else:
                mode_choice = 'token'
            if mode_choice == 'flicker' and candidates:
                try:
                    chosen = ctrl.choose_card(candidates, 'creature to exile and return at end step')
                except Exception:
                    chosen = candidates[0]
                if chosen is not None:
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
                    game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_return_condition, effect=_return_effect, source=source, controller=ctrl))
            else:
                token = _Creature(name='Spirit', subtypes={'Spirit'}, keywords=Keyword.FLYING, base_power=1, base_toughness=1)
                create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
