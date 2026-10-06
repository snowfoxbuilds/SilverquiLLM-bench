from engine.card import Planeswalker
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SarkhanTheMasterlessAbility1:
    text = 'Whenever a creature attacks you or a planeswalker you control, each Dragon you control deals 1 damage to that creature.'


class SarkhanTheMasterlessAbility2:
    text = '+1: Until end of turn, each planeswalker you control becomes a 4/4 red Dragon creature and gains flying.'


class SarkhanTheMasterlessAbility3:
    text = '−3: Create a 4/4 red Dragon creature token with flying.'


# endregion Printed abilities


class SarkhanTheMasterless(Planeswalker):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Sarkhan the Masterless',
            'mana_cost': ManaCost.parse('{3}{R}{R}'),
            'card_types': {CardType.PLANESWALKER},
            'rules_text': 'Whenever a creature attacks you or a planeswalker you control, each Dragon you control deals 1 damage to that creature.\n+1: Until end of turn, each planeswalker you control becomes a 4/4 red Dragon creature and gains flying.\n−3: Create a 4/4 red Dragon creature token with flying.',
            'starting_loyalty': 5,
            'subtypes': {'Sarkhan'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
