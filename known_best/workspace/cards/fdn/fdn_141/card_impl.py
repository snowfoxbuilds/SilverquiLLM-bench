"""Card implementation for Giada, Font of Hope."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

class GiadaFontOfHope(Creature):
    """Giada, Font of Hope — {1}{W} — 2/2 — Legendary Angel.

    Flying, vigilance
    Each other Angel you control enters with an additional +1/+1 counter
    on it for each Angel you already control.
    {T}: Add {W}. Spend this mana only to cast an Angel spell.

    FDN collector number 141.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Giada, Font of Hope')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{W}'))
        kwargs.setdefault('subtypes', {'Angel'})
        kwargs.setdefault('keywords', Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Flying, vigilance\nEach other Angel you control enters with an additional +1/+1 counter on it for each Angel you already control.\n{T}: Add {W}. Spend this mana only to cast an Angel spell.')
        super().__init__(**kwargs)
        self.is_legendary = True

    def register_replacement_effects(self, game: 'GameState') -> None:
        """Each other Angel you control enters with additional +1/+1 counters.

        This is a genuine "enters with additional counters" replacement (rule
        614.1c), not a triggered ability: it contributes to the entering Angel's
        :class:`~engine.events.EntersBattlefieldReplacementEvent` while that
        Angel is still off the battlefield, so the extra counters are on it *as*
        it enters. The bonus is one +1/+1 counter for each Angel Giada's
        controller *already* controls (the entering Angel is not yet on the
        battlefield, so it is naturally excluded from the count).
        """
        from engine.events import EntersBattlefieldReplacementEvent
        from engine.replacement_effects import ReplacementEffect
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            permanent = event.permanent
            if permanent is None or permanent is source:
                return False
            ctrl = getattr(source, 'controller', None)
            if getattr(event, 'controller', None) is not ctrl:
                return False
            return 'Angel' in getattr(permanent, 'subtypes', set())

        def _replacement(game: 'GameState', event: Any) -> Any:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return event
            bf = game.get_battlefield(ctrl)
            angel_count = sum(
                1 for obj in bf.get_all()
                if 'Angel' in getattr(obj, 'subtypes', set())
                and obj is not event.permanent
            )
            if angel_count > 0:
                event.counters['+1/+1'] = (
                    event.counters.get('+1/+1', 0) + angel_count
                )
            return event

        game.replacement_manager.register(ReplacementEffect(
            event_type=EntersBattlefieldReplacementEvent,
            source=self,
            condition=_condition,
            replacement=_replacement,
            controller=controller,
        ))

    def get_mana_abilities(self) -> list:
        """Return the tap-for-white mana ability."""
        from engine.card import ManaAbility
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, 'is_tapped', False):
                return False
            src.is_tapped = True
            return True

        def _mana_produced(game: Any) -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            from engine.types import ManaType
            ctrl.mana_pool.add(ManaType.WHITE, 1)
        return [ManaAbility(cost=_cost, mana_produced=_mana_produced, description='{T}: Add {W}. Spend this mana only to cast an Angel spell.')]
