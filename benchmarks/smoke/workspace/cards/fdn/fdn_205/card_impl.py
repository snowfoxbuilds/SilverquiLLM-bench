from engine.card import Sorcery
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SeismicRuptureAbility1:
    text = 'Seismic Rupture deals 2 damage to each creature without flying.'


# endregion Printed abilities


class SeismicRupture(Sorcery):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Seismic Rupture',
            'mana_cost': ManaCost.parse('{2}{R}'),
            'card_types': {CardType.SORCERY},
            'rules_text': 'Seismic Rupture deals 2 damage to each creature without flying.',
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
