"""Card implementation for Etali, Primal Storm."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, ManaCost, Zone
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class EtaliPrimalStorm(Creature):
    """Etali, Primal Storm — {4}{R}{R} — 6/6 — Legendary Elder Dinosaur.

    Whenever Etali attacks, exile the top card of each player's library,
    then you may cast any number of spells from among those cards without
    paying their mana costs.

    FDN collector number 194.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Etali, Primal Storm')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{R}{R}'))
        kwargs.setdefault('subtypes', {'Elder', 'Dinosaur'})
        kwargs.setdefault('supertypes', {'Legendary'})
        kwargs.setdefault('base_power', 6)
        kwargs.setdefault('base_toughness', 6)
        kwargs.setdefault('rules_text', "Whenever Etali attacks, exile the top card of each player's library, then you may cast any number of spells from among those cards without paying their mana costs.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger for exile-and-cast."""
        from engine.triggers import TriggerRegistration
        from engine.zones import move_to_zone
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            return event.creature is source

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            exiled_cards: list = []
            for player in game.players:
                library = player.zones[Zone.LIBRARY]
                cards = library.get_all()
                if cards:
                    top_card = cards[-1]
                    move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
                    exiled_cards.append(top_card)
            castable = [c for c in exiled_cards if CardType.LAND not in getattr(c, 'card_types', set())]
            for card in castable:
                try:
                    if ctrl.choose_yes_no(f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"):
                        _is_permanent = bool(getattr(card, 'card_types', set()) & {CardType.CREATURE, CardType.ARTIFACT, CardType.ENCHANTMENT, CardType.PLANESWALKER})
                        if _is_permanent:
                            move_to_zone(game, card, Zone.EXILE, Zone.BATTLEFIELD)
                            card.controller = ctrl
                        else:
                            card.controller = ctrl
                            if hasattr(card, 'on_resolve'):
                                card.on_resolve(game)
                            move_to_zone(game, card, Zone.EXILE, Zone.GRAVEYARD)
                except Exception:
                    pass
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
