from engine.card import Instant
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SlaughterPactAbility1:
    text = 'Destroy target nonblack creature.'


class SlaughterPactAbility2:
    text = "At the beginning of your next upkeep, pay {2}{B}. If you don't, you lose the game."


# endregion Printed abilities


class SlaughterPact(Instant):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Slaughter Pact',
            'mana_cost': ManaCost.parse('{0}'),
            'card_types': {CardType.INSTANT},
            'rules_text': "Destroy target nonblack creature.\nAt the beginning of your next upkeep, pay {2}{B}. If you don't, you lose the game.",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
