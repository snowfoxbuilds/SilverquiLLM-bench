"""Card implementation for Kiora, the Rising Tide."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.card_queries import choose_object, query_yes_no
from engine.types import Keyword, ManaCost, Supertype, Zone
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class KioraTheRisingTide(Creature):
    """Kiora, the Rising Tide — {2}{U} — 3/2 — Merfolk Noble — Legendary.

    When Kiora enters, draw two cards, then discard two cards.
    Threshold — Whenever Kiora attacks, if there are seven or more cards in
    your graveyard, you may create Scion of the Deep, a legendary 8/8 blue
    Octopus creature token.

    FDN collector number 45.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Kiora, the Rising Tide')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{U}'))
        kwargs.setdefault('subtypes', {'Merfolk', 'Noble'})
        kwargs.setdefault('supertypes', set())
        kwargs['supertypes'] = (kwargs.get('supertypes') or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'When Kiora enters, draw two cards, then discard two cards.\nThreshold — Whenever Kiora attacks, if there are seven or more cards in your graveyard, you may create Scion of the Deep, a legendary 8/8 blue Octopus creature token.')
        super().__init__(**kwargs)

    def on_resolve(self, game: 'GameState') -> None:
        """ETB: draw 2, then discard 2."""
        from engine.game import discard, draw_card
        controller = self.controller
        if controller is None:
            return
        for _ in range(2):
            draw_card(game, controller)
        for _ in range(2):
            hand = controller.zones[Zone.HAND]
            cards_in_hand = list(hand.get_all())
            if not cards_in_hand:
                break
            chosen = choose_object(game, controller, cards_in_hand, 'Choose a card to discard', source_card=self)
            if chosen is not None:
                discard(game, controller, chosen)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger: threshold → create Scion of the Deep token."""
        from engine.game import create_token
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _attack_condition(game: Any, event: dict) -> bool:
            attacker = event.attacker or event.creature
            if attacker is not source:
                return False
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            gy_count = len(list(ctrl.zones[Zone.GRAVEYARD].get_all()))
            return gy_count >= 7

        def _attack_effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            create_scion = query_yes_no(game, ctrl, 'Create Scion of the Deep token?', source_card=source)
            if create_scion:
                token = Creature(name='Scion of the Deep', supertypes={Supertype.LEGENDARY}, subtypes={'Octopus'}, base_power=8, base_toughness=8)
                create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_attack_condition, effect=_attack_effect, source=self, controller=controller))
