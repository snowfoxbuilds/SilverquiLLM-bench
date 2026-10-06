from engine.card import Creature
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ScavengingOozeAbility1:
    text = '{G}: Exile target card from a graveyard. If it was a creature card, put a +1/+1 counter on this creature and you gain 1 life.'


# endregion Printed abilities


class ScavengingOoze(Creature):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Scavenging Ooze',
            'mana_cost': ManaCost.parse('{1}{G}'),
            'card_types': {CardType.CREATURE},
            'rules_text': '{G}: Exile target card from a graveyard. If it was a creature card, put a +1/+1 counter on this creature and you gain 1 life.',
            'base_power': 2,
            'base_toughness': 2,
            'subtypes': {'Ooze'},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
