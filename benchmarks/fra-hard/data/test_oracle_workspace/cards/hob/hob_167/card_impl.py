from engine.abilities import borrowed_abilities
from engine.card import Creature, ManaAbility
from engine.card_queries import choose_object
from engine.events import EntersBattlefieldTriggeredEvent
from engine.game import discard, draw_card
from engine.triggers import TriggerRegistration
from engine.types import ManaCost, Supertype, Zone


class ThranduiltheElvenking(Creature):

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Thranduil, the Elvenking',
            'mana_cost': ManaCost.parse('{2}{B}{G}{U}'),
            'rules_text': 'Thranduil has all activated abilities of all Elf cards in your graveyard.\nWhenever another legendary Elf you control enters, draw two cards, then discard a card.',
            'base_power': 5,
            'base_toughness': 6,
            'subtypes': {'Elf', 'Noble'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def _borrowed(self):
        if self.controller is None or not self.controller.zones[Zone.BATTLEFIELD].contains(self):
            return []
        return [ability for card in self.controller.zones[Zone.GRAVEYARD].get_all()
                if 'Elf' in card.subtypes and card is not self
                for ability in borrowed_abilities(card, self, available=lambda game, donor=card:
                    self.controller is not None and 'Elf' in donor.subtypes and
                    self.controller.zones[Zone.GRAVEYARD].contains(donor))]

    def get_activated_abilities(self):
        return [ability for ability in self._borrowed() if not isinstance(ability, ManaAbility)]

    def get_mana_abilities(self):
        return [ability for ability in self._borrowed() if isinstance(ability, ManaAbility)]

    def register_triggers(self, game):
        def condition(g, event):
            card = event.permanent
            return (card is not self and card.controller is self.controller and
                    'Elf' in card.subtypes and Supertype.LEGENDARY in card.supertypes)

        def effect(g, controller):
            draw_card(g, controller)
            draw_card(g, controller)
            hand = controller.zones[Zone.HAND].get_all()
            if hand:
                card = choose_object(g, controller, hand, 'Discard a card', source_card=self)
                discard(g, controller, card)
        game.trigger_manager.register(TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent, source=self, controller=self.controller,
            condition=condition, effect=effect))
