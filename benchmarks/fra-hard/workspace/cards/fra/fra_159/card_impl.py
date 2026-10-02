from engine.card import Creature
from engine.types import ManaCost, Supertype


class UldarosTheorix(Creature):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Uldaros Theorix',
            'mana_cost': ManaCost.parse('{3}{U}{B}{B}'),
            'rules_text': 'Flying\nWhen Uldaros Theorix enters, if you cast him, exile up to one target nonland card of each card type from your graveyard. Copy those cards. You may cast any number of spells with total mana value 6 or less from among the copies without paying their mana costs. (Permanent spells cast this way become tokens.)',
            'base_power': 5,
            'base_toughness': 5,
            'subtypes': {'Elder', 'Sphinx'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
