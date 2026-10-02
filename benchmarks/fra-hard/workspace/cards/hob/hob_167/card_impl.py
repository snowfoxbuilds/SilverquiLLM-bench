from engine.card import Creature
from engine.types import ManaCost, Supertype


class ThranduiltheElvenking(Creature):
    """Implementation task: see card_spec.json."""

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
