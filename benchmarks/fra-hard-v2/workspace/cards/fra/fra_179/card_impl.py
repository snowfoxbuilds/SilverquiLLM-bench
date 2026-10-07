from engine.card import Land
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class HallOfEchoesAbility1:
    text = '{T}: Add {C}.'


class HallOfEchoesAbility2:
    text = '{5}: This land becomes a copy of target creature you control until end of turn. The "legend rule" doesn\'t apply to permanents you control this turn.'


# endregion Printed abilities


class HallOfEchoes(Land):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Hall of Echoes',
            'mana_cost': ManaCost(),
            'card_types': {CardType.LAND},
            'rules_text': '{T}: Add {C}.\n{5}: This land becomes a copy of target creature you control until end of turn. The "legend rule" doesn\'t apply to permanents you control this turn.',
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
