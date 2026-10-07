from engine.card import Creature
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class BilboThiefInTheNightAbility1:
    text = 'Spells you cast from anywhere other than your hand cost {1} less to cast.'


class BilboThiefInTheNightAbility2:
    text = 'Whenever Bilbo attacks, you may cast an artifact, instant, or sorcery spell from your graveyard. If an instant or sorcery spell cast this way would be put into your graveyard, exile it instead.'


# endregion Printed abilities


class BilboThiefInTheNight(Creature):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Bilbo, Thief in the Night',
            'mana_cost': ManaCost.parse('{1}{U}'),
            'card_types': {CardType.CREATURE},
            'rules_text': 'Spells you cast from anywhere other than your hand cost {1} less to cast.\nWhenever Bilbo attacks, you may cast an artifact, instant, or sorcery spell from your graveyard. If an instant or sorcery spell cast this way would be put into your graveyard, exile it instead.',
            'base_power': 2,
            'base_toughness': 2,
            'subtypes': {'Halfling', 'Rogue'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
