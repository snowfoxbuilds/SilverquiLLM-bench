"""Card implementation for Loot, Exuberant Explorer."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Creature
from engine.types import CardType, ManaCost, Zone
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class LootExuberantExplorer(Creature):
    """Loot, Exuberant Explorer — {2}{G} — 1/4 — Legendary Beast Noble.

    You may play an additional land on each of your turns.
    {4}{G}{G}, {T}: Look at the top six cards of your library. You may
    reveal a creature card with mana value less than or equal to the
    number of lands you control from among them and put it onto the
    battlefield. Put the rest on the bottom in a random order.

    FDN collector number 106.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Loot, Exuberant Explorer')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{G}'))
        kwargs.setdefault('subtypes', {'Beast', 'Noble'})
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'You may play an additional land on each of your turns.\n{4}{G}{G}, {T}: Look at the top six cards of your library. You may reveal a creature card with mana value less than or equal to the number of lands you control from among them and put it onto the battlefield. Put the rest on the bottom in a random order.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Grant additional land play to controller."""
        controller = getattr(self, 'controller', None) or game.active_player
        controller.additional_lands = getattr(controller, 'additional_lands', 0) + 1
        controller.land_plays_remaining += 1

    def unregister_triggers(self, game: 'GameState') -> None:
        controller = getattr(self, 'controller', None)
        if controller is not None:
            controller.additional_lands = max(getattr(controller, 'additional_lands', 1) - 1, 0)
            controller.land_plays_remaining = max(controller.land_plays_remaining - 1, 0)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, 'controller', None)
            if controller is None:
                return False
            if getattr(src, 'is_tapped', False) or getattr(src, 'tapped', False):
                return False
            if controller.mana_pool.total() < 6:
                return False
            controller.mana_pool.pay(ManaCost(generic=6))
            src.is_tapped = True
            src.tapped = True
            return True

        def _effect(game: Any) -> None:
            import random
            from engine.game import create_token, move_to_zone
            from engine.player import ScriptExhaustedError
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            top_cards = library.top(min(6, len(library)))
            if not top_cards:
                return
            for card in top_cards:
                library.remove(card)
            bf = game.get_battlefield(ctrl)
            land_count = sum((1 for obj in bf.get_all() if CardType.LAND in getattr(obj, 'card_types', set())))
            eligible = [c for c in top_cards if CardType.CREATURE in getattr(c, 'card_types', set()) and getattr(c, 'mana_cost', ManaCost()).cmc <= land_count]
            chosen = None
            if eligible:
                try:
                    chosen = ctrl.choose_card(eligible, 'creature to put onto the battlefield')
                except ScriptExhaustedError:
                    pass
            rest = [c for c in top_cards if c is not chosen]
            if chosen is not None:
                chosen.owner = ctrl
                chosen.controller = ctrl
                bf.add(chosen)
                game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=chosen, controller=ctrl))
                if hasattr(chosen, 'register_triggers'):
                    chosen.register_triggers(game)
            random.shuffle(rest)
            for card in rest:
                library.add(card, position='bottom')
        return [ActivatedAbility(cost=_cost, effect=_effect, description='{4}{G}{G}, {T}: Look at top six, put creature onto battlefield.')]
