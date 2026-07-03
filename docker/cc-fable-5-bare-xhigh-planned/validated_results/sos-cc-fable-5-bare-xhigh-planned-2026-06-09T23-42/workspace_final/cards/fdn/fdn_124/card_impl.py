"""Card implementation for Perforating Artist."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import Keyword, ManaCost
from engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class PerforatingArtist(Creature):
    """Perforating Artist — {1}{B}{R} — 3/2 — Devil.

    Deathtouch
    Raid — At the beginning of your end step, if you attacked this turn,
    each opponent loses 3 life unless that player sacrifices a nonland
    permanent of their choice or discards a card.

    FDN collector number 124.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Perforating Artist')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}{R}'))
        kwargs.setdefault('subtypes', {'Devil'})
        kwargs.setdefault('keywords', Keyword.DEATHTOUCH)
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Deathtouch\nRaid — At the beginning of your end step, if you attacked this turn, each opponent loses 3 life unless that player sacrifices a nonland permanent of their choice or discards a card.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register Raid end-step trigger."""
        from engine.game import sacrifice
        from engine.triggers import TriggerRegistration
        from engine.types import CardType, Zone
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            if game.active_player is not ctrl:
                return False
            attacked = getattr(game, 'attacked_this_turn', False)
            if not attacked:
                attacked = getattr(ctrl, 'attacked_this_turn', False)
            return attacked

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            for player in game.players:
                if player is ctrl:
                    continue
                bf = game.get_battlefield(player)
                nonland = [c for c in bf.get_all() if CardType.LAND not in getattr(c, 'card_types', set())]
                hand = list(player.zones[Zone.HAND].get_all())
                options: list[str] = []
                if nonland:
                    options.append('sacrifice')
                if hand:
                    options.append('discard')
                options.append('lose_life')
                chose_alternative = False
                if len(options) == 1:
                    player.life -= 3
                    continue
                if nonland:
                    try:
                        chosen = player.choose_card(nonland, 'sacrifice a nonland permanent, or decline (discard / lose 3 life)')
                        if chosen is not None:
                            sacrifice(game, player, chosen)
                            chose_alternative = True
                    except Exception:
                        pass
                if not chose_alternative and hand:
                    try:
                        from engine.game import discard as _discard
                        chosen = player.choose_card(hand, 'discard a card or lose 3 life')
                        if chosen is not None:
                            _discard(game, player, chosen)
                            chose_alternative = True
                    except Exception:
                        pass
                if not chose_alternative:
                    player.life -= 3
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
