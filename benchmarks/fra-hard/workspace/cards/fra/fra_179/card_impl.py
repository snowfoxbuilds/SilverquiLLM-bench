from engine.card import Land
from engine.types import ManaCost, Supertype


class HallofEchoes(Land):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Hall of Echoes',
            'mana_cost': ManaCost.parse(''),
            'rules_text': '{T}: Add {C}.\n{5}: This land becomes a copy of target creature you control until end of turn. The "legend rule" doesn\'t apply to permanents you control this turn.',
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
