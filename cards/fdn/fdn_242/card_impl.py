"""Card implementation for Lathril, Blade of the Elves."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype
from engine.events import DealsDamageTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class LathrilBladeOfTheElves(Creature):
    """Lathril, Blade of the Elves — {2}{B}{G} — 2/3 — Legendary Elf Noble.

    Menace
    Whenever Lathril deals combat damage to a player, create that many
    1/1 green Elf Warrior creature tokens.
    {T}, Tap ten untapped Elves you control: Each opponent loses 10 life
    and you gain 10 life.

    FDN collector number 242.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Lathril, Blade of the Elves')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{B}{G}'))
        kwargs.setdefault('subtypes', {'Elf', 'Noble'})
        kwargs.setdefault('supertypes', {Supertype.LEGENDARY})
        kwargs.setdefault('keywords', Keyword.MENACE)
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Menace\nWhenever Lathril deals combat damage to a player, create that many 1/1 green Elf Warrior creature tokens.\n{T}, Tap ten untapped Elves you control: Each opponent loses 10 life and you gain 10 life.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register combat damage trigger for token creation."""
        from engine.game import create_token
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        _damage_queue: list[int] = []

        def _condition(game: Any, event: dict) -> bool:
            dmg_source = event.source
            if dmg_source is not source:
                return False
            target = event.target
            if not hasattr(target, 'life'):
                return False
            amount = event.amount
            if amount <= 0:
                return False
            _damage_queue.append(amount)
            return True

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None or not _damage_queue:
                return
            amount = _damage_queue.pop(0)
            for _ in range(amount):
                token = Creature(name='Elf Warrior', base_power=1, base_toughness=1, subtypes={'Elf', 'Warrior'})
                token.is_token = True
                create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the tap-ten-elves activated ability."""
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, 'is_tapped', False):
                return False
            ctrl = getattr(src, 'controller', None)
            if ctrl is None:
                return False
            bf = game.get_battlefield(ctrl)
            untapped_elves: list[Any] = []
            for obj in bf.get_all():
                if obj is src:
                    continue
                if 'Elf' not in getattr(obj, 'subtypes', set()):
                    continue
                if not getattr(obj, 'is_tapped', True):
                    untapped_elves.append(obj)
            if len(untapped_elves) < 10:
                return False
            src.is_tapped = True
            for elf in untapped_elves[:10]:
                elf.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            for player in game.players:
                if player is not ctrl:
                    player.life -= 10
            ctrl.life += 10
        return [ActivatedAbility(cost=_cost, effect=_effect, description='{T}, Tap ten untapped Elves you control: Each opponent loses 10 life and you gain 10 life.')]
