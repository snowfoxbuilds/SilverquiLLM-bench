from engine.card import Creature
from engine.types import ManaCost, Supertype


class SanctumLurker(Creature):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Sanctum Lurker',
            'mana_cost': ManaCost.parse('{2}{B}'),
            'rules_text': 'When this creature enters, empower Jace 1.\nPlaneswalkers you control aren\'t put into their owners\' graveyards for having 0 loyalty.\nPlaneswalkers you control have "[+2]: This planeswalker deals 1 damage to each opponent and you gain 1 life."',
            'base_power': 3,
            'base_toughness': 2,
            'subtypes': {'Horror'},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
