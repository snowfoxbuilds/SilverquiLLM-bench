from engine.card import Creature
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ThranduilTheElvenkingAbility1:
    text = 'Thranduil has all activated abilities of all Elf cards in your graveyard.'


class ThranduilTheElvenkingAbility2:
    text = 'Whenever another legendary Elf you control enters, draw two cards, then discard a card.'


# endregion Printed abilities


class ThranduilTheElvenking(Creature):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Thranduil, the Elvenking',
            'mana_cost': ManaCost.parse('{2}{B}{G}{U}'),
            'card_types': {CardType.CREATURE},
            'rules_text': 'Thranduil has all activated abilities of all Elf cards in your graveyard.\nWhenever another legendary Elf you control enters, draw two cards, then discard a card.',
            'base_power': 5,
            'base_toughness': 6,
            'subtypes': {'Elf', 'Noble'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
