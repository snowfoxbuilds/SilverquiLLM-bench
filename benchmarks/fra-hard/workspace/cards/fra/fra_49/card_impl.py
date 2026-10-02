from engine.card import Creature
from engine.types import ManaCost, Supertype


class BloodlineRecollector(Creature):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Bloodline Recollector',
            'mana_cost': ManaCost.parse('{1}{B}'),
            'rules_text': "At the beginning of each end step, if three or more creatures died this turn, this creature becomes prepared. (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)",
            'base_power': 2,
            'base_toughness': 2,
            'subtypes': {'Vampire', 'Warlock'},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
