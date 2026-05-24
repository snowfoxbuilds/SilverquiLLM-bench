"""Card implementation for Drakuseth, Maw of Flames."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class DrakusethMawOfFlames(Creature):
    """Drakuseth, Maw of Flames — {4}{R}{R}{R} — 7/7 — Legendary Dragon.

    Flying.
    Whenever Drakuseth attacks, it deals 4 damage to any target and 3
    damage to each of up to two other targets.

    FDN collector number 193.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Drakuseth, Maw of Flames')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{R}{R}{R}'))
        kwargs.setdefault('subtypes', {'Dragon'})
        kwargs.setdefault('supertypes', {'Legendary'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 7)
        kwargs.setdefault('base_toughness', 7)
        kwargs.setdefault('rules_text', 'Flying\nWhenever Drakuseth attacks, it deals 4 damage to any target and 3 damage to each of up to two other targets.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger for damage dealing."""
        from benchmarks.sos.workspace.engine.game import deal_damage
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            return event.creature is source

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            from benchmarks.sos.workspace.engine.types import CardType
            all_targets: list = []
            for player in game.players:
                all_targets.append(player)
                for perm in game.get_battlefield(player).get_all():
                    if CardType.CREATURE in getattr(perm, 'card_types', set()):
                        all_targets.append(perm)
            if not all_targets:
                return
            try:
                target1 = ctrl.choose_card(all_targets, 'Choose a target for 4 damage')
            except Exception:
                target1 = all_targets[0]
            if target1 is not None:
                deal_damage(game, source, target1, 4)
            remaining = [t for t in all_targets if t is not target1]
            for i in range(2):
                if not remaining:
                    break
                try:
                    target = ctrl.choose_card(remaining, f'Choose target {i + 1} for 3 damage (optional)')
                except Exception:
                    break
                if target is not None:
                    deal_damage(game, source, target, 3)
                    remaining = [t for t in remaining if t is not target]
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
